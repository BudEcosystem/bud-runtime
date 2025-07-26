#!/usr/bin/env python3
# /// script
# dependencies = [
#   "requests",
# ]
# ///

import concurrent.futures
import hashlib
import os
from pathlib import Path

import requests

# cd to directory of this file
os.chdir(os.path.dirname(os.path.abspath(__file__)))

# Constants
PART_SIZE = 8388608
FIXTURES = [
    "large_chat_inference_v2.parquet",
    "large_chat_model_inference_v2.parquet",
    "large_json_inference_v2.parquet",
    "large_json_model_inference_v2.parquet",
    "large_chat_boolean_feedback.parquet",
    "large_chat_float_feedback.parquet",
    "large_chat_comment_feedback.parquet",
    "large_chat_demonstration_feedback.parquet",
    "large_json_boolean_feedback.parquet",
    "large_json_float_feedback.parquet",
    "large_json_comment_feedback.parquet",
    "large_json_demonstration_feedback.parquet",
]
R2_BUCKET = "https://pub-147e9850a60643208c411e70b636e956.r2.dev"
S3_FIXTURES_DIR = Path("./s3-fixtures")


def calculate_etag(file_path):
    """Calculate S3/R2 style ETag for a file."""
    file_size = os.path.getsize(file_path)
    num_parts = (file_size + PART_SIZE - 1) // PART_SIZE

    if num_parts == 1:
        # Single part upload - just MD5 of the file
        with open(file_path, "rb") as f:
            return hashlib.md5(f.read()).hexdigest()
    else:
        # Multipart upload - concatenate MD5s of each part
        md5s = []
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(PART_SIZE)
                if not chunk:
                    break
                md5s.append(hashlib.md5(chunk).digest())

        # Calculate MD5 of concatenated part MD5s
        combined_md5 = hashlib.md5(b"".join(md5s)).hexdigest()
        return f"{combined_md5}-{num_parts}"


def get_remote_etag(filename):
    """Get ETag from R2 bucket."""
    try:
        response = requests.head(f"{R2_BUCKET}/{filename}", timeout=30)
        response.raise_for_status()
        return response.headers.get("ETag", "").strip('"')
    except requests.RequestException as e:
        print(f"Failed to get remote ETag for {filename}: {e}")
        raise


def download_file(filename, remote_etag):
    """Download file from R2 bucket."""
    url = f"{R2_BUCKET}/{filename}"
    try:
        response = requests.get(url, stream=True, timeout=300)
        response.raise_for_status()

        local_file = S3_FIXTURES_DIR / filename
        print(f"  Downloading {filename}...")

        with open(local_file, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)

        print(f"  Verifying {filename}...")
        local_etag = calculate_etag(local_file)
        if local_etag != remote_etag:
            local_file.unlink()  # Remove corrupted file
            raise Exception(
                f"ETag mismatch after downloading: {local_etag} != {remote_etag}"
            )
        print(f"  ✓ {filename} downloaded and verified successfully")
    except requests.RequestException as e:
        print(f"Failed to download {filename}: {e}")
        raise
    except Exception as e:
        print(f"Error processing {filename}: {e}")
        raise


def main():
    print("Starting fixture download process...")

    # Create s3-fixtures directory if it doesn't exist
    S3_FIXTURES_DIR.mkdir(exist_ok=True)

    def process_fixture(fixture):
        try:
            local_file = S3_FIXTURES_DIR / fixture
            print(f"Processing {fixture}...")
            remote_etag = get_remote_etag(fixture)

            if not local_file.exists():
                print(f"Downloading {fixture} (file doesn't exist locally)")
                download_file(fixture, remote_etag)
                return True

            local_etag = calculate_etag(local_file)

            if local_etag != remote_etag:
                print(f"Downloading {fixture} (ETag mismatch)")
                print(f"Local ETag: {local_etag}")
                print(f"Remote ETag: {remote_etag}")
                download_file(fixture, remote_etag)
                return True
            else:
                print(f"Skipping {fixture} (up to date)")
                return True
        except Exception as e:
            print(f"Error processing {fixture}: {e}")
            return False

    # Use ThreadPoolExecutor to download files in parallel
    print(f"Processing {len(FIXTURES)} fixture files...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(process_fixture, FIXTURES))

    success_count = sum(results)
    print(f"\nCompleted: {success_count}/{len(FIXTURES)} files processed successfully")

    if success_count < len(FIXTURES):
        print("Some fixtures failed to download!")
        exit(1)
    else:
        print("All fixtures processed successfully!")
        exit(0)


if __name__ == "__main__":
    main()
