#!/bin/bash
# Houdini Remote Render & Cache — Bootstrap Script
# Clones the repo and installs HDAs for all detected Houdini versions.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash
#   or
#   wget -qO- https://raw.githubusercontent.com/kleer001/houdini_remote_render/main/scripts/bootstrap.sh | bash

set -e

REPO_URL="https://github.com/kleer001/houdini_remote_render.git"
INSTALL_DIR="$(pwd)/houdini_remote_render"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m'

print_banner() {
    echo ""
    echo -e "${CYAN}============================================================${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${CYAN}============================================================${NC}"
    echo ""
}

print_ok()   { echo -e "  ${GREEN}[OK]${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}[!!]${NC} $1"; }
print_fail() { echo -e "  ${RED}[FAIL]${NC} $1"; }

# --- Pre-flight checks ---

print_banner "Houdini Remote Render & Cache — Installer"

# Check for git
if ! command -v git &> /dev/null; then
    print_fail "git is not installed. Please install git first."
    exit 1
fi
print_ok "git found"

# Check for python3
PYTHON=""
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
fi

if [ -z "$PYTHON" ]; then
    print_fail "Python 3 is not installed. Please install Python 3.10+."
    exit 1
fi

PY_VERSION=$($PYTHON --version 2>&1)

# Verify it's Python 3
if ! echo "$PY_VERSION" | grep -q "Python 3"; then
    print_fail "$PYTHON is $PY_VERSION, but Python 3.10+ is required."
    exit 1
fi
print_ok "Python found: $PY_VERSION"

# Check for Houdini pref dirs
HOUDINI_FOUND=false
case "$(uname -s)" in
    Linux*)
        for d in ~/houdini*/; do
            if [ -d "$d" ]; then
                HOUDINI_FOUND=true
                break
            fi
        done
        ;;
    Darwin*)
        for d in ~/Library/Preferences/houdini/*/; do
            if [ -d "$d" ]; then
                HOUDINI_FOUND=true
                break
            fi
        done
        ;;
esac

if [ "$HOUDINI_FOUND" = false ]; then
    print_fail "No Houdini preference directories found."
    echo "  Is Houdini installed and has been launched at least once?"
    exit 1
fi
print_ok "Houdini preferences found"

# --- Clone or update repo ---

echo ""
if [ -d "$INSTALL_DIR" ]; then
    echo "Repository already exists at $INSTALL_DIR"
    echo "Updating..."
    cd "$INSTALL_DIR"
    if git pull --ff-only; then
        print_ok "Repository updated"
    else
        print_warn "git pull failed (local changes?). Using existing version."
    fi
else
    echo "Cloning repository..."
    git clone "$REPO_URL" "$INSTALL_DIR"
    cd "$INSTALL_DIR"
    print_ok "Repository cloned to $INSTALL_DIR"
fi

# --- Install ---

echo ""
echo "Installing HDAs..."
if $PYTHON install.py; then
    print_banner "Installation Complete"
    echo "Restart Houdini to load the HDAs."
    echo ""
    echo "HDAs will appear as:"
    echo "  - Karma USD Packager  (LOP networks)"
    echo "  - Remote File Cache   (SOP networks)"
    echo ""
    echo "To check status:    cd $INSTALL_DIR && $PYTHON install.py --status"
    echo "To uninstall:        cd $INSTALL_DIR && $PYTHON install.py --uninstall"
else
    print_fail "Installation failed. Check the output above for details."
    exit 1
fi
