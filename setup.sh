#!/usr/bin/env bash
set -euo pipefail

# Lanyard automated setup script
# Configures Python virtual environment, dependencies, and Camoufox stealth browser.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=================================================="
echo "           Lanyard Setup & Installation           "
echo "=================================================="

# 1. Check Python version
PYTHON_BIN=""
for cmd in python3.14 python3.13 python3.12 python3 python; do
    if command -v "$cmd" >/dev/null 2>&1; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [ "$MAJOR" -ge 3 ] && [ "$MINOR" -ge 12 ]; then
            PYTHON_BIN=$(command -v "$cmd")
            echo "[+] Found compatible Python: $PYTHON_BIN (v$PY_VER)"
            break
        fi
    fi
done

if [ -z "$PYTHON_BIN" ]; then
    echo "[-] Error: Python 3.12 or newer is required." >&2
    echo "    Please install Python 3.12+ and rerun this script." >&2
    exit 1
fi

# 2. Check for uv or fallback to standard venv + pip
USE_UV=false
if command -v uv >/dev/null 2>&1; then
    USE_UV=true
    echo "[+] Found uv package manager (fast install mode)"
else
    echo "[*] uv not found; proceeding with standard pip and venv"
fi

# 3. Create or reuse virtual environment
if [ "$USE_UV" = true ]; then
    echo "[*] Syncing project dependencies with uv..."
    uv sync
    VENV_DIR="$SCRIPT_DIR/.venv"
else
    VENV_DIR="$SCRIPT_DIR/.venv"
    if [ ! -d "$VENV_DIR" ]; then
        echo "[*] Creating virtual environment in .venv..."
        "$PYTHON_BIN" -m venv "$VENV_DIR"
    else
        echo "[+] Reusing existing virtual environment in .venv"
    fi

    echo "[*] Upgrading pip and build tools..."
    "$VENV_DIR/bin/pip" install --upgrade pip setuptools wheel --quiet

    echo "[*] Installing lanyard in editable mode..."
    "$VENV_DIR/bin/pip" install -e . --quiet
fi

# 4. Fetch Camoufox browser binaries
echo "[*] Fetching Camoufox stealth browser binaries..."
if [ -f "$VENV_DIR/bin/camoufox" ]; then
    "$VENV_DIR/bin/camoufox" fetch
elif [ "$USE_UV" = true ]; then
    uv run camoufox fetch
else
    echo "[-] Warning: camoufox executable not found in $VENV_DIR/bin"
fi

# 5. Install Playwright browser system dependencies on Linux if apt is present
if [ "$(uname -s)" = "Linux" ] && command -v apt-get >/dev/null 2>&1 && [ -f "$VENV_DIR/bin/playwright" ]; then
    if [ "${INSTALL_SYSTEM_DEPS:-0}" = "1" ]; then
        echo "[*] Installing system dependencies for Playwright/Camoufox..."
        sudo "$VENV_DIR/bin/playwright" install-deps firefox || true
    fi
fi

# 6. Initialize local configuration and templates
LANYARD_HOME="$HOME/.lanyard"
mkdir -p "$LANYARD_HOME/session"
echo "[+] Initialized directory: $LANYARD_HOME"

if [ ! -f .env ] && [ -f .env.example ]; then
    cp .env.example .env
    echo "[+] Created default .env from .env.example"
fi

# 7. Verification check
echo "[*] Verifying CLI installation..."
if "$VENV_DIR/bin/lanyard" --help >/dev/null 2>&1; then
    echo "[+] Lanyard CLI verified successfully!"
else
    echo "[-] Warning: CLI verification test failed. Check installation logs." >&2
fi

echo ""
echo "=================================================="
echo "           Setup Completed Successfully           "
echo "=================================================="
echo ""
echo "To get started, activate your virtual environment:"
echo "    source .venv/bin/activate"
echo ""
echo "Next steps:"
echo "  1. Authenticate with LinkedIn:"
echo "     lanyard login"
echo "     # or: lanyard cookie \"AQED...\""
echo ""
echo "  2. Configure your vision provider:"
echo "     lanyard config --provider gemini --gemini-key \"AIzaSy...\""
echo ""
echo "  3. Launch a badge hunt:"
echo "     lanyard hunt -c \"Target Company\" --depth 5"
echo ""
