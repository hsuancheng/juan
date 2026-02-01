---
name: migrate_juanlab_dokuwiki_to_astro
description: Complete guide for migrating Juan's Systems Biology Laboratory DokuWiki site to a modern Astro application with QIQB-inspired premium design, bilingual support, and academic lab-specific components.
version: 2.0
target_site: https://sbl.csie.org/JuanLab/doku.php
design_reference: https://qiqb.osaka-u.ac.jp/
---

# Migrate Juan Lab DokuWiki to Astro

This skill provides a comprehensive workflow for migrating Juan's Systems Biology Laboratory website from DokuWiki to a modern, high-performance [Astro](https://astro.build/) application with QIQB-inspired design aesthetics.

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Content Inventory](#content-inventory)
3. [Project Initialization](#1-project-initialization)
4. [Content Migration (ETL)](#2-content-migration-etl-pipeline)
5. [Image Asset Migration](#3-image-asset-migration)
6. [Component Architecture](#4-component-architecture)
7. [QIQB-Inspired Design System](#5-qiqb-inspired-design-system)
8. [Internationalization (i18n)](#6-internationalization-i18n)
9. [SEO & Performance](#7-seo--performance-optimization)
10. [Deployment](#8-deployment-to-github-pages)
11. [Best Practices](#best-practices)

---

## Prerequisites

### Required Tools
- **Node.js** v18+ and npm/pnpm
- **Python 3.9+** with virtual environment
- **Git** for version control

### Python Dependencies
```bash
pip install requests beautifulsoup4 lxml Pillow
```

### Astro Dependencies (installed during init)
```bash
npm install @astrojs/sitemap astro-icon
```

---

## Content Inventory

### Juan Lab Site Structure

| Page | DokuWiki Path | Content Type | Priority |
|------|---------------|--------------|----------|
| Home | `doku.php?id=start` | Hero, News, Research Highlights, Projects | High |
| About PI | `doku.php?id=PI:Hsueh-Fen%20Juan` | Biography, Awards, Positions | High |
| Publications | `doku.php?id=PUBLICATION:Juan` | Citation list with links | High |
| Members | `doku.php?id=members:start` | People grid (PhD, MS, Alumni, etc.) | High |
| Join Us | `doku.php?id=join_us` | Contact info, Recruitment | Medium |

### Content Types to Extract

1. **News Items** (2008-2025): ~100+ entries with dates, titles (ZH/EN mixed), links
2. **People**: Current members, alumni, visiting students with photos
3. **Research Highlights**: 2 major sections with images and detailed descriptions
4. **Research Projects**: 3 current projects
5. **Lab Photos**: Gallery images
6. **PI Information**: Biography, awards, positions, photo

---

## 1. Project Initialization

### Create Astro Project

```bash
# Create new project
npm create astro@latest juanlab-astro -- --template minimal --typescript strict

cd juanlab-astro

# Install integrations
npx astro add sitemap
npm install astro-icon
```

### Project Structure

```
juanlab-astro/
├── public/
│   ├── images/
│   │   ├── people/          # Member photos
│   │   ├── research/        # Research highlight images
│   │   ├── gallery/         # Lab photos
│   │   └── logo.svg         # Lab logo
│   └── favicon.ico
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── Header.astro
│   │   │   ├── Footer.astro
│   │   │   └── LanguageToggle.astro
│   │   ├── home/
│   │   │   ├── Hero.astro
│   │   │   ├── NewsTimeline.astro
│   │   │   ├── ResearchHighlights.astro
│   │   │   └── ProjectCards.astro
│   │   ├── people/
│   │   │   ├── PeopleGrid.astro
│   │   │   └── MemberCard.astro
│   │   └── common/
│   │       ├── Card.astro
│   │       └── Section.astro
│   ├── content/
│   │   ├── news.json
│   │   ├── people.json
│   │   ├── research.json
│   │   ├── projects.json
│   │   └── pi.json
│   ├── i18n/
│   │   ├── en.json
│   │   └── zh.json
│   ├── layouts/
│   │   └── BaseLayout.astro
│   ├── pages/
│   │   ├── index.astro
│   │   ├── about.astro
│   │   ├── publications.astro
│   │   ├── members.astro
│   │   └── join.astro
│   └── styles/
│       ├── global.css
│       └── variables.css
├── scripts/
│   ├── scrape_juanlab.py    # Main scraper
│   └── download_images.py   # Image downloader
├── astro.config.mjs
└── package.json
```

---

## 2. Content Migration (ETL Pipeline)

### Main Scraper Script: `scripts/scrape_juanlab.py`

```python
#!/usr/bin/env python3
"""
Juan Lab DokuWiki Content Scraper
Extracts structured content and saves as JSON for Astro.
"""

import json
import re
import unicodedata
from pathlib import Path
from datetime import datetime
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://sbl.csie.org/JuanLab"
OUTPUT_DIR = Path("src/content")
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JuanLabMigration/1.0)"
}

def fetch_page(path: str) -> BeautifulSoup:
    """Fetch and parse a DokuWiki page."""
    url = f"{BASE_URL}/doku.php?id={path}"
    response = requests.get(url, headers=HEADERS, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "lxml")

def clean_text(text: str) -> str:
    """Normalize Unicode and clean whitespace."""
    if not text:
        return ""
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_news(soup: BeautifulSoup) -> list[dict]:
    """Extract news items from the start page."""
    news_items = []
    
    # Find all list items in news section
    # DokuWiki uses <li> elements for news
    content = soup.find("div", class_="dokuwiki")
    if not content:
        return news_items
    
    # Pattern: YY.MM description
    news_pattern = re.compile(r'^(\d{2})\.(\d{2})\s+(.+)$')
    
    for li in content.find_all("li"):
        text = clean_text(li.get_text())
        match = news_pattern.match(text)
        if match:
            year_short, month, title = match.groups()
            # Convert YY to YYYY (assume 20XX for recent, 19XX for old)
            year = int(year_short)
            year = 2000 + year if year < 50 else 1900 + year
            
            # Extract link if present
            link = None
            a_tag = li.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                if not href.startswith("http"):
                    href = f"{BASE_URL}/{href}"
                link = href
            
            news_items.append({
                "date": f"{year}-{month.zfill(2)}",
                "year": year,
                "month": int(month),
                "title": title,
                "link": link
            })
    
    return news_items

def extract_people(soup: BeautifulSoup) -> dict:
    """Extract people information from members page."""
    people = {
        "phd_students": [],
        "masters_students": [],
        "undergrads": [],
        "visiting": [],
        "alumni": []
    }
    
    # Implementation depends on actual page structure
    # This is a template - adjust selectors based on actual HTML
    
    return people

def extract_research_highlights(soup: BeautifulSoup) -> list[dict]:
    """Extract research highlight sections."""
    highlights = []
    
    # Find sections with images and descriptions
    # Adjust based on actual structure
    
    return highlights

def main():
    print("Starting Juan Lab content extraction...")
    
    # 1. Extract from start page
    print("Fetching start page...")
    start_soup = fetch_page("start")
    
    news = extract_news(start_soup)
    print(f"  Found {len(news)} news items")
    
    with open(OUTPUT_DIR / "news.json", "w", encoding="utf-8") as f:
        json.dump(news, f, ensure_ascii=False, indent=2)
    
    # 2. Extract members
    print("Fetching members page...")
    try:
        members_soup = fetch_page("members:start")
        people = extract_people(members_soup)
        with open(OUTPUT_DIR / "people.json", "w", encoding="utf-8") as f:
            json.dump(people, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"  Warning: Could not fetch members: {e}")
    
    # 3. Extract PI info
    print("Fetching PI page...")
    try:
        pi_soup = fetch_page("PI:Hsueh-Fen Juan")
        # Extract PI information
    except Exception as e:
        print(f"  Warning: Could not fetch PI page: {e}")
    
    print("Content extraction complete!")

if __name__ == "__main__":
    main()
```

### Data Schema Definitions

#### `news.json`
```json
[
  {
    "date": "2025-11",
    "year": 2025,
    "month": 11,
    "title": "楊閎翔和林靖雅榮獲 2025 Multiomics and Precision Medicine Joint Conference Best Poster Award",
    "title_en": "Hong-Xiang Yang and Jing-Ya Lin received Best Poster Award at 2025 Multiomics Conference",
    "link": null,
    "category": "award"
  }
]
```

#### `people.json`
```json
{
  "pi": {
    "name_zh": "阮雪芬",
    "name_en": "Hsueh-Fen Juan",
    "title": "Distinguished Professor",
    "email": "yukijuan@ntu.edu.tw",
    "photo": "/images/people/pi.jpg",
    "bio": "..."
  },
  "phd_students": [
    {
      "name_zh": "游佩蓁",
      "name_en": "Pei-Chen Yu",
      "year_start": 2018,
      "department": "MCB",
      "research": ["Molecular and cellular biology", "Cancer research"],
      "photo": "/images/people/pei-chen-yu.jpg"
    }
  ],
  "alumni": [...]
}
```

#### `research.json`
```json
[
  {
    "id": "ectopic-atp-synthase",
    "title_zh": "癌症研究中的異位 ATP 合成酶",
    "title_en": "Ectopic ATP Synthase in Cancer Research",
    "description_zh": "正如 1997 年諾貝爾獎得主 Paul Boyer 所啟發的名言所述...",
    "description_en": "As inspired by 1997 Nobel laureate Paul Boyer...",
    "image": "/images/research/atp-synthase.png",
    "publications": ["J Proteome Res. 2008", "Cancer Res. 2012"]
  }
]
```

---

## 3. Image Asset Migration

### Image Downloader Script: `scripts/download_images.py`

```python
#!/usr/bin/env python3
"""
Download and organize images from DokuWiki media.
"""

import os
import re
import requests
from pathlib import Path
from urllib.parse import urljoin, unquote
from PIL import Image

BASE_URL = "https://sbl.csie.org/JuanLab"
OUTPUT_DIR = Path("public/images")

def download_image(url: str, output_path: Path) -> bool:
    """Download image and optionally convert to WebP."""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Save original
        with open(output_path, "wb") as f:
            f.write(response.content)
        
        # Optionally create WebP version
        if output_path.suffix.lower() in [".jpg", ".jpeg", ".png"]:
            webp_path = output_path.with_suffix(".webp")
            img = Image.open(output_path)
            img.save(webp_path, "WEBP", quality=85)
        
        return True
    except Exception as e:
        print(f"Error downloading {url}: {e}")
        return False

def extract_media_urls(html_content: str) -> list[str]:
    """Extract all media URLs from HTML content."""
    pattern = r'/JuanLab/lib/exe/fetch\.php\?[^"\'>\s]+'
    matches = re.findall(pattern, html_content)
    return [f"{BASE_URL}{m}" if not m.startswith("http") else m for m in matches]

def main():
    # Implementation for batch downloading
    pass

if __name__ == "__main__":
    main()
```

### Image Organization

```
public/images/
├── people/
│   ├── pi.jpg
│   ├── pi.webp
│   ├── chen-hao-huang.jpg
│   └── ...
├── research/
│   ├── highlight-1-2026.png
│   ├── highlight-2-2026.png
│   └── ...
├── gallery/
│   ├── lab-photo-1.jpg
│   └── ...
└── covers/
    └── cover-20240812.png
```

---

## 4. Component Architecture

### BaseLayout.astro

```astro
---
import "../styles/global.css";

interface Props {
  title: string;
  description?: string;
  lang?: "en" | "zh";
}

const { 
  title, 
  description = "Juan's Systems Biology Laboratory - NTU",
  lang = "zh"
} = Astro.props;
---

<!DOCTYPE html>
<html lang={lang}>
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <meta name="description" content={description} />
  <title>{title} | Juan Lab</title>
  
  <!-- Fonts -->
  <link rel="preconnect" href="https://fonts.googleapis.com" />
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
  <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&family=Outfit:wght@500;600;700&family=Noto+Sans+TC:wght@400;500;700&display=swap" rel="stylesheet" />
  
  <!-- Favicon -->
  <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
</head>
<body>
  <div class="page-wrapper">
    <Header />
    <main>
      <slot />
    </main>
    <Footer />
  </div>
</body>
</html>
```

### Hero.astro (QIQB-Style)

```astro
---
interface Props {
  title: string;
  subtitle: string;
  backgroundImage?: string;
}

const { title, subtitle, backgroundImage } = Astro.props;
---

<section class="hero">
  <div class="hero-bg">
    <div class="mesh-gradient"></div>
    {backgroundImage && <img src={backgroundImage} alt="" class="hero-image" />}
  </div>
  <div class="hero-content">
    <h1 class="hero-title">{title}</h1>
    <p class="hero-subtitle">{subtitle}</p>
  </div>
</section>

<style>
  .hero {
    position: relative;
    min-height: 70vh;
    display: flex;
    align-items: center;
    justify-content: center;
    overflow: hidden;
  }
  
  .hero-bg {
    position: absolute;
    inset: 0;
    z-index: 0;
  }
  
  .mesh-gradient {
    position: absolute;
    inset: 0;
    background: 
      radial-gradient(ellipse at 20% 30%, rgba(99, 102, 241, 0.3) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 70%, rgba(139, 92, 246, 0.3) 0%, transparent 50%),
      radial-gradient(ellipse at 50% 50%, rgba(6, 182, 212, 0.2) 0%, transparent 60%);
    animation: meshMove 20s ease-in-out infinite;
  }
  
  @keyframes meshMove {
    0%, 100% { transform: scale(1) rotate(0deg); }
    50% { transform: scale(1.1) rotate(3deg); }
  }
  
  .hero-content {
    position: relative;
    z-index: 1;
    text-align: center;
    padding: 2rem;
  }
  
  .hero-title {
    font-family: var(--font-heading);
    font-size: clamp(2.5rem, 6vw, 4.5rem);
    font-weight: 700;
    color: var(--text-primary);
    margin-bottom: 1rem;
    text-shadow: 0 2px 20px rgba(0, 0, 0, 0.3);
  }
  
  .hero-subtitle {
    font-size: clamp(1rem, 2vw, 1.5rem);
    color: var(--text-secondary);
    max-width: 800px;
    margin: 0 auto;
  }
</style>
```

### NewsTimeline.astro

```astro
---
import news from "../content/news.json";

interface Props {
  limit?: number;
  showAll?: boolean;
}

const { limit = 10, showAll = false } = Astro.props;

// Group news by year
const groupedNews = news.reduce((acc, item) => {
  const year = item.year;
  if (!acc[year]) acc[year] = [];
  acc[year].push(item);
  return acc;
}, {} as Record<number, typeof news>);

const years = Object.keys(groupedNews)
  .map(Number)
  .sort((a, b) => b - a);
---

<section class="news-timeline">
  <h2 class="section-title">News</h2>
  
  <div class="timeline">
    {years.map((year) => (
      <div class="year-group">
        <div class="year-marker">{year}</div>
        <ul class="news-list">
          {groupedNews[year].slice(0, showAll ? undefined : limit).map((item) => (
            <li class="news-item">
              <span class="news-date">{item.date}</span>
              {item.link ? (
                <a href={item.link} class="news-title">{item.title}</a>
              ) : (
                <span class="news-title">{item.title}</span>
              )}
            </li>
          ))}
        </ul>
      </div>
    ))}
  </div>
  
  {!showAll && (
    <button class="load-more" id="loadMoreNews">
      More news...
    </button>
  )}
</section>

<style>
  .news-timeline {
    padding: var(--section-padding);
  }
  
  .timeline {
    position: relative;
    padding-left: 2rem;
  }
  
  .timeline::before {
    content: "";
    position: absolute;
    left: 0;
    top: 0;
    bottom: 0;
    width: 2px;
    background: linear-gradient(to bottom, var(--accent-primary), var(--accent-secondary));
  }
  
  .year-group {
    margin-bottom: 2rem;
  }
  
  .year-marker {
    position: relative;
    font-family: var(--font-heading);
    font-size: 1.5rem;
    font-weight: 700;
    color: var(--accent-primary);
    margin-bottom: 1rem;
  }
  
  .year-marker::before {
    content: "";
    position: absolute;
    left: -2.35rem;
    top: 50%;
    transform: translateY(-50%);
    width: 12px;
    height: 12px;
    background: var(--accent-primary);
    border-radius: 50%;
    box-shadow: 0 0 10px var(--accent-primary);
  }
  
  .news-list {
    list-style: none;
    padding: 0;
    margin: 0;
  }
  
  .news-item {
    display: flex;
    gap: 1rem;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-color);
  }
  
  .news-date {
    flex-shrink: 0;
    color: var(--text-muted);
    font-size: 0.9rem;
  }
  
  .news-title {
    color: var(--text-primary);
  }
  
  a.news-title:hover {
    color: var(--accent-primary);
  }
  
  .load-more {
    margin-top: 1rem;
    padding: 0.75rem 2rem;
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 9999px;
    color: var(--text-primary);
    cursor: pointer;
    transition: all 0.3s ease;
  }
  
  .load-more:hover {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
  }
</style>
```

### MemberCard.astro

```astro
---
interface Props {
  name_zh: string;
  name_en: string;
  title?: string;
  department?: string;
  research?: string[];
  photo?: string;
  email?: string;
}

const { name_zh, name_en, title, department, research, photo, email } = Astro.props;
---

<div class="member-card">
  <div class="member-photo">
    {photo ? (
      <img src={photo} alt={name_en} loading="lazy" />
    ) : (
      <div class="photo-placeholder">
        <span>{name_en.charAt(0)}</span>
      </div>
    )}
  </div>
  <div class="member-info">
    <h3 class="member-name">
      <span class="name-zh">{name_zh}</span>
      <span class="name-en">{name_en}</span>
    </h3>
    {title && <p class="member-title">{title}</p>}
    {department && <p class="member-dept">{department}</p>}
    {research && research.length > 0 && (
      <ul class="member-research">
        {research.map((topic) => <li>{topic}</li>)}
      </ul>
    )}
    {email && (
      <a href={`mailto:${email}`} class="member-email">{email}</a>
    )}
  </div>
</div>

<style>
  .member-card {
    background: var(--glass-bg);
    border: 1px solid var(--glass-border);
    border-radius: 1rem;
    padding: 1.5rem;
    transition: all 0.3s ease;
    backdrop-filter: blur(10px);
  }
  
  .member-card:hover {
    transform: translateY(-4px);
    box-shadow: 0 20px 40px rgba(0, 0, 0, 0.3);
    border-color: var(--accent-primary);
  }
  
  .member-photo {
    width: 120px;
    height: 120px;
    margin: 0 auto 1rem;
    border-radius: 50%;
    overflow: hidden;
    border: 3px solid var(--accent-primary);
  }
  
  .member-photo img {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }
  
  .photo-placeholder {
    width: 100%;
    height: 100%;
    background: var(--accent-gradient);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 2.5rem;
    color: white;
    font-weight: 700;
  }
  
  .member-name {
    text-align: center;
    margin-bottom: 0.5rem;
  }
  
  .name-zh {
    display: block;
    font-size: 1.25rem;
    color: var(--text-primary);
  }
  
  .name-en {
    display: block;
    font-size: 0.9rem;
    color: var(--text-secondary);
  }
  
  .member-title,
  .member-dept {
    text-align: center;
    font-size: 0.85rem;
    color: var(--text-muted);
    margin: 0.25rem 0;
  }
  
  .member-research {
    list-style: none;
    padding: 0;
    margin: 1rem 0 0;
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    justify-content: center;
  }
  
  .member-research li {
    font-size: 0.75rem;
    padding: 0.25rem 0.75rem;
    background: rgba(99, 102, 241, 0.2);
    border-radius: 9999px;
    color: var(--accent-primary);
  }
  
  .member-email {
    display: block;
    text-align: center;
    margin-top: 1rem;
    font-size: 0.85rem;
    color: var(--accent-secondary);
  }
</style>
```

---

## 5. QIQB-Inspired Design System

### Design Tokens: `src/styles/variables.css`

```css
:root {
  /* ===== Color Palette (Dark Theme) ===== */
  --bg-primary: #0a0a1a;
  --bg-secondary: #12122a;
  --bg-tertiary: #1a1a3a;
  
  /* Accent Colors - Purple/Blue Gradient */
  --accent-primary: #6366f1;    /* Indigo */
  --accent-secondary: #8b5cf6;  /* Purple */
  --accent-tertiary: #06b6d4;   /* Cyan */
  
  --accent-gradient: linear-gradient(135deg, #6366f1 0%, #8b5cf6 50%, #06b6d4 100%);
  
  /* Text Colors */
  --text-primary: #ffffff;
  --text-secondary: #e2e8f0;
  --text-muted: #94a3b8;
  
  /* Glass Effect */
  --glass-bg: rgba(255, 255, 255, 0.05);
  --glass-border: rgba(255, 255, 255, 0.1);
  --glass-blur: 10px;
  
  /* Borders & Shadows */
  --border-color: rgba(255, 255, 255, 0.1);
  --shadow-sm: 0 2px 8px rgba(0, 0, 0, 0.2);
  --shadow-md: 0 8px 24px rgba(0, 0, 0, 0.3);
  --shadow-lg: 0 20px 40px rgba(0, 0, 0, 0.4);
  --shadow-glow: 0 0 30px rgba(99, 102, 241, 0.3);
  
  /* ===== Typography ===== */
  --font-heading: 'Outfit', 'Noto Sans TC', sans-serif;
  --font-body: 'Inter', 'Noto Sans TC', sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  
  --text-xs: 0.75rem;
  --text-sm: 0.875rem;
  --text-base: 1rem;
  --text-lg: 1.125rem;
  --text-xl: 1.25rem;
  --text-2xl: 1.5rem;
  --text-3xl: 2rem;
  --text-4xl: 2.5rem;
  --text-5xl: 3.5rem;
  
  /* ===== Spacing ===== */
  --section-padding: 5rem 2rem;
  --container-max: 1400px;
  --container-padding: 2rem;
  
  /* ===== Transitions ===== */
  --transition-fast: 150ms ease;
  --transition-base: 300ms ease;
  --transition-slow: 500ms ease;
  
  /* ===== Border Radius ===== */
  --radius-sm: 0.375rem;
  --radius-md: 0.75rem;
  --radius-lg: 1rem;
  --radius-xl: 1.5rem;
  --radius-full: 9999px;
}

/* Light Theme Override (optional) */
[data-theme="light"] {
  --bg-primary: #f8fafc;
  --bg-secondary: #ffffff;
  --bg-tertiary: #f1f5f9;
  --text-primary: #0f172a;
  --text-secondary: #334155;
  --text-muted: #64748b;
  --glass-bg: rgba(255, 255, 255, 0.7);
  --glass-border: rgba(0, 0, 0, 0.1);
}
```

### Global Styles: `src/styles/global.css`

```css
@import './variables.css';

/* ===== Reset ===== */
*, *::before, *::after {
  box-sizing: border-box;
  margin: 0;
  padding: 0;
}

/* ===== Base ===== */
html {
  scroll-behavior: smooth;
}

body {
  font-family: var(--font-body);
  font-size: var(--text-base);
  line-height: 1.6;
  color: var(--text-primary);
  background: var(--bg-primary);
  min-height: 100vh;
}

/* ===== Typography ===== */
h1, h2, h3, h4, h5, h6 {
  font-family: var(--font-heading);
  font-weight: 600;
  line-height: 1.2;
}

h1 { font-size: var(--text-5xl); }
h2 { font-size: var(--text-3xl); }
h3 { font-size: var(--text-2xl); }
h4 { font-size: var(--text-xl); }

a {
  color: var(--accent-primary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

a:hover {
  color: var(--accent-secondary);
}

/* ===== Layout ===== */
.container {
  max-width: var(--container-max);
  margin: 0 auto;
  padding: 0 var(--container-padding);
}

.section {
  padding: var(--section-padding);
}

.section-title {
  text-align: center;
  margin-bottom: 3rem;
  background: var(--accent-gradient);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

/* ===== Glass Card ===== */
.glass-card {
  background: var(--glass-bg);
  border: 1px solid var(--glass-border);
  border-radius: var(--radius-lg);
  backdrop-filter: blur(var(--glass-blur));
  -webkit-backdrop-filter: blur(var(--glass-blur));
  padding: 1.5rem;
  transition: all var(--transition-base);
}

.glass-card:hover {
  transform: translateY(-4px);
  box-shadow: var(--shadow-lg), var(--shadow-glow);
  border-color: var(--accent-primary);
}

/* ===== Grid Systems ===== */
.grid-2 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
  gap: 2rem;
}

.grid-3 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 1.5rem;
}

.grid-4 {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 1.5rem;
}

/* ===== Animations ===== */
@keyframes fadeInUp {
  from {
    opacity: 0;
    transform: translateY(20px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.animate-fade-in-up {
  animation: fadeInUp 0.6s ease forwards;
}

/* ===== Responsive ===== */
@media (max-width: 768px) {
  :root {
    --section-padding: 3rem 1rem;
    --container-padding: 1rem;
  }
  
  h1 { font-size: var(--text-3xl); }
  h2 { font-size: var(--text-2xl); }
}
```

---

## 6. Internationalization (i18n)

### Language Files

**`src/i18n/en.json`**
```json
{
  "nav": {
    "home": "Home",
    "about": "About PI",
    "publications": "Publications",
    "members": "Members",
    "join": "Join Us"
  },
  "home": {
    "hero_title": "Juan's Systems Biology Laboratory",
    "hero_subtitle": "From proteins to proteomics and beyond... Aimed for drug discovery and bioenergy development",
    "news_title": "News",
    "research_title": "Research Highlights",
    "projects_title": "Research Projects"
  },
  "members": {
    "title": "Lab Members",
    "pi": "Principal Investigator",
    "phd": "PhD Students",
    "masters": "Master's Students",
    "undergrad": "Undergraduate Students",
    "alumni": "Alumni"
  }
}
```

**`src/i18n/zh.json`**
```json
{
  "nav": {
    "home": "首頁",
    "about": "主持人",
    "publications": "發表論文",
    "members": "實驗室成員",
    "join": "加入我們"
  },
  "home": {
    "hero_title": "阮雪芬系統生物學實驗室",
    "hero_subtitle": "從蛋白質到蛋白質體學及更遠的地方... 致力於藥物開發和生物能源發展",
    "news_title": "最新消息",
    "research_title": "研究亮點",
    "projects_title": "研究計畫"
  },
  "members": {
    "title": "實驗室成員",
    "pi": "主持人",
    "phd": "博士生",
    "masters": "碩士生",
    "undergrad": "大學部學生",
    "alumni": "畢業生"
  }
}
```

### i18n Helper: `src/i18n/utils.ts`

```typescript
import en from './en.json';
import zh from './zh.json';

const translations = { en, zh };

export type Lang = 'en' | 'zh';

export function t(lang: Lang, key: string): string {
  const keys = key.split('.');
  let value: any = translations[lang];
  
  for (const k of keys) {
    value = value?.[k];
  }
  
  return value || key;
}

export function getLangFromUrl(url: URL): Lang {
  const [, lang] = url.pathname.split('/');
  if (lang === 'en') return 'en';
  return 'zh';
}
```

---

## 7. SEO & Performance Optimization

### astro.config.mjs

```javascript
import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://username.github.io',
  base: '/juanlab',
  integrations: [
    sitemap({
      i18n: {
        defaultLocale: 'zh',
        locales: {
          zh: 'zh-TW',
          en: 'en-US',
        },
      },
    }),
  ],
  build: {
    inlineStylesheets: 'auto',
  },
  compressHTML: true,
  vite: {
    build: {
      cssMinify: true,
    },
  },
});
```

### SEO Component: `src/components/SEO.astro`

```astro
---
interface Props {
  title: string;
  description: string;
  image?: string;
  article?: boolean;
}

const canonicalURL = new URL(Astro.url.pathname, Astro.site);
const { title, description, image = '/images/og-default.png', article = false } = Astro.props;
---

<!-- Primary Meta Tags -->
<meta name="title" content={title} />
<meta name="description" content={description} />

<!-- Open Graph / Facebook -->
<meta property="og:type" content={article ? 'article' : 'website'} />
<meta property="og:url" content={canonicalURL} />
<meta property="og:title" content={title} />
<meta property="og:description" content={description} />
<meta property="og:image" content={new URL(image, Astro.url)} />

<!-- Twitter -->
<meta property="twitter:card" content="summary_large_image" />
<meta property="twitter:url" content={canonicalURL} />
<meta property="twitter:title" content={title} />
<meta property="twitter:description" content={description} />
<meta property="twitter:image" content={new URL(image, Astro.url)} />

<!-- Canonical URL -->
<link rel="canonical" href={canonicalURL} />

<!-- Structured Data -->
<script type="application/ld+json">
  {JSON.stringify({
    "@context": "https://schema.org",
    "@type": "ResearchOrganization",
    "name": "Juan's Systems Biology Laboratory",
    "url": Astro.site,
    "logo": new URL('/images/logo.svg', Astro.site),
    "parentOrganization": {
      "@type": "CollegeOrUniversity",
      "name": "National Taiwan University"
    }
  })}
</script>
```

---

## 8. Deployment to GitHub Pages

### GitHub Actions: `.github/workflows/deploy.yml`

```yaml
name: Deploy to GitHub Pages

on:
  push:
    branches: [main]
  workflow_dispatch:

permissions:
  contents: read
  pages: write
  id-token: write

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'

      - name: Install dependencies
        run: npm ci

      - name: Build Astro
        run: npm run build

      - name: Upload artifact
        uses: actions/upload-pages-artifact@v3
        with:
          path: ./dist

  deploy:
    environment:
      name: github-pages
      url: ${{ steps.deployment.outputs.page_url }}
    runs-on: ubuntu-latest
    needs: build
    steps:
      - name: Deploy to GitHub Pages
        id: deployment
        uses: actions/deploy-pages@v4
```

### Repository Settings

1. Go to **Settings → Pages**
2. Source: **GitHub Actions**
3. Wait for workflow to complete
4. Access at: `https://username.github.io/juanlab/`

---

## Best Practices

### Content Management
- ✅ Keep content (JSON) separate from presentation (Astro components)
- ✅ Use TypeScript interfaces for type-safe data
- ✅ Store translations in dedicated i18n files

### Performance
- ✅ Use `loading="lazy"` for images below the fold
- ✅ Serve WebP with fallbacks for older browsers
- ✅ Minimize JavaScript; prefer Astro's zero-JS approach

### Accessibility
- ✅ Ensure sufficient color contrast (WCAG AA minimum)
- ✅ Use semantic HTML (`<nav>`, `<main>`, `<article>`)
- ✅ Add `aria-labels` to interactive elements

### Scraping Resilience
- ✅ Add try/except blocks around network requests
- ✅ Validate JSON output before committing
- ✅ Log warnings for missing or malformed data

### Maintenance
- ✅ Document all data schemas
- ✅ Create a simple admin process for adding news/members
- ✅ Consider headless CMS integration for non-technical updates

---

## Quick Start Commands

```bash
# 1. Clone and setup
git clone https://github.com/username/juanlab-astro.git
cd juanlab-astro
npm install

# 2. Run scraper (first time)
cd scripts
python scrape_juanlab.py
python download_images.py
cd ..

# 3. Development
npm run dev

# 4. Build for production
npm run build

# 5. Preview production build
npm run preview
```

---

*Last updated: February 2026*
*Target completion: Juan's Systems Biology Laboratory migration to GitHub Pages*
