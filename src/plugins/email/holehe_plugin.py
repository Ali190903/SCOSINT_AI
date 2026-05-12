"""
Holehe Plugin — Email ilə 120+ saytda hesab mövcudluğu yoxlaması (subprocess)

NƏ ÜÇÜN: Bir email verildiyi zaman həmin email-in hansı saytlarda qeydiyyatda
olduğunu bildirir. "Şifrəni unutdum" formalarını istifadə edir — hesab sahibinə
heç bir bildiriş getmir. Bu, email-dən rəqəmsal barmaq izini tapmağın ən
effektiv yoludur.

LİSENZİYA: GPLv3 — mütləq subprocess ilə çağırılmalıdır, birbaşa import
etsək bizim MIT kodumuz GPLv3-ə "yoluxar".
"""

from __future__ import annotations

import csv
import io
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


class HolehePlugin(BasePlugin):
    """Holehe CLI-ni subprocess olaraq çağırıb email hesab varlığını yoxlayır.

    GPLv3 lisenziyasına görə subprocess ilə izolasiya edilir.
    """

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="holehe",
            version="1.0.0",
            description="120+ saytda email hesab varlığı yoxlaması (Holehe)",
            category=PluginCategory.EMAIL,
            license="GPLv3",
            execution_mode=ExecutionMode.SUBPROCESS,
            accepts_types=[TargetType.EMAIL],
            timeout_seconds=120,
            priority=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        email = target.value.strip()
        if not email or "@" not in email:
            return []

        # Holehe-ni subprocess olaraq çağır, CSV output al
        cmd = [
            sys.executable, "-m", "holehe",
            email,
            "--csv",  # CSV formatında çıxış
            "--no-color",
        ]

        logger.info("holehe_scan_start", email=email)
        result = await self.run_subprocess(cmd, parse_json=False)

        if hasattr(result, "returncode"):
            if result.stderr and "TIMEOUT" in result.stderr:
                logger.warning("holehe_timeout", email=email)
                return []

        stdout = result.stdout if hasattr(result, "stdout") else str(result)
        findings = self._parse_output(stdout, email)
        logger.info("holehe_scan_complete", email=email, found=len(findings))
        return findings

    def _parse_output(self, output: str, email: str) -> list[Finding]:
        """Holehe çıxışını parse edir.

        Holehe stdout formatı (mətn):
        [+] site.com - Registered
        [-] other.com - Not Registered
        [x] error.com - Error
        """
        findings = []

        for line in output.splitlines():
            line = line.strip()

            # [+] ilə başlayanlar — hesab TAPILDI
            if "[+]" in line:
                # Format: [+] SiteName - Registered  və ya  [+] SiteName
                parts = line.split("[+]", 1)
                if len(parts) < 2:
                    continue
                rest = parts[1].strip()

                # "SiteName - Registered" və ya "SiteName"
                site_name = rest.split(" - ")[0].strip().split(" ")[0].strip()
                if not site_name:
                    continue

                findings.append(self.make_finding(
                    platform=site_name.lower().replace(".", "_"),
                    finding_type=FindingType.EMAIL,
                    value=f"{email} registered on {site_name}",
                    confidence=0.9,
                    url=f"https://{site_name}",
                    raw_data={
                        "site_name": site_name,
                        "email": email,
                        "status": "registered",
                        "source": "holehe",
                    },
                ))

        return findings
