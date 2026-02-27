#!/bin/bash
# ============================================================================
# Rune Installer
# ============================================================================
# Installation script for Linux and macOS.
# Uses uv for fast Python provisioning and package management.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/freddiev4/rune/main/scripts/install.sh | bash
#
# Or with options:
#   curl -fsSL ... | bash -s -- --skip-setup
#
# ============================================================================

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color
BOLD='\033[1m'

# Configuration
REPO_URL_SSH="git@github.com:freddiev4/rune.git"
REPO_URL_HTTPS="https://github.com/freddiev4/rune.git"
RUNE_HOME="$HOME/.rune"
INSTALL_DIR="${RUNE_INSTALL_DIR:-$RUNE_HOME/rune}"
PYTHON_VERSION="3.10"

# Options
USE_VENV=true
RUN_SETUP=true
BRANCH="main"

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-venv)
            USE_VENV=false
            shift
            ;;
        --skip-setup)
            RUN_SETUP=false
            shift
            ;;
        --branch)
            BRANCH="$2"
            shift 2
            ;;
        --dir)
            INSTALL_DIR="$2"
            shift 2
            ;;
        -h|--help)
            echo "Rune Installer"
            echo ""
            echo "Usage: install.sh [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --no-venv      Don't create virtual environment"
            echo "  --skip-setup   Skip interactive API key setup"
            echo "  --branch NAME  Git branch to install (default: main)"
            echo "  --dir PATH     Installation directory (default: ~/.rune/rune)"
            echo "  -h, --help     Show this help"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Helper functions
# ============================================================================

print_banner() {
    echo ""
    echo -e "${MAGENTA}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│                  Rune Installer                         │"
    echo "│          A powerful coding agent with a clean API       │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
}

log_info() {
    echo -e "${CYAN}→${NC} $1"
}

log_success() {
    echo -e "${GREEN}✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

log_error() {
    echo -e "${RED}✗${NC} $1"
}

# ============================================================================
# System detection
# ============================================================================

detect_os() {
    case "$(uname -s)" in
        Linux*)
            OS="linux"
            if [ -f /etc/os-release ]; then
                . /etc/os-release
                DISTRO="$ID"
            else
                DISTRO="unknown"
            fi
            ;;
        Darwin*)
            OS="macos"
            DISTRO="macos"
            ;;
        CYGWIN*|MINGW*|MSYS*)
            log_error "Windows is not supported by this installer."
            log_info "Please install manually: https://github.com/freddiev4/rune"
            exit 1
            ;;
        *)
            OS="unknown"
            DISTRO="unknown"
            log_warn "Unknown operating system — proceeding anyway"
            ;;
    esac

    log_success "Detected: $OS ($DISTRO)"
}

# ============================================================================
# Dependency checks
# ============================================================================

install_uv() {
    log_info "Checking for uv package manager..."

    if command -v uv &> /dev/null; then
        UV_CMD="uv"
        UV_VERSION=$($UV_CMD --version 2>/dev/null)
        log_success "uv found ($UV_VERSION)"
        return 0
    fi

    # Check ~/.local/bin (default uv install location) even if not on PATH yet
    if [ -x "$HOME/.local/bin/uv" ]; then
        UV_CMD="$HOME/.local/bin/uv"
        UV_VERSION=$($UV_CMD --version 2>/dev/null)
        log_success "uv found at ~/.local/bin ($UV_VERSION)"
        return 0
    fi

    # Check ~/.cargo/bin (alternative uv install location)
    if [ -x "$HOME/.cargo/bin/uv" ]; then
        UV_CMD="$HOME/.cargo/bin/uv"
        UV_VERSION=$($UV_CMD --version 2>/dev/null)
        log_success "uv found at ~/.cargo/bin ($UV_VERSION)"
        return 0
    fi

    log_info "Installing uv (fast Python package manager)..."
    if curl -LsSf https://astral.sh/uv/install.sh | sh 2>/dev/null; then
        if [ -x "$HOME/.local/bin/uv" ]; then
            UV_CMD="$HOME/.local/bin/uv"
        elif [ -x "$HOME/.cargo/bin/uv" ]; then
            UV_CMD="$HOME/.cargo/bin/uv"
        elif command -v uv &> /dev/null; then
            UV_CMD="uv"
        else
            log_error "uv installed but not found on PATH"
            log_info "Try adding ~/.local/bin to your PATH and re-running"
            exit 1
        fi
        UV_VERSION=$($UV_CMD --version 2>/dev/null)
        log_success "uv installed ($UV_VERSION)"
    else
        log_error "Failed to install uv"
        log_info "Install manually: https://docs.astral.sh/uv/getting-started/installation/"
        exit 1
    fi
}

