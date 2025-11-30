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


"""Implements services and business logic for license extraction."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.request import ProxyHandler, Request, build_opener

import requests
from bs4 import BeautifulSoup
from budmicroframe.commons import logging
from huggingface_hub import ModelCard, hf_hub_download, list_repo_files
from huggingface_hub import errors as hf_hub_errors
from json_repair import repair_json
from sqlalchemy import select

from ..commons.config import app_settings, secrets_settings
from ..commons.constants import COMMON_LICENSE_MINIO_OBJECT_NAME, LICENSE_ANALYSIS_PROMPT, LICENSE_MINIO_OBJECT_NAME
from ..commons.exceptions import LicenseExtractionException
from ..commons.helpers import extract_json_from_string
from ..commons.inference import InferenceClient
from .helper import get_pdf_file_content, get_text_file_content, get_url_content
from .models import LicenseInfoCRUD, LicenseInfoSchema
from .parser import fetch_response_from_perplexity
from .schemas import LicenseCreate
from .store import ModelStore


logger = logging.get_logger(__name__)


class LicenseExtractor:
    """Extracts license information from a given text."""

    def get_license_content_from_source(self, source: str) -> str:
        """Get license content from a given source.

        Args:
            source (str): The source to get the license content from.

        Returns:
            str: The license content.
        """
        try:
            content = None
            if source.startswith(("http://", "https://")):
                # Fetch content from URL
                content = get_url_content(source)
            elif os.path.isfile(source):
                # Fetch content from a file
                file_extension = Path(source).suffix.lower()
                if file_extension in [".txt", ".md", ".rst", ""]:
                    content = get_text_file_content(source)
                elif file_extension == ".pdf":
                    content = get_pdf_file_content(source)
                else:
                    logger.error("Unsupported file type: %s", file_extension)
                    raise LicenseExtractionException(f"Unsupported file type: {file_extension}")
            else:
                logger.error("Invalid source provided: %s", source)
                raise LicenseExtractionException("Invalid source provided: %s", source)

            if content.startswith("Error:"):
                raise LicenseExtractionException(content)

            return content
        except Exception as e:
            logger.error("Unexpected error fetching license content: %s", e)
            raise LicenseExtractionException("Unexpected error fetching license content") from e

    def get_license_content_from_minio(self, object_name: str) -> str:
        """Get license content from a given minio object name."""
        try:
            # Download file from minio to a temporary file
            with tempfile.TemporaryDirectory() as temp_dir:
                # Download file from minio
                minio_client = ModelStore(app_settings.model_download_dir)
                minio_download = minio_client.download_file(object_name, temp_dir, app_settings.minio_model_bucket)
                if not minio_download:
                    logger.error("License file not found in minio")
                    raise LicenseExtractionException("License file not found in minio")

                # Downloaded file path
                temp_file = minio_download[0]
                logger.debug("License file downloaded to: %s with size: %s", temp_file, minio_download[1])

                # Get file extension
                file_extension = Path(temp_file).suffix.lower()
                if file_extension in [".txt", ".md", ".rst", ""]:
                    content = get_text_file_content(temp_file)
                elif file_extension == ".pdf":
                    content = get_pdf_file_content(temp_file)
                else:
                    logger.error("Unsupported file type: %s", file_extension)
                    raise LicenseExtractionException(f"Unsupported file type: {file_extension}")
                return content
        except Exception as e:
            logger.exception("Unexpected error fetching license content: %s", e)
            raise LicenseExtractionException("Unexpected error fetching license content") from e

    def get_license_content_from_url(self, url: str) -> str:
        """Get license content from a given url."""
        try:
            req = Request(url=url, headers={"User-Agent": "Mozilla/5.0"})
            opener = build_opener(ProxyHandler({}))
            with opener.open(req, timeout=10) as response:
                content = response.read()

            soup = BeautifulSoup(content, "html.parser")
            license_content = str(soup.text).strip()
            if license_content.startswith("Error:"):
                logger.error("Error fetching license content from url: %s", license_content)
                raise LicenseExtractionException(license_content)
            elif not license_content:
                logger.error("Unable to get license text from given url: %s", url)
                raise LicenseExtractionException("Unable to get license text from given url: %s", url)
            return license_content
        except (Exception, LicenseExtractionException) as e:
            logger.exception("Unexpected error fetching license content from url: %s", url)
            raise LicenseExtractionException("Unexpected error fetching license content from url: %s", url) from e

    def generate_license_details(self, license_text: str) -> List[Dict[str, Any]]:
        """Generate license details from the license source."""
        if not license_text:
            logger.error("License content is None or empty.")
            raise LicenseExtractionException("License content is empty.")

        LICENSE_QUESTIONS = {
            "Q1": {"question": "Can you modify the software, model, or framework?", "impact": "POSITIVE"},
            "Q2": {"question": "Are there any restrictions on modifying core components?", "impact": "NEGATIVE"},
            "Q3": {"question": "Can you distribute the modified version of the software/model?", "impact": "POSITIVE"},
            "Q4": {"question": "Are there limitations on how you share derivative works?", "impact": "NEGATIVE"},
            "Q5": {
                "question": "Must you open-source your modifications (Copyleft vs. Permissive)?",
                "impact": "NEGATIVE",
            },
            "Q6": {"question": "Are you allowed to monetize the tool you build on top of it?", "impact": "POSITIVE"},
            "Q7": {
                "question": "Does the license restrict commercial applications (e.g., Non-Commercial License)?",
                "impact": "NEGATIVE",
            },
            "Q8": {"question": "Are there royalty requirements or revenue-sharing clauses?", "impact": "NEGATIVE"},
            "Q9": {
                "question": "Are you required to credit the original software, model, or tool?",
                "impact": "NEGATIVE",
            },
            "Q10": {
                "question": "Must you include license texts, disclaimers, or notices in your product?",
                "impact": "NEGATIVE",
            },
            "Q11": {"question": "Does the license require you to make your changes public?", "impact": "NEGATIVE"},
            "Q12": {"question": "If the tool provides API access, what are the usage limits?", "impact": "NEGATIVE"},
            "Q13": {
                "question": "Are you allowed to build commercial applications using the API?",
                "impact": "POSITIVE",
            },
            "Q14": {"question": "Are there rate limits or paywalls for extended use?", "impact": "NEGATIVE"},
            "Q15": {"question": "Does the license provide any patent grants or protections?", "impact": "POSITIVE"},
            "Q16": {
                "question": "Could you face legal risks if your tool extends the licensed software?",
                "impact": "NEGATIVE",
            },
            "Q17": {
                "question": "Are there restrictions on filing patents for derivative works?",
                "impact": "NEGATIVE",
            },
            "Q18": {
                "question": "If it’s an AI model, does the license restrict how you can use the training data?",
                "impact": "NEGATIVE",
            },
            "Q19": {
                "question": "Are there privacy constraints that affect how user data is handled?",
                "impact": "NEGATIVE",
            },
            "Q20": {"question": "Can the licensor revoke your usage rights at any time?", "impact": "NEGATIVE"},
            "Q21": {
                "question": "Is there a clause that limits their liability in case of legal issues?",
                "impact": "NEGATIVE",
            },
            "Q22": {
                "question": "Are there terms that prevent the use of the tool for specific purposes (e.g., ethical AI clauses)?",
                "impact": "NEGATIVE",
            },
        }

        LICENSE_TYPES = [
            {
                "type": "Permissive Open Source",
                "description": "Allows modification and redistribution with minimal restrictions, usually requiring only attribution.",
                "suitability": "MOST",
            },
            {
                "type": "Copyleft Open Source",
                "description": "Requires any modifications or derivative works to be shared under the same license terms.",
                "suitability": "GOOD",
            },
            {
                "type": "Weak Copyleft Open Source",
                "description": "Allows linking with proprietary software, but modifications to the open-source parts must remain open.",
                "suitability": "GOOD",
            },
            {
                "type": "Open Source but Restrictive",
                "description": "Allows modification but places restrictions such as non-commercial use or additional compliance requirements.",
                "suitability": "LOW",
            },
            {
                "type": "Open Source but No Redistribution",
                "description": "Allows modifications for personal use but prohibits sharing or distributing modified versions.",
                "suitability": "LOW",
            },
            {
                "type": "Non-Commercial License",
                "description": "The software can be modified and shared, but only for personal or educational use. Commercial distribution is prohibited.",
                "suitability": "LOW",
            },
            {
                "type": "Fully Proprietary",
                "description": "Users cannot modify, distribute, or access the source code; typically requires a paid license.",
                "suitability": "WORST",
            },
            {
                "type": "Proprietary with API Access",
                "description": "Source code remains closed, but users can integrate with the software via an API.",
                "suitability": "WORST",
            },
            {
                "type": "Proprietary with Limited Customization",
                "description": "Some modifications are allowed but only within defined boundaries set by the licensor.",
                "suitability": "LOW",
            },
            {
                "type": "Closed Source but Free to Use",
                "description": "Users can access and use the software without cost but cannot modify or distribute it.",
                "suitability": "WORST",
            },
        ]

        try:
            if secrets_settings.perplexity_api_key:
                llm_response = fetch_response_from_perplexity(
                    app_settings.model, license_text, LICENSE_ANALYSIS_PROMPT
                )
            else:
                inference_client = InferenceClient()
                llm_response = inference_client.chat_completions(
                    license_text, system_prompt=LICENSE_ANALYSIS_PROMPT, temperature=0.1
                )

            if isinstance(llm_response, str):
                llm_response = extract_json_from_string(llm_response)
                llm_response = json.loads(repair_json(llm_response))

            answers = {}
            answers["name"] = llm_response["name"]
            answers["type"] = llm_response["type"]
            answers["type_description"] = ""
            answers["type_suitability"] = ""
            answers["faqs"] = {}

            for license in LICENSE_TYPES:
                if license["type"].lower() == answers["type"].lower():
                    answers["type_description"] = license["description"]
                    answers["type_suitability"] = license["suitability"]
                    break

            for k, v in llm_response.items():
                if k.upper() in LICENSE_QUESTIONS:
                    # Initialize the dictionary for this question if it doesn't exist
                    answers["faqs"][k] = {}

                    # Set default impact as NEUTRAL
                    impact = "NEUTRAL"

                    # Get the expected impact from license questions
                    expected_impact = LICENSE_QUESTIONS[k.upper()]["impact"]

                    # Determine actual impact based on answer
                    if v.get("answer", "").lower() == "yes":
                        impact = expected_impact
                    elif v.get("answer", "").lower() == "no":
                        impact = "POSITIVE" if expected_impact == "NEGATIVE" else "NEGATIVE"

                    # Safely assign values using get() to avoid KeyError
                    answers["faqs"][k]["impact"] = impact
                    answers["faqs"][k]["answer"] = v.get("answer", "")
                    answers["faqs"][k]["question"] = v.get("question", "")
                    answers["faqs"][k]["reason"] = v.get("reason", "")

            # Convert answers to a list of dictionaries (For compatibility with the existing implementation)
            # NOTE: Doing this as an extra loop incase to revert back to the default format
            reformatted_faqs = []
            for _k, v in answers["faqs"].items():
                reformatted_faqs.append(v)
            answers["faqs"] = reformatted_faqs

            return answers
        except Exception as e:
            logger.exception(f"Error generating licence FAQ: {e}")
            raise LicenseExtractionException("Extracting license details failed") from e

    def extract_license(
        self, license_source: str | None = None, license_id: str | None = None, license_name: str | None = None
    ) -> LicenseCreate | None:
        """Extract license details from the license text.

        Args:
            license_id (str | None): The ID of the license.
            license_source (str | None): The source of the license.
        """
        license_details = {
            "license_id": None,
            "name": None,
            "type": None,
            "type_description": None,
            "type_suitability": None,
            "faqs": [],
            "is_extracted": False,
        }
        if license_source:
            # Get license details from the source
            try:
                license_text = self.get_license_content_from_source(license_source)
            except LicenseExtractionException as e:
                logger.error(f"Error fetching license content: {e}")
                return None

            try:
                license_details = self.generate_license_details(license_text)
                license_details["is_extracted"] = True
            except LicenseExtractionException as e:
                logger.error(f"Error generating license details: {e}")

        if license_id:
            license_details["license_id"] = license_id
            # Use license_id as fallback if name is still None or empty
            if not license_details.get("name"):
                license_details["name"] = license_id

        if license_name:
            license_details["name"] = license_name

        # Final safety check: ensure name is never None
        if not license_details.get("name"):
            logger.warning(
                f"License name is missing, using license_id as fallback: {license_details.get('license_id')}"
            )
            license_details["name"] = license_details.get("license_id") or "unknown"

        return LicenseCreate(
            license_id=license_details["license_id"],
            name=license_details["name"],
            type=license_details["type"],
            description=license_details["type_description"],
            suitability=license_details["type_suitability"],
            faqs=license_details["faqs"],
            is_extracted=license_details["is_extracted"],
            url=license_source,
        )

    def sanitized_model_uri(self, uri: str) -> str:
        """Sanitize the model uri."""
        return uri.replace("/", "_")

    def upsert_in_minio(self, license_source: str, minio_object_name: str | None = None):
        """Upsert the license in minio storage."""
        # Get license file name from license source
        if not minio_object_name:
            license_file = os.path.basename(license_source)
            minio_object_name = f"{LICENSE_MINIO_OBJECT_NAME}/{license_file}"

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


class HuggingFaceLicenseExtractor(LicenseExtractor):
    """Extract license details from a Hugging Face model card."""

    def extract_license(self, uri: str, hf_token: str | None = None) -> LicenseInfoSchema | None:
        """Extract license details from a Hugging Face model card."""
        # Get license data from huggingface
        hf_license_id, hf_license_name = self.get_hf_license_data(uri, hf_token)

        # Check License file exist in huggingface model files
        model_files = list_repo_files(uri, token=hf_token)

        # Check if license file exist in model files
        license_file = next((file for file in model_files if "LICENSE" in os.path.basename(file).upper()), None)

        if license_file:
            logger.debug(f"License file found in huggingface model files: {license_file}")
            # Check if license is already extracted and present in database
            sanitized_uri = self.sanitized_model_uri(uri)
            db_license_info = None
            with LicenseInfoCRUD() as crud:
                stmt = select(LicenseInfoSchema).where(
                    LicenseInfoSchema.license_id == hf_license_id,
                    LicenseInfoSchema.url.startswith(f"{LICENSE_MINIO_OBJECT_NAME}/{sanitized_uri}/"),
                )
                results = crud.session.execute(stmt).scalars().all()
                if results:
                    if len(results) > 1:
                        logger.warning(
                            f"Found {len(results)} duplicate licenses for {hf_license_id} "
                            f"with URL pattern {sanitized_uri}, using most recent"
                        )
                    # Use the most recent license record
                    db_license_info = max(results, key=lambda x: x.created_at if x.created_at else datetime.min)
                    if db_license_info and db_license_info.is_extracted:
                        logger.debug("License info already extracted and present in database")
                        return db_license_info
                else:
                    db_license_info = None

            # Get license content from huggingface
            headers = {}
            if hf_token:
                headers["Authorization"] = f"Bearer {hf_token}"
            try:
                response = requests.get(
                    f"https://huggingface.co/{uri}/resolve/main/{license_file}", headers=headers, timeout=30
                )
                license_content = response.text
            except Exception as e:
                logger.error(f"Error fetching license content: {e}")
                return None

            # Extract license details from license content
            license_details = {
                "license_id": None,
                "name": None,
                "type": None,
                "type_description": None,
                "type_suitability": None,
                "faqs": [],
                "is_extracted": False,
            }

            try:
                license_details = self.generate_license_details(license_content)
                license_details["is_extracted"] = True
            except LicenseExtractionException as e:
                logger.error(f"Error generating license details: {e}")
                license_details["is_extracted"] = False

            if hf_license_id:
                license_details["license_id"] = hf_license_id
                # Use license_id as fallback if name is still None or empty
                if not license_details.get("name"):
                    license_details["name"] = hf_license_id

            if hf_license_name and hf_license_name != "Unknown":
                license_details["name"] = hf_license_name

            # Upload license details to minio by downloading to a temporary file
            with tempfile.TemporaryDirectory() as temp_dir:
                temp_extract_dir = Path(temp_dir)

                # Download license file from huggingface
                download_path = hf_hub_download(uri, license_file, token=hf_token, local_dir=temp_extract_dir)

                # Sanitize model uri
                sanitized_uri = self.sanitized_model_uri(uri)

                minio_object_name = f"{LICENSE_MINIO_OBJECT_NAME}/{sanitized_uri}/{os.path.basename(download_path)}"

                # Upload license details to minio
                is_uploaded = self.upsert_in_minio(download_path, minio_object_name)

                # Handle upload failure
                if not is_uploaded:
                    return None

                logger.debug(f"License info uploaded to minio: {minio_object_name}")

                # Ensure name is never None before creating LicenseCreate (safety check)
                if not license_details.get("name"):
                    logger.warning(
                        f"License name is missing for {uri}, using license_id as fallback: {license_details.get('license_id')}"
                    )
                    license_details["name"] = license_details.get("license_id") or "unknown"

                # Create license data
                license_data = LicenseCreate(
                    license_id=license_details["license_id"],
                    name=license_details["name"],
                    type=license_details["type"],
                    description=license_details["type_description"],
                    suitability=license_details["type_suitability"],
                    faqs=license_details["faqs"],
                    is_extracted=license_details["is_extracted"],
                    url=minio_object_name,
                )

                # Use upsert pattern to avoid duplicates from concurrent inserts
                with LicenseInfoCRUD() as crud:
                    # If we found an existing record, update it
                    if db_license_info:
                        crud.update(license_data.model_dump(), {"id": db_license_info.id})
                        db_license_info = crud.fetch_one({"id": db_license_info.id})
                        logger.debug("License info updated in database")
                        return db_license_info
                    else:
                        # Try to insert, but handle potential race condition
                        try:
                            db_license_info = crud.insert(LicenseInfoSchema(**license_data.model_dump()))
                            logger.debug("License info inserted in database")
                            return db_license_info
                        except Exception as e:
                            # If insert fails due to unique constraint, fetch the existing record
                            if "duplicate" in str(e).lower() or "unique" in str(e).lower():
                                logger.warning("Concurrent insert detected, fetching existing license record")
                                stmt = select(LicenseInfoSchema).where(
                                    LicenseInfoSchema.license_id == license_data.license_id,
                                    LicenseInfoSchema.url == license_data.url,
                                )
                                db_license_info = crud.session.execute(stmt).scalar_one_or_none()
                                if db_license_info:
                                    return db_license_info
                            # Re-raise if it's a different error
                            raise
        else:
            with LicenseInfoCRUD() as crud:
                stmt = select(LicenseInfoSchema).where(
                    LicenseInfoSchema.license_id == hf_license_id,
                    LicenseInfoSchema.url.startswith(f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/"),
                )
                results = crud.session.execute(stmt).scalars().all()
                if results:
                    if len(results) > 1:
                        logger.warning(
                            f"Found {len(results)} duplicate common licenses for {hf_license_id}, using most recent"
                        )
                    # Use the most recent license record
                    db_license_info = max(results, key=lambda x: x.created_at if x.created_at else datetime.min)
                    logger.debug("License info found in database")
                    return db_license_info
                else:
                    logger.debug("License info not found in database")
                    return None

    def get_hf_license_data(self, uri: str, hf_token: str | None = None) -> Dict[str, Any]:
        """Get license data from huggingface."""
        # Handle missing README.md gracefully
        try:
            model_card = ModelCard.load(uri, token=hf_token)
        except hf_hub_errors.EntryNotFoundError as e:
            logger.warning("README.md not found for %s when extracting license, using defaults: %s", uri, str(e))
            # Return default values when README is missing
            return "unknown", "Unknown"
        except Exception as e:
            logger.error("Failed to load ModelCard for license extraction from %s: %s", uri, str(e))
            # Return default values on any error
            return "unknown", "Unknown"

        license_name = model_card.data.get("license_name", "Unknown")
        license_id = model_card.data.get("license", "Unknown")
        if isinstance(license_id, str):
            license_id = license_id.lower()
        elif isinstance(license_id, list) and len(license_id) > 0:
            license_id = license_id[0].lower()
        return license_id, license_name


class LocalModelLicenseExtractor(LicenseExtractor):
    """Extract license details from a local model."""

    def extract_license(self, model_path: str) -> LicenseInfoSchema | None:
        """Extract license details from a local model."""
        # Get license data
        license_data, license_path = LocalModelLicenseExtractor.get_license_data(model_path)

        if not license_data or not license_path:
            logger.error(f"License data not found in {model_path}")
            return None

        # Get mapped licenses
        # existing_licenses_mapper = mapped_licenses()

        extracted_license = {
            "license_id": None,
            "name": None,
            "type": None,
            "description": None,
            "suitability": None,
            "faqs": [],
            "is_extracted": False,
        }

        try:
            # Generate license details
            license_details = self.generate_license_details(license_data)
            extracted_license["is_extracted"] = True
        except LicenseExtractionException as e:
            logger.error(f"Error generating license details: {e}")
            license_details = {}

        license_name = license_details.get("name")
        if license_name:
            # NOTE: Commented Out: Reason - For local models no need to reuse foreign id of common licenses, since model license relation is one to one if model is onboarded from disk, url
            # # Check if license_name is in existing_licenses_mapper
            # for mapped_license in existing_licenses_mapper:
            #     key_words = [mapped_license["license_id"]] + mapped_license["potential_names"]
            #     normalized_key_words = [normalize_license_identifier(keyword) for keyword in key_words]
            #     normalized_license_name = normalize_license_identifier(license_name)
            #     if any(keyword in normalized_license_name for keyword in normalized_key_words):
            #         with LicenseInfoCRUD() as crud:
            #             stmt = select(LicenseInfoSchema).where(
            #                 LicenseInfoSchema.license_id == mapped_license["license_id"],
            #                 LicenseInfoSchema.url.startswith(f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/"),
            #             )
            #             db_license_info = crud.session.execute(stmt).scalar_one_or_none()
            #             if db_license_info:
            #                 logger.debug(f"License {license_name} found in database")
            #                 return db_license_info
            #             else:
            #                 logger.debug(
            #                     f"License {mapped_license['license_id']} not found in database. Uploading to minio"
            #                 )
            #                 # Upload license to minio and update the url
            #                 model_name = os.path.relpath(model_path, app_settings.model_download_dir)
            #                 minio_object_name = (
            #                     f"{LICENSE_MINIO_OBJECT_NAME}/{model_name}/{os.path.basename(license_path)}"
            #                 )
            #                 is_uploaded = self.upsert_in_minio(
            #                     os.path.join(app_settings.model_download_dir, license_path), minio_object_name
            #                 )
            #                 if is_uploaded:
            #                     extracted_license["url"] = minio_object_name
            #                     logger.debug(f"License {license_name} uploaded to minio: {minio_object_name}")
            #                 else:
            #                     logger.error(f"License {extracted_license['url']} failed to upload to minio")
            #                     return None
            #                 extracted_license["license_id"] = mapped_license["license_id"]
            #                 extracted_license["name"] = license_name
            #                 extracted_license["url"] = minio_object_name
            # else:
            #     logger.debug(f"License {license_name} not found in mapped licenses")
            #     extracted_license["license_id"] = "unknown"
            #     extracted_license["name"] = license_name
            #     extracted_license["url"] = license_path
            # Commented out till here

            # No longer needed, if above code is uncommented
            extracted_license["license_id"] = "unknown"
            extracted_license["name"] = license_name
            extracted_license["url"] = license_path
        else:
            logger.debug("License name not found in license details")
            extracted_license["license_id"] = "unknown"
            extracted_license["name"] = "Unknown"
            extracted_license["url"] = license_path

        # Add license details to extracted license
        logger.debug("License details added to extracted license")
        extracted_license["faqs"] = license_details.get("faqs", [])
        extracted_license["type"] = license_details.get("type", "")
        extracted_license["suitability"] = license_details.get("type_suitability", "")
        extracted_license["description"] = license_details.get("type_description", "")

        if extracted_license["url"] == license_path:
            logger.debug("Uploading license to minio")
            # Upload license to minio and update the url
            model_name = os.path.relpath(model_path, app_settings.model_download_dir)
            minio_object_name = f"{LICENSE_MINIO_OBJECT_NAME}/{model_name}/{os.path.basename(license_path)}"
            is_uploaded = self.upsert_in_minio(
                os.path.join(app_settings.model_download_dir, license_path), minio_object_name
            )
            if is_uploaded:
                extracted_license["url"] = minio_object_name
                logger.debug(f"License {license_name} uploaded to minio: {minio_object_name}")
            else:
                logger.error(f"License {extracted_license['url']} failed to upload to minio")
                return None

        return LicenseInfoSchema(**extracted_license)

    @staticmethod
    def get_license_data(model_path: str) -> Tuple[str, str]:
        """Get the license data from the model path."""
        # Common license directories
        directories = [".", "docs", "legal", "LICENSE", "licenses"]

        # Common license files
        file_names = [
            "LICENSE",
            "LICENSE.txt",
            "LICENSE.md",
            "LICENSE.rst",
        ]

        for directory in directories:
            directory_path = model_path if directory == "." else os.path.join(model_path, directory)

            if not os.path.exists(directory_path):
                continue

            # Get list of files in directory (case-insensitive)
            dir_files = [f.lower() for f in os.listdir(directory_path)]

            for file_name in file_names:
                if file_name.lower() in dir_files:
                    # Get the actual filename with correct case
                    actual_filename = os.listdir(directory_path)[dir_files.index(file_name.lower())]
                    license_path = os.path.join(directory_path, actual_filename)

                    if os.path.isfile(license_path):
                        # exclude app_settings.model_download_dir from license path
                        license_relative_path = os.path.relpath(license_path, app_settings.model_download_dir)
                        with open(license_path, "r") as f:
                            return f.read(), license_relative_path

        return "", ""
