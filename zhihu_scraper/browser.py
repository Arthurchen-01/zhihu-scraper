"""Persistent browser fallback behind one small, testable interface."""

from __future__ import annotations

from pathlib import Path
from types import TracebackType
from typing import Any, Protocol, Self
from urllib.parse import urlparse

from .platform import RuntimePlatform


class BrowserFallbackError(RuntimeError):
    """Base error for the optional browser fallback."""


class BrowserDependencyError(BrowserFallbackError):
    """Raised when the optional browser runtime is not installed."""


class BrowserLaunchError(BrowserFallbackError):
    """Raised when a browser context cannot be started or connected."""


class BrowserNavigationError(BrowserFallbackError):
    """Raised when the requested page cannot be loaded."""


class BrowserCookieError(BrowserFallbackError):
    """Raised when browser cookies cannot be read."""


class BrowserCloseError(BrowserFallbackError):
    """Raised when browser resources could not be closed cleanly."""


class BrowserPage(Protocol):
    def goto(self, url: str, *, wait_until: str, timeout: int) -> object: ...

    def wait_for_load_state(self, state: str, *, timeout: int) -> object: ...

    def content(self) -> str: ...

    def close(self) -> object: ...


class BrowserContext(Protocol):
    def new_page(self) -> BrowserPage: ...

    def cookies(self) -> list[dict[str, object]]: ...

    def add_cookies(self, cookies: list[dict[str, object]]) -> object: ...

    def close(self) -> object: ...


class BrowserExecutor(Protocol):
    """Adapter seam used by the fallback and its in-memory test fake."""

    def connect_over_cdp(self, cdp_url: str) -> BrowserContext: ...

    def launch_persistent_context(
        self,
        profile_dir: Path,
        *,
        headless: bool,
        executable_path: Path | None,
    ) -> BrowserContext: ...

    def close(self) -> object: ...


class _PlaywrightExecutor:
    """Lazy synchronous Playwright adapter.

    Importing the project does not require Playwright. The optional dependency
    is loaded only when browser fallback is actually used.
    """

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._cdp_browser: Any | None = None

    def connect_over_cdp(self, cdp_url: str) -> BrowserContext:
        try:
            playwright = self._start_playwright()
            self._cdp_browser = playwright.chromium.connect_over_cdp(cdp_url)
            contexts = self._cdp_browser.contexts
            if not contexts:
                raise RuntimeError("CDP browser has no default context")
            return contexts[0]
        except BrowserDependencyError:
            raise
        except Exception:
            self.close()
            raise BrowserLaunchError(
                "The running Chrome browser could not be connected. Start Chrome "
                "with a loopback remote-debugging port and try again."
            ) from None

    def launch_persistent_context(
        self,
        profile_dir: Path,
        *,
        headless: bool,
        executable_path: Path | None,
    ) -> BrowserContext:
        try:
            playwright = self._start_playwright()
            options: dict[str, object] = {"headless": headless}
            if executable_path is not None:
                options["executable_path"] = str(executable_path)
            return playwright.chromium.launch_persistent_context(
                str(profile_dir),
                **options,
            )
        except BrowserDependencyError:
            raise
        except Exception:
            self.close()
            raise BrowserLaunchError(
                "The persistent browser could not be started. Close any browser "
                "using the same profile, or run `playwright install chromium`."
            ) from None

    def _start_playwright(self) -> Any:
        if self._playwright is not None:
            return self._playwright
        try:
            from playwright.sync_api import sync_playwright
        except (ImportError, ModuleNotFoundError):
            raise BrowserDependencyError(
                "Browser fallback requires the optional Playwright package. "
                "Install `zhihu-scraper[full]`, then run "
                "`playwright install chromium`."
            ) from None
        self._playwright = sync_playwright().start()
        return self._playwright

    def close(self) -> None:
        if self._playwright is None:
            return
        try:
            self._playwright.stop()
        finally:
            self._playwright = None
            self._cdp_browser = None


