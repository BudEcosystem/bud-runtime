"""Download model author/organization icons from HuggingFace.

Usage:
    python -m scripts.download_model_author_icons meta-llama/Llama-2-7b mistralai/Mistral-7B
"""

import logging
import sys
import time
from pathlib import Path
from typing import Optional

import requests
from lxml import html


logger = logging.getLogger(__name__)

ICONS_DIR = Path(__file__).resolve().parent.parent / "static" / "icons" / "providers"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/91.0.4472.124 Safari/537.36"
    )
}


def scrape_hf_logo(model_id: str) -> Optional[str]:
    """Scrape the HuggingFace organization page to extract the logo URL.

    Args:
        model_id: HuggingFace model identifier (e.g. "mistralai/Mistral-7B").

    Returns:
        Absolute URL to the logo image if found, else None.
    """
    org_name = model_id.split("/")[0] if "/" in model_id else model_id
    full_url = f"https://huggingface.co/{org_name}"

    try:
        time.sleep(1)  # gentle delay to avoid rate-limiting
        response = requests.get(full_url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        tree = html.fromstring(response.content)

        xpath_sel = "//main/header//img[@alt and (contains(@class,'rounded') or contains(@class,'avatar'))]"
        img_elems = tree.xpath(xpath_sel)

        if not img_elems:
            img_elems = tree.cssselect("header img")

        if img_elems:
            img_url = img_elems[0].get("src")
            if img_url and img_url.startswith("/"):
                img_url = f"https://huggingface.co{img_url}"
            return img_url
        return None
    except Exception as e:
        logger.warning("Failed to scrape logo for %s: %s", org_name, e)
        return None


def save_logo(model_id: str, logo_url: str, output_dir: Path) -> Optional[Path]:
    """Download a logo and save it locally.

    Args:
        model_id: HuggingFace model identifier.
        logo_url: URL of the logo image.
        output_dir: Directory to save the icon into.

    Returns:
        Path to the saved file, or None on failure.
    """
    try:
        resp = requests.get(logo_url, stream=True, timeout=10)
        resp.raise_for_status()

        ext = Path(logo_url).suffix or ".png"
        safe_name = model_id.replace("/", "_") + ext
        local_path = output_dir / safe_name

        with open(local_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        return local_path
    except Exception as e:
        logger.warning("Unable to download logo for %s: %s", model_id, e)
        return None


def download_icons(model_ids: list[str], output_dir: Path = ICONS_DIR) -> None:
    """Download author icons for a list of HuggingFace model IDs."""
    output_dir.mkdir(parents=True, exist_ok=True)

    for model_id in model_ids:
        org = model_id.split("/")[0] if "/" in model_id else model_id
        print(f"[{org}] Scraping logo URL...")

        logo_url = scrape_hf_logo(model_id)
        if not logo_url:
            print(f"[{org}] No logo found, skipping.")
            continue

        print(f"[{org}] Downloading {logo_url}")
        saved = save_logo(model_id, logo_url, output_dir)
        if saved:
            print(f"[{org}] Saved to {saved}")
        else:
            print(f"[{org}] Download failed.")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__.strip())
        sys.exit(1)

    logging.basicConfig(level=logging.WARNING)
    download_icons(sys.argv[1:])
