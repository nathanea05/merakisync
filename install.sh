#!/bin/sh
# merakisync installer
#
# Usage:
#   curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh
#
# Options (pass after --):
#   --version VERSION     Install a specific version tag (e.g. v1.0.0). Default: latest.
#   --install-dir DIR     Install binary to DIR. Default: /usr/local/bin or ~/.local/bin.
#
# Example — pin to a version:
#   curl -LsSf .../install.sh | sh -s -- --version v1.2.0

set -eu

REPO="nathanea05/merakisync"
BINARY="merakisync"
VERSION=""
INSTALL_DIR=""

# ── helpers ──────────────────────────────────────────────────────────────────

say()  { printf "  %s\n" "$1"; }
ok()   { printf "✓ %s\n" "$1"; }
err()  { printf "error: %s\n" "$1" >&2; exit 1; }

need() {
    command -v "$1" > /dev/null 2>&1 || err "required tool not found: $1"
}

# Download a URL to a file. Tries curl, then wget.
download() {
    url="$1"; dest="$2"
    if command -v curl > /dev/null 2>&1; then
        curl -LsSf --retry 3 "$url" -o "$dest"
    elif command -v wget > /dev/null 2>&1; then
        wget -q --tries=3 "$url" -O "$dest"
    else
        err "neither curl nor wget found — cannot download"
    fi
}

# ── platform detection ────────────────────────────────────────────────────────

detect_platform() {
    os="$(uname -s)"
    case "$os" in
        Linux)  os="linux"  ;;
        Darwin) os="darwin" ;;
        *)      err "unsupported OS: $os" ;;
    esac

    arch="$(uname -m)"
    case "$arch" in
        x86_64 | amd64)  arch="x86_64" ;;
        aarch64 | arm64) arch="arm64"  ;;
        *)               err "unsupported architecture: $arch" ;;
    esac

    PLATFORM="${os}-${arch}"
}

# ── argument parsing ──────────────────────────────────────────────────────────

parse_args() {
    while [ $# -gt 0 ]; do
        case "$1" in
            --version)
                shift
                VERSION="${1:-}"
                [ -z "$VERSION" ] && err "--version requires an argument"
                ;;
            --install-dir)
                shift
                INSTALL_DIR="${1:-}"
                [ -z "$INSTALL_DIR" ] && err "--install-dir requires an argument"
                ;;
            --help | -h)
                cat <<EOF
merakisync installer

USAGE:
    curl -LsSf https://raw.githubusercontent.com/nathanea05/merakisync/main/install.sh | sh

OPTIONS:
    --version VERSION     Install a specific release tag (e.g. v1.0.0)
    --install-dir DIR     Install to DIR instead of the default location
EOF
                exit 0
                ;;
            *)
                err "unknown argument: $1"
                ;;
        esac
        shift
    done
}

# ── install directory ─────────────────────────────────────────────────────────

resolve_install_dir() {
    if [ -n "$INSTALL_DIR" ]; then
        return
    fi

    # MERAKISYNC_INSTALL_DIR env var allows sysadmins to override via their
    # config-management tooling without touching the command line.
    if [ -n "${MERAKISYNC_INSTALL_DIR:-}" ]; then
        INSTALL_DIR="$MERAKISYNC_INSTALL_DIR"
        return
    fi

    if [ "$(id -u)" = "0" ] || [ -w "/usr/local/bin" ]; then
        INSTALL_DIR="/usr/local/bin"
    else
        INSTALL_DIR="${HOME}/.local/bin"
    fi
}

# ── version resolution ────────────────────────────────────────────────────────

