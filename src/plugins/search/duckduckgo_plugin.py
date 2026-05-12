"""
DuckDuckGo Search Plugin — Ad/soyad/email ilə veb axtarış (API key lazım deyil)

NƏ ÜÇÜN: İnsan adı verildiyi zaman DuckDuckGo HTML axtarışı edib nəticələri
çıxarır. Google-dan fərqli olaraq DuckDuckGo captcha/blok qoymur, API key
tələb etmir. Bu plugin ad-soyad ilə axtarış üçün fundamental axtarış motorudur.

NECƏ: httpx ilə DuckDuckGo HTML axtarış səhifəsini çəkir, nəticələrdəki
URL, başlıq və təsviri parse edir. Sosial media profillərini avtomatik yüksək
confidence ilə qeyd edir.
"""

from __future__ import annotations

import re
from urllib.parse import quote_plus

import httpx
import structlog

from src.core.models import (
    ExecutionMode,
    Finding,
    FindingType,
    PluginCategory,
    PluginMeta,
    Target,
    TargetType,
)
from src.core.plugin_base import BasePlugin

logger = structlog.get_logger(__name__)

# Sosial media domainləri — bu URL-lər tapılsa confidence yüksək olur
SOCIAL_DOMAINS = {
    "facebook.com", "instagram.com", "twitter.com", "x.com",
    "linkedin.com", "vk.com", "tiktok.com", "youtube.com",
    "reddit.com", "pinterest.com", "tumblr.com", "flickr.com",
    "github.com", "medium.com", "telegram.me", "t.me",
}


class DuckDuckGoPlugin(BasePlugin):
    """DuckDuckGo HTML scraping ilə ad/email axtarışı."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="duckduckgo",
            version="1.0.0",
            description="DuckDuckGo ilə veb axtarış — ad, email, username",
            category=PluginCategory.SEARCH,
            license="MIT",
            execution_mode=ExecutionMode.HTTP,
            accepts_types=[TargetType.NAME, TargetType.EMAIL, TargetType.USERNAME],
            timeout_seconds=30,
            priority=20,
        )

    async def execute(self, target: Target) -> list[Finding]:
        query = target.value.strip()
        if not query:
            return []

        # Ad üçün əlavə kontekst: əgər metadata-da ölkə varsa əlavə et
        if target.type == TargetType.NAME:
            country = target.metadata.get("country", "")
            if country:
                query = f'"{query}" {country}'
            else:
                query = f'"{query}"'

        findings = []
        logger.info("ddg_search_start", query=query)

        try:
            async with httpx.AsyncClient(
                timeout=15,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                    "Accept": "text/html,application/xhtml+xml",
                    "Accept-Language": "en-US,en;q=0.9",
                },
            ) as client:
                url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
                resp = await client.get(url)

                if resp.status_code == 200:
                    findings = self._parse_html(resp.text, target)

        except httpx.TimeoutException:
            logger.warning("ddg_timeout", query=query)
        except Exception as e:
            logger.error("ddg_error", query=query, error=str(e))

        logger.info("ddg_search_complete", query=query, found=len(findings))
        return findings

    def _parse_html(self, html: str, target: Target) -> list[Finding]:
        """DuckDuckGo HTML nəticələrini parse edir.

        DuckDuckGo HTML formatı:
        <a class="result__a" href="URL">Title</a>
        <a class="result__snippet">Description</a>
        """
        findings = []
        seen_urls = set()

        # URL-ləri çıxar: class="result__a" href="..."
        url_pattern = re.compile(
            r'class="result__a"[^>]*href="([^"]+)"[^>]*>([^<]+)',
            re.IGNORECASE,
        )

        # Snippet-ləri çıxar
        snippet_pattern = re.compile(
            r'class="result__snippet"[^>]*>(.+?)</a>',
            re.IGNORECASE | re.DOTALL,
        )

        urls_and_titles = url_pattern.findall(html)
        snippets = snippet_pattern.findall(html)

        for i, (url, title) in enumerate(urls_and_titles[:20]):  # İlk 20 nəticə
            # DuckDuckGo redirect URL-lərini decode et
            if "uddg=" in url:
                match = re.search(r'uddg=([^&]+)', url)
                if match:
                    from urllib.parse import unquote
                    url = unquote(match.group(1))

            if url in seen_urls or not url.startswith("http"):
                continue
            seen_urls.add(url)

            # Sosial media olub-olmadığını yoxla
            is_social = any(domain in url.lower() for domain in SOCIAL_DOMAINS)
            confidence = 0.7 if is_social else 0.4

            # HTML tag-ları təmizlə
            title = re.sub(r'<[^>]+>', '', title).strip()
            snippet = ""
            if i < len(snippets):
                snippet = re.sub(r'<[^>]+>', '', snippets[i]).strip()

            finding_type = FindingType.PROFILE_URL if is_social else FindingType.WEBSITE

            findings.append(self.make_finding(
                platform=self._extract_domain(url),
                finding_type=finding_type,
                value=url,
                confidence=confidence,
                url=url,
                raw_data={
                    "title": title,
                    "snippet": snippet[:200],
                    "is_social": is_social,
                    "source": "duckduckgo",
                },
            ))

        return findings

    @staticmethod
    def _extract_domain(url: str) -> str:
        """URL-dən domain çıxarır."""
        try:
            from urllib.parse import urlparse
            parsed = urlparse(url)
            domain = parsed.netloc.replace("www.", "")
            return domain.split(".")[0] if domain else "unknown"
        except Exception:
            return "unknown"
