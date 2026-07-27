from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class NewInstallContractTests(unittest.TestCase):
    def test_ci_covers_supported_operating_systems_and_python_versions(self) -> None:
        workflow = self._read(".github/workflows/ci.yml")

        for runner in ("ubuntu-latest", "windows-latest", "macos-latest"):
            with self.subTest(runner=runner):
                self.assertIn(runner, workflow)
        for version in ('"3.12"', '"3.13"', '"3.14"'):
            with self.subTest(version=version):
                self.assertIn(version, workflow)

        self.assertIn('python -m pip install -e ".[dev]"', workflow)
        self.assertIn("python -m pytest", workflow)
        self.assertIn("zhihu --help", workflow)
        self.assertIn("fail-fast: false", workflow)

    def test_ci_does_not_keep_obsolete_package_or_unittest_commands(self) -> None:
        workflow = self._read(".github/workflows/ci.yml")

        self.assertNotRegex(workflow, r"compileall\s+.*\b(?:cli|core)\b")
        self.assertNotIn("python -m unittest", workflow)
        self.assertNotIn("cli/app.py", workflow)

    def test_posix_installer_is_relocatable_and_fails_fast(self) -> None:
        script = self._read("scripts/install.sh")

        self.assertTrue(script.startswith("#!/usr/bin/env sh\n"))
        self.assertIn("set -eu", script)
        self.assertIn('dirname -- "$0"', script)
        self.assertIn('"$python_command" -m venv "$venv_dir"', script)
        self.assertIn('"$venv_python" -m pip install --upgrade pip', script)
        self.assertIn('"$venv_python" -m pip install -e .', script)
        self.assertIn('"$venv_python" -m pip install -e ".[full]"', script)
        self._assert_browser_download_is_instruction_only(script)

    def test_powershell_installer_is_relocatable_and_fails_fast(self) -> None:
        script = self._read("scripts/install.ps1")

        self.assertIn('$ErrorActionPreference = "Stop"', script)
        self.assertIn("Set-StrictMode -Version Latest", script)
        self.assertIn("$PSScriptRoot", script)
        self.assertIn("-m venv $VenvDir", script)
        self.assertIn("-m pip install --upgrade pip", script)
        self.assertIn('-m pip install -e ".[full]"', script)
        self.assertRegex(script, re.compile(r"-m pip install -e \.\s*$", re.MULTILINE))
        self._assert_browser_download_is_instruction_only(script)

    def _assert_browser_download_is_instruction_only(self, script: str) -> None:
        install_lines = [
            line.strip() for line in script.splitlines() if "playwright install chromium" in line
        ]
        self.assertEqual(len(install_lines), 1)
        self.assertRegex(install_lines[0], r"^(?:\"|Write-Host)")

    def _read(self, relative_path: str) -> str:
        return (REPO_ROOT / relative_path).read_text(encoding="utf-8")


if __name__ == "__main__":
    unittest.main()
