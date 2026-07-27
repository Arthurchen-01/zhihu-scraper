import unittest
from pathlib import PurePosixPath, PureWindowsPath

from zhihu_scraper.platform import (
    OperatingSystem,
    RuntimePlatform,
    UnsupportedPlatformError,
)


class RuntimePlatformTests(unittest.TestCase):
    def test_windows_runtime_uses_local_app_data_and_windows_browser_locations(self):
        runtime = RuntimePlatform.for_system(
            "Windows",
            home_directory=PureWindowsPath("C:/Users/Ada"),
            environment={
                "LOCALAPPDATA": r"C:\Users\Ada\AppData\Local",
                "PROGRAMFILES": r"C:\Program Files",
                "PROGRAMFILES(X86)": r"C:\Program Files (x86)",
            },
        )

        self.assertEqual(OperatingSystem.WINDOWS, runtime.operating_system)
        self.assertEqual(
            PureWindowsPath("C:/Users/Ada/AppData/Local/ZhihuScraper"),
            runtime.user_data_directory,
        )
        self.assertEqual(
            (
                PureWindowsPath("C:/Users/Ada/AppData/Local/Google/Chrome/Application/chrome.exe"),
                PureWindowsPath("C:/Program Files/Google/Chrome/Application/chrome.exe"),
                PureWindowsPath("C:/Program Files (x86)/Google/Chrome/Application/chrome.exe"),
                PureWindowsPath("C:/Users/Ada/AppData/Local/Chromium/Application/chrome.exe"),
            ),
            runtime.browser_candidates,
        )

    def test_macos_runtime_uses_application_support_and_app_bundle_executables(self):
        runtime = RuntimePlatform.for_system(
            "Darwin",
            home_directory=PurePosixPath("/Users/ada"),
            environment={},
        )

        self.assertEqual(OperatingSystem.MACOS, runtime.operating_system)
        self.assertEqual(
            PurePosixPath("/Users/ada/Library/Application Support/zhihu-scraper"),
            runtime.user_data_directory,
        )
        self.assertEqual(
            (
                PurePosixPath("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
                PurePosixPath(
                    "/Users/ada/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
                ),
                PurePosixPath("/Applications/Chromium.app/Contents/MacOS/Chromium"),
            ),
            runtime.browser_candidates,
        )

    def test_linux_runtime_honors_xdg_data_home_and_common_browser_locations(self):
        runtime = RuntimePlatform.for_system(
            "Linux",
            home_directory=PurePosixPath("/home/ada"),
            environment={"XDG_DATA_HOME": "/mnt/user-data"},
        )

        self.assertEqual(OperatingSystem.LINUX, runtime.operating_system)
        self.assertEqual(
            PurePosixPath("/mnt/user-data/zhihu-scraper"),
            runtime.user_data_directory,
        )
        self.assertEqual(
            (
                PurePosixPath("/usr/bin/google-chrome"),
                PurePosixPath("/usr/bin/google-chrome-stable"),
                PurePosixPath("/usr/bin/chromium"),
                PurePosixPath("/usr/bin/chromium-browser"),
                PurePosixPath("/snap/bin/chromium"),
            ),
            runtime.browser_candidates,
        )

    def test_unsupported_operating_system_has_an_actionable_error(self):
        with self.assertRaisesRegex(
            UnsupportedPlatformError,
            "FreeBSD.*Windows, macOS, and Linux",
        ):
            RuntimePlatform.for_system(
                "FreeBSD",
                home_directory=PurePosixPath("/home/ada"),
                environment={},
            )

    def test_runtime_detection_is_shared_for_the_process(self):
        first_detection = RuntimePlatform.detect()
        second_detection = RuntimePlatform.detect()

        self.assertIs(first_detection, second_detection)


if __name__ == "__main__":
    unittest.main()
