#!/usr/bin/env bash
# IDM Quota Monitor — installer
# Run once after a fresh system install.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
PLASMOID_SRC="$REPO_DIR/idm-quota-monitor"
PLASMOID_ID="com.github.idm-quota-monitor"
PLASMOID_DEST="$HOME/.local/share/plasma/plasmoids/$PLASMOID_ID"
SYSTEMD_USER="$HOME/.config/systemd/user"

# ── 1. Install python-requests ─────────────────────────────────────────────
echo "==> Installing python-requests"
if command -v pacman &>/dev/null; then
    sudo pacman -S --needed --noconfirm python-requests
elif command -v apt &>/dev/null; then
    sudo apt install -y python3-requests
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-requests
else
    echo "    Unknown package manager — install python3-requests manually"
fi

# ── 2. Copy plasmoid ───────────────────────────────────────────────────────
echo "==> Copying plasmoid to $PLASMOID_DEST"
mkdir -p "$PLASMOID_DEST"
rsync -a --exclude='history_*.json' "$PLASMOID_SRC/" "$PLASMOID_DEST/"

# ── 3. Install systemd units ───────────────────────────────────────────────
echo "==> Installing systemd user units"
mkdir -p "$SYSTEMD_USER"
cp "$PLASMOID_SRC/idm-quota.timer" "$SYSTEMD_USER/"
sed "s|PLACEHOLDER_USER|$(whoami)|g" \
    "$PLASMOID_SRC/idm-quota.service" > "$SYSTEMD_USER/idm-quota.service"

# ── 4. Enable and start ────────────────────────────────────────────────────
echo "==> Enabling + starting systemd timer"
systemctl --user daemon-reload
systemctl --user enable --now idm-quota.timer
systemctl --user start idm-quota.service

echo ""
echo "Done. Next steps:"
echo "  1. Restart plasmashell:  kquitapp6 plasmashell; plasmashell &"
echo "  2. Right-click panel → Add Widgets → search 'IDM Quota'"
echo "  3. Right-click widget → Configure → enter your IDM username and password"
echo "  4. Click the ADSL/LTE badge on the panel to toggle which connection is shown"
echo ""
systemctl --user status idm-quota.timer --no-pager | grep -E "Active|Trigger"
