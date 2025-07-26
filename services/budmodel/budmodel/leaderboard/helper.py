from budmicroframe.commons import logging
from sqlalchemy import select

from ..commons.constants import COMMON_LICENSE_MINIO_OBJECT_NAME
from ..model_info.helper import get_license_details, mapped_licenses
from ..model_info.models import LicenseInfoCRUD, LicenseInfoSchema
from ..model_info.schemas import LicenseInfo


logger = logging.get_logger(__name__)


def upsert_license_details(model_license: str) -> LicenseInfo:
    """Insert or update the license details of a model"""
    licenses = mapped_licenses()

    if model_license:
        license_id, license_name, license_url = get_license_details(model_license, licenses)
    else:
        license_id = license_name = license_url = None

    license_details = None

    if license_id and license_url:
        # Check it is a common license
        try:
            with LicenseInfoCRUD() as license_crud:
                stmt = select(LicenseInfoSchema).where(
                    LicenseInfoSchema.license_id == license_id,
                    LicenseInfoSchema.url.startswith(f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/"),
                )
                existing_license = license_crud.session.execute(stmt).scalar_one_or_none()

            if existing_license:
                logger.debug("License data already exists in the database.")
                license_details = LicenseInfo(
                    name=existing_license.name,
                    id=existing_license.id,
                    url=existing_license.url,
                    faqs=existing_license.faqs,
                    type=existing_license.type,
                    description=existing_license.description,
                    suitability=existing_license.suitability,
                    is_extracted=existing_license.is_extracted,
                    license_id=existing_license.license_id,
                )
                return license_details
            else:
                logger.debug("License id %s does not exist in the database.", license_id)

        except Exception as db_error:
            logger.error(f"Database error: Failed to fetch existing license {license_id}: {db_error}")
            return None
