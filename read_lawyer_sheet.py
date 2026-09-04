import pandas as pd
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

file_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")

if not file_path.exists():
    print(f"File not found: {file_path}")
    # Check parent directory
    parent = file_path.parent
    if parent.exists():
        print(f"Parent directory contents of {parent}:")
        for f in parent.iterdir():
            print(" ", f.name)
    else:
        print(f"Parent directory not found: {parent}")
else:
    print(f"Loading Excel file: {file_path}")
    xl = pd.ExcelFile(file_path)
    print("Sheet names:", xl.sheet_names)
    for sheet in xl.sheet_names:
        df = xl.parse(sheet)
        print(f"\n--- Sheet: {sheet} (Shape: {df.shape}) ---")
        print("Columns:", df.columns.tolist())
        print("First 5 rows:")
        print(df.head())
