# 一键把「清一新教育 · 修改助手」扩展放到固定位置，并打开扩展管理页。
#
# 用法（在扩展文件夹里右键 → 使用 PowerShell 运行，或）：
#     powershell -ExecutionPolicy Bypass -File install-extension.ps1
#     powershell -ExecutionPolicy Bypass -File install-extension.ps1 -Browser Chrome
#
# 说明：Chrome/Edge 明确禁止脚本注入 chrome:// / edge:// 页面，
#       所以最后的「加载已解压的扩展程序」这 2~3 下必须由人来点。
#       本脚本把「找路径 / 复制文件 / 复制剪贴板 / 打开页面」都代劳了。

param(
  [ValidateSet("Auto", "Edge", "Chrome")]
  [string]$Browser = "Auto",
  [string]$Dest = ""
)

$ErrorActionPreference = "Stop"

$src = $PSScriptRoot
if (-not $Dest) { $Dest = Join-Path $env:LOCALAPPDATA "QingyiEdu\extension" }

Write-Host ""
Write-Host "  清一新教育 · 修改助手 — 安装助手" -ForegroundColor Cyan
Write-Host "  ==============================================" -ForegroundColor DarkGray

# ---------- 1. 校验扩展文件齐不齐 ----------
$need = @("manifest.json", "config.js", "background.js", "popup.html",
          "popup.js", "options.html", "options.js", "help.html",
          "icons\icon-16.png", "icons\icon-32.png",
          "icons\icon-48.png", "icons\icon-128.png")
$missing = @()
foreach ($f in $need) {
  if (-not (Test-Path (Join-Path $src $f))) { $missing += $f }
}
if ($missing.Count -gt 0) {
  Write-Host ""
  Write-Host "  [X] 扩展文件不完整，缺少：" -ForegroundColor Red
  $missing | ForEach-Object { Write-Host ("      - " + $_) -ForegroundColor Red }
  Write-Host ""
  Write-Host "  请确认本脚本就在扩展文件夹里运行（和 manifest.json 同一层）。" -ForegroundColor Yellow
  exit 1
}
Write-Host ("  [OK] 扩展文件完整（{0} 项）" -f $need.Count) -ForegroundColor Green

# ---------- 2. 复制到固定位置 ----------
New-Item -ItemType Directory -Force -Path $Dest | Out-Null
Copy-Item -Path (Join-Path $src "*") -Destination $Dest -Recurse -Force
Write-Host ("  [OK] 已放到固定位置： {0}" -f $Dest) -ForegroundColor Green

# ---------- 3. 判断该用哪个浏览器 ----------
function Get-BrowserRoot([string]$name) {
  if ($name -eq "Edge") {
    return (Join-Path $env:LOCALAPPDATA "Microsoft\Edge\User Data")
  }
  return (Join-Path $env:LOCALAPPDATA "Google\Chrome\User Data")
}

function Get-NewestCookie([string]$root) {
  if (-not (Test-Path $root)) { return $null }
  $best = $null
  foreach ($p in Get-ChildItem $root -Directory -ErrorAction SilentlyContinue) {
    foreach ($rel in @("Network\Cookies", "Cookies")) {
      $f = Join-Path $p.FullName $rel
      if (Test-Path $f) {
        $t = (Get-Item $f).LastWriteTime
        if (-not $best -or $t -gt $best.Time) {
          $best = [pscustomobject]@{ Time = $t; Path = $f; Profile = $p.Name }
        }
      }
    }
  }
  return $best
}

$edgeRoot = Get-BrowserRoot "Edge"
$chromeRoot = Get-BrowserRoot "Chrome"
$edge = Get-NewestCookie $edgeRoot
$chrome = Get-NewestCookie $chromeRoot

$pick = $Browser
if ($pick -eq "Auto") {
  if ($edge -and $chrome) {
    # 两个都装了：看谁最近被用过（Cookies 文件更新时间更近）
    $pick = if ($chrome.Time -gt $edge.Time) { "Chrome" } else { "Edge" }
  } elseif ($chrome) {
    $pick = "Chrome"
  } elseif ($edge) {
    $pick = "Edge"
  } else {
    $pick = "Edge"
  }
}

if ($pick -eq "Edge") {
  $exe = (Get-Command msedge.exe -ErrorAction SilentlyContinue).Source
  if (-not $exe) {
    $c = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
    if (Test-Path $c) { $exe = $c }
  }
  $page = "edge://extensions"
  $info = $edge
} else {
  $exe = (Get-Command chrome.exe -ErrorAction SilentlyContinue).Source
  if (-not $exe) {
    $c = "C:\Program Files\Google\Chrome\Application\chrome.exe"
    if (Test-Path $c) { $exe = $c }
    if (-not (Test-Path $exe)) {
      $c2 = "C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"
      if (Test-Path $c2) { $exe = $c2 }
    }
  }
  $page = "chrome://extensions"
  $info = $chrome
}

if ($info) {
  Write-Host ("  [i] {0} 最近使用的配置： {1}（Cookies 更新于 {2}）" -f `
    $pick, $info.Profile, $info.Time.ToString("yyyy-MM-dd HH:mm")) -ForegroundColor DarkGray
}

# ---------- 4. 路径进剪贴板 ----------
try {
  Set-Clipboard -Value $Dest
  Write-Host "  [OK] 文件夹路径已复制到剪贴板（待会 Ctrl+V 就能粘贴）" -ForegroundColor Green
} catch {
  Write-Host "  [i] 剪贴板不可用，请手动输入路径" -ForegroundColor Yellow
}

# ---------- 5. 打开扩展管理页 ----------
if ($exe) {
  Start-Process $exe $page
  Write-Host ("  [OK] 已打开 {0}" -f $page) -ForegroundColor Green
} else {
  Write-Host ("  [!] 没找到 {0} 的可执行文件，请手动打开 {1}" -f $pick, $page) -ForegroundColor Yellow
}

# ---------- 6. 剩下的人工步骤 ----------
Write-Host ""
Write-Host "  接下来只需 3 下（浏览器不允许脚本代点）：" -ForegroundColor Cyan
Write-Host "    1. 打开右上角「开发人员模式 / Developer mode」开关"
Write-Host "    2. 点「加载解压缩的扩展 / Load unpacked」"
Write-Host "    3. 在文件对话框地址栏按 Ctrl+V，回车"
Write-Host ""
Write-Host "  装好后点工具栏上的扩展图标，应看到：" -ForegroundColor Cyan
Write-Host "    本浏览器知乎登录：已登录"
Write-Host "    云端凭证柜：刚刚"
Write-Host ""
Write-Host ("  文件夹位置（如果 Ctrl+V 没生效，手动到这里选）：{0}" -f $Dest) -ForegroundColor DarkGray
Write-Host ""
