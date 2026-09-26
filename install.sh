#!/usr/bin/env bash
# IDM Quota Monitor installer
# Run once after a fresh system install.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLASMOID_SRC="$REPO_DIR/idm-quota-monitor"
PLASMOID_ID="com.github.idm-quota-monitor"
PLASMOID_DEST="$HOME/.local/share/plasma/plasmoids/$PLASMOID_ID"
SYSTEMD_USER="$HOME/.config/systemd/user"

# ── 1. Install Python dependencies ─────────────────────────────────────────
echo "==> Installing Python dependencies (requests, cryptography)"
if command -v pacman &>/dev/null; then
    sudo pacman -S --needed --noconfirm python-requests python-cryptography
elif command -v apt &>/dev/null; then
    sudo apt install -y python3-requests python3-cryptography
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-requests python3-cryptography
else
    echo "    Unknown package manager, falling back to pip"
fi

declare -A PIP_NAMES=([requests]=requests [cryptography.fernet]=cryptography)
for module in "${!PIP_NAMES[@]}"; do
    python3 -c "import $module" 2>/dev/null || {
        echo "    ${PIP_NAMES[$module]} not found via system package, installing with pip"
        pip install --user "${PIP_NAMES[$module]}"
    }
done

# ── 2. Copy plasmoid + bust QML cache ─────────────────────────────────────
echo "==> Copying plasmoid to $PLASMOID_DEST"
rm -rf "$PLASMOID_DEST"
mkdir -p "$PLASMOID_DEST"
cp -a "$PLASMOID_SRC/." "$PLASMOID_DEST/"
find "$PLASMOID_DEST" -name __pycache__ -type d -prune -exec rm -rf {} +

echo "==> Clearing QML cache"
find ~/.cache -maxdepth 4 \( -name "*.qmlc" -o -name "*.jsc" \) \
     -path "*$PLASMOID_ID*" -delete 2>/dev/null || true
rm -rf ~/.cache/plasmashell 2>/dev/null || true

# ── 3. Remove the systemd units older versions installed ───────────────────
if [ -e "$SYSTEMD_USER/idm-quota.timer" ] || [ -e "$SYSTEMD_USER/idm-quota.service" ]; then
    echo "==> Removing old idm-quota systemd units (the widget refreshes itself now)"
    systemctl --user disable --now idm-quota.timer 2>/dev/null || true
    rm -f "$SYSTEMD_USER/idm-quota.timer" "$SYSTEMD_USER/idm-quota.service"
    systemctl --user daemon-reload
fi

echo ""
echo "Done. Next steps:"
echo "  1. Restart plasmashell:  kquitapp6 plasmashell; plasmashell &"
echo "  2. Right-click panel -> Add Widgets -> search 'IDM Quota'"
echo "  3. Right-click widget -> Configure -> enter your IDM login, then click 'Detect services'"
echo "  4. Tick up to 3 services to show; click the badge on the panel to cycle them"
