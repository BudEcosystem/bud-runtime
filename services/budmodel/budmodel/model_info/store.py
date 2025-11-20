import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional, Tuple

from budmicroframe.commons import logging
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from ..commons.config import app_settings, secrets_settings
from ..commons.constants import LOCAL_MIN_SIZE_GB
from ..commons.helpers import safe_delete
from .schemas import UploadFile


logger = logging.get_logger(__name__)


class ModelStore:
    def __init__(self, model_download_dir: str):
        """Initialize the ModelStore class.

        Args:
            model_download_dir (str): The directory to download the model to
        """
        self.model_download_dir = model_download_dir
        self.client = Minio(
            app_settings.minio_endpoint,  # Example endpoint
            access_key=secrets_settings.minio_access_key,  # Example credentials
            secret_key=secrets_settings.minio_secret_key,
            secure=app_settings.minio_secure,
        )

    def upload_file(self, file_path: str, object_name: str, bucket_name: str = app_settings.minio_bucket) -> bool:
        """Upload a file to the MinIO store.

        Args:
            file_path (str): The path to the file to upload
            object_name (str): The name of the object to upload

        Returns:
            bool: True if the upload was successful, False otherwise
        """
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
            logger.exception(f"Error uploading {file_path} -> {object_name}: {err}")
            return False
        except Exception as e:
            logger.exception(f"Error uploading {file_path} -> {object_name}: {e}")
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
            logger.exception(f"Error checking if {object_name} exists: {err}")
            return False

    def perform_threaded_upload(self, upload_files: List[UploadFile]) -> bool:
        """Perform a threaded upload of a file to the MinIO store.

        Args:
            upload_files (list[UploadFile]): The files to upload

        Returns:
            bool: True if the upload was successful, False otherwise
        """
        max_workers = min(len(upload_files), app_settings.max_thread_workers)
        failed_uploads = []

        executor = ThreadPoolExecutor(max_workers=max_workers)
        try:
            futures = [executor.submit(self.upload_file, file.file_path, file.object_name) for file in upload_files]
            for future in as_completed(futures):
                try:
                    if not future.result():
                        failed_uploads.append(future)
                        # On first failure, cancel all pending/running uploads
                        logger.warning("Upload failed, cancelling remaining uploads")
                        for f in futures:
                            if not f.done():
                                f.cancel()
                        # Exit early - don't wait for other uploads
                        break
                except Exception as e:
                    logger.exception("Unexpected error uploading file: %s", e)
                    failed_uploads.append(future)
                    # On exception, cancel all pending/running uploads
                    logger.warning("Upload error, cancelling remaining uploads")
                    for f in futures:
                        if not f.done():
                            f.cancel()
                    # Exit early - don't wait for other uploads
                    break
        finally:
            # Shutdown executor immediately without waiting for running tasks
            # cancel_futures=True cancels all pending tasks (Python 3.9+)
            executor.shutdown(wait=False, cancel_futures=True)

        if failed_uploads:
            logger.error("Failed to upload %d files", len(failed_uploads))
            return False

        return True

    def upload_folder(self, prefix: str) -> bool:
        """Upload a folder to the MinIO store.

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

        # Prepare upload tasks and files to delete
        upload_tasks = []
        files_to_delete = []

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

                # All files with size greater than 1gb will be deleted from local folder
                if file_size_gb > LOCAL_MIN_SIZE_GB:
                    files_to_delete.append(full_path)

                # Compute the relative path from the base local_folder_path
                relative_path = os.path.relpath(full_path, start=local_folder_path)

                # Build the MinIO object name
                # Example: prefix + "subfolder/file.txt"
                object_name = prefix + relative_path.replace(
                    "\\", "/"
                )  # Replace backslashes (Windows) with forward slashes

                upload_tasks.append(UploadFile(file_path=full_path, object_name=object_name))

        if not upload_tasks:
            logger.info("No files to upload")
            return True

        # Perform the upload
        upload_result = self.perform_threaded_upload(upload_tasks)

        if not upload_result:
            logger.error(f"Failed to upload {prefix} to store://{app_settings.minio_bucket}/{prefix}")
            return False

        logger.info(f"Uploaded {len(upload_tasks)} files in {prefix} to store://{app_settings.minio_bucket}/{prefix}")

        # Add ignore paths to files_to_delete
        for ignore_path in IGNORE_PATHS:
            files_to_delete.append(os.path.join(local_folder_path, ignore_path))

        # Delete files
        for file_path in files_to_delete:
            safe_delete(file_path)

        logger.info(f"Deleted {len(files_to_delete)} files after upload")

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
