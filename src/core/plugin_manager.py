"""
SCOSINT_AI Plugin Manager — Microkernel Brain

WHY: Bu fayl sistemin beynidir. Plugin-ləri tapır, yükləyir, idarə edir
və scan zamanı uyğun plugin-ləri target-ə görə seçib işlədir.

DESIGN: Microkernel pattern — bu manager heç bir OSINT məntiqi bilmir.
O yalnız bilir ki: plugin-lər var, onları tapmaq lazımdır, target-ə uyğun
olanları seçmək lazımdır, timeout ilə işlətmək lazımdır, nəticələri
toplamaq lazımdır.

PLUGIN DISCOVERY: src/plugins/ altındakı bütün *_plugin.py fayllarını
avtomatik skan edir və içindəki BasePlugin subclass-larını tapır.
"""

from __future__ import annotations

import asyncio
import importlib
import inspect
import pkgutil
import time
from pathlib import Path
from typing import Any

import structlog

from src.core.exceptions import PluginExecutionError, PluginLoadError
from src.core.models import Finding, PluginMeta, ScanResult, ScanStatus, Target
from src.core.plugin_base import BasePlugin

logger = structlog.get_logger(__name__)


class PluginManager:
    """Plugin lifecycle manager — discover, load, execute, aggregate.

    Usage:
        manager = PluginManager()
        manager.discover_plugins()         # Bütün plugin-ləri tap
        manager.enable("sherlock")         # Aktivləşdir
        manager.disable("maigret")        # Deaktivləşdir
        results = await manager.execute_scan(targets)  # Scan
    """

    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}   # name → instance
        self._disabled: set[str] = set()             # deaktiv plugin adları

    # ================================================================
    # Plugin Discovery — plugin-ləri avtomatik tap və yüklə
    # ================================================================

    def discover_plugins(self, plugins_package: str = "src.plugins") -> int:
        """src/plugins/ altındakı bütün plugin-ləri tapır və yükləyir.

        Strategiya:
        1. plugins_package-in bütün sub-package-lərini (username/, email/...) skan et
        2. Hər sub-package-dəki *_plugin.py modullarını import et
        3. Hər modulda BasePlugin subclass-ını tap
        4. Instance yarat və qeyd et

        Returns:
            Uğurla yüklənmiş plugin sayı
        """
        loaded_count = 0

        try:
            package = importlib.import_module(plugins_package)
        except ModuleNotFoundError:
            logger.warning("plugins_package_not_found", package=plugins_package)
            return 0

        package_path = Path(package.__file__).parent if package.__file__ else None
        if not package_path:
            return 0

        # Sub-package-ləri skan et (username/, email/, phone/, ...)
        for sub_info in pkgutil.iter_modules([str(package_path)]):
            if not sub_info.ispkg:
                continue

            sub_package_path = package_path / sub_info.name

            # Hər sub-package-dəki *_plugin.py modullarını tap
            for module_info in pkgutil.iter_modules([str(sub_package_path)]):
                if not module_info.name.endswith("_plugin"):
                    continue

                module_name = f"{plugins_package}.{sub_info.name}.{module_info.name}"

                try:
                    loaded_count += self._load_plugin_from_module(module_name)
                except Exception as e:
                    logger.error(
                        "plugin_load_failed",
                        module=module_name,
                        error=str(e),
                    )

        logger.info("plugin_discovery_complete", loaded=loaded_count, total=len(self._plugins))
        return loaded_count

    def _load_plugin_from_module(self, module_name: str) -> int:
        """Bir moduldan BasePlugin subclass-larını tapıb yükləyir."""
        count = 0

        try:
            module = importlib.import_module(module_name)
        except Exception as e:
            raise PluginLoadError(f"Cannot import {module_name}: {e}") from e

        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BasePlugin)
                and obj is not BasePlugin
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    plugin_name = instance.meta.name

                    if plugin_name in self._plugins:
                        logger.warning(
                            "plugin_name_conflict",
                            name=plugin_name,
                            existing=type(self._plugins[plugin_name]).__name__,
                            new=obj.__name__,
                        )
                        continue

                    self._plugins[plugin_name] = instance

                    # Default deaktiv olanları disable et
                    if not instance.meta.enabled_by_default:
                        self._disabled.add(plugin_name)

                    logger.info(
                        "plugin_loaded",
                        name=plugin_name,
                        category=instance.meta.category.value,
                        mode=instance.meta.execution_mode.value,
                    )
                    count += 1

                except Exception as e:
                    logger.error("plugin_instantiation_failed", cls=obj.__name__, error=str(e))

        return count

    def register_plugin(self, plugin: BasePlugin) -> None:
        """Plugin-i manual olaraq qeydiyyata al (test və runtime üçün)."""
        name = plugin.meta.name
        self._plugins[name] = plugin
        if not plugin.meta.enabled_by_default:
            self._disabled.add(name)
        logger.info("plugin_registered", name=name)

    # ================================================================
    # Plugin State Management
    # ================================================================

    def enable(self, name: str) -> bool:
        """Plugin-i aktivləşdir."""
        if name not in self._plugins:
            return False
        self._disabled.discard(name)
        return True

    def disable(self, name: str) -> bool:
        """Plugin-i deaktivləşdir."""
        if name not in self._plugins:
            return False
        self._disabled.add(name)
        return True

    def is_enabled(self, name: str) -> bool:
        """Plugin aktiv olub-olmadığını yoxla."""
        return name in self._plugins and name not in self._disabled

    @property
    def all_plugins(self) -> dict[str, PluginMeta]:
        """Bütün plugin-lərin metadata-sı."""
        return {name: p.meta for name, p in self._plugins.items()}

    @property
    def enabled_plugins(self) -> list[BasePlugin]:
        """Yalnız aktiv plugin-lərin siyahısı (prioritetə görə sıralı)."""
        return sorted(
            [p for name, p in self._plugins.items() if name not in self._disabled],
            key=lambda p: p.meta.priority,
        )

    # ================================================================
    # Scan Execution — əsl iş burada baş verir
    # ================================================================

    async def execute_scan(
        self,
        targets: list[Target],
        enabled_only: list[str] | None = None,
        disabled_list: list[str] | None = None,
    ) -> ScanResult:
        """Bütün uyğun plugin-ləri target-lərə qarşı işlədir.

        Strategiya:
        1. Hər target üçün uyğun plugin-ləri filtrlə (accepts + enabled)
        2. Bütün (target, plugin) cütlərini paralel işlət
        3. Hər birini timeout ilə qoru
        4. Nəticələri ScanResult-da topla

        Args:
            targets: Axtarılacaq hədəflər
            enabled_only: Yalnız bu plugin-ləri işlət (None = hamısını)
            disabled_list: Bu plugin-ləri istisna et

        Returns:
            ScanResult — bütün tapıntılar, xətalar, statistikalar
        """
        result = ScanResult(targets=targets, status=ScanStatus.RUNNING)
        result.started_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )

        start_time = time.monotonic()

        # Plugin filtrləmə
        active_plugins = self._resolve_active_plugins(enabled_only, disabled_list)

        # Bütün (target, plugin) task-larını yığ
        tasks: list[tuple[str, asyncio.Task[list[Finding]]]] = []

        for target in targets:
            for plugin in active_plugins:
                if not plugin.accepts(target):
                    continue

                task_name = f"{plugin.meta.name}:{target.type.value}:{target.value[:20]}"
                coro = self._execute_plugin_safe(plugin, target)
                tasks.append((task_name, asyncio.create_task(coro, name=task_name)))

        # Paralel icra
        for task_name, task in tasks:
            try:
                findings = await task
                result.findings.extend(findings)
                # Plugin adını plugin_name:target formatından çıxar
                plugin_name = task_name.split(":")[0]
                if plugin_name not in result.plugins_executed:
                    result.plugins_executed.append(plugin_name)
            except Exception as e:
                result.errors.append(f"{task_name}: {e}")
                logger.error("scan_task_failed", task=task_name, error=str(e))

        # Nəticə
        elapsed = time.monotonic() - start_time
        result.duration_seconds = round(elapsed, 2)
        result.status = ScanStatus.COMPLETED if not result.errors else ScanStatus.COMPLETED
        result.completed_at = __import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        )

        logger.info(
            "scan_completed",
            scan_id=result.scan_id,
            findings=result.findings_count,
            plugins=len(result.plugins_executed),
            errors=len(result.errors),
            duration=result.duration_seconds,
        )

        return result

    async def _execute_plugin_safe(
        self, plugin: BasePlugin, target: Target
    ) -> list[Finding]:
        """Tək bir plugin-i timeout və error handling ilə işlədir.

        Plugin crash etsə belə scan davam edir — bir plugin digərini bloklamamalıdır.
        """
        plugin_name = plugin.meta.name
        timeout = plugin.meta.timeout_seconds

        try:
            findings = await asyncio.wait_for(
                plugin.execute(target),
                timeout=timeout,
            )

            logger.debug(
                "plugin_executed",
                plugin=plugin_name,
                target=target.value[:20],
                findings=len(findings),
            )
            return findings

        except asyncio.TimeoutError:
            logger.warning("plugin_timeout", plugin=plugin_name, timeout=timeout)
            return []

        except Exception as e:
            logger.error(
                "plugin_execution_error",
                plugin=plugin_name,
                error=str(e),
                error_type=type(e).__name__,
            )
            return []

    def _resolve_active_plugins(
        self,
        enabled_only: list[str] | None,
        disabled_list: list[str] | None,
    ) -> list[BasePlugin]:
        """Scan üçün hansı plugin-lərin aktiv olduğunu hesabla."""
        if enabled_only is not None:
            # Yalnız spesifik plugin-lər
            return [
                self._plugins[name]
                for name in enabled_only
                if name in self._plugins
            ]

        # Default: enabled plugin-lər, minus disabled_list
        result = self.enabled_plugins
        if disabled_list:
            result = [p for p in result if p.meta.name not in disabled_list]

        return result
