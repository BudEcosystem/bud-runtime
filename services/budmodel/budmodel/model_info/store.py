import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Set, Tuple

from budmicroframe.commons import logging
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error
from urllib3 import PoolManager

from ..commons.config import app_settings, secrets_settings
from ..commons.constants import LOCAL_MIN_SIZE_GB
from ..commons.helpers import safe_delete
from ..shared.io_monitor import get_io_monitor
from .schemas import UploadFile


logger = logging.get_logger(__name__)

# Process-wide semaphore to limit concurrent large file uploads
# This prevents disk saturation on single-VM deployments
MAX_PARALLEL_UPLOADS = getattr(app_settings, "max_parallel_uploads", 2)
_upload_semaphore = threading.BoundedSemaphore(MAX_PARALLEL_UPLOADS)


class ThrottledFileReader:
    """File reader that monitors I/O stress and dynamically throttles upload speed."""

    def __init__(self, file_path: str, io_monitor: Optional[any], file_size: int, chunk_size: int = 64 * 1024):
        """Initialize throttled file reader with dynamic speed calculation.

        Args:
            file_path: Path to file to read
            io_monitor: I/O monitor instance (can be None)
            file_size: Total file size in bytes
            chunk_size: Size of chunks to read (default 64 KB)
        """
        self.file_path = file_path
        self.io_monitor = io_monitor
        self.file_size = file_size
        self.chunk_size = chunk_size

        self.file = None
        self.start_time = None
        self.bytes_read = 0
        self.last_speed_check = 0
        self.current_max_bps = 0  # Will be calculated dynamically

    def __enter__(self):
        """Initialize file reading with throttling setup."""
        self.file = open(self.file_path, "rb")
        self.start_time = time.time()
        self.bytes_read = 0
        self.last_speed_check = self.start_time

        # Get initial speed limit
        if self.io_monitor:
            self.current_max_bps, _ = self.io_monitor.calculate_upload_speed_limit(disk_path=self.file_path)
        else:
            self.current_max_bps = 0  # Unlimited if no monitor

        return self

    def read(self, size=-1):
        """Read data with dynamic I/O-based speed throttling."""
        # Determine how much to read
        read_size = self.chunk_size if size == -1 or size > self.chunk_size else size

        # Read chunk
        data = self.file.read(read_size)
        if not data:
            return b""

        self.bytes_read += len(data)

        # Recalculate speed limit every 2 seconds
        now = time.time()
        if self.io_monitor and now - self.last_speed_check >= 2.0:
            self.current_max_bps, stress = self.io_monitor.calculate_upload_speed_limit(disk_path=self.file_path)
            self.last_speed_check = now

            # Log if speed changed significantly or stress is high
            if stress > 0.5:
                progress_pct = (self.bytes_read / self.file_size) * 100 if self.file_size > 0 else 0
                logger.debug(
                    "Upload speed adjusted to %s (stress: %.2f, progress: %.1f%%)",
                    "Unlimited" if self.current_max_bps == 0 else f"{self.current_max_bps / (1024 * 1024):.1f} MB/s",
                    stress,
                    progress_pct,
                )

        # Enforce rate limit (if not unlimited)
        if self.current_max_bps > 0:
            elapsed = now - self.start_time
            if elapsed > 0:
                current_bps = self.bytes_read / elapsed
                if current_bps > self.current_max_bps:
                    # Sleep to stay under limit
                    target_elapsed = self.bytes_read / self.current_max_bps
                    sleep_time = target_elapsed - elapsed
                    if sleep_time > 0:
                        time.sleep(sleep_time)

        return data

    def __exit__(self, *args):
        """Cleanup file handle and log final upload statistics."""
        if self.file:
            self.file.close()

            # Log final stats
            if self.bytes_read > 0 and self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    avg_speed_mbps = (self.bytes_read / elapsed) / (1024 * 1024)
                    logger.info(
                        "Upload of %s completed: %.2f GB in %.1fs (avg: %.1f MB/s)",
                        os.path.basename(self.file_path),
                        self.bytes_read / (1024**3),
                        elapsed,
                        avg_speed_mbps,
                    )


