#!/usr/bin/env python3
"""
Juan Lab Image Downloader
=========================
Downloads images from the images manifest and organizes them.

Usage:
    python download_images.py

Input:
    src/content/images_manifest.json

Output:
    public/images/
        ├── people/
        ├── research/
        ├── gallery/
        └── covers/

Requirements:
    pip install requests Pillow
"""

import json
import re
import time
from pathlib import Path
from urllib.parse import unquote
import requests
from PIL import Image
from io import BytesIO

# ============================================================================
# Configuration
# ============================================================================

MANIFEST_PATH = Path("src/content/images_manifest.json")
OUTPUT_DIR = Path("public/images")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "image/avif,image/webp,image/apng,image/svg+xml,image/*,*/*;q=0.8",
}

REQUEST_DELAY = 0.5  # seconds between requests

# Image category detection
CATEGORY_PATTERNS = {
    "people": [r"member", r"student", r"alumni", r"pi", r"photo", r"portrait"],
    "research": [r"highlight", r"research", r"figure", r"diagram"],
    "covers": [r"cover", r"banner", r"hero"],
    "gallery": [r"lab", r"group", r"event", r"阮雪芬"],
}

# ============================================================================
# Functions
# ============================================================================

def detect_category(filename: str, url: str) -> str:
    """Detect image category based on filename/URL patterns."""
    combined = (filename + " " + url).lower()
    
    for category, patterns in CATEGORY_PATTERNS.items():
        for pattern in patterns:
            if re.search(pattern, combined):
                return category
    
    return "misc"


def sanitize_filename(filename: str) -> str:
    """Create a clean, safe filename."""
    # Decode URL encoding
    filename = unquote(filename)
    
    # Remove path components
    filename = filename.split("/")[-1]
    
    # Remove query parameters
    filename = filename.split("?")[0]
    
    # Replace problematic characters
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    
    # Ensure it has an extension
    if not re.search(r'\.(jpg|jpeg|png|gif|webp|svg)$', filename.lower()):
        filename += ".png"
    
    return filename


def download_image(url: str, output_path: Path, create_webp: bool = True) -> bool:
    """
    Download an image and optionally create WebP version.
    
    Returns True if successful.
    """
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Verify it's actually an image
        content_type = response.headers.get("content-type", "")
        if not content_type.startswith("image/"):
            print(f"    Warning: Not an image ({content_type})")
            return False
        
        # Save original
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        # Create WebP version for jpg/png
        if create_webp and output_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            try:
                img = Image.open(BytesIO(response.content))
                
                # Convert RGBA to RGB for JPG compatibility
                if img.mode == "RGBA":
                    img = img.convert("RGB")
                
                webp_path = output_path.with_suffix(".webp")
                img.save(webp_path, "WEBP", quality=85, method=6)
            except Exception as e:
                print(f"    Warning: Could not create WebP: {e}")
        
        return True
        
    except requests.RequestException as e:
        print(f"    Error downloading: {e}")
        return False


def main():
    """Run the image download pipeline."""
    print("=" * 60)
    print("Juan Lab Image Downloader")
    print("=" * 60)
    
    # Load manifest
    if not MANIFEST_PATH.exists():
        print(f"Error: Manifest not found at {MANIFEST_PATH}")
        print("Run scrape_juanlab.py first to generate the manifest.")
        return
    
    with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
        images = json.load(f)
    
    print(f"Found {len(images)} images in manifest")
    print()
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    # Track statistics
    stats = {
        "downloaded": 0,
        "skipped": 0,
        "failed": 0,
    }
    
    # Download each image
    for i, img in enumerate(images, 1):
        url = img["url"]
        original_filename = img.get("filename", "")
        
        # Determine category and filename
        category = detect_category(original_filename, url)
        filename = sanitize_filename(original_filename) if original_filename else f"image_{i}.png"
        
        output_path = OUTPUT_DIR / category / filename
        
        # Skip if already exists
        if output_path.exists():
            print(f"[{i}/{len(images)}] Skipping (exists): {filename}")
            stats["skipped"] += 1
            continue
        
        print(f"[{i}/{len(images)}] Downloading: {filename} -> {category}/")
        
        if download_image(url, output_path):
            stats["downloaded"] += 1
        else:
            stats["failed"] += 1
        
        time.sleep(REQUEST_DELAY)
    
    # Summary
    print("\n" + "=" * 60)
    print("Download Complete!")
    print("=" * 60)
    print(f"\nStatistics:")
    print(f"  - Downloaded: {stats['downloaded']}")
    print(f"  - Skipped (existing): {stats['skipped']}")
    print(f"  - Failed: {stats['failed']}")
    
    print(f"\nFiles by category:")
    for category_dir in OUTPUT_DIR.iterdir():
        if category_dir.is_dir():
            count = len(list(category_dir.glob("*")))
            print(f"  - {category_dir.name}: {count} files")


if __name__ == "__main__":
    main()
