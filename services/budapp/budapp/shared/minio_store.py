#  -----------------------------------------------------------------------------
#  Copyright (c) 2024 Bud Ecosystem Inc.
#  #
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#  #
#      http://www.apache.org/licenses/LICENSE-2.0
#  #
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.
#  -----------------------------------------------------------------------------

"""Provides shared functions for managing minio store."""

from budmicroframe.commons import logging
from minio import Minio
from minio.deleteobjects import DeleteObject
from minio.error import S3Error

from ..commons.config import app_settings, secrets_settings
from ..commons.exceptions import MinioException


logger = logging.get_logger(__name__)


class ModelStore:
    def __init__(self):
        """Initialize the ModelStore class."""
        self.client = Minio(
            endpoint=app_settings.minio_endpoint,
            access_key=secrets_settings.minio_access_key,
            secret_key=secrets_settings.minio_secret_key,
            secure=app_settings.minio_secure,
        )

    def upload_file(self, bucket_name: str, file_path: str, object_name: str) -> None:
        """Upload a file to the minio store.

        Args:
            bucket_name (str): The name of the bucket to upload the file to
            file_path (str): The path to the file to upload
            object_name (str): The name of the object to upload the file to
        """
        try:
            # Upload the file
            self.client.fput_object(
                bucket_name=bucket_name,
                object_name=object_name,
                file_path=file_path,
            )
            logger.info(f"Uploaded {file_path} to store://{bucket_name}/{object_name}")
        except S3Error as err:
            logger.exception(f"Error uploading {file_path} -> {object_name}: {err}")
            raise MinioException(f"Error uploading {file_path} -> {object_name}: {err}") from err
        except Exception as e:
            logger.exception(f"Error uploading {file_path} -> {object_name}: {e}")
            raise MinioException(f"Error uploading {file_path} -> {object_name}: {e}") from e

    def remove_objects(self, bucket_name: str, prefix: str, recursive: bool = False) -> bool:
        """Remove objects from the MinIO store.

        Args:
            bucket_name (str): The name of the bucket to remove the objects from
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
            raise MinioException(f"Error occurred when deleting minio object: {e}") from e

        is_error = False
        for error in errors:
            logger.error(f"Error occurred when deleting minio object: {error}")
            is_error = True

        if is_error:
            raise MinioException("Failed to delete objects from MinIO store")

        logger.debug(f"Deleted {len(delete_object_list)} objects from {prefix}")

    def check_file_exists(self, bucket_name: str, object_name: str) -> bool:
        """Check if a file exists in the MinIO store.

        Args:
            bucket_name (str): The name of the bucket to check the file in
            object_name (str): The name of the object to check the file in

        Returns:
            bool: True if the file exists, False otherwise
        """
        try:
            self.client.stat_object(bucket_name, object_name)
            return True
        except S3Error:
            return False

    def download_object(self, bucket_name: str, object_name: str, file_path: str) -> None:
        """Download an object from the MinIO store.

        Args:
            bucket_name (str): The name of the bucket to download the object from
            object_name (str): The name of the object to download
            file_path (str): The path to save the object to
        """
        try:
            self.client.fget_object(bucket_name, object_name, file_path)
        except S3Error as e:
            logger.exception(f"Error occurred when downloading minio object: {e}")
            raise MinioException(f"Error occurred when downloading minio object: {e}") from e
        except Exception as e:
            logger.exception(f"Error occurred when downloading minio object: {e}")
            raise MinioException(f"Error occurred when downloading minio object: {e}") from e

    def get_object_url(self, bucket_name: str, object_name: str) -> str:
        """Get the URL of an object in the MinIO store.

        Args:
            bucket_name (str): The name of the bucket to get the object from
            object_name (str): The name of the object to get the URL of
        """
        return self.client.presigned_get_object(bucket_name, object_name)

    def get_folder_size(self, bucket_name: str, prefix: str) -> float:
        """Get the total size of all objects under a prefix in GiB.

        This method calculates the total storage size of all objects (files)
        under a given prefix in a MinIO bucket. Useful for determining model
        storage requirements.

        Args:
            bucket_name (str): The name of the bucket to calculate size for
            prefix (str): The folder prefix (e.g., "models/llama-2-7b")

        Returns:
            float: Total size in gibibytes (GiB)

        Raises:
            MinioException: If there's an error listing or accessing objects
        """
        try:
            total_size_bytes = 0
            object_count = 0

            # List all objects recursively under the prefix
            for obj in self.client.list_objects(bucket_name, prefix, recursive=True):
                total_size_bytes += obj.size
                object_count += 1

            total_size_gib = total_size_bytes / (1024**3)
            logger.info(
                f"Calculated folder size for {bucket_name}/{prefix}: {total_size_gib:.2f} GiB ({object_count} objects)"
            )
            return total_size_gib

        except Exception as e:
            logger.exception(f"Error calculating folder size for {bucket_name}/{prefix}: {e}")
            raise MinioException(f"Error calculating folder size: {e}") from e
