"""
Web Search - Enable bots to search the internet for information.

Supports multiple search providers with a unified interface.
Bots can use this to stay informed, research topics, and provide
up-to-date information to users.
"""

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
import aiohttp

logger = logging.getLogger(__name__)


class SearchProvider(str, Enum):
    """Available search providers."""
    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"
    SERPER = "serper"
    BRAVE = "brave"
    BING = "bing"


@dataclass
class SearchResult:
    """A single search result."""
    title: str
    url: str
    snippet: str
    source: str = ""
    published_date: Optional[datetime] = None
    relevance_score: float = 0.0
    metadata: dict = field(default_factory=dict)


@dataclass
class SearchResponse:
    """Response from a search query."""
    query: str
    results: list[SearchResult]
    provider: SearchProvider
    total_results: int = 0
    search_time_ms: float = 0
    error: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.error is None and len(self.results) > 0

    def to_text(self, max_results: int = 5) -> str:
        """Format results as readable text for bot consumption."""
        if not self.results:
            return f"No results found for: {self.query}"

        lines = [f"Search results for: {self.query}\n"]
        for i, result in enumerate(self.results[:max_results], 1):
            lines.append(f"{i}. {result.title}")
            lines.append(f"   {result.snippet[:200]}...")
            lines.append(f"   Source: {result.url}\n")

        return "\n".join(lines)


class WebSearchProvider(ABC):
    """Abstract base class for search providers."""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._session: Optional[aiohttp.ClientSession] = None

    @property
    @abstractmethod
    def provider_id(self) -> SearchProvider:
        """Get the provider identifier."""
        pass

    @abstractmethod
    async def search(
        self,
        query: str,
        num_results: int = 10,
        **kwargs
    ) -> SearchResponse:
        """Execute a search query."""
        pass

    async def _ensure_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self) -> None:
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()


class DuckDuckGoSearch(WebSearchProvider):
    """
    DuckDuckGo search provider (no API key required).

    Uses the DuckDuckGo HTML interface for searching.
    Rate limited but free and privacy-respecting.
    """

    @property
    def provider_id(self) -> SearchProvider:
        return SearchProvider.DUCKDUCKGO

    async def search(
        self,
        query: str,
        num_results: int = 10,
        region: str = "wt-wt",
        **kwargs
    ) -> SearchResponse:
        """Search using DuckDuckGo."""
        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            # Use DuckDuckGo's HTML search
            params = {
                "q": query,
                "kl": region,
            }

            async with session.get(
                "https://html.duckduckgo.com/html/",
                params=params,
                headers={"User-Agent": "Mozilla/5.0 (compatible; SentientAI/1.0)"}
            ) as resp:
                if resp.status != 200:
                    return SearchResponse(
                        query=query,
                        results=[],
                        provider=self.provider_id,
                        error=f"HTTP {resp.status}"
                    )

                html = await resp.text()
                results = self._parse_results(html, num_results)

                return SearchResponse(
                    query=query,
                    results=results,
                    provider=self.provider_id,
                    total_results=len(results),
                    search_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"DuckDuckGo search error: {e}")
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider_id,
                error=str(e)
            )

    def _parse_results(self, html: str, limit: int) -> list[SearchResult]:
        """Parse search results from DuckDuckGo HTML."""
        results = []

        # Simple parsing without BeautifulSoup dependency
        # Look for result blocks
        import re

        # Find result links and snippets
        pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>'
        snippet_pattern = r'<a[^>]*class="result__snippet"[^>]*>([^<]*)</a>'

        links = re.findall(pattern, html)
        snippets = re.findall(snippet_pattern, html)

        for i, (url, title) in enumerate(links[:limit]):
            snippet = snippets[i] if i < len(snippets) else ""
            results.append(SearchResult(
                title=title.strip(),
                url=url,
                snippet=snippet.strip(),
                source="duckduckgo"
            ))

        return results


