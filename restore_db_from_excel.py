"""Restore data/zhihu_monitor.db from latest synced Excel report.
Populates tables:
- evidence (567+ items)
- suspect_users (178+ users)
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(r"C:\Users\25472\Desktop\AI brain storming\工具栏\zhihu-black")
DATA_DIR = ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "zhihu_monitor.db"

reports_dir = Path(r"C:\Users\25472\Desktop\清一武道馆\outputs\excel_reports")
excel_files = sorted(list(reports_dir.glob("*.xlsx")), key=lambda p: p.stat().st_mtime, reverse=True)
valid_excels = [p for p in excel_files if not p.name.startswith("~$")]

if not valid_excels:
    print("❌ 未找到有效 Excel 报表！")
    sys.exit(1)

latest_excel = valid_excels[0]
print(f"📖 正在从最新报表导入数据: {latest_excel.name}")

xl = pd.ExcelFile(latest_excel)
df_ev = xl.parse(xl.sheet_names[0])
df_sus = xl.parse(xl.sheet_names[1]) if len(xl.sheet_names) > 1 else pd.DataFrame()

with sqlite3.connect(DB_PATH) as conn:
    df_ev.to_sql("evidence", conn, if_exists="replace", index=False)
    if not df_sus.empty:
        df_sus.to_sql("suspect_users", conn, if_exists="replace", index=False)
    conn.commit()

print(f"✅ 成功生成并填充 SQLite 数据库: {DB_PATH}")
print(f"  - evidence 证据表记录数: {len(df_ev)}")
print(f"  - suspect_users 可疑人员表记录数: {len(df_sus)}")
print(f"  - 数据库文件大小: {DB_PATH.stat().st_size / 1024:.1f} KB")
