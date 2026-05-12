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
        import os
        import tempfile
        import csv

        tmp_dir = tempfile.mkdtemp(prefix="sherlock_")
        # Sherlock CSV faylını avtomatik olaraq {username}.csv kimi adlandırır
        csv_path = os.path.join(tmp_dir, f"{username}.csv")

        cmd = [
            sys.executable, "-m", "sherlock_project",
            username,
            "--csv",
            "--folderoutput", tmp_dir,
            "--timeout", "10",
            "--no-color",
        ]

        logger.info("sherlock_scan_start", username=username, tmp_dir=tmp_dir)
        
        # Windows-da unicode çöküşlərinin qarşısını almaq üçün qlobal UTF-8 ayarı
        env = os.environ.copy()
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        
        result = await self.run_subprocess(cmd, parse_json=False, env=env)

        findings = []
        try:
            if os.path.exists(csv_path) and os.path.getsize(csv_path) > 0:
                with open(csv_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Sherlock CSV formatı: username,name,url_main,url_user,exists,http_status,response_time_s
                        # Əgər csv output formalaşıbsa, o deməkdir ki profil tapılıb (exists=yes)
                        url = row.get("url_user", "")
                        site = row.get("name", "Unknown")
                        if url.startswith("http"):
                            findings.append(self.make_finding(
                                platform=site.lower().replace(" ", "_"),
                                finding_type=FindingType.PROFILE_URL,
                                value=url,
                                confidence=0.85,  # Sherlock-da false positive ehtimalı Maigretdən az da olsa var
                                url=url,
                                raw_data={"site_name": site, "source": "sherlock"},
                            ))
        except Exception as e:
            logger.error("sherlock_csv_parse_error", error=str(e))
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)
            try:
                os.rmdir(tmp_dir)
            except OSError:
                pass

        logger.info("sherlock_scan_complete", username=username, found=len(findings))
        return findings
