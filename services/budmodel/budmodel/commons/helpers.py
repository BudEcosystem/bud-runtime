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

"""Helper functions for the application."""

import logging
import os
import re
import shutil
import time
import unicodedata
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse

import requests


logger = logging.getLogger(__name__)


def sanitize_name(name: str, is_directory: bool = True, max_length: int = 20, default_name: str = "unnamed") -> str:
    """Sanitize a name to remove special characters and limit its length.

    Args:
        name: The name to sanitize.
        is_directory: Whether the name is a directory or a file.
        max_length: The maximum length of the sanitized name.
        default_name: The default name to use if the sanitization results in an empty string.

    Returns:
        The sanitized name.
    """
    if max_length < 1:
        raise ValueError("max_length must be greater than 0")

    _DIR_PATTERN = re.compile(r"[^a-zA-Z0-9_-]")
    _FILE_PATTERN = re.compile(r"[^a-zA-Z0-9._-]")
    pattern = _DIR_PATTERN if is_directory else _FILE_PATTERN

    # Convert unicode to ASCII
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ASCII", "ignore").decode("ASCII")

    safe_name = pattern.sub("_", ascii_name).strip("._")

    # Convert to lowercase
    safe_name = safe_name.lower()

    # Use default name if sanitization resulted in empty string
    if not safe_name:
        safe_name = default_name

    return safe_name[:max_length]


def generate_unique_name(base_name: str, use_timestamp: bool = False) -> str:
    """Generate a unique name by adding a timestamp or UUID.

    Args:
        base_name: The base name to make unique
        use_timestamp: If True, uses timestamp; if False, uses UUID

    Returns:
        A unique name string
    """
    if use_timestamp:
        # Format: base_name_YYYYMMDD_HHMMSS
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        unique_name = f"{base_name}_{timestamp}"
    else:
        # Format: base_name_uuid4-first-8-chars
        unique_id = str(uuid.uuid4())[:8]
        unique_name = f"{base_name}_{unique_id}"

    return unique_name


def safe_delete(path: str) -> bool:
    """Safely delete a file or directory.

    Args:
        path (str): The path to the file or directory to delete.

    Returns:
        bool: True if the path doesn't exist or deletion was successful, False if deletion failed.
    """
    if not os.path.exists(path):
        logger.debug("Path does not exist: %s", path)
        return True

    try:
        if os.path.isdir(path):
            shutil.rmtree(path)
            logger.info("Deleted directory: %s", path)
        else:
            os.remove(path)
            logger.info("Deleted file: %s", path)
        return True
    except PermissionError:
        logger.error("Permission denied for %s", path)
        return False
    except OSError as e:
        logger.error("OS error deleting %s: %s", path, e)
        return False
    except Exception as e:
        logger.exception("Unexpected error deleting %s: %s", path, e)
        return False


def is_zip_url(url: str) -> bool:
    """Check if a given URL refers to a zip file."""
    # Check Content-Type header
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        content_type = response.headers.get("Content-Type", "").lower()
        if "zip" in content_type:
            return True
    except Exception as e:
        logger.error("Error checking if URL is a zip file: %s", str(e))

    # Check if URL ends with ".zip"
    if url.lower().endswith(".zip"):
        return True

    # Check if URL path (excluding query parameters) contains ".zip"
    parsed_url = urlparse(url)

    return ".zip" in parsed_url.path.lower()


def is_zip_file(path: str) -> bool:
    """Check if a given file path or name refers to a zip file."""
    return path.lower().endswith(".zip")


def estimate_download_speed(url: str, chunk_size=1024, test_duration=2) -> float:
    """Estimate download speed in bytes per second from HuggingFace."""
    try:
        response = requests.get(url, stream=True)
        response.raise_for_status()

        start_time = time.time()
        total_bytes = 0

        # Measure download speed for a few seconds
        for chunk in response.iter_content(chunk_size=chunk_size):
            total_bytes += len(chunk)
            elapsed_time = time.time() - start_time
            if elapsed_time > test_duration:
                break

        # Calculate speed
        speed_bps = total_bytes / elapsed_time

        return speed_bps

    except requests.exceptions.RequestException as e:
        logger.error("Error estimating download speed: %s", e)
        return 0


def get_remote_file_size(url):
    """Get the file size in bytes from a URL using HEAD request.

    Args:
        url (str): URL of the file

    Returns:
        int: File size in bytes, or None if size cannot be determined
    """
    try:
        response = requests.head(url, allow_redirects=True)
        response.raise_for_status()

        # Try to get Content-Length header
        content_length = response.headers.get("content-length")
        if content_length:
            return int(content_length)

        # If no Content-Length header, try Range header
        response = requests.get(url, stream=True, headers={"Range": "bytes=0-0"})
        content_range = response.headers.get("content-range")
        if content_range:
            size = content_range.split("/")[-1]
            if size.isdigit():
                return int(size)

        return None

    except requests.exceptions.RequestException as e:
        logger.error("Error determining file size: %s", e)
        return None
    except Exception as e:
        logger.error("Error determining file size: %s", e)
        return None