resolve_version() {
    [ -n "$VERSION" ] && return

    say "Fetching latest release..."
    tmp="$(mktemp)"
    download "https://api.github.com/repos/${REPO}/releases/latest" "$tmp"

    # Parse tag_name without requiring jq
    VERSION="$(grep '"tag_name"' "$tmp" | head -1 | sed 's/.*"tag_name" *: *"\([^"]*\)".*/\1/')"
    rm -f "$tmp"

    [ -n "$VERSION" ] || err "could not determine latest version — try --version vX.Y.Z"
}

# ── checksum verification ─────────────────────────────────────────────────────

verify_checksum() {
    binary_file="$1"
    checksums_file="$2"
    expected_name="${BINARY}-${PLATFORM}"

    expected="$(grep " ${expected_name}$" "$checksums_file" | awk '{print $1}')"
    [ -n "$expected" ] || { say "No checksum entry for ${expected_name} — skipping verification"; return; }

    if command -v sha256sum > /dev/null 2>&1; then
        actual="$(sha256sum "$binary_file" | awk '{print $1}')"
    elif command -v shasum > /dev/null 2>&1; then
        actual="$(shasum -a 256 "$binary_file" | awk '{print $1}')"
    else
        say "sha256sum / shasum not found — skipping checksum verification"
        return
    fi

    [ "$actual" = "$expected" ] || err "checksum mismatch for ${expected_name}
  expected: $expected
  actual:   $actual
Download may be corrupted. Aborting."

    ok "Checksum verified"
}

# ── main ──────────────────────────────────────────────────────────────────────

main() {
    parse_args "$@"
    detect_platform
    resolve_version
    resolve_install_dir

    base_url="https://github.com/${REPO}/releases/download/${VERSION}"
    binary_url="${base_url}/${BINARY}-${PLATFORM}"
    checksums_url="${base_url}/checksums.txt"

    printf "\nInstalling %s %s (%s)\n\n" "$BINARY" "$VERSION" "$PLATFORM"
    say "Download:    $binary_url"
    say "Install dir: $INSTALL_DIR"
    printf "\n"

    # Temp files — cleaned up on exit
    tmp_dir="$(mktemp -d)"
    trap 'rm -rf "$tmp_dir"' EXIT

    tmp_binary="${tmp_dir}/${BINARY}"
    tmp_checksums="${tmp_dir}/checksums.txt"

    # Download binary
    say "Downloading binary..."
    download "$binary_url" "$tmp_binary" \
        || err "download failed: $binary_url
Check that ${VERSION} exists at https://github.com/${REPO}/releases"

    # Download and verify checksum (best-effort — warn but don't fail if
    # checksums.txt is absent, e.g. for pre-release builds)
    say "Verifying checksum..."
    if download "$checksums_url" "$tmp_checksums" 2>/dev/null; then
        verify_checksum "$tmp_binary" "$tmp_checksums"
    else
        say "checksums.txt not found for this release — skipping verification"
    fi

    chmod +x "$tmp_binary"

    # Create install dir if needed
    if [ ! -d "$INSTALL_DIR" ]; then
        mkdir -p "$INSTALL_DIR" 2>/dev/null \
            || sudo mkdir -p "$INSTALL_DIR" \
            || err "could not create install directory: $INSTALL_DIR"
    fi

    # Install — use sudo if the directory isn't writable by the current user
    dest="${INSTALL_DIR}/${BINARY}"
    if [ -w "$INSTALL_DIR" ]; then
        mv "$tmp_binary" "$dest"
    else
        say "Requesting sudo to write to ${INSTALL_DIR}..."
        sudo mv "$tmp_binary" "$dest"
    fi

    ok "Installed ${dest}"

    # Warn if install dir is not on PATH
    case ":${PATH}:" in
        *":${INSTALL_DIR}:"*) ;;
        *)
            printf "\nNOTE: %s is not in your PATH.\n" "$INSTALL_DIR"
            printf "      Add the following to your shell profile:\n\n"
            printf "          export PATH=\"%s:\$PATH\"\n\n" "$INSTALL_DIR"
            ;;
    esac

    printf "\nRun '%s init' to configure your API key and database.\n\n" "$BINARY"
}

main "$@"
