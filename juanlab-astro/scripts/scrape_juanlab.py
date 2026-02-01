#!/usr/bin/env python3
"""
Juan Lab DokuWiki Content Scraper
=================================
Extracts structured content from https://sbl.csie.org/JuanLab/doku.php
and saves as JSON for Astro migration.

Usage:
    python scrape_juanlab.py

Output:
    src/content/news.json
    src/content/people.json
    src/content/research.json
    src/content/projects.json
    src/content/pi.json
    src/content/images_manifest.json

Requirements:
    pip install requests beautifulsoup4 lxml
"""

import json
import re
import unicodedata
import time
from pathlib import Path
from datetime import datetime
from urllib.parse import urljoin, unquote, quote
from typing import Optional
import requests
from bs4 import BeautifulSoup, Tag

# ============================================================================
# Configuration
# ============================================================================

BASE_URL = "https://sbl.csie.org/JuanLab"
DOKU_URL = f"{BASE_URL}/doku.php"

OUTPUT_DIR = Path("src/content")
IMAGES_DIR = Path("public/images")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,zh-TW;q=0.8",
}

# Rate limiting
REQUEST_DELAY = 1.0  # seconds between requests

# ============================================================================
# Utility Functions
# ============================================================================

def clean_text(text: Optional[str]) -> str:
    """Normalize Unicode and clean whitespace."""
    if not text:
        return ""
    # Normalize Unicode (NFKC handles full-width characters, etc.)
    text = unicodedata.normalize("NFKC", text)
    # Replace multiple whitespace with single space
    text = re.sub(r'\s+', ' ', text)
    # Strip leading/trailing whitespace
    return text.strip()


