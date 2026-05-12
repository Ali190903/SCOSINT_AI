"""
Scan API Routes — OSINT axtarış endpoint-ləri.

POST /scan — yeni scan başlat (sinxron, nəticəni birbaşa qaytarır)
             Gələcəkdə Celery ilə asinxron olacaq.
"""

from __future__ import annotations

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from src.core.models import ScanRequest, ScanResult

router = APIRouter()


class QuickScanRequest(BaseModel):
    """Sadələşdirilmiş scan sorğusu — tək bir dəyər göndərmək üçün."""
    value: str = Field(..., min_length=1, description="Axtarılacaq dəyər (username, email, phone)")
    type: str = Field(default="username", description="Dəyərin tipi: username, email, phone, name")


@router.post("/scan", response_model=ScanResult)
async def create_scan(req: QuickScanRequest, request: Request):
    """Yeni OSINT scan başlat.

    Hazırda sinxron işləyir — nəticəni birbaşa qaytarır.
    Gələcəkdə Celery task olaraq asinxron olacaq.
    """
    from src.core.models import Target, TargetType

    # Target yarat
    try:
        target_type = TargetType(req.type)
    except ValueError:
        target_type = TargetType.USERNAME

    target = Target(value=req.value, type=target_type)

    # Plugin Manager-dən scan icra et
    manager = request.app.state.plugin_manager
    result = await manager.execute_scan([target])

    return result


@router.post("/scan/advanced", response_model=ScanResult)
async def create_advanced_scan(req: ScanRequest, request: Request):
    """Ətraflı scan — çoxlu target, plugin filtrləmə."""
    manager = request.app.state.plugin_manager
    result = await manager.execute_scan(
        targets=req.targets,
        enabled_only=req.enabled_plugins,
        disabled_list=req.disabled_plugins,
    )
    return result
