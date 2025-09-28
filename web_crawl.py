import os
import time
import html
import logging
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlencode
import requests
import asyncio
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig, CacheMode, LLMConfig, LLMExtractionStrategy
import re
from dotenv import load_dotenv
from langdetect import detect
from pydantic import BaseModel, Field
import json


load_dotenv() 
logger = logging.getLogger("crawl")
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 20
RETRY_BACKOFF = [1, 2, 4]  # seconds
DISALLOWED_DOMAINS = {
    "facebook.com", "x.com", "twitter.com", "t.co", "instagram.com",
    "linkedin.com", "pinterest.com", "tiktok.com", "reddit.com"
}

def _req_json(method: str, url: str, params: Dict = None, headers: Dict = None) -> Dict:
    headers = {"User-Agent": USER_AGENT, **(headers or {})}
    for i, backoff in enumerate([0, *RETRY_BACKOFF]):
        try:
            if backoff:
                time.sleep(backoff)
            resp = requests.request(
                method, url, params=params, headers=headers, timeout=DEFAULT_TIMEOUT
            )
            if resp.status_code in (429, 500, 502, 503, 504):
                logger.warning("Retryable HTTP %s for %s", resp.status_code, url)
                continue
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            if i == len(RETRY_BACKOFF):
                raise
            logger.warning("Request failed (%s), retrying in %ss...", e, RETRY_BACKOFF[i])
    return {}

def _clean_snippet(text: str) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:400]



def _detect_lang(text: str) -> bool:
    """
    Returns True if the detected language is Malay (code 'ms'), else False.
    """
    if detect(text) == 'ms' or detect(text) == 'id':
        return "ms"
    elif detect(text) == 'en':
        return "en"
    else:
        return None

def _search_serpapi(query: str, k: int = 5) -> List[Dict]:
    api_key = os.getenv("SERPAPI_API_KEY")
    url = "https://google.serper.dev/news"

    lang = _detect_lang(query)
    print(lang)

    if lang is None:
        return []
    
    params = {
        "engine": "google",
        "location": "Malaysia",
        "q": query,
        "hl": lang,
        "gl": "my",
        "num": min(max(k, 1), 10),
        "google_domain": "google.com.my",
        "api_key": api_key,
    }
    data = _req_json("GET", url, params=params)
 
    results = []
    for item in data.get("news", []):
        link = item.get("link")
        if not link or any(bad in link for bad in DISALLOWED_DOMAINS):
            continue
        results.append({
            "title": item.get("title", ""),
            "url": link,
            "snippet": _clean_snippet(item.get("snippet", "")),
            "source": item.get("source", "web"),
            "provider": "serpapi",
            "note": "Searched from the web",
        })
    
    return results

def web_search(query: str, k: int = 5) -> List[Dict]:
    if not os.getenv("SERPAPI_API_KEY"):
        raise ValueError("No search provider configured.")

    results = _search_serpapi(query, k=k)
    return results[:k]

class NewsArticle(BaseModel):
    title: str = Field(..., description="Title of the news article.")
    content: str = Field(..., description="Full article text.")
    source: str = Field(..., description="Source name.")
    published_date: str = Field(..., description="Published date in YYYY-MM-DD format.")
    url: str = Field(..., description="URL of the article.")
    score: float = Field(..., description="Relevance score to the query, between 0 (not relevant) and 1 (highly relevant).")

async def fetch_news(query: str, url: str, max_chars: int = 8000, snippet: str = "") -> Dict:

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in environment")
    
    browser_config = BrowserConfig(verbose=True)
    run_config = CrawlerRunConfig(
        word_count_threshold=1,
        extraction_strategy=LLMExtractionStrategy(
       
            temperature=0.0,
            llm_config=LLMConfig(provider="gemini/gemini-2.0-flash-001", api_token=os.getenv("GEMINI_API_KEY")),               
            max_tokens=1200,              
            chunk_token_threshold=1500,
            schema=NewsArticle.model_json_schema(),
            extraction_type="schema",
            instruction=(
                f"Extract only the most relevant facts about the query.\n"
                f"Query: {query}\n"
                f"Snippet: {snippet}\n\n"
                "From the crawled content, extract all news articles. "
                "For each article, assign a 'score' field between 0 (not relevant) and 1 (highly relevant) indicating how relevant the article is to the query. "
                "Do not miss any news. One extracted model JSON format should look like this: "
                '{"title": "title text", "content": "full article text", "source": "source name", '
                '"published_date": "YYYY-MM-DD", "url": "https://article.url", "score": 0.95}.'
            ),
        ),            
        cache_mode=CacheMode.BYPASS,
    )

    async with AsyncWebCrawler(config=browser_config) as crawler:
        res = await crawler.arun(url, config=run_config)
        try:
            extracted_articles = json.loads(res.extracted_content)
        except Exception as e:
            logger.warning(f"Could not parse extracted_content as JSON: {e}")
            extracted_articles = []

        return {
            "url": url,
            "status": getattr(res, "status", 200),
            "title": extracted_articles[0].get("title", "") if extracted_articles else "",
            "article_content": extracted_articles[0].get("content", "")[:max_chars] if extracted_articles else "",
            "score": extracted_articles[0].get("score", 0) if extracted_articles else 0,
            "error": getattr(res, "error", None),
        }
 
def web_search_and_fetch(query: str, k: int = 5, max_chars: int = 8000) -> List[Dict]:
    hits = web_search(query, k=k)
    async def gather_all():
        async def safe_fetch(hit):
            url = hit["url"]
            snippet = hit.get("snippet", "")
            try:
                return await fetch_news(query,url, max_chars=max_chars, snippet=snippet)  
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                return {"url": url, "error": str(e)}
        tasks = [safe_fetch(h) for h in hits]
        return await asyncio.gather(*tasks)
    return asyncio.run(gather_all())


##test
# ans = web_search_and_fetch("Adakah SSM terbabit dengan kes-kes mahkamah?", k=3, max_chars=8000)
# print(ans)