class TavilySearch(WebSearchProvider):
    """
    Tavily search provider - optimized for AI/LLM applications.

    Provides clean, relevant results specifically designed for
    AI consumption. Requires API key.
    """

    BASE_URL = "https://api.tavily.com/search"

    @property
    def provider_id(self) -> SearchProvider:
        return SearchProvider.TAVILY

    async def search(
        self,
        query: str,
        num_results: int = 10,
        search_depth: str = "basic",  # or "advanced"
        include_answer: bool = True,
        **kwargs
    ) -> SearchResponse:
        """Search using Tavily API."""
        if not self.api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider_id,
                error="Tavily API key required"
            )

        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            payload = {
                "api_key": self.api_key,
                "query": query,
                "search_depth": search_depth,
                "include_answer": include_answer,
                "max_results": num_results,
            }

            async with session.post(self.BASE_URL, json=payload) as resp:
                if resp.status != 200:
                    error_text = await resp.text()
                    return SearchResponse(
                        query=query,
                        results=[],
                        provider=self.provider_id,
                        error=f"HTTP {resp.status}: {error_text}"
                    )

                data = await resp.json()
                results = [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("url", ""),
                        snippet=r.get("content", ""),
                        source="tavily",
                        relevance_score=r.get("score", 0),
                    )
                    for r in data.get("results", [])
                ]

                return SearchResponse(
                    query=query,
                    results=results,
                    provider=self.provider_id,
                    total_results=len(results),
                    search_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"Tavily search error: {e}")
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider_id,
                error=str(e)
            )


class SerperSearch(WebSearchProvider):
    """
    Serper search provider - Google Search API alternative.

    Fast and affordable Google search results. Requires API key.
    """

    BASE_URL = "https://google.serper.dev/search"

    @property
    def provider_id(self) -> SearchProvider:
        return SearchProvider.SERPER

    async def search(
        self,
        query: str,
        num_results: int = 10,
        country: str = "us",
        **kwargs
    ) -> SearchResponse:
        """Search using Serper API."""
        if not self.api_key:
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider_id,
                error="Serper API key required"
            )

        import time
        start_time = time.time()

        try:
            session = await self._ensure_session()

            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            }

            payload = {
                "q": query,
                "num": num_results,
                "gl": country,
            }

            async with session.post(
                self.BASE_URL,
                json=payload,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return SearchResponse(
                        query=query,
                        results=[],
                        provider=self.provider_id,
                        error=f"HTTP {resp.status}"
                    )

                data = await resp.json()
                results = [
                    SearchResult(
                        title=r.get("title", ""),
                        url=r.get("link", ""),
                        snippet=r.get("snippet", ""),
                        source="google",
                    )
                    for r in data.get("organic", [])
                ]

                return SearchResponse(
                    query=query,
                    results=results,
                    provider=self.provider_id,
                    total_results=len(results),
                    search_time_ms=(time.time() - start_time) * 1000
                )

        except Exception as e:
            logger.error(f"Serper search error: {e}")
            return SearchResponse(
                query=query,
                results=[],
                provider=self.provider_id,
                error=str(e)
            )


# Registry of available providers
_search_providers: dict[SearchProvider, type[WebSearchProvider]] = {
    SearchProvider.DUCKDUCKGO: DuckDuckGoSearch,
    SearchProvider.TAVILY: TavilySearch,
    SearchProvider.SERPER: SerperSearch,
}

_default_provider: Optional[WebSearchProvider] = None


def get_search_provider(
    provider: SearchProvider = SearchProvider.DUCKDUCKGO,
    api_key: Optional[str] = None
) -> WebSearchProvider:
    """Get a search provider instance."""
    provider_class = _search_providers.get(provider)
    if not provider_class:
        raise ValueError(f"Unknown search provider: {provider}")
    return provider_class(api_key=api_key)


async def search_web(
    query: str,
    provider: SearchProvider = SearchProvider.DUCKDUCKGO,
    num_results: int = 10,
    api_key: Optional[str] = None,
    **kwargs
) -> SearchResponse:
    """
    Convenience function to search the web.

    Usage:
        results = await search_web("latest AI news")
        print(results.to_text())
    """
    search_provider = get_search_provider(provider, api_key)
    try:
        return await search_provider.search(query, num_results, **kwargs)
    finally:
        await search_provider.close()
