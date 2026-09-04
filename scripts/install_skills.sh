#!/usr/bin/env bash
# Universal Skill Installer for Linux / macOS (Codex, Cursor, Antigravity)

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SKILL_SRC="$ROOT_DIR/skills/zhihu-scraper-investigator"

TARGET_DIRS=(
    "$HOME/.gemini/config/skills/zhihu-scraper-investigator"
    "$HOME/.codex/skills/zhihu-scraper-investigator"
    "$HOME/.cursor/skills-cursor/zhihu-scraper-investigator"
    "$HOME/.agents/skills/zhihu-scraper-investigator"
)

echo "🚀 Injecting zhihu-scraper-investigator Skill across environments..."

for target in "${TARGET_DIRS[@]}"; do
    mkdir -p "$(dirname "$target")"
    rm -rf "$target"
    cp -r "$SKILL_SRC" "$target"
    echo "  ✓ Injected into: $target"
done

echo "🎉 Done! Skill is now active for Codex, Cursor, and Antigravity."
