"""
Gravatar Plugin — Email-dən profil şəkli və məlumat çıxarma (birbaşa HTTP)

NƏ ÜÇÜN: Gravatar dünyanın ən böyük avatar xidmətidir. WordPress, GitHub,
StackOverflow kimi saytlar istifadə edir. Email-dən MD5 hash hesablanır,
Gravatar API-sinə sorğu göndərilir — profil varsa şəkil URL-i və ad qaytarır.
Heç bir asılılıq yoxdur, sadəcə HTTP sorğu.
"""

from __future__ import annotations

import hashlib

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


class GravatarPlugin(BasePlugin):
    """Email-dən Gravatar profili çıxarır (birbaşa HTTP, asılılıq yox)."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="gravatar",
            version="1.0.0",
            description="Email-dən Gravatar profil şəkli və məlumatı",
            category=PluginCategory.EMAIL,
            license="MIT",
            execution_mode=ExecutionMode.HTTP,
            accepts_types=[TargetType.EMAIL],
            timeout_seconds=15,
            priority=5,  # Çox sürətli — ilk işləsin
        )

    async def execute(self, target: Target) -> list[Finding]:
        email = target.value.strip().lower()
        if not email or "@" not in email:
            return []

        email_hash = hashlib.md5(email.encode()).hexdigest()
        profile_url = f"https://gravatar.com/{email_hash}.json"

        findings = []

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(profile_url)

                if resp.status_code == 200:
                    data = resp.json()
                    entries = data.get("entry", [])
                    if entries:
                        entry = entries[0]
                        # Avatar URL
                        avatar = entry.get("thumbnailUrl", "")
                        if avatar:
                            findings.append(self.make_finding(
                                platform="gravatar",
                                finding_type=FindingType.AVATAR_URL,
                                value=avatar,
                                confidence=1.0,
                                url=f"https://gravatar.com/{email_hash}",
                                raw_data={"email_hash": email_hash, "source": "gravatar"},
                            ))

                        # Display name
                        display_name = entry.get("displayName", "")
                        if display_name:
                            findings.append(self.make_finding(
                                platform="gravatar",
                                finding_type=FindingType.FULL_NAME,
                                value=display_name,
                                confidence=0.95,
                                url=f"https://gravatar.com/{email_hash}",
                            ))

                        # Profildəki əlavə URL-lər (blog, sosial media)
                        for account in entry.get("accounts", []):
                            url = account.get("url", "")
                            shortname = account.get("shortname", "unknown")
                            if url:
                                findings.append(self.make_finding(
                                    platform=shortname.lower(),
                                    finding_type=FindingType.PROFILE_URL,
                                    value=url,
                                    confidence=0.9,
                                    url=url,
                                    raw_data={"source": "gravatar_linked"},
                                ))

        except httpx.TimeoutException:
            logger.warning("gravatar_timeout", email=email)
        except Exception as e:
            logger.error("gravatar_error", email=email, error=str(e))

        logger.info("gravatar_complete", email=email, found=len(findings))
        return findings
