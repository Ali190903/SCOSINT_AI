"""
Sherlock Plugin — 400+ saytda sürətli username axtarışı (subprocess)

NƏ ÜÇÜN: Sherlock ən sürətli username enumeration alətidir (~400 sayt).
WhatsMyName daha çox sayt əhatə edir, amma Sherlock daha az false-positive
verir. İkisini paralel işlədib nəticələri birləşdirmək ən yaxşı yanaşmadır.

LİSENZİYA: MIT — subprocess ilə çağırırıq (əlavə təhlükəsizlik üçün,
birbaşa import da mümkün olardı amma subprocess bütün plugin-lər üçün
vahid pattern saxlayır).
"""

from __future__ import annotations

import json
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


class SherlockPlugin(BasePlugin):
    """Sherlock CLI-ni subprocess olaraq çağırıb nəticələri parse edir."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="sherlock",
            version="1.0.0",
            description="400+ saytda sürətli username axtarışı (Sherlock)",
            category=PluginCategory.USERNAME,
            license="MIT",
            execution_mode=ExecutionMode.SUBPROCESS,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=120,
            priority=15,
        )

    async def execute(self, target: Target) -> list[Finding]:
        username = target.value.strip()
        if not username:
            return []
        import sys

        cmd = [
            sys.executable, "-m", "sherlock_project",
            username,
            "--print-found",
            "--timeout", "10",
            "--no-color",
        ]

        logger.info("sherlock_scan_start", username=username)
        result = await self.run_subprocess(cmd, parse_json=False)

        if hasattr(result, "returncode") and result.returncode != 0:
            # JSON parse birbaşa cəhd edək — bəzi versiyalarda exit code fərqlidir
            if not result.stdout.strip():
                logger.warning("sherlock_no_output", stderr=result.stderr[:200] if result.stderr else "")
                return []

        # Sherlock JSON output-u parse et
        findings = self._parse_output(result.stdout if hasattr(result, "stdout") else str(result), username)
        logger.info("sherlock_scan_complete", username=username, found=len(findings))
        return findings

    def _parse_output(self, output: str, username: str) -> list[Finding]:
        """Sherlock stdout-unu parse edib Finding-lərə çevirir.

        Sherlock --json - formatı:
        {"sitename": {"url_user": "...", "status": "Claimed", ...}, ...}
        """
        findings = []

        try:
            data = json.loads(output)
        except (json.JSONDecodeError, TypeError):
            # JSON olmayan çıxışı sətir-sətir parse et
            return self._parse_text_output(output, username)

        if isinstance(data, dict):
            for site_name, info in data.items():
                if not isinstance(info, dict):
                    continue
                status = info.get("status", "")
                if status == "Claimed":
                    url = info.get("url_user", "")
                    if url:
                        findings.append(self.make_finding(
                            platform=site_name.lower(),
                            finding_type=FindingType.PROFILE_URL,
                            value=url,
                            confidence=0.9,
                            url=url,
                            raw_data={"site_name": site_name, "source": "sherlock"},
                        ))

        return findings

    def _parse_text_output(self, output: str, username: str) -> list[Finding]:
        """JSON parse uğursuz olsa, mətn çıxışını parse et.

        Sherlock text output formatı:
        [+] SiteName: https://site.com/username
        """
        findings = []
        for line in output.splitlines():
            line = line.strip()
            if line.startswith("[+]") or line.startswith("[*]"):
                parts = line.split(":", 1)
                if len(parts) == 2:
                    site_part = parts[0].replace("[+]", "").replace("[*]", "").strip()
                    url = parts[1].strip()
                    if url.startswith("http"):
                        findings.append(self.make_finding(
                            platform=site_part.lower(),
                            finding_type=FindingType.PROFILE_URL,
                            value=url,
                            confidence=0.85,
                            url=url,
                            raw_data={"site_name": site_part, "source": "sherlock"},
                        ))
        return findings