check_python() {
    log_info "Checking Python $PYTHON_VERSION..."

    if $UV_CMD python find "$PYTHON_VERSION" &> /dev/null; then
        PYTHON_PATH=$($UV_CMD python find "$PYTHON_VERSION")
        PYTHON_FOUND_VERSION=$($PYTHON_PATH --version 2>/dev/null)
        log_success "Python found: $PYTHON_FOUND_VERSION"
        return 0
    fi

    log_info "Python $PYTHON_VERSION not found, installing via uv..."
    if $UV_CMD python install "$PYTHON_VERSION"; then
        PYTHON_PATH=$($UV_CMD python find "$PYTHON_VERSION")
        PYTHON_FOUND_VERSION=$($PYTHON_PATH --version 2>/dev/null)
        log_success "Python installed: $PYTHON_FOUND_VERSION"
    else
        log_error "Failed to install Python $PYTHON_VERSION"
        log_info "Install Python $PYTHON_VERSION manually, then re-run this script"
        exit 1
    fi
}

check_git() {
    log_info "Checking Git..."

    if command -v git &> /dev/null; then
        GIT_VERSION=$(git --version | awk '{print $3}')
        log_success "Git $GIT_VERSION found"
        return 0
    fi

    log_error "Git not found"
    log_info "Please install Git:"

    case "$OS" in
        linux)
            case "$DISTRO" in
                ubuntu|debian) log_info "  sudo apt update && sudo apt install git" ;;
                fedora)        log_info "  sudo dnf install git" ;;
                arch)          log_info "  sudo pacman -S git" ;;
                *)             log_info "  Use your package manager to install git" ;;
            esac
            ;;
        macos)
            log_info "  xcode-select --install"
            log_info "  Or: brew install git"
            ;;
    esac

    exit 1
}

# ============================================================================
# Installation
# ============================================================================

clone_repo() {
    log_info "Installing to $INSTALL_DIR..."

    if [ -d "$INSTALL_DIR" ]; then
        if [ -d "$INSTALL_DIR/.git" ]; then
            log_info "Existing installation found, updating..."
            cd "$INSTALL_DIR"
            git fetch origin
            git checkout "$BRANCH"
            git pull origin "$BRANCH"
        else
            log_error "Directory exists but is not a git repository: $INSTALL_DIR"
            log_info "Remove it or choose a different directory with --dir"
            exit 1
        fi
    else
        # Try SSH first (fails fast if no key is configured), fall back to HTTPS
        log_info "Trying SSH clone..."
        if GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=5" \
           git clone --branch "$BRANCH" "$REPO_URL_SSH" "$INSTALL_DIR" 2>/dev/null; then
            log_success "Cloned via SSH"
        else
            rm -rf "$INSTALL_DIR" 2>/dev/null
            log_info "SSH failed, trying HTTPS..."
            if git clone --branch "$BRANCH" "$REPO_URL_HTTPS" "$INSTALL_DIR"; then
                log_success "Cloned via HTTPS"
            else
                log_error "Failed to clone repository"
                exit 1
            fi
        fi
    fi

    log_success "Repository ready"
}

setup_venv() {
    if [ "$USE_VENV" = false ]; then
        log_info "Skipping virtual environment (--no-venv)"
        return 0
    fi

    log_info "Creating virtual environment with Python $PYTHON_VERSION..."

    cd "$INSTALL_DIR"

    if [ -d ".venv" ]; then
        log_info "Virtual environment already exists, recreating..."
        rm -rf .venv
    fi

    $UV_CMD venv .venv --python "$PYTHON_VERSION"

    log_success "Virtual environment ready"
}

install_deps() {
    log_info "Installing dependencies..."

    cd "$INSTALL_DIR"

    if [ "$USE_VENV" = true ]; then
        export VIRTUAL_ENV="$INSTALL_DIR/.venv"
    fi

    if ! $UV_CMD pip install -e "." 2>/dev/null; then
        log_error "Package installation failed."
        log_info "Try manually: cd $INSTALL_DIR && uv pip install -e ."
        exit 1
    fi

    log_success "Dependencies installed"
}

