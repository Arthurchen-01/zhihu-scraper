import pandas as pd
import json
import re
from pathlib import Path
from collections import defaultdict
import sys

sys.stdout.reconfigure(encoding="utf-8")

file_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
xl = pd.ExcelFile(file_path)

all_records = []
sheet_summary = []

for sheet in xl.sheet_names:
    if "备用" in sheet or "空白" in sheet:
        continue
    df = xl.parse(sheet)
    if df.empty:
        continue
    
    # Standardize column names
    col_map = {}
    for c in df.columns:
        c_str = str(c).strip()
        if "发帖者" in c_str or "账号" in c_str or "作者" in c_str:
            col_map[c] = "author_account"
        elif "日期" in c_str or "时间" in c_str:
            col_map[c] = "post_date"
        elif "链接" in c_str or "url" in c_str.lower():
            col_map[c] = "link"
        elif "标题" in c_str or "题目" in c_str:
            col_map[c] = "title"
        elif "原因" in c_str or "侵权" in c_str or "理由" in c_str or "描述" in c_str:
            col_map[c] = "reason"
    
    df_renamed = df.rename(columns=col_map)
    
    sheet_authors = []
    sheet_reasons = []
    sheet_titles = []
    sheet_links = []
    
    for idx, row in df_renamed.iterrows():
        acc = str(row.get("author_account", "")).strip()
        title = str(row.get("title", "")).strip()
        link = str(row.get("link", "")).strip()
        reason = str(row.get("reason", "")).strip()
        
        if not acc and not link and not title:
            continue
        
        rec = {
            "sheet": sheet,
            "author_account": acc if acc != "nan" else "",
            "title": title if title != "nan" else "",
            "link": link if link != "nan" else "",
            "reason": reason if reason != "nan" else ""
        }
        all_records.append(rec)
        sheet_authors.append(rec["author_account"])
        sheet_reasons.append(rec["reason"])
        sheet_titles.append(rec["title"])
        sheet_links.append(rec["link"])

    sheet_summary.append({
        "sheet": sheet,
        "total_rows": len(df_renamed),
        "authors": list(set(filter(None, sheet_authors))),
        "titles_sample": [t for t in sheet_titles if t][:5],
        "reasons_sample": [r for r in sheet_reasons if r][:5],
    })

print(f"Total sheets analyzed: {len(sheet_summary)}")
print(f"Total records extracted: {len(all_records)}")

# Group by Author / Person
authors_map = defaultdict(list)
for r in all_records:
    # Key can be extracted from sheet name e.g. "60.王乐乐，future2035" -> Person: 王乐乐, Account: future2035
    s_name = r["sheet"]
    authors_map[s_name].append(r)

summary_output = {
    "total_records": len(all_records),
    "sheets_count": len(sheet_summary),
    "sheet_list": sheet_summary
}

Path("outputs/lawyer_summary.json").write_text(json.dumps(summary_output, ensure_ascii=False, indent=2), encoding="utf-8")
print("Saved outputs/lawyer_summary.json")
