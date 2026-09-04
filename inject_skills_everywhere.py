"""Inject zhihu-scraper-investigator Skill into Antigravity, Codex, Cursor, and Agents."""

from pathlib import Path
import shutil
import sys

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
SKILL_SRC = ROOT / "skills" / "zhihu-scraper-investigator"

HOME = Path.home()
TARGET_DIRS = [
    HOME / ".gemini" / "config" / "skills" / "zhihu-scraper-investigator",
    HOME / ".codex" / "skills" / "zhihu-scraper-investigator",
    HOME / ".cursor" / "skills-cursor" / "zhihu-scraper-investigator",
    HOME / ".agents" / "skills" / "zhihu-scraper-investigator"
]

print("🚀 开始注入 zhihu-scraper-investigator Skill 到所有 IDE 与智能体环境...")

for target in TARGET_DIRS:
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(SKILL_SRC, target)
        print(f"  ✓ 成功注入到: {target}")
    except Exception as e:
        print(f"  ⚠️ 注入失败 {target}: {e}")

print("\n🎉 Skill 注入完成！Antigravity、Codex、Cursor 全环境均已就绪。")