class ModelStore:
    def __init__(self, model_download_dir: str):
        """Initialize the ModelStore class.

        Args:
            model_download_dir (str): The directory to download the model to
        """
        self.model_download_dir = model_download_dir

        # Create HTTP client with controlled connection pool
        # Small pool prevents connection storms to MinIO on single-VM deployments
        pool_size = getattr(app_settings, "http_pool_size", 4)
        http_client = PoolManager(
            num_pools=pool_size,
            maxsize=pool_size,
            block=True,  # Block when pool is full instead of creating more connections
        )
        logger.debug("Initialized MinIO client with HTTP pool size: %d", pool_size)

        self.client = Minio(
            app_settings.minio_endpoint,
            access_key=secrets_settings.minio_access_key,
            secret_key=secrets_settings.minio_secret_key,
            secure=app_settings.minio_secure,
            http_client=http_client,
        )

        # Initialize I/O monitor if enabled
        self.io_monitor = None
        if app_settings.enable_io_monitoring:
            self.io_monitor = get_io_monitor()

        # Upload retry configuration
        self.upload_retry_attempts = getattr(app_settings, "upload_retry_attempts", 3)
        self.upload_retry_backoff = getattr(app_settings, "upload_retry_backoff_factor", 2.0)

    def _wait_for_io_clearance(self, disk_path: str) -> None:
        """Wait for I/O stress to clear before proceeding.

        Args:
            disk_path: Path to the file/disk to monitor for I/O stress
        """
        if not self.io_monitor:
            return

        # Check if we should pause due to high stress
        if self.io_monitor.should_pause_downloads(disk_path=disk_path):
            logger.warning("High I/O stress detected. Pausing upload temporarily...")
            if self.io_monitor.wait_for_io_recovery():
                logger.info("I/O stress recovered. Resuming upload.")
            else:
                logger.warning("I/O recovery timeout, proceeding with upload anyway")

    def upload_file(self, file_path: str, object_name: str, bucket_name: str = app_settings.minio_bucket) -> bool:
        """Upload a file to the MinIO store with retry logic and idempotency.

        Args:
            file_path (str): The path to the file to upload
            object_name (str): The name of the object to upload
            bucket_name (str): The bucket name

        Returns:
            bool: True if the upload was successful, False otherwise
        """
        # Check if file already exists (idempotency)
        if self.check_object_exists(object_name, bucket_name):
            logger.info(f"{object_name} already exists in MinIO, skipping upload")
            return True

        # Check for I/O clearance before starting upload
        self._wait_for_io_clearance(disk_path=file_path)

        # Determine file size and use appropriate upload method
        file_size = os.path.getsize(file_path)
        large_file_threshold = 100 * 1024 * 1024  # 100 MB

        if file_size > large_file_threshold:
            # Use semaphore for large files to limit concurrency across ALL workflows
            with _upload_semaphore:
                logger.info(f"Uploading large file ({file_size / (1024**3):.2f} GB): {file_path}")
                return self._upload_large_file_with_monitoring(file_path, object_name, bucket_name, file_size)
        else:
            return self._upload_small_file_with_retry(file_path, object_name, bucket_name)

    def _upload_small_file_with_retry(self, file_path: str, object_name: str, bucket_name: str) -> bool:
        """Upload small file with retry logic (no I/O monitoring during upload)."""
        # Retry logic with exponential backoff
        for attempt in range(self.upload_retry_attempts):
            try:
                # Upload the file
                self.client.fput_object(
                    bucket_name=bucket_name,
                    object_name=object_name,
                    file_path=file_path,
                )
                logger.info(f"Uploaded {file_path} to store://{bucket_name}/{object_name}")
                return True

            except S3Error as err:
                # Check if it's a transient error worth retrying
                is_transient = err.code in ["IncompleteBody", "RequestTimeout", "SlowDown", "ServiceUnavailable"]

                if attempt < self.upload_retry_attempts - 1 and is_transient:
                    backoff = self.upload_retry_backoff**attempt
                    logger.warning(
                        f"Transient error uploading {file_path} (attempt {attempt + 1}/{self.upload_retry_attempts}): "
                        f"{err.code}. Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(f"Failed to upload {file_path} -> {object_name} after {attempt + 1} attempts: {err}")
                    return False

            except Exception as e:
                if attempt < self.upload_retry_attempts - 1:
                    backoff = self.upload_retry_backoff**attempt
                    logger.warning(
                        f"Error uploading {file_path} (attempt {attempt + 1}/{self.upload_retry_attempts}): {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.exception(
                        f"Failed to upload {file_path} -> {object_name} after {attempt + 1} attempts: {e}"
                    )
                    return False

        return False

    def _upload_large_file_with_monitoring(
        self, file_path: str, object_name: str, bucket_name: str, file_size: int
    ) -> bool:
        """Upload large file with continuous I/O monitoring and dynamic throttling."""
        for attempt in range(self.upload_retry_attempts):
            try:
                # Use throttled file reader that monitors I/O and adapts speed during upload
                with ThrottledFileReader(file_path, self.io_monitor, file_size) as throttled_file:
                    self.client.put_object(
                        bucket_name=bucket_name,
                        object_name=object_name,
                        data=throttled_file,
                        length=file_size,
                    )

                logger.info(
                    f"Uploaded large file {file_path} ({file_size / (1024**3):.2f} GB) "
                    f"to store://{bucket_name}/{object_name}"
                )
                return True

            except S3Error as err:
                is_transient = err.code in ["IncompleteBody", "RequestTimeout", "SlowDown", "ServiceUnavailable"]

                if attempt < self.upload_retry_attempts - 1 and is_transient:
                    backoff = self.upload_retry_backoff**attempt
                    logger.warning(
                        f"Transient error uploading large file {file_path} "
                        f"(attempt {attempt + 1}/{self.upload_retry_attempts}): {err.code}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.error(
                        f"Failed to upload large file {file_path} -> {object_name} after {attempt + 1} attempts: {err}"
                    )
                    return False

            except Exception as e:
                if attempt < self.upload_retry_attempts - 1:
                    backoff = self.upload_retry_backoff**attempt
                    logger.warning(
                        f"Error uploading large file {file_path} "
                        f"(attempt {attempt + 1}/{self.upload_retry_attempts}): {e}. "
                        f"Retrying in {backoff}s..."
                    )
                    time.sleep(backoff)
                else:
                    logger.exception(
                        f"Failed to upload large file {file_path} -> {object_name} after {attempt + 1} attempts: {e}"
                    )
                    return False

        return False

    def check_object_exists(self, object_name: str, bucket_name: str = app_settings.minio_bucket) -> bool:
        """Check if an object exists in the MinIO store.

        Args:
            object_name (str): The name of the object to check

        Returns:
            bool: True if the object exists, False otherwise
        """
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error as err:
            # NoSuchKey is expected for new uploads, log as debug
            if err.code == "NoSuchKey":
                logger.debug(
                    "Object %s does not exist in bucket %s (expected for new uploads)", object_name, bucket_name
                )
                return False
            else:
                # Other S3 errors are unexpected, log as error
                logger.error("Error checking if %s exists in bucket %s: %s", object_name, bucket_name, err)
                return False
        except Exception as e:
            logger.error("Unexpected error checking if %s exists: %s", object_name, e)
            return False

    def perform_threaded_upload(self, upload_files: List[UploadFile]) -> Tuple[bool, List[str]]:
        """Perform uploads in adaptive batches with continuous I/O monitoring.

        Args:
            upload_files (list[UploadFile]): The files to upload

        Returns:
            Tuple[bool, List[str]]: (success, list of failed object names)
        """
        if not upload_files:
            return True, []

        remaining_files = upload_files.copy()
        failed_object_names = []
        total_files = len(upload_files)
        completed_files = 0

        logger.info("Starting adaptive batch upload for %d files", total_files)

        while remaining_files:
            # Re-evaluate I/O stress before each batch
            if self.io_monitor:
                metrics = self.io_monitor.get_current_metrics(str(self.model_download_dir))
                stress_level = metrics.io_stress_level

                # Determine batch size based on current I/O stress
                if stress_level > 0.7:
                    # High stress - very small batches
                    batch_size = 3
                    logger.warning("High I/O stress detected (%.2f), using batch size of %d", stress_level, batch_size)
                elif stress_level > 0.5:
                    # Medium stress - moderate batches
                    batch_size = 8
                    logger.info("Medium I/O stress detected (%.2f), using batch size of %d", stress_level, batch_size)
                else:
                    # Low stress - larger batches
                    batch_size = min(15, app_settings.max_thread_workers)
                    logger.debug("Low I/O stress (%.2f), using batch size of %d", stress_level, batch_size)
            else:
                # No I/O monitoring - use moderate batch size
                batch_size = 10

            # Get next batch
            batch = remaining_files[:batch_size]
            remaining_files = remaining_files[batch_size:]

            logger.info(
                "Processing batch of %d files (%d/%d completed, %d remaining)",
                len(batch),
                completed_files,
                total_files,
                len(remaining_files),
            )

            # Process batch with thread pool
            with ThreadPoolExecutor(max_workers=len(batch)) as executor:
                future_to_file = {
                    executor.submit(self.upload_file, file.file_path, file.object_name): file for file in batch
                }

                # Wait for batch to complete
                for future in as_completed(future_to_file):
                    file = future_to_file[future]
                    try:
                        if not future.result():
                            failed_object_names.append(file.object_name)
                            logger.error("Failed to upload: %s", file.object_name)
                        else:
                            completed_files += 1
                    except Exception as e:
                        logger.exception("Unexpected error uploading file %s: %s", file.object_name, e)
                        failed_object_names.append(file.object_name)

            # Brief pause between batches to let I/O settle (if more files remain)
            if remaining_files:
                if self.io_monitor:
                    metrics = self.io_monitor.get_current_metrics(str(self.model_download_dir))
                    if metrics.io_stress_level > 0.6:
                        pause_duration = 3
                        logger.info(
                            "I/O stress elevated (%.2f), pausing %ds between batches",
                            metrics.io_stress_level,
                            pause_duration,
                        )
                        time.sleep(pause_duration)
                    else:
                        # Brief pause even on low stress to allow I/O metrics to update
                        time.sleep(0.5)
                else:
                    time.sleep(0.5)

        success = len(failed_object_names) == 0
        if failed_object_names:
            logger.error(
                "Failed to upload %d/%d files: %s",
                len(failed_object_names),
                total_files,
                failed_object_names[:10] if len(failed_object_names) > 10 else failed_object_names,
            )
        else:
            logger.info("Successfully uploaded all %d files", total_files)

        return success, failed_object_names

    def get_uploaded_files(self, prefix: str) -> Set[str]:
        """Get set of files already uploaded to MinIO for the given prefix.

        Args:
            prefix (str): The prefix to check

        Returns:
            Set[str]: Set of object names already uploaded
        """
        try:
            objects = self.client.list_objects(app_settings.minio_bucket, prefix=prefix, recursive=True)
            uploaded = {obj.object_name for obj in objects if not obj.object_name.endswith("/")}
            logger.debug("Found %d files already uploaded for prefix %s", len(uploaded), prefix)
            return uploaded
        except Exception as e:
            logger.warning("Error listing uploaded files for prefix %s: %s", prefix, e)
            return set()

    def upload_folder(self, prefix: str) -> bool:
        """Upload a folder to the MinIO store with partial upload recovery.

        Args:
            prefix (str): The prefix to use for the upload

        Returns:
            bool: True if the upload was successful, False otherwise
        """
        found = self.client.bucket_exists(app_settings.minio_bucket)
        if not found:
            self.client.make_bucket(app_settings.minio_bucket)

        local_folder_path = os.path.join(self.model_download_dir, prefix)

        # Ensure prefix ends with a slash if it's not empty
        if prefix and not prefix.endswith("/"):
            prefix += "/"

        # Get already uploaded files for partial upload recovery
        already_uploaded = self.get_uploaded_files(prefix)
        if already_uploaded:
            logger.info("Found %d files already uploaded, will skip them", len(already_uploaded))

        # Prepare upload tasks - track which files should be deleted after successful upload
        upload_tasks = []
        file_deletion_map = {}  # Maps object_name -> (file_path, should_delete)

        # Ignore paths
        IGNORE_PATHS = [".cache"]

        # Walk through all subdirectories and files
        for root, _dirs, files in os.walk(local_folder_path):
            relative_root = os.path.relpath(root, local_folder_path)
            should_ignore = any(
                relative_root == ignore_path or relative_root.startswith(ignore_path + os.sep)
                for ignore_path in IGNORE_PATHS
            )
            if should_ignore:
                logger.debug("Ignoring %s to minio upload", root)
                continue

            for file_name in files:
                # Full local path of the file
                full_path = os.path.join(root, file_name)

                # Calculate file size in gb
                file_size_gb = os.path.getsize(full_path) / (1024**3)
                logger.debug("File size: %.4f GB for %s", file_size_gb, full_path)

                # Compute the relative path from the base local_folder_path
                relative_path = os.path.relpath(full_path, start=local_folder_path)

                # Build the MinIO object name
                # Example: prefix + "subfolder/file.txt"
                object_name = prefix + relative_path.replace(
                    "\\", "/"
                )  # Replace backslashes (Windows) with forward slashes

                # Skip if already uploaded (partial upload recovery)
                if object_name in already_uploaded:
                    logger.debug("Skipping already uploaded file: %s", object_name)
                    continue

                # Track if this file should be deleted after successful upload
                should_delete = file_size_gb > LOCAL_MIN_SIZE_GB
                file_deletion_map[object_name] = (full_path, should_delete)

                upload_tasks.append(UploadFile(file_path=full_path, object_name=object_name))

        if not upload_tasks:
            if already_uploaded:
                logger.info("All files already uploaded, nothing to do")
            else:
                logger.info("No files to upload")
            return True

        logger.info("Uploading %d files (skipped %d already uploaded)", len(upload_tasks), len(already_uploaded))

        # Perform the upload
        upload_result, failed_files = self.perform_threaded_upload(upload_tasks)

        if not upload_result:
            logger.error(
                f"Failed to upload {len(failed_files)} files to store://{app_settings.minio_bucket}/{prefix}. "
                f"Failed files: {failed_files[:10]}..."
                if len(failed_files) > 10
                else f"Failed files: {failed_files}"
            )
            # DON'T delete local files on failure - allows retry/resume
            logger.warning("Local files preserved for retry. Failed files can be resumed on next attempt.")
            return False

        logger.info(f"Uploaded {len(upload_tasks)} files in {prefix} to store://{app_settings.minio_bucket}/{prefix}")

        # Delete files that were successfully uploaded AND marked for deletion
        files_deleted = 0
        failed_files_set = set(failed_files)

        for object_name, (file_path, should_delete) in file_deletion_map.items():
            # Only delete if:
            # 1. File was successfully uploaded (not in failed_files)
            # 2. File was marked for deletion (large file)
            if object_name not in failed_files_set and should_delete:
                safe_delete(file_path)
                files_deleted += 1

        # Delete ignore paths
        for ignore_path in IGNORE_PATHS:
            ignore_full_path = os.path.join(local_folder_path, ignore_path)
            if os.path.exists(ignore_full_path):
                safe_delete(ignore_full_path)
                files_deleted += 1

        if files_deleted > 0:
            logger.info(f"Deleted {files_deleted} files after successful upload")

        return True

    def remove_objects(
        self, prefix: str, recursive: bool = False, bucket_name: str = app_settings.minio_bucket
    ) -> bool:
        """Remove objects from the MinIO store.

        Args:
            prefix (str): The prefix to use for the removal
            recursive (bool): Whether to remove the objects recursively

        Returns:
            bool: True if the removal was successful, False otherwise
        """
        delete_object_list = [
            DeleteObject(x.object_name)
            for x in self.client.list_objects(
                bucket_name,
                prefix,
                recursive=recursive,
            )
        ]

        # Remove the objects
        try:
            errors = self.client.remove_objects(bucket_name, delete_object_list)
        except Exception as e:
            logger.exception("Error occurred when deleting minio object: %s", e)
            return False

        is_error = False
        for error in errors:
            logger.error(f"Error occurred when deleting minio object: {error}")
            is_error = True

        if is_error:
            logger.error("Failed to delete objects from MinIO store")
            return False

        logger.debug(f"Deleted {len(delete_object_list)} objects from {prefix}")
        return True

    def download_folder(self, prefix: str, local_destination: str) -> List[str]:
        """Download all objects in the bucket with the given prefix.

        Preserves the same folder structure.

        Args:
            prefix (str): The prefix (folder path) in the bucket to download.
            local_destination (str): Local directory to store downloaded files.

        Returns:
            List[str]: List of downloaded file paths
        """
        # Ensure destination directory exists
        os.makedirs(local_destination, exist_ok=True)

        logger.info(f"Starting download from bucket: {app_settings.minio_bucket}, prefix: {prefix}")
        logger.info(f"Downloading to: {local_destination}")

        # List all objects under the specified prefix
        try:
            objects = self.client.list_objects(app_settings.minio_bucket, prefix=prefix, recursive=True)
            objects_list = list(objects)  # Convert iterator to list to check if empty
        except S3Error as err:
            logger.error(f"Error listing objects: {err}")
            return []

        downloaded_files = []

        if not objects_list:
            logger.warning(f"No objects found in bucket {app_settings.minio_bucket} with prefix {prefix}")
            return downloaded_files

        for obj in objects_list:
            # Skip directory markers
            if obj.object_name.endswith("/"):
                continue

            # Calculate relative path
            relative_path = obj.object_name[len(prefix) :] if obj.object_name.startswith(prefix) else obj.object_name
            if relative_path.startswith("/"):
                relative_path = relative_path[1:]

            # Construct the full local file path
            local_file_path = os.path.join(local_destination, relative_path)

            # Create any necessary directories
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            # Download the object to the local file path
            try:
                self.client.fget_object(app_settings.minio_bucket, obj.object_name, local_file_path)
                downloaded_files.append(local_file_path)
                logger.info(f"Successfully downloaded: {obj.object_name} -> {local_file_path}")
            except S3Error as err:
                logger.error(f"Error downloading {obj.object_name}: {err}")

        logger.info(f"Downloaded {len(downloaded_files)} files")
        return downloaded_files

    def get_object_count_and_size(self, prefix: str = "") -> tuple[int, int]:
        """Get total number of files and storage size in a bucket with prefix.

        Args:
            prefix (str): The prefix to filter objects (default: empty string for all objects)

        Returns:
            tuple[int, int]: Tuple containing:
                - Number of files
                - Total size in bytes
        """
        try:
            # List all objects under the specified prefix
            objects = self.client.list_objects(bucket_name=app_settings.minio_bucket, prefix=prefix, recursive=True)

            file_count = 0
            total_size = 0

            # Process each object
            for obj in objects:
                # Skip directory markers
                if obj.object_name.endswith("/"):
                    continue

                # Get object stats for accurate size
                stat = self.client.stat_object(bucket_name=app_settings.minio_bucket, object_name=obj.object_name)

                file_count += 1
                total_size += stat.size

            return file_count, total_size

        except S3Error as err:
            logger.exception(f"Error listing bucket contents: {err}")
            return 0, 0
        except Exception as e:
            logger.exception(f"Unexpected error while listing bucket: {e}")
            return 0, 0

    def download_file(
        self, object_path: str, local_destination: str, bucket_name: str = app_settings.minio_bucket
    ) -> Optional[Tuple[str, int]]:
        """Download a single object from the bucket to the local destination.

        Args:
            object_path (str): The full path of the object in the bucket.
            local_destination (str): The local file path or directory to save the object.

        Returns:
            Optional[Tuple[str, int]]: Tuple containing the downloaded file path and its size in bytes,
                                    or None if download failed.
        """
        try:
            logger.info(f"Starting download from bucket: {bucket_name}, object: {object_path}")

            # If destination is a directory, append the file name
            if os.path.isdir(local_destination):
                filename = os.path.basename(object_path)
                local_file_path = os.path.join(local_destination, filename)
            else:
                local_file_path = local_destination

            # Ensure the local directory exists
            os.makedirs(os.path.dirname(local_file_path), exist_ok=True)

            # Download the object
            self.client.fget_object(bucket_name, object_path, local_file_path)

            # Get the downloaded file size
            file_size = os.path.getsize(local_file_path)

            logger.info(f"Successfully downloaded: {object_path} -> {local_file_path} ({file_size} bytes)")
            return local_file_path, file_size

        except S3Error as err:
            logger.error(f"Error downloading {object_path}: {err}")
            return None

    def get_client(self):
        """Return the MinIO client used for interacting with the object storage."""
        return self.client


def measure_minio_upload_speed(file_size_mb: int = 20) -> float:
    """Measure MinIO upload speed by uploading test files twice.

    Args:
        endpoint: MinIO endpoint
        access_key: MinIO access key
        secret_key: MinIO secret key
        bucket_name: Bucket to upload to
        secure: Use HTTPS if True
        file_size_mb: Size of test file in MB

    Returns:
        float: Average upload speed in bytes/s
    """
    try:
        # Initialize MinIO client
        client = Minio(
            endpoint=app_settings.minio_endpoint,
            access_key=secrets_settings.minio_access_key,
            secret_key=secrets_settings.minio_secret_key,
            secure=app_settings.minio_secure,
        )

        # Convert MB to bytes
        file_size_bytes = file_size_mb * 1024 * 1024

        # Create test file
        test_file = "upload_test_file"
        data = os.urandom(1024 * 1024)  # 1MB of random data

        logger.debug(f"Creating test file of size {file_size_mb}MB ({file_size_bytes} bytes)...")
        with open(test_file, "wb") as f:
            for _ in range(file_size_mb):
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

        # Ensure bucket exists
        if not client.bucket_exists(app_settings.minio_bucket):
            client.make_bucket(app_settings.minio_bucket)

        # Run tests for TEST_COUNT times
        TEST_COUNT = 1
        speeds = []
        for i in range(TEST_COUNT):
            logger.info(f"\nRunning test {i + 1}/{TEST_COUNT}")

            # Upload file and measure time
            start_time = time.time()
            client.fput_object(app_settings.minio_bucket, f"test_upload_{i}.bin", test_file)
            end_time = time.time()

            # Calculate speed in bytes/s
            duration = end_time - start_time
            speed = file_size_bytes / duration  # bytes/s
            speeds.append(speed)

            logger.info(f"Test {i + 1} Speed: {speed:.2f} bytes/s")

            # Clean up uploaded file
            client.remove_object(app_settings.minio_bucket, f"test_upload_{i}.bin")

        # Calculate average speed in bytes/s
        avg_speed = sum(speeds) / len(speeds)

        # Clean up local test file
        os.remove(test_file)

        return avg_speed

    except Exception as e:
        logger.error(f"Error measuring upload speed: {e}")
        return 134846302.4  # Average speed tested


def measure_minio_download_speed(file_size_mb: int = 100) -> float:
    """Measure MinIO download speed by downloading test files.

    Args:
        file_size_mb: Size of test file in MB

    Returns:
        float: Average download speed in bytes/s
    """
    try:
        # Initialize MinIO client
        client = Minio(
            endpoint=app_settings.minio_endpoint,
            access_key=secrets_settings.minio_access_key,
            secret_key=secrets_settings.minio_secret_key,
            secure=app_settings.minio_secure,
        )

        # Convert MB to bytes
        file_size_bytes = file_size_mb * 1024 * 1024

        # Create test file
        test_file = "upload_test_file"
        download_file = "download_test_file"
        data = os.urandom(1024 * 1024)  # 1MB of random data

        logger.debug(f"Creating test file of size {file_size_mb}MB ({file_size_bytes} bytes)...")
        with open(test_file, "wb") as f:
            for _ in range(file_size_mb):
                f.write(data)
                f.flush()
                os.fsync(f.fileno())

        # Ensure bucket exists
        if not client.bucket_exists(app_settings.minio_bucket):
            client.make_bucket(app_settings.minio_bucket)

        # Upload the test file first
        test_object_name = "test_download.bin"
        client.fput_object(app_settings.minio_bucket, test_object_name, test_file)

        # Run tests for TEST_COUNT times
        TEST_COUNT = 1
        speeds = []
        for i in range(TEST_COUNT):
            logger.info(f"\nRunning download test {i + 1}/{TEST_COUNT}")

            # Download file and measure time
            start_time = time.time()
            client.fget_object(app_settings.minio_bucket, test_object_name, download_file)
            end_time = time.time()

            # Calculate speed in bytes/s
            duration = end_time - start_time
            speed = file_size_bytes / duration  # bytes/s
            speeds.append(speed)

            logger.info(f"Test {i + 1} Download Speed: {speed:.2f} bytes/s")

            # Clean up downloaded file
            if os.path.exists(download_file):
                os.remove(download_file)

        # Calculate average speed in bytes/s
        avg_speed = sum(speeds) / len(speeds)

        # Clean up remote and local test files
        client.remove_object(app_settings.minio_bucket, test_object_name)
        if os.path.exists(test_file):
            os.remove(test_file)

        return avg_speed

    except Exception as e:
        logger.error(f"Error measuring download speed: {e}")
        return 142657891.3  # Default average download speed if test fails
