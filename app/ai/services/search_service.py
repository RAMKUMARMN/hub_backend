import logging
import re
import httpx
from ddgs import DDGS
from app.config import settings

logger = logging.getLogger(__name__)


def _clean_snippet(text: str) -> str:
    """
    Strip noisy HTML/markdown artifacts from search snippets so small LLMs
    can focus on the actual content instead of getting confused by URLs,
    image tags, and navigation boilerplate.
    """
    # Remove markdown image references: ![...](...)
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)
    # Remove markdown links but keep the link text: [text](url) -> text
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    # Remove bare URLs
    text = re.sub(r"https?://\S+", "", text)
    # Remove HTML tags
    text = re.sub(r"<[^>]+>", "", text)
    # Collapse multiple whitespace/newlines
    text = re.sub(r"\s+", " ", text).strip()
    return text

async def search_tavily(query: str, max_results: int = 5) -> str:
    """Queries Tavily API for search results."""
    if not settings.tavily_api_key:
        raise ValueError("Tavily API key is not configured.")
        
    url = "https://api.tavily.com/search"
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            url,
            json={
                "api_key": settings.tavily_api_key,
                "query": query,
                "max_results": max_results
            }
        )
        response.raise_for_status()
        results = response.json().get("results", [])
        
        formatted = []
        for res in results:
            snippet = _clean_snippet(res.get('content', ''))
            if len(snippet) > 2000:
                snippet = snippet[:2000] + "..."
            formatted.append(f"Source: {res['url']}\nTitle: {res['title']}\nSnippet: {snippet}")
        return "\n\n".join(formatted)


def search_duckduckgo(query: str, max_results: int = 5) -> str:
    """Queries DuckDuckGo as a zero-cost backup search engine."""
    logger.info("Using DuckDuckGo fallback search for query: '%s'", query)
    try:
        with DDGS() as ddgs:
            results = ddgs.text(query, max_results=max_results)
            formatted = []
            for r in results:
                snippet = _clean_snippet(r.get('body', ''))
                if len(snippet) > 2000:
                    snippet = snippet[:2000] + "..."
                formatted.append(f"Source: {r['href']}\nTitle: {r['title']}\nSnippet: {snippet}")
            return "\n\n".join(formatted)
    except Exception as e:
        logger.error("DuckDuckGo scraping failed: %s", e)
        raise e


async def unified_web_search(query: str, max_results: int = 5) -> str:
    """
    Tries to search using Tavily first. If the rate limit hits, API fails, 
    or quota runs out, it seamlessly falls back to DuckDuckGo.
    """
    try:
        return await search_tavily(query, max_results=max_results)
    except Exception as exc:
        logger.warning(
            "Tavily search failed or quota limit reached. Falling back to DuckDuckGo. Error: %s",
            exc
        )
        try:
            import asyncio
            return await asyncio.to_thread(search_duckduckgo, query, max_results=max_results)
        except Exception as ddg_exc:
            logger.error("DuckDuckGo fallback search also failed: %s", ddg_exc)
            return "Error: Web search is temporarily unavailable."
