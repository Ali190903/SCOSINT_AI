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
import os
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

        import tempfile
        import os
        
        # Nəticə üçün müvəqqəti qovluq yaradırıq
        tmp_dir = tempfile.mkdtemp(prefix="maigret_")
        
        # Maigret `--json simple` olanda `report_{username}_simple.json` yaradır
        expected_report_path = os.path.join(tmp_dir, f"report_{username}_simple.json")

        cmd = [
            sys.executable, "-m", "maigret",
            username,
            "--no-progressbar",
            "--json", "simple",
            "--folderoutput", tmp_dir,
            "--no-color",
            "--timeout", "10",
        ]

        logger.info("maigret_scan_start", username=username, tmp_dir=tmp_dir)
        
        # Windows-da unicode çöküşünün qarşısını almaq üçün UTF-8 məcbur edilir
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        result = await self.run_subprocess(cmd, parse_json=False, env=env)

        findings = []
        try:
            if os.path.exists(expected_report_path) and os.path.getsize(expected_report_path) > 0:
                with open(expected_report_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    findings = self._parse_json(data, username)
        except Exception as e:
            logger.error("maigret_json_parse_error", error=str(e))
        finally:
            # Faylı və qovluğu mütləq silirik
            if os.path.exists(expected_report_path):
                os.remove(expected_report_path)
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

        logger.info("maigret_scan_complete", username=username, found=len(findings))
        return findings

    def _parse_json(self, data: dict, username: str) -> list[Finding]:
        """Maigret JSON çıxışını parse edir."""
        findings = []
        
        # Maigret simple JSON formatı: {"SiteName": {"status": {"status": "Claimed", "url": "..."}}}
        for site_name, info in data.items():
            if not isinstance(info, dict):
                continue
                
            status_obj = info.get("status", {})
            if status_obj.get("status") in ("Found", "Claimed"):
                url = status_obj.get("url", info.get("url_user", ""))
                if url.startswith("http"):
                    findings.append(self.make_finding(
                        platform=site_name.lower().replace(" ", "_"),
                        finding_type=FindingType.PROFILE_URL,
                        value=url,
                        confidence=0.9,
                        url=url,
                        raw_data={
                            "site_name": site_name,
                            "source": "maigret",
                        },
                    ))

        return findings
