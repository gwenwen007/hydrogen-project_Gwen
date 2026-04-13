"""
news_fetcher.py — Fetch hydrogen-related news from the Mediastack API.

Renamed from 'News API' so it can be imported by other Python modules
(the space in the old name made import impossible).

Usage:
    from data.news.news_fetcher import get_hydrogen_news

    articles = get_hydrogen_news()
    # → list of dicts with title, source, published_at, url
"""

import requests
from datetime import datetime, timezone


# ==============================================================================
# CONFIGURATION
# ==============================================================================

API_KEY = "cfd9b9b3f23e9a769b6725c0f7bc480c"
MEDIASTACK_URL = "https://api.mediastack.com/v1/news"

# Search terms targeting different aspects of the hydrogen market
BUZZWORDS = [
    "green hydrogen import",
    "hydrogen economy Asia",
    "electricity price hydrogen",
    "excess generation electrolyzer",
    "hydrogen terminal Japan",
    "ammonia port Korea",
    "electrolyzer order Korea",
    "hydrogen plant Asia Pacific",
    "hydrogen MOU ministry",
    "hydrogen trade deal",
    "renewable surplus hydrogen",
    "variable renewable hydrogen",
]


# ==============================================================================
# INTERNAL FETCH FUNCTION
# ==============================================================================

def fetch_hydrogen_news_today(keyword: str, max_results: int = 10) -> dict:
    """
    Fetch news articles from the Mediastack API for a single keyword,
    filtered to today's date only (UTC).

    Returns dict with keys: keyword, date, articles (list), error (if failed)
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    params = {
        "access_key": API_KEY,
        "keywords":   keyword,
        "languages":  "en",
        "date":       today,
        "sort":       "published_desc",
        "limit":      max_results,
    }

    try:
        response = requests.get(MEDIASTACK_URL, params=params, timeout=10)
        response.raise_for_status()
        raw = response.json()

        articles = []
        for entry in raw.get("data", []):
            articles.append({
                "title":        entry.get("title"),
                "source":       entry.get("source"),
                "published_at": entry.get("published_at"),
                "url":          entry.get("url"),
            })

        return {"keyword": keyword, "date": today, "articles": articles}

    except Exception as e:
        return {"keyword": keyword, "date": today, "error": str(e)}


# ==============================================================================
# PUBLIC FUNCTION — call this from the Streamlit app
# ==============================================================================

def get_hydrogen_news(max_keywords: int = 3, max_articles: int = 5) -> list[dict]:
    """
    Fetch recent hydrogen news and return a flat list of articles
    ready for display in the Streamlit app.

    To keep API usage low (free tier has limits), we only query the
    first few buzzwords by default.

    Parameters:
        max_keywords: how many buzzwords to query (default 3)
        max_articles: max total articles to return (default 5)

    Returns:
        list of dicts, each with keys:
            title, source, published_at, url, keyword
        Sorted by published_at (newest first).
        Returns empty list if all API calls fail.
    """
    all_articles = []

    for keyword in BUZZWORDS[:max_keywords]:
        result = fetch_hydrogen_news_today(keyword, max_results=5)

        if "error" in result:
            continue

        for article in result.get("articles", []):
            article["keyword"] = keyword
            all_articles.append(article)

    # Deduplicate by title (same article may match multiple keywords)
    seen_titles = set()
    unique = []
    for a in all_articles:
        if a["title"] and a["title"] not in seen_titles:
            seen_titles.add(a["title"])
            unique.append(a)

    # Sort newest first and limit
    unique.sort(key=lambda x: x.get("published_at", ""), reverse=True)
    return unique[:max_articles]
