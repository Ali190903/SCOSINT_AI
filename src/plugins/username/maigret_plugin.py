"""
Maigret Plugin — 3000+ saytda dərin username axtarışı (subprocess)

NƏ ÜÇÜN: Maigret ən əhatəli username enumeration alətidir — 3000+ sayt.
Sherlock/WhatsMyName-dən daha çox sayt yoxlayır və recursive axtarış edir
(tapılan profildən yeni username-lər çıxarıb onları da axtarır).

LİSENZİYA: MIT — subprocess ilə çağırırıq.

QEYD: Maigret ayrıca quraşdırılmalıdır: pip install maigret
Quraşdırılmayıbsa plugin avtomatik skip olur.
"""

from __future__ import annotations

import json
import sys

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


class MaigretPlugin(BasePlugin):
    """Maigret CLI-ni subprocess olaraq çağırır — 3000+ sayt."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="maigret",
            version="1.0.0",
            description="3000+ saytda dərin username axtarışı (Maigret)",
            category=PluginCategory.USERNAME,
            license="MIT",
            execution_mode=ExecutionMode.SUBPROCESS,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=300,  # Maigret uzun sürə bilər
            priority=25,  # WhatsMyName/Sherlock-dan sonra
        )

    async def execute(self, target: Target) -> list[Finding]:
        username = target.value.strip()
        if not username:
            return []

        cmd = [
            sys.executable, "-m", "maigret",
            username,
            "--json", "nul",  # Windows: /dev/null əvəzi
            "--no-color",
            "--timeout", "10",
        ]

        logger.info("maigret_scan_start", username=username)
        result = await self.run_subprocess(cmd, parse_json=False)

        if hasattr(result, "returncode"):
            if result.stderr and "Command not found" in result.stderr:
                logger.warning("maigret_not_installed")
                return []
            if result.stderr and "No module named" in result.stderr:
                logger.warning("maigret_not_installed", stderr=result.stderr[:100])
                return []

        stdout = result.stdout if hasattr(result, "stdout") else str(result)
        findings = self._parse_output(stdout, username)
        logger.info("maigret_scan_complete", username=username, found=len(findings))
        return findings

    def _parse_output(self, output: str, username: str) -> list[Finding]:
        """Maigret text çıxışını parse edir.

        Format:
        [+] site_name: url
        [-] site_name: Not found
        """
        findings = []

        for line in output.splitlines():
            line = line.strip()
            if not line:
                continue

            # [+] — profil tapıldı
            if "[+]" in line:
                parts = line.split("[+]", 1)
                if len(parts) < 2:
                    continue
                rest = parts[1].strip()

                # "SiteName: URL" və ya "SiteName - URL"
                for sep in [":", " - "]:
                    if sep in rest:
                        site_part, url_part = rest.split(sep, 1)
                        site_name = site_part.strip()
                        url = url_part.strip()
                        if url.startswith("http"):
                            findings.append(self.make_finding(
                                platform=site_name.lower().replace(" ", "_"),
                                finding_type=FindingType.PROFILE_URL,
                                value=url,
                                confidence=0.85,
                                url=url,
                                raw_data={
                                    "site_name": site_name,
                                    "source": "maigret",
                                },
                            ))
                            break

        return findings
