"""
Phone Number Lookup Plugin — Telefon nömrəsindən OSINT (birbaşa HTTP)

NƏ ÜÇÜN: Telefon nömrəsi verildiyi zaman NumVerify/NumLookupAPI kimi
pulsuz servislər vasitəsilə ölkə, operator, xətt tipi müəyyən edir.
Bundan əlavə, sosial mediada telefon nömrəsinin qeydiyyatda olub-
olmadığını WhatsApp, Telegram kimi platformalarda yoxlaya bilir.

Hazırda: Nömrə formatını yoxlayır, ölkə kodunu çıxarır,
əsas metadata-nı qaytarır. API key opsionaldır.
"""

from __future__ import annotations

import re

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

# Ölkə kodları (əsas)
COUNTRY_CODES = {
    "1": "US/CA", "7": "RU", "20": "EG", "27": "ZA",
    "30": "GR", "31": "NL", "32": "BE", "33": "FR",
    "34": "ES", "36": "HU", "39": "IT", "40": "RO",
    "41": "CH", "43": "AT", "44": "GB", "45": "DK",
    "46": "SE", "47": "NO", "48": "PL", "49": "DE",
    "51": "PE", "52": "MX", "53": "CU", "54": "AR",
    "55": "BR", "56": "CL", "57": "CO", "58": "VE",
    "60": "MY", "61": "AU", "62": "ID", "63": "PH",
    "64": "NZ", "65": "SG", "66": "TH", "81": "JP",
    "82": "KR", "84": "VN", "86": "CN", "90": "TR",
    "91": "IN", "92": "PK", "93": "AF", "94": "LK",
    "95": "MM", "98": "IR", "212": "MA", "213": "DZ",
    "216": "TN", "218": "LY", "220": "GM", "234": "NG",
    "249": "SD", "254": "KE", "255": "TZ", "256": "UG",
    "260": "ZM", "263": "ZW", "351": "PT", "352": "LU",
    "353": "IE", "354": "IS", "355": "AL", "358": "FI",
    "359": "BG", "370": "LT", "371": "LV", "372": "EE",
    "380": "UA", "381": "RS", "385": "HR", "386": "SI",
    "387": "BA", "389": "MK", "420": "CZ", "421": "SK",
    "852": "HK", "853": "MO", "855": "KH", "856": "LA",
    "880": "BD", "886": "TW", "960": "MV", "961": "LB",
    "962": "JO", "963": "SY", "964": "IQ", "965": "KW",
    "966": "SA", "967": "YE", "968": "OM", "971": "AE",
    "972": "IL", "973": "BH", "974": "QA", "992": "TJ",
    "993": "TM", "994": "AZ", "995": "GE", "996": "KG",
    "998": "UZ",
}


class PhoneLookupPlugin(BasePlugin):
    """Telefon nömrəsindən ölkə, operator, format məlumatı çıxarır."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="phone_lookup",
            version="1.0.0",
            description="Telefon nömrəsindən ölkə, operator məlumatı",
            category=PluginCategory.PHONE,
            license="MIT",
            execution_mode=ExecutionMode.HTTP,
            accepts_types=[TargetType.PHONE],
            timeout_seconds=20,
            priority=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        raw_phone = target.value.strip()
        if not raw_phone:
            return []

        # Nömrəni təmizlə
        phone = re.sub(r'[^\d+]', '', raw_phone)
        if not phone:
            return []

        # + ilə başlamasa əlavə et
        if not phone.startswith('+'):
            phone = '+' + phone

        digits = phone.lstrip('+')
        findings = []

        # Ölkə kodunu tap
        country = None
        country_code = None
        for code_len in (3, 2, 1):
            prefix = digits[:code_len]
            if prefix in COUNTRY_CODES:
                country = COUNTRY_CODES[prefix]
                country_code = prefix
                break

        if country:
            findings.append(self.make_finding(
                platform="phone_analysis",
                finding_type=FindingType.LOCATION,
                value=f"Country: {country} (+{country_code})",
                confidence=0.95,
                raw_data={
                    "phone": phone,
                    "country_code": country_code,
                    "country": country,
                    "source": "phone_lookup",
                },
            ))

        findings.append(self.make_finding(
            platform="phone_analysis",
            finding_type=FindingType.METADATA,
            value=f"Phone: {phone} (digits: {len(digits)})",
            confidence=1.0,
            raw_data={
                "phone_normalized": phone,
                "digits_only": digits,
                "digit_count": len(digits),
                "source": "phone_lookup",
            },
        ))

        # WhatsApp yoxlaması — profil şəkli URL-i ilə
        wa_result = await self._check_whatsapp(digits)
        if wa_result:
            findings.append(wa_result)

        # Telegram yoxlaması
        tg_result = await self._check_telegram(phone)
        if tg_result:
            findings.append(tg_result)

        logger.info("phone_lookup_complete", phone=phone, found=len(findings))
        return findings

    async def _check_whatsapp(self, digits: str) -> Finding | None:
        """WhatsApp-da nömrənin mövcudluğunu yoxlayır."""
        try:
            url = f"https://wa.me/{digits}"
            async with httpx.AsyncClient(timeout=10, follow_redirects=False) as client:
                resp = await client.head(url)
                # WhatsApp mövcud nömrələr üçün 200/302 qaytarır
                if resp.status_code in (200, 301, 302):
                    return self.make_finding(
                        platform="whatsapp",
                        finding_type=FindingType.PROFILE_URL,
                        value=url,
                        confidence=0.6,  # Aşağı — sadəcə link mövcuddur
                        url=url,
                        raw_data={"source": "phone_lookup", "service": "whatsapp"},
                    )
        except Exception:
            pass
        return None

    async def _check_telegram(self, phone: str) -> Finding | None:
        """Telegram-da nömrənin mövcudluğunu yoxlayır (əsas format)."""
        # Telegram birbaşa telefon axtarışı dəstəkləmir API olmadan
        # Amma nömrə formatını saxlayırıq gələcək Playwright plugin üçün
        return None
