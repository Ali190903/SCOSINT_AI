"""
Alias Generator Plugin — Adın bütün mümkün yazılış formalarını yaradır

NƏ ÜÇÜN: Gömrük kontekstində ən böyük problem insanların adlarının fərqli
dillər/əlifbalarda fərqli yazılmasıdır. "Məhəmməd" → Muhammad, Mohammed,
Mohamed, Muhammed, Mehmed... Bu plugin bir ad verildiyi zaman bütün
mümkün fonetik və transliterasiya variantlarını yaradır.

NECƏ: Kiril → Latın, Latın → Kiril transliterasiyası, ümumi ad variantları,
username format generasiyası (ad.soyad, ad_soyad, adsoyad, ad123, və s.)
"""

from __future__ import annotations

import re
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

# Ümumi ad variantları (fonetik yaxın)
NAME_VARIANTS = {
    "muhammad": ["mohammed", "mohamed", "mehmed", "mehmet", "muhammet", "muhammed", "mohammad"],
    "ahmed": ["ahmad", "ahmet", "achmed", "achmad"],
    "ali": ["aly", "alee"],
    "hussein": ["husain", "husein", "hüseyin", "huseyn", "hossein"],
    "hasan": ["hassan", "hasen", "hassen"],
    "ibrahim": ["ebrahim", "abrahim", "abraham", "avram"],
    "ismail": ["ismael", "ishmael"],
    "yusuf": ["yusif", "yousef", "youssef", "joseph", "yosef", "iosif"],
    "omar": ["umar", "omer", "ömer"],
    "fatima": ["fatimah", "fatime", "fatma"],
    "alexander": ["aleksandr", "aleksander", "alejandro", "alessandro"],
    "john": ["jon", "jan", "jean", "juan", "ivan", "giovanni", "hans", "yohannes"],
    "michael": ["mikhail", "mikail", "miguel", "michel", "michal"],
    "david": ["davit", "dawid", "davud", "daud"],
    "george": ["georgiy", "georgi", "jorge", "jörg", "giorgi"],
    "peter": ["pyotr", "piotr", "pedro", "pietro", "petar"],
    "paul": ["pavel", "pablo", "paolo", "pawel"],
    "nicholas": ["nikolay", "nikolai", "nikolas", "nicolás", "nicola"],
    "william": ["wilhelm", "guillermo", "gulielmo"],
    "james": ["jacob", "jakov", "yakov", "yakub", "jaime", "giacomo"],
    "robert": ["roberto"],
    "sergey": ["sergei", "serge", "sergio"],
    "dmitry": ["dimitri", "dimitry", "dmitri"],
    "andrey": ["andrei", "andrew", "andres", "andrea", "andreas"],
    "vladimir": ["volodymyr", "wladimir"],
    "natalia": ["natalya", "natalie", "nathalie"],
    "elena": ["helen", "helena", "yelena", "alena"],
    "maria": ["mary", "marie", "mariya", "miriam"],
    "anna": ["anne", "ana", "hanna", "hannah"],
}

# Kiril → Latın transliterasiyası
CYRILLIC_TO_LATIN = {
    "а": "a", "б": "b", "в": "v", "г": "g", "д": "d",
    "е": "e", "ё": "yo", "ж": "zh", "з": "z", "и": "i",
    "й": "y", "к": "k", "л": "l", "м": "m", "н": "n",
    "о": "o", "п": "p", "р": "r", "с": "s", "т": "t",
    "у": "u", "ф": "f", "х": "kh", "ц": "ts", "ч": "ch",
    "ш": "sh", "щ": "shch", "ъ": "", "ы": "y", "ь": "",
    "э": "e", "ю": "yu", "я": "ya",
}

# Azərbaycan xüsusi hərfləri
AZ_TO_LATIN = {
    "ə": "a", "ğ": "g", "ı": "i", "ö": "o", "ü": "u",
    "ş": "sh", "ç": "ch", "ä": "a", "ñ": "n",
}


class AliasGeneratorPlugin(BasePlugin):
    """Ad/soyaddan bütün mümkün username variantlarını yaradır."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="alias_generator",
            version="1.0.0",
            description="Adın fonetik variantları və username formatları",
            category=PluginCategory.ALIAS,
            license="MIT",
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.NAME],
            timeout_seconds=10,
            priority=5,  # Çox sürətli — ilk işləsin
        )

    async def execute(self, target: Target) -> list[Finding]:
        name = target.value.strip().lower()
        if not name:
            return []

        parts = name.split()
        first_name = parts[0] if parts else ""
        last_name = parts[-1] if len(parts) > 1 else ""

        aliases = set()

        # 1. Fonetik variantlar
        for part in parts:
            aliases.update(self._get_name_variants(part))

        # 2. Transliterasiya
        transliterated = self._transliterate(name)
        if transliterated != name:
            aliases.add(transliterated)

        # 3. Username formatları
        if first_name and last_name:
            aliases.update(self._generate_usernames(first_name, last_name))
            # Variant adlar ilə də username-lər yarat
            for variant in self._get_name_variants(first_name):
                aliases.update(self._generate_usernames(variant, last_name))

        # Boş və orijinalı sil
        aliases.discard("")
        aliases.discard(name)

        findings = []
        for alias in sorted(aliases):
            findings.append(self.make_finding(
                platform="alias_generator",
                finding_type=FindingType.ALIAS,
                value=alias,
                confidence=0.5,
                raw_data={
                    "original_name": name,
                    "source": "alias_generator",
                },
            ))

        logger.info("alias_generated", name=name, count=len(findings))
        return findings

    def _get_name_variants(self, name: str) -> set[str]:
        """Bir adın fonetik variantlarını qaytarır."""
        variants = {name}
        name_lower = name.lower()

        for base, alts in NAME_VARIANTS.items():
            if name_lower == base:
                variants.update(alts)
            elif name_lower in alts:
                variants.add(base)
                variants.update(alts)

        return variants

    def _transliterate(self, text: str) -> str:
        """Kiril/Azərbaycan hərflərini Latına çevirir."""
        result = []
        for char in text.lower():
            if char in CYRILLIC_TO_LATIN:
                result.append(CYRILLIC_TO_LATIN[char])
            elif char in AZ_TO_LATIN:
                result.append(AZ_TO_LATIN[char])
            else:
                result.append(char)
        return "".join(result)

    def _generate_usernames(self, first: str, last: str) -> set[str]:
        """Ad+soyaddan mümkün username formatlarını yaradır."""
        first = re.sub(r'[^a-z0-9]', '', first)
        last = re.sub(r'[^a-z0-9]', '', last)
        if not first or not last:
            return set()

        return {
            f"{first}{last}",           # adsoyad
            f"{first}.{last}",          # ad.soyad
            f"{first}_{last}",          # ad_soyad
            f"{first}-{last}",          # ad-soyad
            f"{last}{first}",           # soyadad
            f"{last}.{first}",          # soyad.ad
            f"{first[0]}{last}",        # asoyad
            f"{first}{last[0]}",        # ads
            f"{first[0]}.{last}",       # a.soyad
            f"{first}{last}1",          # adsoyad1
            f"{first}_{last}_",         # ad_soyad_
            f"{first[0]}{first[1] if len(first) > 1 else ''}{last}",  # absoyad
        }
