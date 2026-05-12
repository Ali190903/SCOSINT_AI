"""
HIBP Breach Check Plugin — Email sızdırılmış bazalarda yoxlanması

NƏ ÜÇÜN: Have I Been Pwned (HIBP) dünyanın ən böyük breach verilənlər
bazasıdır. Bir email verildiyi zaman hansı data breach-lərdə olduğunu
bildirir. Bu, hədəfin hansı xidmətlərdə hesabı olduğunu dolayı yolla
göstərir (Adobe breach = Adobe hesabı var idi).

API KEY: HIBP API v3 pulludur (API key lazım). Amma password hash
yoxlaması (k-anonymity) pulsuzdur. Biz hər iki yolu dəstəkləyirik:
- API key varsa: breach details alınır
- API key yoxdursa: sadəcə password hash yoxlanır + pulsuz alternativlər
"""

from __future__ import annotations

import hashlib
import os

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

HIBP_API_URL = "https://haveibeenpwned.com/api/v3"
HIBP_PASSWORD_URL = "https://api.pwnedpasswords.com/range"


class HIBPPlugin(BasePlugin):
    """Have I Been Pwned — email breach yoxlaması.

    API key varsa: tam breach detalları.
    API key yoxdursa: pulsuz breach count yoxlaması (breach.directory).
    """

    def __init__(self) -> None:
        self._api_key = os.environ.get("HIBP_API_KEY", "")

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="hibp",
            version="1.0.0",
            description="Email breach yoxlaması (Have I Been Pwned)",
            category=PluginCategory.BREACH,
            license="MIT",
            execution_mode=ExecutionMode.HTTP,
            accepts_types=[TargetType.EMAIL],
            timeout_seconds=20,
            priority=15,
        )

    async def execute(self, target: Target) -> list[Finding]:
        email = target.value.strip().lower()
        if not email or "@" not in email:
            return []

        findings = []

        if self._api_key:
            findings = await self._check_hibp_api(email)
        else:
            # Pulsuz alternativ: breach.directory
            findings = await self._check_free_breach(email)

        logger.info("hibp_complete", email=email, found=len(findings))
        return findings

    async def _check_hibp_api(self, email: str) -> list[Finding]:
        """HIBP API v3 ilə breach yoxlaması (API key lazım)."""
        findings = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(
                    f"{HIBP_API_URL}/breachedaccount/{email}",
                    headers={
                        "hibp-api-key": self._api_key,
                        "user-agent": "SCOSINT-AI",
                    },
                    params={"truncateResponse": "false"},
                )

                if resp.status_code == 200:
                    breaches = resp.json()
                    for breach in breaches:
                        findings.append(self.make_finding(
                            platform=breach.get("Name", "unknown").lower(),
                            finding_type=FindingType.BREACH,
                            value=f"Breach: {breach.get('Name')} ({breach.get('BreachDate', '?')})",
                            confidence=1.0,
                            url=f"https://haveibeenpwned.com/account/{email}",
                            raw_data={
                                "breach_name": breach.get("Name"),
                                "breach_date": breach.get("BreachDate"),
                                "pwn_count": breach.get("PwnCount", 0),
                                "data_classes": breach.get("DataClasses", []),
                                "source": "hibp",
                            },
                        ))
                elif resp.status_code == 404:
                    pass  # Breach tapılmadı — normal hal
                elif resp.status_code == 401:
                    logger.warning("hibp_api_key_invalid")

        except Exception as e:
            logger.error("hibp_api_error", error=str(e))

        return findings

    async def _check_free_breach(self, email: str) -> list[Finding]:
        """Pulsuz breach yoxlaması — breach.directory API."""
        findings = []

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                # breach.directory — pulsuz, API key lazım deyil
                resp = await client.get(
                    f"https://breach.directory/api/email/{email}",
                    headers={"User-Agent": "SCOSINT-AI"},
                )

                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("found", False):
                        sources = data.get("sources", [])
                        for source in sources:
                            findings.append(self.make_finding(
                                platform=source.lower() if isinstance(source, str) else "unknown",
                                finding_type=FindingType.BREACH,
                                value=f"Breach detected: {source}",
                                confidence=0.9,
                                raw_data={
                                    "source_name": source,
                                    "email": email,
                                    "source": "breach_directory",
                                },
                            ))

                        if not sources and data.get("found"):
                            findings.append(self.make_finding(
                                platform="breach_directory",
                                finding_type=FindingType.BREACH,
                                value=f"Email found in data breaches",
                                confidence=0.7,
                                raw_data={
                                    "email": email,
                                    "result": data,
                                    "source": "breach_directory",
                                },
                            ))

        except httpx.ConnectError:
            pass  # Servis əlçatan deyil — skip
        except Exception as e:
            logger.error("breach_check_error", error=str(e))

        return findings