setup_path() {
    log_info "Setting up rune command..."

    if [ "$USE_VENV" = true ]; then
        RUNE_BIN="$INSTALL_DIR/.venv/bin/rune"
    else
        RUNE_BIN="$(command -v rune 2>/dev/null || echo "")"
        if [ -z "$RUNE_BIN" ]; then
            log_warn "rune not found on PATH after install"
            return 0
        fi
    fi

    if [ ! -x "$RUNE_BIN" ]; then
        log_warn "rune entry point not found at $RUNE_BIN"
        log_info "Try: cd $INSTALL_DIR && uv pip install -e ."
        return 0
    fi

    mkdir -p "$HOME/.local/bin"
    ln -sf "$RUNE_BIN" "$HOME/.local/bin/rune"
    log_success "Symlinked rune → ~/.local/bin/rune"

    # Add ~/.local/bin to PATH in shell configs if not already present
    if ! echo "$PATH" | tr ':' '\n' | grep -q "^$HOME/.local/bin$"; then
        SHELL_CONFIGS=()
        LOGIN_SHELL="$(basename "${SHELL:-/bin/bash}")"
        case "$LOGIN_SHELL" in
            zsh)
                [ -f "$HOME/.zshrc" ] && SHELL_CONFIGS+=("$HOME/.zshrc")
                ;;
            bash)
                [ -f "$HOME/.bashrc" ]       && SHELL_CONFIGS+=("$HOME/.bashrc")
                [ -f "$HOME/.bash_profile" ] && SHELL_CONFIGS+=("$HOME/.bash_profile")
                ;;
            *)
                [ -f "$HOME/.bashrc" ] && SHELL_CONFIGS+=("$HOME/.bashrc")
                [ -f "$HOME/.zshrc" ]  && SHELL_CONFIGS+=("$HOME/.zshrc")
                ;;
        esac
        [ -f "$HOME/.profile" ] && SHELL_CONFIGS+=("$HOME/.profile")

        PATH_LINE='export PATH="$HOME/.local/bin:$PATH"'

        for SHELL_CONFIG in "${SHELL_CONFIGS[@]}"; do
            if ! grep -q '\.local/bin' "$SHELL_CONFIG" 2>/dev/null; then
                echo "" >> "$SHELL_CONFIG"
                echo "# Rune — ensure ~/.local/bin is on PATH" >> "$SHELL_CONFIG"
                echo "$PATH_LINE" >> "$SHELL_CONFIG"
                log_success "Added ~/.local/bin to PATH in $SHELL_CONFIG"
            fi
        done

        if [ ${#SHELL_CONFIGS[@]} -eq 0 ]; then
            log_warn "Could not detect shell config file to add ~/.local/bin to PATH"
            log_info "Add manually: $PATH_LINE"
        fi
    else
        log_info "~/.local/bin already on PATH"
    fi

    export PATH="$HOME/.local/bin:$PATH"
    log_success "rune command ready"
}

copy_config_templates() {
    log_info "Setting up configuration directory..."

    mkdir -p "$RUNE_HOME"

    # Create .env at ~/.rune/.env if it doesn't exist
    if [ ! -f "$RUNE_HOME/.env" ]; then
        if [ -f "$INSTALL_DIR/.env.example" ]; then
            cp "$INSTALL_DIR/.env.example" "$RUNE_HOME/.env"
            log_success "Created ~/.rune/.env from template"
        else
            cat > "$RUNE_HOME/.env" << 'EOF'
# Rune API Keys — edit this file to add your keys, then run: source ~/.rune/.env

# OpenAI API key (https://platform.openai.com/api-keys)
export OPENAI_API_KEY=

# Anthropic API key (https://console.anthropic.com/)
export ANTHROPIC_API_KEY=

# Tavily API key — optional, enables web_search tool (https://tavily.com/)
export TAVILY_API_KEY=
EOF
            log_success "Created ~/.rune/.env"
        fi
    else
        log_info "~/.rune/.env already exists, keeping it"
    fi

    log_success "Configuration directory ready: ~/.rune/"
}

run_setup_wizard() {
    if [ "$RUN_SETUP" = false ]; then
        log_info "Skipping setup (--skip-setup)"
        log_info "Edit ~/.rune/.env to add your API keys"
        return 0
    fi

    echo ""
    echo -e "${CYAN}${BOLD}API Key Setup${NC}"
    echo -e "${CYAN}─────────────────────────────────────────────────────────${NC}"
    echo ""
    echo "Rune supports OpenAI and Anthropic models. You need at least one API key."
    echo "Keys are saved to ~/.rune/.env and sourced automatically on login."
    echo ""

    ENV_FILE="$RUNE_HOME/.env"
    ADDED_KEYS=false

    # OpenAI
    read -p "Enter your OpenAI API key (sk-...) or press Enter to skip: " -r OPENAI_KEY < /dev/tty
    if [ -n "$OPENAI_KEY" ]; then
        if grep -q "^export OPENAI_API_KEY=" "$ENV_FILE" 2>/dev/null; then
            # Update existing line
            sed -i.bak "s|^export OPENAI_API_KEY=.*|export OPENAI_API_KEY=$OPENAI_KEY|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
        else
            echo "export OPENAI_API_KEY=$OPENAI_KEY" >> "$ENV_FILE"
        fi
        log_success "OpenAI API key saved"
        ADDED_KEYS=true
    fi

    # Anthropic
    read -p "Enter your Anthropic API key (sk-ant-...) or press Enter to skip: " -r ANTHROPIC_KEY < /dev/tty
    if [ -n "$ANTHROPIC_KEY" ]; then
        if grep -q "^export ANTHROPIC_API_KEY=" "$ENV_FILE" 2>/dev/null; then
            sed -i.bak "s|^export ANTHROPIC_API_KEY=.*|export ANTHROPIC_API_KEY=$ANTHROPIC_KEY|" "$ENV_FILE"
            rm -f "$ENV_FILE.bak"
        else
            echo "export ANTHROPIC_API_KEY=$ANTHROPIC_KEY" >> "$ENV_FILE"
        fi
        log_success "Anthropic API key saved"
        ADDED_KEYS=true
    fi

    if [ "$ADDED_KEYS" = false ]; then
        log_warn "No API keys entered. Edit ~/.rune/.env before running rune."
    fi

    # Add source line to shell configs so keys are available on login
    SOURCE_LINE="[ -f \"\$HOME/.rune/.env\" ] && source \"\$HOME/.rune/.env\""
    SHELL_CONFIGS=()
    LOGIN_SHELL="$(basename "${SHELL:-/bin/bash}")"
    case "$LOGIN_SHELL" in
        zsh)  [ -f "$HOME/.zshrc" ]  && SHELL_CONFIGS+=("$HOME/.zshrc") ;;
        bash)
            [ -f "$HOME/.bashrc" ]       && SHELL_CONFIGS+=("$HOME/.bashrc")
            [ -f "$HOME/.bash_profile" ] && SHELL_CONFIGS+=("$HOME/.bash_profile")
            ;;
        *)
            [ -f "$HOME/.bashrc" ] && SHELL_CONFIGS+=("$HOME/.bashrc")
            [ -f "$HOME/.zshrc" ]  && SHELL_CONFIGS+=("$HOME/.zshrc")
            ;;
    esac

    for SHELL_CONFIG in "${SHELL_CONFIGS[@]}"; do
        if ! grep -q '\.rune/\.env' "$SHELL_CONFIG" 2>/dev/null; then
            echo "" >> "$SHELL_CONFIG"
            echo "# Rune — load API keys" >> "$SHELL_CONFIG"
            echo "$SOURCE_LINE" >> "$SHELL_CONFIG"
            log_success "Added .env auto-load to $SHELL_CONFIG"
        fi
    done

    # Source for the current session too
    # shellcheck source=/dev/null
    source "$ENV_FILE" 2>/dev/null || true
}