class BrowserFallback:
    """Reuse a persistent profile or an already-running local Chrome session."""

    def __init__(
        self,
        *,
        cdp_url: str | None = None,
        profile_dir: Path | None = None,
        headless: bool = False,
        timeout_ms: int = 30_000,
        runtime_platform: RuntimePlatform | None = None,
        executor: BrowserExecutor | None = None,
    ) -> None:
        if timeout_ms <= 0:
            raise ValueError("timeout_ms must be positive")
        if cdp_url is not None:
            _validate_cdp_url(cdp_url)
        runtime = runtime_platform or RuntimePlatform.detect()
        self.profile_dir = profile_dir or (
            Path(str(runtime.user_data_directory)) / "browser-profile"
        )
        self.cdp_url = cdp_url
        self.headless = headless
        self.timeout_ms = timeout_ms
        self._runtime = runtime
        self._executor: BrowserExecutor = executor or _PlaywrightExecutor()
        self._context: BrowserContext | None = None
        self._closed = False

    def fetch_html(self, url: str) -> str:
        _validate_zhihu_url(url)
        page: BrowserPage | None = None
        try:
            page = self._ensure_context().new_page()
            page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=self.timeout_ms,
            )
            page.wait_for_load_state("domcontentloaded", timeout=self.timeout_ms)
            return page.content()
        except BrowserFallbackError:
            raise
        except Exception:
            raise BrowserNavigationError(
                "The browser could not load the requested Zhihu page."
            ) from None
        finally:
            if page is not None:
                try:
                    page.close()
                except Exception:
                    # Per-page cleanup is best effort; closing the persistent
                    # context remains available through ``close``.
                    pass

    def cookie_dict(self) -> dict[str, str]:
        """Return browser cookies scoped to Zhihu without logging their values."""
        try:
            cookie_records = self._ensure_context().cookies()
        except BrowserFallbackError:
            raise
        except Exception:
            raise BrowserCookieError(
                "The browser session cookies could not be read."
            ) from None

        result: dict[str, str] = {}
        for cookie in cookie_records:
            name = cookie.get("name")
            value = cookie.get("value")
            domain = cookie.get("domain")
            if not isinstance(name, str) or not name:
                continue
            if not isinstance(value, str) or not isinstance(domain, str):
                continue
            normalized_domain = domain.casefold().lstrip(".")
            if (
                normalized_domain == "zhihu.com"
                or normalized_domain.endswith(".zhihu.com")
            ):
                result[name] = value
        return result

    def set_cookie_dict(self, cookies: dict[str, str]) -> None:
        """Import Zhihu cookies into the persistent context without logging values."""

        records = [
            {
                "name": name,
                "value": value,
                "domain": ".zhihu.com",
                "path": "/",
                "secure": True,
            }
            for name, value in cookies.items()
            if isinstance(name, str)
            and name.strip()
            and isinstance(value, str)
            and value
        ]
        if not records:
            return
        try:
            self._ensure_context().add_cookies(records)
        except BrowserFallbackError:
            raise
        except Exception:
            raise BrowserCookieError(
                "The Zhihu cookies could not be imported into the browser session."
            ) from None

    def _ensure_context(self) -> BrowserContext:
        if self._closed:
            raise BrowserFallbackError("Browser fallback is closed.")
        if self._context is not None:
            return self._context
        if self.cdp_url is not None:
            try:
                self._context = self._executor.connect_over_cdp(self.cdp_url)
            except BrowserFallbackError:
                raise
            except Exception:
                raise BrowserLaunchError(
                    "The running Chrome browser could not be connected."
                ) from None
            return self._context
        self.profile_dir.mkdir(parents=True, exist_ok=True)
        try:
            self._context = self._executor.launch_persistent_context(
                self.profile_dir,
                headless=self.headless,
                executable_path=self._installed_browser(),
            )
        except BrowserFallbackError:
            raise
        except Exception:
            raise BrowserLaunchError(
                "The persistent browser could not be started."
            ) from None
        return self._context

    def _installed_browser(self) -> Path | None:
        for candidate in self._runtime.browser_candidates:
            path = Path(str(candidate))
            if path.is_file():
                return path
        return None

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        failed = False
        context = self._context
        self._context = None
        if context is not None and self.cdp_url is None:
            try:
                context.close()
            except Exception:
                failed = True
        try:
            self._executor.close()
        except Exception:
            failed = True
        if failed:
            raise BrowserCloseError(
                "The browser resources could not be closed cleanly."
            ) from None

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        try:
            self.close()
        except BrowserCloseError:
            if exc_value is None:
                raise


def _validate_zhihu_url(url: str) -> None:
    parsed = urlparse(url)
    hostname = (parsed.hostname or "").casefold()
    trusted = hostname == "zhihu.com" or hostname.endswith(".zhihu.com")
    if (
        parsed.scheme != "https"
        or not trusted
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise BrowserNavigationError(
            "Browser fallback only opens trusted Zhihu HTTPS pages."
        )


def _validate_cdp_url(url: str) -> None:
    """Keep the authenticated browser-control channel on this machine."""

    try:
        parsed = urlparse(url)
        hostname = (parsed.hostname or "").casefold()
        # Accessing ``port`` also rejects malformed and out-of-range values.
        parsed.port
    except ValueError:
        raise BrowserLaunchError(
            "CDP connection requires a valid loopback HTTP or WebSocket URL."
        ) from None

    if (
        parsed.scheme not in {"http", "ws"}
        or hostname not in {"127.0.0.1", "localhost", "::1"}
        or parsed.username is not None
        or parsed.password is not None
    ):
        raise BrowserLaunchError(
            "CDP connection requires a loopback HTTP or WebSocket URL "
            "(127.0.0.1, localhost, or [::1])."
        )
