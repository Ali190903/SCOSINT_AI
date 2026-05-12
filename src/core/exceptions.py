"""
SCOSINT_AI Custom Exceptions

WHY: Xüsusi exception-lar sistemi predictable edir. Hər error tipi fərqli
handling tələb edir — plugin timeout-u ilə DB connection error-u eyni deyil.
Plugin developer-lər də bu exception-ları istifadə etməli olacaq.
"""


class SCOSINTError(Exception):
    """Base exception for all SCOSINT_AI errors."""


# --- Plugin Exceptions ---


class PluginError(SCOSINTError):
    """Base exception for plugin-related errors."""


class PluginLoadError(PluginError):
    """Plugin yüklənərkən xəta — modul tapılmadı, interface uyğun deyil, və s."""


class PluginExecutionError(PluginError):
    """Plugin icrası zamanı xəta — timeout, network failure, parsing error."""

    def __init__(self, plugin_name: str, message: str, original: Exception | None = None):
        self.plugin_name = plugin_name
        self.original = original
        super().__init__(f"[{plugin_name}] {message}")


class PluginTimeoutError(PluginExecutionError):
    """Plugin icra müddəti bitdi — subprocess və ya HTTP sorğu cavab vermədi."""


# --- Scan Exceptions ---


class ScanError(SCOSINTError):
    """Base exception for scan-related errors."""


class ScanNotFoundError(ScanError):
    """Verilmiş ID ilə scan tapılmadı."""


class ScanAlreadyRunningError(ScanError):
    """Bu target üçün artıq aktiv scan var."""


# --- External Service Exceptions ---


class ExternalServiceError(SCOSINTError):
    """Xarici servis (SearXNG, Ollama, DB) ilə əlaqə problemi."""


class BrowserError(SCOSINTError):
    """Playwright browser pool ilə bağlı xəta."""


class RateLimitError(SCOSINTError):
    """Rate limit-ə çatıldı — gözləmək lazımdır."""

    def __init__(self, service: str, retry_after_seconds: float | None = None):
        self.service = service
        self.retry_after_seconds = retry_after_seconds
        msg = f"Rate limit hit for {service}"
        if retry_after_seconds:
            msg += f" — retry after {retry_after_seconds}s"
        super().__init__(msg)
