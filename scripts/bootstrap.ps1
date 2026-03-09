# Houdini Remote Render & Cache — Bootstrap Script (Windows)
# Clones the repo and installs HDAs for all detected Houdini versions.
#
# Usage:
#   irm https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.ps1 | iex

$ErrorActionPreference = "Stop"

$REPO_URL = "https://github.com/kleer001/houdini_remote_render.git"
$INSTALL_DIR = Join-Path (Get-Location) "houdini_remote_render"

function Print-Banner($text) {
    Write-Host ""
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host "  $text" -ForegroundColor Cyan
    Write-Host "============================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Print-Ok($text)   { Write-Host "  [OK] $text" -ForegroundColor Green }
function Print-Warn($text) { Write-Host "  [!!] $text" -ForegroundColor Yellow }
function Print-Fail($text) { Write-Host "  [FAIL] $text" -ForegroundColor Red }

# --- Pre-flight checks ---

Print-Banner "Houdini Remote Render & Cache — Installer"

# Check for git
try {
    $gitVersion = git --version 2>&1
    Print-Ok "git found: $gitVersion"
} catch {
    Print-Fail "git is not installed. Please install git first."
    Print-Warn "Try: winget install Git.Git"
    exit 1
}

# Check for python
$python = $null
try {
    $pyVersion = python --version 2>&1
    if ($pyVersion -match "Python 3") {
        $python = "python"
        Print-Ok "Python found: $pyVersion"
    }
} catch {}

if (-not $python) {
    try {
        $pyVersion = python3 --version 2>&1
        $python = "python3"
        Print-Ok "Python found: $pyVersion"
    } catch {
        Print-Fail "Python 3 is not installed. Please install Python 3.10+."
        exit 1
    }
}

# Check for Houdini pref dirs
$houdiniDirs = Get-ChildItem "$env:USERPROFILE\Documents" -Directory -Filter "houdini*" -ErrorAction SilentlyContinue
if (-not $houdiniDirs -or $houdiniDirs.Count -eq 0) {
    Print-Fail "No Houdini preference directories found."
    Write-Host "  Is Houdini installed and has been launched at least once?"
    exit 1
}
Print-Ok "Houdini preferences found ($($houdiniDirs.Count) version(s))"

# --- Clone or update repo ---

Write-Host ""
if (Test-Path $INSTALL_DIR) {
    Write-Host "Repository already exists at $INSTALL_DIR"
    Write-Host "Updating..."
    Push-Location $INSTALL_DIR
    try {
        git pull --ff-only
        Print-Ok "Repository updated"
    } catch {
        Print-Warn "git pull failed (local changes?). Using existing version."
    } finally {
        Pop-Location
    }
} else {
    Write-Host "Cloning repository..."
    git clone $REPO_URL $INSTALL_DIR
    Print-Ok "Repository cloned to $INSTALL_DIR"
}

# --- Install ---

Write-Host ""
Write-Host "Installing HDAs..."
Push-Location $INSTALL_DIR
try {
    & $python install.py
    if ($LASTEXITCODE -ne 0) { throw "install.py exited with code $LASTEXITCODE" }

    Print-Banner "Installation Complete"
    Write-Host "Restart Houdini to load the HDAs."
    Write-Host ""
    Write-Host "HDAs will appear as:"
    Write-Host "  - Karma USD Packager  (LOP networks)"
    Write-Host "  - Remote File Cache   (SOP networks)"
    Write-Host ""
    Write-Host "To check status:    cd $INSTALL_DIR; $python install.py --status"
    Write-Host "To uninstall:        cd $INSTALL_DIR; $python install.py --uninstall"
} catch {
    Print-Fail "Installation failed. Check the output above for details."
    exit 1
} finally {
    Pop-Location
}