def get_size_in_bytes(path_or_string) -> int:
    """Get size in bytes for a file or directory.

    Args:
        path_or_string: String path or Path object

    Returns:
        int: Total size in bytes

    Raises:
        FileNotFoundError: If path doesn't exist
        PermissionError: If access is denied
    """
    try:
        # Convert to Path object if string
        path = Path(path_or_string)

        # Check if path exists
        if not path.exists():
            raise FileNotFoundError(f"Path does not exist: {path}")

        # If it's a file, return its size
        if path.is_file():
            return path.stat().st_size

        # If it's a directory, calculate total size
        if path.is_dir():
            total_size = 0
            for dirpath, _, filenames in os.walk(path):
                # Add size of all files in current directory
                for filename in filenames:
                    file_path = Path(dirpath) / filename
                    try:
                        total_size += file_path.stat().st_size
                    except (PermissionError, FileNotFoundError):
                        continue
            return total_size
    except PermissionError:
        logger.error("Permission denied accessing path: %s", path)
        return 0
    except Exception as e:
        logger.error("Error calculating size: %s", e)
        return 0


def measure_transfer_speed(file_size_mb=100):
    """Measure file transfer speed in bytes per second."""
    file_size_bytes = file_size_mb * 1024 * 1024  # Convert MB to Bytes
    data = os.urandom(1024 * 1024)  # 1MB of random data
    source_file = "source_test_file"
    dest_file = "dest_test_file"

    # Create the source file
    with open(source_file, "wb") as f:
        for _ in range(file_size_mb):
            f.write(data)
            f.flush()
            os.fsync(f.fileno())

    # Measure transfer speed
    start_time = time.time()
    shutil.copy2(source_file, dest_file)  # copy2 preserves metadata
    end_time = time.time()

    # Calculate transfer speed in bytes per second
    elapsed_time = end_time - start_time
    transfer_speed_bps = file_size_bytes / elapsed_time if elapsed_time > 0 else float("inf")

    # Cleanup
    try:
        os.remove(source_file)
        os.remove(dest_file)
    except OSError:
        pass

    return transfer_speed_bps


def list_directory_files(directory: str) -> Tuple[List[Dict], int]:
    """List all files in a directory with their sizes (cross-platform compatible).

    Args:
        directory (str): Path to the directory

    Returns:
        Tuple[List[Dict], int]: Tuple containing:
            - List of dictionaries with file information
            - Total size in bytes
    """
    try:
        dir_path = Path(directory).resolve()
        if not dir_path.exists() or not dir_path.is_dir():
            raise ValueError(f"Invalid directory path: {directory}")

        file_info = []
        total_size = 0

        relative_dir = Path(dir_path).parent
        # Walk through directory using os.walk (more reliable cross-platform)
        for root, _, files in os.walk(dir_path):
            for index, filename in enumerate(sorted(files), start=len(file_info) + 1):
                try:
                    # identify relative path
                    relative_path = Path(root).relative_to(relative_dir)
                    file_path = Path(root) / filename
                    size = file_path.stat().st_size
                    file_info.append(
                        {"index": index, "filename": file_path.name, "path": str(relative_path), "size_bytes": size}
                    )
                    total_size += size
                except (PermissionError, OSError) as e:
                    logger.warning(f"Could not access file {file_path}: {e}")
                    continue

        return file_info, total_size

    except Exception as e:
        logger.error("Error listing directory files: %s", e)
        return [], 0


def extract_json_from_string(text):
    """Extract text between <json> and </json> tags from a string.

    Excluding the tags themselves.

    Args:
        text (str): The input string to search in

    Returns:
        str or None: The extracted JSON string if found, None otherwise
    """
    if not text or not isinstance(text, str):
        return None

    # Find the start and end positions of the JSON tags
    start_tag = "<json>"
    end_tag = "</json>"

    start_pos = text.find(start_tag)
    if start_pos == -1:
        return None  # Start tag not found

    # Calculate the position after the start tag
    start_pos += len(start_tag)  # This correctly positions after the tag

    end_pos = text.find(end_tag, start_pos)
    if end_pos == -1:
        return None  # End tag not found

    # Extract the text between the tags (excluding the tags)
    json_text = text[start_pos:end_pos].strip()

    return json_text
