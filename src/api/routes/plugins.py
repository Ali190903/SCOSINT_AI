"""Plugins API — plugin siyahısı və idarəsi."""

from __future__ import annotations

from fastapi import APIRouter, Request, HTTPException

router = APIRouter()


@router.get("/plugins")
async def list_plugins(request: Request):
    """Bütün plugin-lərin siyahısı (aktiv/deaktiv statusu ilə)."""
    manager = request.app.state.plugin_manager
    plugins = []
    for name, meta in manager.all_plugins.items():
        plugins.append({
            "name": meta.name,
            "version": meta.version,
            "description": meta.description,
            "category": meta.category.value,
            "license": meta.license,
            "execution_mode": meta.execution_mode.value,
            "accepts_types": [t.value for t in meta.accepts_types],
            "enabled": manager.is_enabled(name),
        })
    return {"plugins": plugins, "total": len(plugins)}


@router.put("/plugins/{name}/toggle")
async def toggle_plugin(name: str, request: Request):
    """Plugin-i aktiv/deaktiv et."""
    manager = request.app.state.plugin_manager
    if name not in manager.all_plugins:
        raise HTTPException(status_code=404, detail=f"Plugin '{name}' not found")

    if manager.is_enabled(name):
        manager.disable(name)
        return {"name": name, "enabled": False}
    else:
        manager.enable(name)
        return {"name": name, "enabled": True}
