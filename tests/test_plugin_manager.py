"""
Plugin Manager Tests — Core-un düzgün işlədiyini yoxlayır.

Test-lər real OSINT alətləri istifadə etmir — mock plugin-lər yaradılır.
Bu sayədə test-lər sürətli, etibarlı və network-dən asılı deyil.
"""

from __future__ import annotations

import asyncio
import pytest

from src.core.models import (
    ExecutionMode,
    Finding,
    FindingType,
    PluginCategory,
    PluginMeta,
    ScanStatus,
    Target,
    TargetType,
)
from src.core.plugin_base import BasePlugin
from src.core.plugin_manager import PluginManager


# ============================================================
# Mock Plugin-lər (test üçün)
# ============================================================


class MockUsernamePlugin(BasePlugin):
    """Test plugin — username axtarışını simulyasiya edir."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="mock_username",
            version="1.0.0",
            description="Test username plugin",
            category=PluginCategory.USERNAME,
            license="MIT",
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        return [
            self.make_finding(
                platform="twitter",
                finding_type=FindingType.PROFILE_URL,
                value=f"https://twitter.com/{target.value}",
                confidence=0.9,
            ),
            self.make_finding(
                platform="github",
                finding_type=FindingType.PROFILE_URL,
                value=f"https://github.com/{target.value}",
                confidence=0.85,
            ),
        ]


class MockEmailPlugin(BasePlugin):
    """Test plugin — email axtarışını simulyasiya edir."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="mock_email",
            version="1.0.0",
            description="Test email plugin",
            category=PluginCategory.EMAIL,
            license="MIT",
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.EMAIL],
            timeout_seconds=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        return [
            self.make_finding(
                platform="gravatar",
                finding_type=FindingType.AVATAR_URL,
                value=f"https://gravatar.com/avatar/{target.value}",
                confidence=0.7,
            ),
        ]


class MockSlowPlugin(BasePlugin):
    """Test plugin — timeout test üçün yavaş plugin."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="mock_slow",
            version="1.0.0",
            category=PluginCategory.USERNAME,
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=5,  # minimum 5 saniyə (Pydantic constraint)
        )

    async def execute(self, target: Target) -> list[Finding]:
        await asyncio.sleep(30)  # 30 saniyə gözlə — timeout olmalıdır
        return []


class MockCrashPlugin(BasePlugin):
    """Test plugin — crash test üçün xəta atan plugin."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="mock_crash",
            version="1.0.0",
            category=PluginCategory.USERNAME,
            execution_mode=ExecutionMode.DIRECT,
            accepts_types=[TargetType.USERNAME],
            timeout_seconds=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        raise RuntimeError("Plugin crashed intentionally!")


class MockDisabledPlugin(BasePlugin):
    """Test plugin — default olaraq deaktiv."""

    @property
    def meta(self) -> PluginMeta:
        return PluginMeta(
            name="mock_disabled",
            version="1.0.0",
            category=PluginCategory.BREACH,
            execution_mode=ExecutionMode.HTTP,
            accepts_types=[TargetType.EMAIL],
            enabled_by_default=False,  # Default OFF
            timeout_seconds=10,
        )

    async def execute(self, target: Target) -> list[Finding]:
        return []


# ============================================================
# Tests
# ============================================================


