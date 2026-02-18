#!/usr/bin/env bash
# TRUST Protocol installer
# Usage: curl -fsSL https://agitrust.network/install.sh | bash
#
# This script installs the TRUST Protocol CLI and Python library.
# It requires Python 3.10+ and pip.

set -euo pipefail

REPO="https://github.com/jarethmt/TRUST-Protocol.git"
MIN_PYTHON_MAJOR=3
MIN_PYTHON_MINOR=10
INSTALL_DIR="${TRUST_PROTOCOL_HOME:-$HOME/.trust-protocol}"

# --- Colors (only if terminal supports them) ---
if [ -t 1 ]; then
    RED='\033[0;31m'
    GREEN='\033[0;32m'
    YELLOW='\033[0;33m'
    BLUE='\033[0;34m'
    BOLD='\033[1m'
    DIM='\033[2m'
    RESET='\033[0m'
else
    RED='' GREEN='' YELLOW='' BLUE='' BOLD='' DIM='' RESET=''
fi

info()  { printf "${BLUE}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
ok()    { printf "${GREEN}==>${RESET} ${BOLD}%s${RESET}\n" "$*"; }
warn()  { printf "${YELLOW}warning:${RESET} %s\n" "$*"; }
err()   { printf "${RED}error:${RESET} %s\n" "$*" >&2; }
dim()   { printf "${DIM}    %s${RESET}\n" "$*"; }

# --- Banner ---
printf "\n"
printf "${BOLD}  TRUST Protocol${RESET}\n"
printf "${DIM}  Transparent Revocable Unified Security & Trust${RESET}\n"
printf "${DIM}  https://agitrust.network${RESET}\n"
printf "\n"

# --- Check Python ---
info "Checking Python version..."

PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        py_version=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || true)
        if [ -n "$py_version" ]; then
            py_major=$(echo "$py_version" | cut -d. -f1)
            py_minor=$(echo "$py_version" | cut -d. -f2)
            if [ "$py_major" -ge "$MIN_PYTHON_MAJOR" ] && [ "$py_minor" -ge "$MIN_PYTHON_MINOR" ]; then
                PYTHON="$cmd"
                break
            fi
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    err "Python ${MIN_PYTHON_MAJOR}.${MIN_PYTHON_MINOR}+ is required but not found."
    printf "\n"
    printf "  Install Python:\n"
    printf "    macOS:   brew install python@3.12\n"
    printf "    Ubuntu:  sudo apt install python3.12 python3.12-venv\n"
    printf "    Fedora:  sudo dnf install python3.12\n"
    printf "    Windows: https://python.org/downloads\n"
    printf "\n"
    exit 1
fi

ok "Found $PYTHON ($py_version)"

# --- Check pip ---
info "Checking pip..."

if ! "$PYTHON" -m pip --version &>/dev/null; then
    err "pip is not available for $PYTHON."
    printf "\n"
    printf "  Install pip:\n"
    printf "    ${PYTHON} -m ensurepip --upgrade\n"
    printf "    # or: curl -fsSL https://bootstrap.pypa.io/get-pip.py | ${PYTHON}\n"
    printf "\n"
    exit 1
fi

ok "pip available"

# --- Check git ---
info "Checking git..."

if ! command -v git &>/dev/null; then
    err "git is required but not found."
    printf "\n"
    printf "  Install git:\n"
    printf "    macOS:   xcode-select --install\n"
    printf "    Ubuntu:  sudo apt install git\n"
    printf "    Fedora:  sudo dnf install git\n"
    printf "\n"
    exit 1
fi

ok "git available"

# --- Install ---
info "Installing TRUST Protocol..."

# Use pip install directly from git (no clone needed)
"$PYTHON" -m pip install --quiet --upgrade "trust-protocol @ git+${REPO}" 2>&1 | while IFS= read -r line; do
    dim "$line"
done

# Verify installation
if ! command -v trust-protocol &>/dev/null; then
    # pip --user installs might not be on PATH
    USER_BIN=$("$PYTHON" -c "import site; print(site.getusersitepackages().replace('lib/python', 'bin').split('/lib/')[0] + '/bin')" 2>/dev/null || true)
    if [ -n "$USER_BIN" ] && [ -f "$USER_BIN/trust-protocol" ]; then
        warn "trust-protocol was installed to $USER_BIN which is not on your PATH."
        printf "\n"
        printf "  Add it to your shell config:\n"
        printf "    export PATH=\"\$PATH:$USER_BIN\"\n"
        printf "\n"
    else
        err "Installation completed but trust-protocol command not found."
        printf "  Try: ${PYTHON} -m trust_protocol.cli.main --help\n"
        exit 1
    fi
fi

# --- Done ---
printf "\n"
printf "${GREEN}${BOLD}  TRUST Protocol installed successfully.${RESET}\n"
printf "\n"
printf "  ${BOLD}Quick start:${RESET}\n"
printf "\n"
printf "    # Start the server\n"
printf "    trust-protocol serve\n"
printf "\n"
printf "    # Read the auto-generated admin key\n"
printf "    cat data/.admin_key\n"
printf "\n"
printf "    # Unseal the vault (interactive password prompt)\n"
printf "    trust-protocol unseal --admin-key \$(cat data/.admin_key)\n"
printf "\n"
printf "  ${BOLD}Full guide:${RESET} https://agitrust.network/getting-started/quickstart/\n"
printf "\n"
printf "  ${BOLD}Set up skill signing:${RESET}\n"
printf "\n"
printf "    trust-protocol setup\n"
printf "\n"