print_success() {
    echo ""
    echo -e "${GREEN}${BOLD}"
    echo "┌─────────────────────────────────────────────────────────┐"
    echo "│              ✓ Installation Complete!                   │"
    echo "└─────────────────────────────────────────────────────────┘"
    echo -e "${NC}"
    echo ""

    echo -e "${CYAN}${BOLD}📁 Files:${NC}"
    echo ""
    echo -e "   ${YELLOW}API Keys:${NC}  ~/.rune/.env"
    echo -e "   ${YELLOW}Code:${NC}      ~/.rune/rune/"
    echo ""

    echo -e "${CYAN}─────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "${CYAN}${BOLD}🚀 Commands:${NC}"
    echo ""
    echo -e "   ${GREEN}rune${NC}                    Start interactive agent"
    echo -e "   ${GREEN}rune -p \"fix the bug\"${NC}   Single prompt mode"
    echo -e "   ${GREEN}rune --agent plan${NC}        Read-only planning agent"
    echo -e "   ${GREEN}rune --model anthropic/claude-sonnet-4-20250514${NC}"
    echo ""

    echo -e "${CYAN}─────────────────────────────────────────────────────────${NC}"
    echo ""
    echo -e "${YELLOW}⚡ Reload your shell to use the rune command:${NC}"
    echo ""
    echo "   source ~/.bashrc   # or ~/.zshrc"
    echo ""
}

# ============================================================================
# Main
# ============================================================================

main() {
    print_banner

    detect_os
    install_uv
    check_python
    check_git

    clone_repo
    setup_venv
    install_deps
    setup_path
    copy_config_templates
    run_setup_wizard

    print_success
}

main
