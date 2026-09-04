"""Inspect all 67 sheets in 和律师商定版-收集清黑文章链接汇总表-最终.xlsx and extract all valid article links."""

import pandas as pd
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

excel_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
xl = pd.ExcelFile(excel_path)

print(f"📊 Total Sheets: {len(xl.sheet_names)}")

all_links = []

for sname in xl.sheet_names:
    if sname in ["全网清黑文章汇总表", "Sheet1", "总览"]:
        continue
    df = xl.parse(sname)
    link_col = None
    for c in df.columns:
        if any(k in str(c).lower() for k in ["链接", "url", "link"]):
            link_col = c
            break
    
    if link_col is not None:
        for idx, row in df.iterrows():
            val = str(row[link_col]).strip()
            if "zhihu.com" in val:
                all_links.append({
                    "sheet": sname,
                    "row_idx": idx + 1,
                    "url": val,
                    "title": str(row.get("文章标题", "")).strip(),
                    "sheet_author": sname
                })

print(f"🔗 Extracted {len(all_links)} Zhihu article/answer/pin links from 67 sheets!")
if all_links:
    print(f"Sample 1: {all_links[0]}")
    print(f"Sample 2: {all_links[1]}")
    print(f"Sample 3: {all_links[2]}")