class TestPluginManager:
    """Plugin Manager unit test-ləri."""

    def setup_method(self):
        """Hər test öncəsi təmiz PluginManager yarat."""
        self.manager = PluginManager()
        self.manager.register_plugin(MockUsernamePlugin())
        self.manager.register_plugin(MockEmailPlugin())

    def test_register_plugin(self):
        """Plugin qeydiyyata alınmalıdır."""
        assert "mock_username" in self.manager.all_plugins
        assert "mock_email" in self.manager.all_plugins
        assert len(self.manager.all_plugins) == 2

    def test_plugin_meta(self):
        """Plugin metadata düzgün olmalıdır."""
        meta = self.manager.all_plugins["mock_username"]
        assert meta.name == "mock_username"
        assert meta.category == PluginCategory.USERNAME
        assert TargetType.USERNAME in meta.accepts_types

    def test_enable_disable(self):
        """Plugin enable/disable düzgün işləməlidir."""
        assert self.manager.is_enabled("mock_username")
        self.manager.disable("mock_username")
        assert not self.manager.is_enabled("mock_username")
        self.manager.enable("mock_username")
        assert self.manager.is_enabled("mock_username")

    def test_disabled_by_default(self):
        """enabled_by_default=False olan plugin avtomatik deaktiv olmalıdır."""
        self.manager.register_plugin(MockDisabledPlugin())
        assert not self.manager.is_enabled("mock_disabled")

    def test_enabled_plugins_sorted_by_priority(self):
        """Enabled plugin-lər prioritetə görə sıralanmalıdır."""
        plugins = self.manager.enabled_plugins
        priorities = [p.meta.priority for p in plugins]
        assert priorities == sorted(priorities)

    @pytest.mark.asyncio
    async def test_execute_scan_username(self):
        """Username target ilə scan işləməlidir."""
        targets = [Target(value="testuser", type=TargetType.USERNAME)]
        result = await self.manager.execute_scan(targets)

        assert result.status == ScanStatus.COMPLETED
        assert result.findings_count == 2  # twitter + github
        assert "mock_username" in result.plugins_executed
        assert "mock_email" not in result.plugins_executed  # email plugin username qəbul etmir

    @pytest.mark.asyncio
    async def test_execute_scan_email(self):
        """Email target ilə scan işləməlidir."""
        targets = [Target(value="test@gmail.com", type=TargetType.EMAIL)]
        result = await self.manager.execute_scan(targets)

        assert result.findings_count == 1  # gravatar
        assert "mock_email" in result.plugins_executed

    @pytest.mark.asyncio
    async def test_execute_scan_mixed_targets(self):
        """Müxtəlif target tipləri paralel işləməlidir."""
        targets = [
            Target(value="testuser", type=TargetType.USERNAME),
            Target(value="test@gmail.com", type=TargetType.EMAIL),
        ]
        result = await self.manager.execute_scan(targets)

        assert result.findings_count == 3  # 2 username + 1 email
        assert "mock_username" in result.plugins_executed
        assert "mock_email" in result.plugins_executed

    @pytest.mark.asyncio
    async def test_plugin_timeout_does_not_block(self):
        """Timeout olan plugin scan-ı bloklamaz, digərləri işləməyə davam edir."""
        self.manager.register_plugin(MockSlowPlugin())

        targets = [Target(value="testuser", type=TargetType.USERNAME)]
        result = await self.manager.execute_scan(targets)

        # mock_username 2 tapıntı verir, mock_slow timeout olur
        assert result.findings_count == 2
        assert result.duration_seconds is not None
        assert result.duration_seconds < 8  # 30 saniyə gözləmədi, timeout işlədi

    @pytest.mark.asyncio
    async def test_plugin_crash_does_not_kill_scan(self):
        """Crash edən plugin scan-ı öldürməz."""
        self.manager.register_plugin(MockCrashPlugin())

        targets = [Target(value="testuser", type=TargetType.USERNAME)]
        result = await self.manager.execute_scan(targets)

        # mock_username hələ də işləyir
        assert result.findings_count == 2
        assert result.status == ScanStatus.COMPLETED

    @pytest.mark.asyncio
    async def test_scan_with_enabled_only_filter(self):
        """enabled_only ilə yalnız seçilmiş plugin-lər işləməlidir."""
        targets = [Target(value="testuser", type=TargetType.USERNAME)]
        result = await self.manager.execute_scan(
            targets, enabled_only=["mock_username"]
        )

        assert "mock_username" in result.plugins_executed
        assert result.findings_count == 2

    @pytest.mark.asyncio
    async def test_scan_with_disabled_list(self):
        """disabled_list ilə həmin plugin-lər istisna edilməlidir."""
        targets = [Target(value="testuser", type=TargetType.USERNAME)]
        result = await self.manager.execute_scan(
            targets, disabled_list=["mock_username"]
        )

        assert result.findings_count == 0  # email plugin username qəbul etmir


class TestModels:
    """Data model validation test-ləri."""

    def test_target_validation(self):
        """Target boş value ilə yaradıla bilməz."""
        with pytest.raises(Exception):
            Target(value="", type=TargetType.USERNAME)

    def test_finding_auto_id(self):
        """Finding avtomatik unique ID almalıdır."""
        f1 = Finding(source_plugin="test", finding_type=FindingType.PROFILE_URL, value="url1")
        f2 = Finding(source_plugin="test", finding_type=FindingType.PROFILE_URL, value="url2")
        assert f1.id != f2.id

    def test_finding_confidence_bounds(self):
        """Finding confidence 0-1 arasında olmalıdır."""
        with pytest.raises(Exception):
            Finding(
                source_plugin="test",
                finding_type=FindingType.RAW,
                value="x",
                confidence=1.5,
            )

    def test_plugin_meta_name_pattern(self):
        """Plugin adı lowercase+underscore pattern-ə uyğun olmalıdır."""
        # Valid
        meta = PluginMeta(
            name="sherlock_v2",
            category=PluginCategory.USERNAME,
            execution_mode=ExecutionMode.SUBPROCESS,
            accepts_types=[TargetType.USERNAME],
        )
        assert meta.name == "sherlock_v2"

        # Invalid — böyük hərf
        with pytest.raises(Exception):
            PluginMeta(
                name="Sherlock",
                category=PluginCategory.USERNAME,
                execution_mode=ExecutionMode.SUBPROCESS,
                accepts_types=[TargetType.USERNAME],
            )
