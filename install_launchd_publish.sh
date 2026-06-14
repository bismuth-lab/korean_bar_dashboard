#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

LABEL="com.nohjunho.barpass-public-publish"
SOURCE_PLIST="$PWD/launchd/$LABEL.plist"
TARGET_PLIST="$HOME/Library/LaunchAgents/$LABEL.plist"

mkdir -p "$HOME/Library/LaunchAgents"
cp "$SOURCE_PLIST" "$TARGET_PLIST"

launchctl unload "$TARGET_PLIST" >/dev/null 2>&1 || true
launchctl load "$TARGET_PLIST"

echo "Installed daily BarPass public publish job:"
echo "$TARGET_PLIST"
echo "Schedule: every day at 07:10"
