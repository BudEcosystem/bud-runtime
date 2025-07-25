import json
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import requests  # type: ignore
from bs4 import BeautifulSoup
from PyPDF2 import PdfReader

from ..commons.constants import COMMON_LICENSE_MINIO_OBJECT_NAME


logger = logging.getLogger(__name__)


def extract_answer_and_description(text: str) -> Dict[str, Optional[str]]:
    """Extract the "Answer" (YES/NO) and the corresponding "Description" from the given text."""
    try:
        pattern = r"\*\*Answer\*\*: (YES|NO)\s*\*\*Description\*\*: (.+)"
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return {"answer": match.group(1), "description": match.group(2).strip()}
        return {"answer": None, "description": None}
    except Exception as e:
        logger.error("Error extracting answer and description: %s", e)
        return {"answer": None, "description": None}


# def extract_urls_from_modelcard(model_card):
#     """
#     Extract all URLs from a given model card text.
#     """
#     try:
#         url_pattern = r'https?:\/\/[\w\s"\'\/\+\.\-]+|www\.[\w\s"\'\/\+\.\-]+'
#         urls = re.findall(url_pattern, model_card)
#         return urls
#     except Exception as e:
#         logger.error("Error extracting URLs from model card: %s", e)
#         return []


def extract_urls_from_modelcard(model_card: str) -> Dict[str, List[str]]:
    """Extract all URLs from a given model card text and filters out Git URLs from them."""
    try:
        url_pattern = r'https?:\/\/[\w\s"\'\/\+\.\-]+|www\.[\w\s"\'\/\+\.\-]+'
        git_url_pattern = r"(https?:\/\/|www\.)?(github\.com|gitlab\.com|bitbucket\.org|gitea\.io|sourcehut\.org)\/\S*"

        # Extract all URLs
        all_urls = re.findall(url_pattern, model_card)
        print(all_urls)
        # Filter Git URLs
        git_urls = [url for url in all_urls if re.search(git_url_pattern, url)]

        # Remaining URLs are other URLs
        other_urls = [url for url in all_urls if url not in git_urls]

        return {"git_urls": git_urls, "other_urls": other_urls}
    except Exception as e:
        logger.error("Error extracting and filtering URLs from model card: %s", e)
        return {"git_urls": [], "other_urls": []}


def extract_urls_from_markdown(markdown_output: str) -> Dict[str, Optional[str]]:
    """Extract Git repository and website URLs from markdown-formatted text."""
    try:
        git_repo_pattern = r"\- \*\*Git Repository URL\*\*: \[(.*?)\]\(\1\)"
        website_url_pattern = r"\- \*\*Website URL\*\*: \[(.*?)\]\(\1\)"

        git_repo_match = re.search(git_repo_pattern, markdown_output)
        website_url_match = re.search(website_url_pattern, markdown_output)

        git_repo_url = git_repo_match.group(1) if git_repo_match else None
        website_url = website_url_match.group(1) if website_url_match else None

        return {"git_repo_url": git_repo_url, "website_url": website_url}
    except Exception as e:
        logger.error("Error extracting URLs from markdown: %s", e)
        return {"git_repo_url": None, "website_url": None}


def get_license_content(source: str) -> Optional[str]:
    """Fetch and returns the text content from the given source,which can be a URL or a local file path (.txt, .md, .pdf)."""
    try:
        if source.startswith(("http://", "https://")):
            # Fetch content from URL
            return get_url_content(source)
        elif os.path.isfile(source):
            # Fetch content from a file
            file_extension = Path(source).suffix.lower()
            if file_extension in [".txt", ".md", ".rst", ""]:
                return get_text_file_content(source)
            elif file_extension == ".pdf":
                return get_pdf_file_content(source)
            else:
                logger.error("Unsupported file type: %s", file_extension)
                return f"Error: Unsupported file type '{file_extension}'."
        else:
            logger.error("Invalid source provided: %s", source)
            return "Error: Source is neither a valid URL nor a file path."
    except Exception as e:
        logger.error("Unexpected error fetching license content: %s", e)
        return "Error: Unable to fetch content."


def get_url_content(url: str) -> Optional[str]:
    """Fetch and returns the text content from a URL."""
    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")
        return str(soup.get_text())
    except requests.exceptions.RequestException as e:
        logger.error("HTTP error fetching URL content: %s", e)
        return "Error: Unable to fetch content from the URL."


def get_text_file_content(file_path: str) -> Optional[str]:
    """Read and returns the content of a text or markdown file."""
    try:
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        return "Error: The specified text file does not exist."
    except PermissionError:
        logger.error("Permission denied for file: %s", file_path)
        return "Error: Permission denied while accessing the text file."
    except Exception as e:
        logger.error("Error reading text file: %s", e)
        return "Error: Unable to fetch content from the text file due to an unexpected issue."


def get_pdf_file_content(file_path: str) -> Optional[str]:
    """Read and returns the text content from a PDF file."""
    try:
        pdf_text = []
        with open(file_path, "rb") as pdf_file:
            reader = PdfReader(pdf_file)
            for page in reader.pages:
                pdf_text.append(page.extract_text())
        return "\n".join(pdf_text)
    except FileNotFoundError:
        logger.error("File not found: %s", file_path)
        return "Error: The specified PDF file does not exist."
    except PermissionError:
        logger.error("Permission denied for file: %s", file_path)
        return "Error: Permission denied while accessing the PDF file."
    except Exception as e:
        logger.error("Error reading PDF file: %s", e)
        return "Error: Unable to fetch content from the PDF file due to an unexpected issue."


def extract_json_from_response(response_text: str) -> Dict[str, Any]:
    """Extract the JSON from the given response text."""
    try:
        json_pattern = r"\{.*\}"
        match = re.search(json_pattern, response_text, re.DOTALL)
        if match:
            json_text = match.group()
            return dict(json.loads(json_text))
        return {}
    except json.JSONDecodeError as e:
        logger.error("JSON decoding error: %s", e)
        return {}
    except Exception as e:
        logger.error("Error extracting JSON from response: %s", e)
        return {}


def get_license_details(
    license_name: str, licenses: List[Dict[str, Any]]
) -> Tuple[Optional[str], Optional[str], Optional[str]]:
    """Extract license details using license name."""
    try:
        license_name_lower = license_name.strip().lower()

        for license in licenses:
            license_url = f"{COMMON_LICENSE_MINIO_OBJECT_NAME}/{license['license_file']}"
            if license_name_lower in {license["license_id"].lower(), license["license_name"].lower()}:
                return license["license_id"], license["license_name"], license_url
            if any(license_name_lower == potential.lower() for potential in license.get("potential_names", [])):
                return license["license_id"], license["license_name"], license_url

        return None, None, None
    except Exception as e:
        print(f"Error: {str(e)}")
        return None, None, None


@lru_cache(maxsize=None)
def mapped_licenses(path: str = "seeders/licenses.json") -> Dict[str, Any]:
    """Extract mapped licenses from a JSON file with caching."""
    try:
        with open(path, "r", encoding="utf-8") as file:
            license_identifiers = json.load(file)
        return license_identifiers
    except FileNotFoundError as e:
        logger.error("File not found: %s", e)
        return {}
    except json.JSONDecodeError as e:
        logger.error("JSON decoding error in license file: %s", e)
        return {}
    except Exception as e:
        logger.error("Error reading license file: %s", e)
        return {}
