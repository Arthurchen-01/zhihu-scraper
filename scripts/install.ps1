[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvDir = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvDir "Scripts\python.exe"
$PythonCommand = if ($env:PYTHON) { $env:PYTHON } else { "python" }

Push-Location $ProjectRoot
try {
    & $PythonCommand -m venv $VenvDir
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to create the virtual environment."
    }

    & $VenvPython -m pip install --upgrade pip
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to upgrade pip."
    }

    & $VenvPython -m pip install -e .
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install the crawler."
    }

    & $VenvPython -m playwright install chromium
    if ($LASTEXITCODE -ne 0) {
        throw "Failed to install the managed Chromium browser."
    }
}
finally {
    Pop-Location
}

Write-Host "Installation complete, including managed browser fallback."
Write-Host "Activate the environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Then check the command with:"
Write-Host "  zhihu --help"
