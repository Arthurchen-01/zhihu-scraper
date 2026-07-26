[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet("default", "full")]
    [string]$Profile = "default"
)

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

    if ($Profile -eq "full") {
        & $VenvPython -m pip install -e ".[full]"
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install the full profile."
        }

        Write-Host "Browser fallback support is installed."
        Write-Host "Browser binaries are not downloaded automatically."
        Write-Host "If you need browser fallback, run:"
        Write-Host "  $VenvPython -m playwright install chromium"
    }
    else {
        & $VenvPython -m pip install -e .
        if ($LASTEXITCODE -ne 0) {
            throw "Failed to install the default profile."
        }
    }
}
finally {
    Pop-Location
}

Write-Host "Installation complete."
Write-Host "Activate the environment with:"
Write-Host "  .\.venv\Scripts\Activate.ps1"
Write-Host "Then check the command with:"
Write-Host "  zhihu --help"
