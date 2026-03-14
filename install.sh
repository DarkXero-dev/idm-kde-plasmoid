#!/usr/bin/env bash
# IDM Quota Monitor — installer
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
    echo "    Unknown package manager — falling back to pip"
fi

# Verify both are importable; pip-install anything still missing
for pkg in requests "cryptography.fernet"; do
    python3 -c "import $pkg" 2>/dev/null || {
        pip_pkg="${pkg%%.*}"   # strip submodule for pip name
        echo "    $pip_pkg not found via system package — installing with pip"
        pip install --user "$pip_pkg"
    }
done

# ── 2. Copy plasmoid + bust QML cache ─────────────────────────────────────
echo "==> Copying plasmoid to $PLASMOID_DEST"
mkdir -p "$PLASMOID_DEST"
rsync -a --exclude='history_*.json' "$PLASMOID_SRC/" "$PLASMOID_DEST/"

echo "==> Clearing QML cache"
find ~/.cache -maxdepth 4 \( -name "*.qmlc" -o -name "*.jsc" \) \
     -path "*$PLASMOID_ID*" -delete 2>/dev/null
rm -rf ~/.cache/plasmashell 2>/dev/null || true

# ── 3. Install systemd units ───────────────────────────────────────────────
echo "==> Installing systemd user units"
mkdir -p "$SYSTEMD_USER"
cp "$PLASMOID_SRC/idm-quota.timer" "$SYSTEMD_USER/"
sed "s|PLACEHOLDER_USER|$(whoami)|g" \
    "$PLASMOID_SRC/idm-quota.service" > "$SYSTEMD_USER/idm-quota.service"

# ── 4. Reload systemd (timer stays off until enabled via widget Settings) ──
echo "==> Reloading systemd user daemon"
systemctl --user daemon-reload

echo ""
echo "Done. Next steps:"
echo "  1. Restart plasmashell:  kquitapp6 plasmashell; plasmashell &"
echo "  2. Right-click panel → Add Widgets → search 'IDM Quota'"
echo "  3. Right-click widget → Configure → enter your IDM username and password"
echo "  4. In widget Settings, toggle 'Enable timer' ON to start auto-refresh"
echo "  5. Click the ADSL/LTE badge on the panel to toggle which connection is shown"
