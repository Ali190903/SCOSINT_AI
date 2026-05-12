"""
WhatsMyName Plugin — 732+ saytda username axtarışı

NƏ ÜÇÜN (Final Cause): Bir username verildiyi zaman internetdəki 732+
saytda həmin adın qeydiyyatda olub-olmadığını real HTTP sorğularla yoxlayır.
Bu, rəqəmsal barmaq izinin ilk və ən vacib addımıdır.

NƏDƏN (Material Cause): WebBreacher/WhatsMyName açıq JSON verilənlər bazası.
Hər sayt üçün URL template, mövcudluq kodu/stringi, yoxluq kodu/stringi var.

NECƏ (Efficient Cause): Hər sayta asinxron HTTP GET göndərilir. Cavabdakı
status code + body string ilə hesabın mövcudluğu müəyyən edilir. Paralel
icra — 732 saytı ardıcıl yoxlasaq 20+ dəqiqə çəkər, paraleldə ~30 saniyə.

FORMA (Formal Cause): BasePlugin interface-i implement edir. JSON DB-ni
başlanğıcda yükləyir, cache-ləyir, hər scan-da yenidən yükləmir.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path

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

# WhatsMyName JSON DB URL-i
WMN_DB_URL = "https://raw.githubusercontent.com/WebBreacher/WhatsMyName/main/wmn-data.json"

# Eyni anda neçə sayta sorğu göndərilsin (çox olsa IP bloklanır)
MAX_CONCURRENT = 30

# Hər sorğu üçün timeout (saniyə)
REQUEST_TIMEOUT = 10


class WhatsMyNamePlugin(BasePlugin):
    """732+ saytda username mövcudluğunu yoxlayır.

    Heç bir xarici alətdən asılı deyil — yalnız HTTP sorğular göndərir.
    JSON DB başlanğıcda GitHub-dan yüklənir və memory-də cache-lənir.
    """

    def __init__(self) -> None:
        self._sites: list[dict] = []
        self._loaded = False

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="whatsmyname",
            version="1.0.0",
            description="732+ saytda username axtarışı (WhatsMyName DB)",
            category=PluginCategory.USERNAME,
            license="MIT",
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=120,
            priority=10,  # Yüksək prioritet — ilk işləyən plugin
        )

    async def execute(self, target: Target) -> list[Finding]:
        """Hər sayta paralel HTTP sorğu göndərib username-i axtarır."""
        username = target.value.strip()
        if not username:
            return []

        # DB-ni yüklə (ilk dəfə)
        if not self._loaded:
            await self._load_database()

        if not self._sites:
            logger.error("wmn_no_sites_loaded")
            return []

        findings: list[Finding] = []
        semaphore = asyncio.Semaphore(MAX_CONCURRENT)
        start = time.monotonic()

        async with httpx.AsyncClient(
            timeout=REQUEST_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
        ) as client:
            tasks = [
                self._check_site(client, semaphore, site, username)
                for site in self._sites
            ]
            results = await asyncio.gather(*tasks, return_exceptions=True)

        for result in results:
            if isinstance(result, Finding):
                findings.append(result)

        elapsed = round(time.monotonic() - start, 1)
        logger.info(
            "wmn_scan_complete",
            username=username,
            sites_checked=len(self._sites),
            found=len(findings),
            duration=elapsed,
        )

        return findings

    async def _check_site(
        self,
        client: httpx.AsyncClient,
        semaphore: asyncio.Semaphore,
        site: dict,
        username: str,
    ) -> Finding | None:
        """Tək bir saytda username-i yoxlayır.

        Məntiqi:
        1. URL-dəki {account} → username ilə əvəzlə
        2. HTTP GET göndər
        3. Status code == e_code VƏ response body-də e_string varsa → TAPILDI
        4. Əks halda → yoxdur, None qaytar
        """
        url = site["uri_check"].replace("{account}", username)
        site_name = site.get("name", "unknown")
        expected_code = site.get("e_code", 200)
        expected_string = site.get("e_string", "")

        async with semaphore:
            try:
                resp = await client.get(url)

                # Mövcudluq yoxlaması: status code + body string
                if resp.status_code == expected_code:
                    body = resp.text
                    if expected_string and expected_string in body:
                        return self.make_finding(
                            platform=site_name.lower(),
                            finding_type=FindingType.PROFILE_URL,
                            value=url,
                            confidence=0.85,
                            url=url,
                            raw_data={
                                "site_name": site_name,
                                "category": site.get("cat", "unknown"),
                                "status_code": resp.status_code,
                            },
                        )

            except httpx.TimeoutException:
                pass  # Sayt cavab vermədi — skip
            except httpx.ConnectError:
                pass  # Sayta qoşulmaq mümkün deyil — skip
            except Exception:
                pass  # Gözlənilməz xəta — scan-ı dayandırma

        return None

    async def _load_database(self) -> None:
        """WhatsMyName JSON DB-ni GitHub-dan yükləyir."""
        logger.info("wmn_loading_database", url=WMN_DB_URL)

        try:
            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.get(WMN_DB_URL)
                resp.raise_for_status()
                data = resp.json()

            self._sites = data.get("sites", [])
            self._loaded = True
            logger.info("wmn_database_loaded", sites=len(self._sites))

        except Exception as e:
            logger.error("wmn_database_load_failed", error=str(e))
            self._sites = []
            self._loaded = True  # Təkrar yükləmə cəhdinin qarşısını al
