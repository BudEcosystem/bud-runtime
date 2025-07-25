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
                part = f.read(PART_SIZE)
                if not part:
                    break
                md5s.append(hashlib.md5(part).hexdigest())
        
        # Concatenate and hash
        combined = "".join(md5s)
        final_hash = hashlib.md5(combined.encode()).hexdigest()
        return f"{final_hash}-{len(md5s)}"


def download_file(filename):
    """Download a single fixture file if it doesn't exist or has wrong checksum."""
    local_path = S3_FIXTURES_DIR / filename
    remote_url = f"{R2_BUCKET}/{filename}"
    
    print(f"Checking {filename}...")
    
    # Get remote ETag
    try:
        head_response = requests.head(remote_url, timeout=10)
        head_response.raise_for_status()
        remote_etag = head_response.headers.get("etag", "").strip('"')
    except requests.RequestException as e:
        print(f"Failed to get remote info for {filename}: {e}")
        return False
    
    # Check if local file exists and has correct checksum
    if local_path.exists():
        local_etag = calculate_etag(local_path)
        if local_etag == remote_etag:
            print(f"✓ {filename} is up to date")
            return True
        else:
            print(f"✗ {filename} checksum mismatch (local: {local_etag}, remote: {remote_etag})")
    else:
        print(f"- {filename} doesn't exist locally")
    
    # Download the file
    try:
        print(f"Downloading {filename}...")
        response = requests.get(remote_url, timeout=60)
        response.raise_for_status()
        
        # Ensure directory exists
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write file
        with open(local_path, "wb") as f:
            f.write(response.content)
        
        # Verify checksum
        local_etag = calculate_etag(local_path)
        if local_etag == remote_etag:
            print(f"✓ Successfully downloaded {filename}")
            return True
        else:
            print(f"✗ Checksum verification failed for {filename}")
            local_path.unlink()  # Remove corrupted file
            return False
            
    except requests.RequestException as e:
        print(f"Failed to download {filename}: {e}")
        return False


def main():
    """Download all fixture files."""
    print("Downloading ClickHouse test fixtures...")
    
    # Create fixtures directory if it doesn't exist
    S3_FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    
    # Download files in parallel
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(download_file, filename): filename for filename in FIXTURES}
        
        success_count = 0
        for future in concurrent.futures.as_completed(futures):
            filename = futures[future]
            try:
                if future.result():
                    success_count += 1
            except Exception as e:
                print(f"Exception downloading {filename}: {e}")
    
    print(f"\nDownload complete: {success_count}/{len(FIXTURES)} files successful")
    
    if success_count == len(FIXTURES):
        print("All fixtures downloaded successfully!")
        return 0
    else:
        print("Some fixtures failed to download!")
        return 1


if __name__ == "__main__":
    exit(main())