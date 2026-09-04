"""Analyze all sheet names in lawyer excel to parse [Investigator (自己人)] vs [Target Attacker (坏人)]."""

import pandas as pd
from pathlib import Path
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

excel_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
xl = pd.ExcelFile(excel_path)

print("📋 All 67 Sheet Names in Lawyer Excel:")
for idx, s in enumerate(xl.sheet_names, 1):
    print(f"Sheet {idx}: {s}")
