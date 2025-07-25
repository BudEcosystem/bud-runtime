import json
import os

from budmicroframe.commons import logging

from budmodel.commons.config import app_settings
from budmodel.commons.constants import COMMON_LICENSE_MINIO_OBJECT_NAME
from budmodel.model_info.license import LicenseExtractor
from budmodel.model_info.models import LicenseInfoCRUD, LicenseInfoSchema
from budmodel.model_info.store import ModelStore

from .base_seeder import BaseSeeder


logger = logging.get_logger(__name__)

# Get current directory
current_dir = os.path.dirname(os.path.abspath(__file__))


class LicenseSeeder(BaseSeeder):
    def seed(self):
        """Seed the licenses."""
        # Get licenses directory
        license_files_dir = os.path.join(current_dir, "data", "licenses")

        # Source the licenses.json file
        source_licenses_file = os.path.join(current_dir, "licenses.json")

        # Read the licenses.json file
        with open(source_licenses_file, "r") as f:
            source_licenses = json.load(f)

        # Extract individual licenses
        for license in source_licenses:
            # Get license source
            license_source = os.path.join(license_files_dir, license["license_file"])

            # Minio object name
            license_file = os.path.basename(license_source)
            minio_object_name = f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/{license_file}"

            # Check license in database
            with LicenseInfoCRUD() as crud:
                license_info = crud.fetch_one(
                    conditions={
                        "license_id": license["license_id"],
                        "url": f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/{license['license_file']}",
                    }
                )

                if license_info and license_info.is_extracted:
                    logger.debug(f"License {license['license_id']} already exists")
                    self.upsert_in_minio(license_source, minio_object_name)
                    continue

                license_data = LicenseExtractor().extract_license(
                    license_source=license_source,
                    license_id=license["license_id"],
                    license_name=license["license_name"],
                )

                logger.debug(f"License {license['license_id']} exists but not extracted")
                if license_info and not license_info.is_extracted and license_data.is_extracted:
                    logger.debug(f"License {license['license_id']} extracted")

                    # Update in minio storage
                    is_uploaded = self.upsert_in_minio(license_source, minio_object_name)
                    if not is_uploaded:
                        logger.error(f"License {license['license_id']} failed to upload to minio")
                        continue

                    license_data.url = minio_object_name

                    # Update in database
                    crud.update(license_data.model_dump(), conditions={"id": license_info.id})
                    logger.debug(f"License {license['license_id']} updated in database")
                if not license_info:
                    logger.debug(f"License {license['license_id']} not found in database")

                    # Upsert in minio storage
                    is_uploaded = self.upsert_in_minio(license_source, minio_object_name)
                    if not is_uploaded:
                        logger.error(f"License {license['license_id']} failed to upload to minio")
                        continue

                    # Insert in database
                    license_data.url = minio_object_name
                    crud.insert(LicenseInfoSchema(**license_data.model_dump()))
                    logger.debug(f"License {license['license_id']} inserted in database")

    def upsert_in_minio(self, license_source: str, minio_object_name: str | None = None):
        """Upsert the license in minio storage."""
        # Get license file name from license source
        if not minio_object_name:
            license_file = os.path.basename(license_source)
            minio_object_name = f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/{license_file}"

        # Get minio client
        model_store_client = ModelStore(app_settings.model_download_dir)

        # Check if license file exists in minio
        is_exists = model_store_client.check_object_exists(minio_object_name, app_settings.minio_model_bucket)
        if is_exists:
            logger.debug(f"License {minio_object_name} already exists in minio")
            return True

        # Upload license file to minio
        is_uploaded = model_store_client.upload_file(
            license_source, minio_object_name, app_settings.minio_model_bucket
        )

        if is_uploaded:
            logger.debug(f"License {minio_object_name} uploaded to minio")
            return True
        else:
            logger.error(f"License {minio_object_name} failed to upload to minio")
            return False


if __name__ == "__main__":
    seeder = LicenseSeeder()
    seeder.seed()

    # python -m seeders.license_seeder
