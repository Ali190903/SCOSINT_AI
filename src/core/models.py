"""
SCOSINT_AI Data Models

WHY: Bütün sistem bu model-lərlə danışır. Plugin nə qaytarmalıdır? Scan nə
qəbul edir? Bu suallara cavab burada. Pydantic validasiya verir — səhv data
sistemə girə bilməz. Hər plugin eyni Finding formatında cavab qaytarır ki,
nəticələr aggregate edilə bilsin.

DESIGN: Target → Plugin(lər) → Finding(lər) → ScanResult
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field


# ============================================================
# Enums — sistemdəki bütün sabit tiplər
# ============================================================


class TargetType(str, Enum):
    """Giriş məlumatının tipi. Plugin-lər buna görə filtrləyir."""

    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    NAME = "name"       # ad + soyad (alias generasiya ilə)
    IMAGE = "image"     # şəkil faylının yolu və ya URL
    URL = "url"         # birbaşa profil URL-i


class ScanStatus(str, Enum):
    """Scan-ın lifecycle state-ləri."""

    PENDING = "pending"         # Yaradılıb, hələ başlamayıb
    RUNNING = "running"         # Plugin-lər işləyir
    COMPLETED = "completed"     # Bütün plugin-lər tamamladı
    FAILED = "failed"           # Kritik xəta — scan dayandı
    CANCELLED = "cancelled"     # İstifadəçi dayandırdı


class PluginCategory(str, Enum):
    """Plugin kateqoriyası — UI-da qruplaşdırma və queue routing üçün."""

    USERNAME = "username"
    EMAIL = "email"
    PHONE = "phone"
    SEARCH = "search"
    WEB_SCRAPER = "web_scraper"
    IMAGE = "image"
    BREACH = "breach"
    ALIAS = "alias"
    AI = "ai"


class ExecutionMode(str, Enum):
    """Plugin-in necə icra edildiyini bildirir — lisenziya strategiyası üçün."""

    DIRECT = "direct"           # Birbaşa Python import (MIT/Apache)
    SUBPROCESS = "subprocess"   # Ayrı proses (GPLv3 izolasiyası)
    BROWSER = "browser"         # Playwright browser lazımdır
    HTTP = "http"               # Xarici API-yə HTTP sorğu


class FindingType(str, Enum):
    """Tapıntının tipi — UI-da icon/format seçimi üçün."""

    PROFILE_URL = "profile_url"
    USERNAME = "username"
    FULL_NAME = "full_name"
    BIO = "bio"
    AVATAR_URL = "avatar_url"
    POST = "post"
    EMAIL = "email"
    PHONE = "phone"
    LOCATION = "location"
    WEBSITE = "website"
    BREACH = "breach"
    IMAGE_MATCH = "image_match"
    METADATA = "metadata"
    AI_SUMMARY = "ai_summary"
    RISK_SCORE = "risk_score"
    ALIAS = "alias"
    RAW = "raw"


# ============================================================
# Core Data Models
# ============================================================


class Target(BaseModel):
    """Scan üçün hədəf — bir nəfərin identifikatoru.

    Tək bir Target bir neçə TargetType-a sahib ola bilməz.
    Bir nəfərin email+phone+ad-ı varsa, hər biri ayrı Target-dir,
    lakin eyni scan_id altında qruplanır.
    """

    value: str = Field(..., min_length=1, description="Axtarılacaq dəyər")
    type: TargetType
    metadata: dict = Field(
        default_factory=dict,
        description="Əlavə kontekst: ad, soyad, ölkə, doğum tarixi və s."
    )


class PluginMeta(BaseModel):
    """Plugin haqqında metadata — plugin manager bu məlumata əsasən qərar verir.

    name: unikal identifikator (məs. "sherlock", "holehe")
    category: hansı kateqoriyaya aiddir
    execution_mode: necə işlədilir (lisenziya izolasiyası)
    accepts_types: hansı TargetType-ları qəbul edir
    enabled_by_default: plugin default olaraq aktiv olsun?
    """

    name: str = Field(..., pattern=r"^[a-z][a-z0-9_]{1,49}$")
    version: str = Field(default="0.1.0")
    description: str = Field(default="")
    category: PluginCategory
    license: str = Field(default="MIT")
    execution_mode: ExecutionMode
    accepts_types: list[TargetType]
    enabled_by_default: bool = Field(default=True)
    timeout_seconds: int = Field(default=120, ge=5, le=600)
    priority: int = Field(
        default=50, ge=0, le=100,
        description="0=ən yüksək prioritet, 100=ən aşağı"
    )


class Finding(BaseModel):
    """Bir plugin-in tapdığı tək bir nəticə.

    Bütün plugin-lər nəticələrini bu formatda qaytarır. Bu standartlaşdırma
    sayəsində 30+ fərqli plugin-dən gələn nəticələr eyni cədvəldə
    aggregate edilə bilir.

    confidence: 0.0 (ehtimal) → 1.0 (mütləq dəqiq)
    """

    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    source_plugin: str = Field(..., description="Tapan plugin-in adı")
    platform: str = Field(default="unknown", description="instagram, linkedin, vk...")
    finding_type: FindingType
    value: str = Field(..., description="Tapılan əsas dəyər")
    confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    url: str | None = Field(default=None, description="Əlaqəli URL (varsa)")
    raw_data: dict = Field(default_factory=dict, description="Çiy/əlavə data")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def __repr__(self) -> str:
        return f"Finding({self.source_plugin}:{self.platform}:{self.finding_type.value}={self.value!r})"


# ============================================================
# Scan Models
# ============================================================


class ScanRequest(BaseModel):
    """API-dən gələn scan sorğusu."""

    targets: list[Target] = Field(..., min_length=1, max_length=10)
    enabled_plugins: list[str] | None = Field(
        default=None,
        description="Yalnız bu plugin-ləri işlət. None = hamısını işlət."
    )
    disabled_plugins: list[str] | None = Field(
        default=None,
        description="Bu plugin-ləri deaktiv et."
    )


class ScanResult(BaseModel):
    """Tamamlanmış scan-ın nəticəsi."""

    scan_id: str = Field(default_factory=lambda: uuid.uuid4().hex)
    status: ScanStatus = Field(default=ScanStatus.PENDING)
    targets: list[Target] = Field(default_factory=list)
    findings: list[Finding] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
    plugins_executed: list[str] = Field(default_factory=list)
    started_at: datetime | None = Field(default=None)
    completed_at: datetime | None = Field(default=None)
    duration_seconds: float | None = Field(default=None)

    @property
    def findings_count(self) -> int:
        return len(self.findings)

    @property
    def unique_platforms(self) -> set[str]:
        return {f.platform for f in self.findings}
