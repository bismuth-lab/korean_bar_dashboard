#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

LABEL="com.nohjunho.barpass-public-publish"
SOURCE_PLIST="$PWD/launchd/$LABEL.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"
WRAPPER="$HOME/.local/bin/barpass_public_publish_launchd.sh"
TERMINAL_COMMAND="$HOME/.local/bin/barpass_public_publish_terminal.command"

mkdir -p "$HOME/Library/LaunchAgents"
mkdir -p "$HOME/.local/bin" "$HOME/Library/Logs/barpass"
cat > "$WRAPPER" <<EOF
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$PWD"
cd "\$PROJECT_DIR"

if [ -x "/Library/Frameworks/Python.framework/Versions/3.13/bin/python3" ]; then
  PYTHON="/Library/Frameworks/Python.framework/Versions/3.13/bin/python3"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON="\$(command -v python3)"
else
  PYTHON="python"
fi

"\$PYTHON" export_public.py
"\$PYTHON" export_static_public.py

mkdir -p docs
cp public/public_log.csv public/public_summary.json public/index.html docs/

git add public/public_log.csv public/public_summary.json public/index.html docs/public_log.csv docs/public_summary.json docs/index.html

if git diff --cached --quiet; then
  echo "No public dashboard changes to publish."
  exit 0
fi

git commit -m "Update public BarPass log"
git push
EOF
chmod +x "$WRAPPER"
cat > "$TERMINAL_COMMAND" <<EOF
#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$PWD"
LOG_DIR="\$HOME/Library/Logs/barpass"
mkdir -p "\$LOG_DIR"

{
  echo "[\$(date '+%Y-%m-%d %H:%M:%S')] start"
  cd "\$PROJECT_DIR"
  ./publish_public.sh
  echo "[\$(date '+%Y-%m-%d %H:%M:%S')] done"
} >> "\$LOG_DIR/public_publish.log" 2>> "\$LOG_DIR/public_publish.err.log"
EOF
chmod +x "$TERMINAL_COMMAND"
cp "$SOURCE_PLIST" "$TARGET_PLIST"

launchctl bootout "gui/$(id -u)" "$TARGET_PLIST" >/dev/null 2>&1 || true
launchctl bootstrap "gui/$(id -u)" "$TARGET_PLIST"

echo "Installed daily BarPass public publish job:"
echo "$TARGET_PLIST"
echo "Schedule: every day at 07:10"