def fetch_page(page_id: str, retries: int = 3) -> Optional[BeautifulSoup]:
    """
    Fetch and parse a DokuWiki page.
    
    Args:
        page_id: The DokuWiki page ID (e.g., "start", "members:start")
        retries: Number of retry attempts
        
    Returns:
        BeautifulSoup object or None if failed
    """
    url = f"{DOKU_URL}?id={quote(page_id, safe=':')}"
    
    for attempt in range(retries):
        try:
            print(f"  Fetching: {url}")
            response = requests.get(url, headers=HEADERS, timeout=30)
            response.raise_for_status()
            time.sleep(REQUEST_DELAY)
            return BeautifulSoup(response.text, "lxml")
        except requests.RequestException as e:
            print(f"    Attempt {attempt + 1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
    
    return None


def extract_image_urls(soup: BeautifulSoup) -> list[dict]:
    """Extract all image URLs from the page."""
    images = []
    
    for img in soup.find_all("img"):
        src = img.get("src", "")
        if "/lib/exe/fetch.php" in src or src.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp")):
            # Build full URL
            if not src.startswith("http"):
                src = urljoin(BASE_URL, src)
            
            # Extract filename from URL
            filename = ""
            if "media=" in src:
                filename = unquote(src.split("media=")[-1])
            else:
                filename = unquote(src.split("/")[-1].split("?")[0])
            
            images.append({
                "url": src,
                "filename": filename,
                "alt": img.get("alt", ""),
            })
    
    return images


def make_absolute_url(href: str) -> str:
    """Convert relative URL to absolute."""
    if not href:
        return ""
    if href.startswith("http"):
        return href
    return urljoin(BASE_URL + "/", href)


# ============================================================================
# Content Extractors
# ============================================================================

def extract_news(soup: BeautifulSoup) -> list[dict]:
    """
    Extract news items from the start page.
    
    News format in DokuWiki:
    * YY.MM Description text
    
    Returns list of news items with parsed dates and titles.
    """
    news_items = []
    
    # Find the content area
    content = soup.find("div", class_="dokuwiki") or soup.find("div", id="dokuwiki__content")
    if not content:
        print("    Warning: Could not find content area")
        return news_items
    
    # Pattern: YY.MM followed by text
    news_pattern = re.compile(r'^(\d{2})\.(\d{2})\s+(.+)$')
    
    # Find all list items
    for li in content.find_all("li"):
        text = clean_text(li.get_text())
        match = news_pattern.match(text)
        
        if match:
            year_short, month, title = match.groups()
            
            # Convert YY to YYYY
            year = int(year_short)
            year = 2000 + year if year < 50 else 1900 + year
            
            # Extract link if present
            link = None
            a_tag = li.find("a")
            if a_tag and a_tag.get("href"):
                link = make_absolute_url(a_tag["href"])
            
            # Detect category based on keywords
            category = "general"
            title_lower = title.lower()
            if any(kw in title_lower for kw in ["獎", "award", "榮獲", "得獎"]):
                category = "award"
            elif any(kw in title_lower for kw in ["發表", "paper", "publish", "journal"]):
                category = "publication"
            elif any(kw in title_lower for kw in ["徵", "recruit", "聘"]):
                category = "recruitment"
            
            news_items.append({
                "date": f"{year}-{month.zfill(2)}",
                "year": year,
                "month": int(month),
                "title": title,
                "link": link,
                "category": category,
            })
    
    # Sort by date (newest first)
    news_items.sort(key=lambda x: (x["year"], x["month"]), reverse=True)
    
    return news_items


def extract_research_highlights(soup: BeautifulSoup) -> list[dict]:
    """
    Extract research highlight sections from start page.
    
    Structure:
    - Section title (h1 or h2)
    - Image
    - Description paragraphs
    """
    highlights = []
    
    content = soup.find("div", class_="dokuwiki") or soup.find("div", id="dokuwiki__content")
    if not content:
        return highlights
    
    # Find Research Highlights section
    # Look for headers containing "Research Highlight"
    current_highlight = None
    
    for element in content.find_all(["h1", "h2", "h3", "p", "img", "a"]):
        text = clean_text(element.get_text()) if element.name != "img" else ""
        
        # Check for section headers
        if element.name in ["h1", "h2", "h3"]:
            if "Research Highlight" in text:
                continue  # This is the main section header
            
            # Check if this is a highlight sub-header
            if current_highlight is None and ("ATP" in text or "生醫大數據" in text or "Ectopic" in text or "Big Data" in text):
                if current_highlight:
                    highlights.append(current_highlight)
                
                current_highlight = {
                    "id": re.sub(r'[^a-z0-9]+', '-', text.lower()).strip('-'),
                    "title_zh": text if re.search(r'[\u4e00-\u9fff]', text) else "",
                    "title_en": text if not re.search(r'[\u4e00-\u9fff]', text) else "",
                    "description": [],
                    "image": None,
                    "publications": [],
                }
        
        # Collect images
        if element.name == "a" and element.find("img"):
            img = element.find("img")
            if img and current_highlight:
                src = img.get("src", "")
                if "highlight" in src.lower() or "research" in src.lower():
                    current_highlight["image"] = make_absolute_url(src)
        
        # Collect description paragraphs
        if element.name == "p" and current_highlight:
            para_text = clean_text(element.get_text())
            if para_text and len(para_text) > 50:  # Filter out short snippets
                current_highlight["description"].append(para_text)
    
    if current_highlight:
        highlights.append(current_highlight)
    
    return highlights


def extract_research_projects(soup: BeautifulSoup) -> list[dict]:
    """Extract current research projects from start page."""
    projects = []
    
    content = soup.find("div", class_="dokuwiki") or soup.find("div", id="dokuwiki__content")
    if not content:
        return projects
    
    # Pattern for numbered projects
    project_pattern = re.compile(r'^\*?\*?\s*(\d+)\.\s*(.+)$')
    
    in_projects_section = False
    
    for element in content.find_all(["h1", "h2", "h3", "p", "li"]):
        text = clean_text(element.get_text())
        
        if element.name in ["h1", "h2", "h3"]:
            if "Research Project" in text or "研究計畫" in text:
                in_projects_section = True
                continue
            elif in_projects_section and element.name in ["h1", "h2"]:
                # New major section, stop
                in_projects_section = False
        
        if in_projects_section:
            # Check for numbered list items
            match = project_pattern.match(text)
            if match:
                number, title = match.groups()
                
                # Try to split Chinese/English titles
                title_zh = ""
                title_en = ""
                
                # Check if there's a newline or clear separation
                if "\n" in element.get_text():
                    parts = element.get_text().strip().split("\n")
                    for part in parts:
                        part = clean_text(part)
                        if part and not part[0].isdigit():
                            if re.search(r'[\u4e00-\u9fff]', part):
                                title_zh = part
                            else:
                                title_en = part
                else:
                    # Single line - detect language
                    if re.search(r'[\u4e00-\u9fff]', title):
                        title_zh = title
                    else:
                        title_en = title
                
                projects.append({
                    "id": f"project-{number}",
                    "number": int(number),
                    "title_zh": title_zh,
                    "title_en": title_en,
                    "description": "",
                })
    
    return projects


def extract_people(soup: BeautifulSoup) -> dict:
    """
    Extract people information from members page.
    
    Returns dict with categories: phd_students, masters_students, undergrads, visiting, alumni
    """
    people = {
        "phd_students": [],
        "masters_students": [],
        "undergrads": [],
        "visiting": [],
        "alumni": [],
        "postdocs": [],
    }
    
    content = soup.find("div", class_="dokuwiki") or soup.find("div", id="dokuwiki__content")
    if not content:
        return people
    
    current_category = None
    
    # Category detection keywords
    category_keywords = {
        "phd": "phd_students",
        "ph.d": "phd_students",
        "博士": "phd_students",
        "doctoral": "phd_students",
        "master": "masters_students",
        "碩士": "masters_students",
        "ms student": "masters_students",
        "undergrad": "undergrads",
        "大專": "undergrads",
        "大學部": "undergrads",
        "visiting": "visiting",
        "exchange": "visiting",
        "訪問": "visiting",
        "alumni": "alumni",
        "畢業": "alumni",
        "former": "alumni",
        "postdoc": "postdocs",
        "博士後": "postdocs",
    }
    
    is_alumni_section = False
    
    # Flexible pattern: Name (Info) ...
    # Captures: Name, Info found in first parens
    member_pattern = re.compile(r'^([^\(]+?)\s*\(([^)]+)\)(.*)$')
    
    for element in content.find_all(["h1", "h2", "h3", "h4", "li", "p", "tr"]):
        text = clean_text(element.get_text())
        if not text:
            continue
            
        text_lower = text.lower()
        
        # Check for category headers
        if element.name in ["h1", "h2", "h3", "h4"]:
            # Check if entering Alumni section
            if "alumni" in text_lower:
                is_alumni_section = True
                current_category = "alumni"
                continue

            # Check if entering a section that might reset Alumni (e.g. Visiting if considered current)
            # But usually Alumni is at the end. 
            # If we hit a known category header:
            category_found = False
            for keyword, category in category_keywords.items():
                if keyword in text_lower:
                    category_found = True
                    # If we are in alumni section, standard roles map to alumni list
                    if is_alumni_section: 
                        if category in ["phd_students", "masters_students", "undergrads", "postdocs"]:
                            current_category = "alumni"
                        else:
                            # Visiting or others, keep as matches (e.g. visiting might be distinct)
                            current_category = category
                    else:
                        current_category = category
                    break
            
            # If header didn't match any category, we keep previous category or wait?
            # If it's just "Table of Contents" ignore.
        
        # Extract member info from list items or paragraphs/table rows
        if element.name in ["li", "p", "tr"] and current_category:
            # Skip if it's just a spacer or empty
            if not text or len(text) < 2:
                continue

            # Debug what we are seeing in current categories (excluding alumni to reduce noise)
            if current_category in ["phd_students", "masters_students", "postdocs"] and not is_alumni_section:
               print(f"DEBUG: Checking {element.name} in {current_category}: '{text[:50]}...'")

            # Try to parse member format
            match = member_pattern.match(text)
            if match:
                name_part = match.group(1).strip()
                info_part = match.group(2).strip()
                rest_part = match.group(3).strip()
                
                # Parse Year and Dept from info_part
                # Examples: "23- Med", "20-21 LS", "19-22 LS; BEBI ms"
                year_start = 2024 # Default
                dept = ""
                
                # Find first 2 digits
                year_match = re.search(r'(\d{2})', info_part)
                if year_match:
                    y_str = year_match.group(1)
                    year_val = int(y_str)
                    year_start = 2000 + year_val if year_val < 50 else 1900 + year_val
                    
                    # Remove year from info to find Dept?
                    # valid dept text usually follows year
                    # Simple heuristic: take everything after the year digits?
                    dept = info_part.replace(y_str, "", 1).strip(" -;,")
                else:
                    dept = info_part # No year found

                # Split Chinese and English names
                name_parts = name_part.split()
                name_zh = ""
                name_en = ""
                
                for part in name_parts:
                    if re.search(r'[\u4e00-\u9fff]', part):
                        name_zh = part
                    else:
                        name_en = (name_en + " " + part).strip()
                
                # Parse research areas (from rest_part)
                research_areas = [r.strip() for r in rest_part.split(",") if r.strip()]
                
                # Extract photo if present
                img = element.find("img")
                photo_url = None
                if img:
                    photo_url = make_absolute_url(img.get("src", ""))
                
                # Extract email if present
                email = None
                email_link = element.find("a", href=re.compile(r'^mailto:'))
                if email_link:
                    email = email_link.get("href", "").replace("mailto:", "")
                
                member = {
                    "name_zh": name_zh,
                    "name_en": name_en,
                    "year_start": year_start,
                    "department": dept,
                    "research": research_areas,
                    "photo": photo_url,
                    "email": email,
                }
                
                people[current_category].append(member)
            else:
                # Fallback: if no parens, might be just "Name" or "Name, Info"
                # Check if it looks like a person entry (not empty)
                text_clean = text.strip()
                if len(text_clean) > 1 and len(text_clean) < 50:
                    print(f"DEBUG: Unmatched LI: '{text}' -> using as Name")
                    # Assume entire text is name? Or format: "Name Title"
                    # Just use as name for now
                    
                    # Check if there are years in the text?
                    year_start = 2024
                    dept = ""
                    name = text_clean
                    
                    # Try to find year if any
                    year_match = re.search(r'(\d{4})', text_clean)
                    if not year_match:
                         # Try 2 digits
                         year_match = re.search(r'\b(\d{2})\b', text_clean) # word boundary
                    
                    if year_match:
                        # If year found, maybe extract it?
                        pass 
                        
                    member = {
                        "name_zh": name if re.search(r'[\u4e00-\u9fff]', name) else "",
                        "name_en": name if not re.search(r'[\u4e00-\u9fff]', name) else "",
                        "year_start": year_start,
                        "department": "",
                        "research": [],
                        "photo": None,
                        "email": None,
                    }
                    
                    # Try to find photo in this LI even if text didn't match
                    img = element.find("img")
                    if img:
                        member["photo"] = make_absolute_url(img.get("src", ""))
                        
                    people[current_category].append(member)
                else:
                    print(f"DEBUG: Skipping LI: '{text}'")

    return people


def extract_pi_info(soup: BeautifulSoup) -> dict:
    """Extract PI (Principal Investigator) information."""
    pi = {
        "name_zh": "阮雪芬",
        "name_en": "Hsueh-Fen Juan",
        "title": "Distinguished Professor",
        "department": "Department of Life Science",
        "institution": "National Taiwan University",
        "email": "yukijuan@ntu.edu.tw",
        "email2": "yukijuan@gmail.com",
        "phone": "+886-2-3366-4536",
        "fax": "+886-2-2367-3374",
        "address": "Rm. 1105, Life Science Building, National Taiwan University, No. 1 Sec. 4 Roosevelt Road, Taipei 106, Taiwan",
        "photo": None,
        "bio": "",
        "education": [],
        "positions": [],
        "awards": [],
        "societies": [],
    }
    
    content = soup.find("div", class_="dokuwiki") or soup.find("div", id="dokuwiki__content")
    if not content:
        return pi
    
    # Extract photo
    for img in content.find_all("img"):
        src = img.get("src", "")
        if "juan" in src.lower() or "pi" in src.lower():
            pi["photo"] = make_absolute_url(src)
            break
    
    # Extract bio text (first few paragraphs)
    paragraphs = []
    for p in content.find_all("p"):
        text = clean_text(p.get_text())
        if len(text) > 100:  # Filter out short snippets
            paragraphs.append(text)
    
    if paragraphs:
        pi["bio"] = "\n\n".join(paragraphs[:3])  # First 3 substantial paragraphs
    
    # Look for structured lists (education, positions, awards)
    current_section = None
    section_keywords = {
        "education": "education",
        "學歷": "education",
        "position": "positions",
        "經歷": "positions",
        "award": "awards",
        "榮譽": "awards",
        "honor": "awards",
        "society": "societies",
        "學會": "societies",
    }
    
    for element in content.find_all(["h2", "h3", "h4", "li"]):
        text = clean_text(element.get_text())
        text_lower = text.lower()
        
        if element.name in ["h2", "h3", "h4"]:
            for keyword, section in section_keywords.items():
                if keyword in text_lower:
                    current_section = section
                    break
        
        if element.name == "li" and current_section and text:
            pi[current_section].append(text)
    
    return pi


# ============================================================================
# Main Extraction Pipeline
# ============================================================================

def main():
    """Run the full extraction pipeline."""
    print("=" * 60)
    print("Juan Lab DokuWiki Content Scraper")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Output: {OUTPUT_DIR}")
    print()
    
    # Create output directory
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    all_images = []
    
    # -------------------------------------------------------------------------
    # 1. Extract from start page (Home)
    # -------------------------------------------------------------------------
    print("[1/4] Fetching start page...")
    start_soup = fetch_page("start")
    
    if start_soup:
        # News
        print("  Extracting news...")
        news = extract_news(start_soup)
        print(f"    Found {len(news)} news items")
        with open(OUTPUT_DIR / "news.json", "w", encoding="utf-8") as f:
            json.dump(news, f, ensure_ascii=False, indent=2)
        
        # Research highlights
        print("  Extracting research highlights...")
        highlights = extract_research_highlights(start_soup)
        print(f"    Found {len(highlights)} highlights")
        with open(OUTPUT_DIR / "research.json", "w", encoding="utf-8") as f:
            json.dump(highlights, f, ensure_ascii=False, indent=2)
        
        # Research projects
        print("  Extracting research projects...")
        projects = extract_research_projects(start_soup)
        print(f"    Found {len(projects)} projects")
        with open(OUTPUT_DIR / "projects.json", "w", encoding="utf-8") as f:
            json.dump(projects, f, ensure_ascii=False, indent=2)
        
        # Images
        print("  Extracting image URLs...")
        images = extract_image_urls(start_soup)
        all_images.extend(images)
        print(f"    Found {len(images)} images")
    else:
        print("  ERROR: Could not fetch start page")
    
    # -------------------------------------------------------------------------
    # 2. Extract from members page
    # -------------------------------------------------------------------------
    print("\n[2/4] Fetching members page...")
    members_soup = fetch_page("members:start")
    
    if members_soup:
        print("  Extracting people...")
        people = extract_people(members_soup)
        
        total_people = sum(len(v) for v in people.values())
        print(f"    Found {total_people} people total:")
        for category, members in people.items():
            if members:
                print(f"      - {category}: {len(members)}")
        
        with open(OUTPUT_DIR / "people.json", "w", encoding="utf-8") as f:
            json.dump(people, f, ensure_ascii=False, indent=2)
        
        # Images
        images = extract_image_urls(members_soup)
        all_images.extend(images)
        print(f"    Found {len(images)} images")
    else:
        print("  WARNING: Could not fetch members page")
        # Create empty people.json
        with open(OUTPUT_DIR / "people.json", "w", encoding="utf-8") as f:
            json.dump({
                "phd_students": [],
                "masters_students": [],
                "undergrads": [],
                "visiting": [],
                "alumni": [],
                "postdocs": [],
            }, f, ensure_ascii=False, indent=2)
    
    # -------------------------------------------------------------------------
    # 3. Extract PI information
    # -------------------------------------------------------------------------
    print("\n[3/4] Fetching PI page...")
    pi_soup = fetch_page("PI:Hsueh-Fen Juan")
    
    if pi_soup:
        print("  Extracting PI information...")
        pi = extract_pi_info(pi_soup)
        with open(OUTPUT_DIR / "pi.json", "w", encoding="utf-8") as f:
            json.dump(pi, f, ensure_ascii=False, indent=2)
        
        # Images
        images = extract_image_urls(pi_soup)
        all_images.extend(images)
        print(f"    Found {len(images)} images")
    else:
        print("  WARNING: Could not fetch PI page")
    
    # -------------------------------------------------------------------------
    # 4. Save images manifest
    # -------------------------------------------------------------------------
    print("\n[4/4] Creating images manifest...")
    
    # Deduplicate images
    seen_urls = set()
    unique_images = []
    for img in all_images:
        if img["url"] not in seen_urls:
            seen_urls.add(img["url"])
            unique_images.append(img)
    
    print(f"  Total unique images: {len(unique_images)}")
    
    with open(OUTPUT_DIR / "images_manifest.json", "w", encoding="utf-8") as f:
        json.dump(unique_images, f, ensure_ascii=False, indent=2)
    
    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print("\n" + "=" * 60)
    print("Extraction Complete!")
    print("=" * 60)
    print(f"\nOutput files:")
    for f in OUTPUT_DIR.glob("*.json"):
        size = f.stat().st_size
        print(f"  - {f.name} ({size:,} bytes)")
    
    print(f"\nNext steps:")
    print(f"  1. Review JSON files in {OUTPUT_DIR}")
    print(f"  2. Run download_images.py to fetch images")
    print(f"  3. Build Astro site with 'npm run dev'")


if __name__ == "__main__":
    main()
