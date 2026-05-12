"""
SCOSINT_AI Plugin Base — Plugin Interface Contract

WHY: Bu fayl bütün OSINT plugin-lərin "kontraktı"dır. Hər plugin bu
ABC-ni inherit etməlidir. ABC seçildi (Protocol yox) çünki plugin
developer-lərə helper metodlar (run_subprocess, make_finding) miras
olaraq verilir — Protocol buna imkan vermir.

DESIGN DECISION: execute() async-dir çünki OSINT əməliyyatları I/O-bound-dur
(HTTP, subprocess, browser). accepts() isə sync-dir çünki sadəcə type yoxlamasıdır.
"""

from __future__ import annotations

import asyncio
import subprocess
import json
from abc import ABC, abstractmethod
from typing import Any

from src.core.models import Finding, PluginMeta, Target


class BasePlugin(ABC):
    """Bütün SCOSINT plugin-ləri bu abstract class-dan inherit edir.

    Niyə Protocol yox ABC?
    — Plugin developer-lər üçün aydınlıq: IDE autocomplete, docstring,
      default metodlar (run_subprocess, make_finding) burada verilir.
    — Protocol structural typing üçün yaxşıdır amma helper metodları
      miras almağa imkan vermir.

    Hər plugin 3 şeyi təmin etməlidir:
    1. meta property — kim olduğunu bildirir
    2. accepts() — hansı target tipini qəbul edir
    3. execute() — əsl işi görür
    """

    @property
    @abstractmethod
    def meta(self) -> PluginMeta:
        """Plugin metadata — ad, versiya, kateqoriya, lisenziya."""
        ...

    def accepts(self, target: Target) -> bool:
        """Bu plugin verilmiş target-i qəbul edirmi?

        Default implementasiya: PluginMeta.accepts_types ilə yoxlayır.
        Plugin override edə bilər (məs. yalnız Gmail qəbul edən GHunt).
        """
        return target.type in self.meta.accepts_types

    @abstractmethod
    async def execute(self, target: Target) -> list[Finding]:
        """Plugin-in əsas məntiqi. Target alır, Finding-lər qaytarır.

        Qaydalar:
        - Heç vaxt exception atma → boş list qaytar
        - Timeout-u özün idarə etmə → plugin_manager timeout qoyacaq
        - Hər tapıntını Finding olaraq qaytar
        - confidence dəyərini dürüst qoy (0.0-1.0)
        """
        ...

    # ================================================================
    # Helper metodlar — plugin developer-lər üçün utility-lər
    # ================================================================

    def make_finding(self, **kwargs: Any) -> Finding:
        """Finding yaradır, source_plugin avtomatik doldurulur."""
        kwargs.setdefault("source_plugin", self.meta.name)
        return Finding(**kwargs)

    async def run_subprocess(
        self,
        cmd: list[str],
        timeout: int | None = None,
        parse_json: bool = False,
    ) -> subprocess.CompletedProcess | dict | list:
        """GPLv3 alətləri subprocess olaraq çağırmaq üçün helper.

        WHY subprocess: GPLv3 lisenziyalı alətlər (Holehe, PhoneInfoga)
        birbaşa import edilsə, bizim kodumuz da GPLv3 olmalıdır. Subprocess
        ilə çağırdıqda bu "linking" sayılmır → bizim MIT lisenziyamız qorunur.

        Args:
            cmd: İcra ediləcək komanda (list formatında)
            timeout: Saniyə cinsindən timeout (None = plugin meta timeout)
            parse_json: True olsa, stdout-u JSON olaraq parse edir

        Returns:
            CompletedProcess və ya parse edilmiş JSON dict/list
        """
        effective_timeout = timeout or self.meta.timeout_seconds

        try:
            result = await asyncio.to_thread(
                subprocess.run,
                cmd,
                capture_output=True,
                text=True,
                timeout=effective_timeout,
            )

            if parse_json and result.returncode == 0 and result.stdout.strip():
                return json.loads(result.stdout)

            return result

        except subprocess.TimeoutExpired:
            return subprocess.CompletedProcess(
                args=cmd, returncode=-1, stdout="", stderr="TIMEOUT"
            )
        except FileNotFoundError:
            return subprocess.CompletedProcess(
                args=cmd, returncode=-1, stdout="", stderr=f"Command not found: {cmd[0]}"
            )

    def __repr__(self) -> str:
        return f"<Plugin:{self.meta.name} v{self.meta.version} [{self.meta.category.value}]>"
