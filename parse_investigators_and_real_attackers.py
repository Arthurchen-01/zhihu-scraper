"""Strict Parser for [Investigator (自己人)] vs [Target Attacker (坏人 / 黑号)].
Parses all 67 Sheets in 和律师商定版 to separate:
- 己方调查责任人 / 成员 (郑婉芳, 许冰, 魏台龙, 谭琛怡, 蔡凯琪, 赵刚, 盛静美, 马超, 吕晓全, etc.)
- 真正被调查的外部黑子 / 黑号 (守其黑, 五湖散人, 乐山乐水, 茅箴, 大王, 逸尘, 所谓高人皆为凡人, etc.)
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DESKTOP_TARGET = Path(r"C:\Users\25472\Desktop\清一武道馆")

excel_path = DESKTOP_TARGET / "和律师商定版-收集清黑文章链接汇总表-最终.xlsx"
xl = pd.ExcelFile(excel_path)

parsed_sheets = []

for idx, sname in enumerate(xl.sheet_names, 1):
    if sname in ["全网清黑文章汇总表", "Sheet1", "总览", "目录", "备用空白(副本6)"]:
        continue
    
    # 统计链接数
    df = xl.parse(sname)
    link_count = 0
    sample_link = ""
    for col in ["链接", "文章链接", "url", "URL"]:
        if col in df.columns:
            valid_links = [str(x).strip() for x in df[col].dropna() if "http" in str(x)]
            link_count = len(valid_links)
            if valid_links:
                sample_link = valid_links[0]
            break

    # 解析认领格式
    # 典型格式:
    # "1、郑婉芳 认领守其黑"
    # "2.许冰 认领五湖散人"
    # "4.锺文-云南 认领-茅箴"
    # "6.周河川广州   大王"
    # "7.王秀兰 清风溪流"
    # "14.吴伟-上海 黄传科"
    # "44.黄微认领逸尘"
    # "53.【谭琛怡】来时路"
    # "56.【蔡凯琪】闲散王菲"

    clean_title = re.sub(r"^\d+[\.、\s]+", "", sname).strip()
    clean_title = clean_title.replace("【", "").replace("】", "")

    investigator = ""
    target_attacker = ""

    if "认领" in clean_title:
        parts = clean_title.split("认领")
        investigator = parts[0].strip(" -+、，")
        target_attacker = parts[1].strip(" -+、，")
    elif " " in clean_title:
        parts = clean_title.split()
        if len(parts) >= 2:
            investigator = parts[0].strip(" -+、，")
            target_attacker = " ".join(parts[1:]).strip(" -+、，")
        else:
            investigator = "未标明责任人"
            target_attacker = clean_title
    elif "，" in clean_title or "," in clean_title:
        parts = re.split(r"[,，]", clean_title)
        investigator = parts[0].strip()
        target_attacker = parts[1].strip() if len(parts) > 1 else clean_title
    else:
        investigator = "责任人"
        target_attacker = clean_title

    # 规范化调查目标名称
    target_attacker = re.sub(r"\(.*?\)|（.*?）", "", target_attacker).strip()

    parsed_sheets.append({
        "序号": len(parsed_sheets) + 1,
        "Excel原始表单名": sname,
        "己方排查责任人 (自己人)": investigator or "待核定",
        "真正被调查的外部黑子/黑号 (坏人)": target_attacker or sname,
        "该黑子在库侵权文章篇数": link_count,
        "样本文章链接": sample_link,
        "知乎主页直达链接": f"https://www.zhihu.com/search?type=people&q={target_attacker}" if target_attacker else ""
    })

# 1. 导出清晰的对照表 Excel
df_parsed = pd.DataFrame(parsed_sheets)
out_excel = DESKTOP_TARGET / "清一武道馆_内部排查责任人与被调查黑子精准对照表.xlsx"
df_parsed.to_excel(out_excel, index=False)
print(f"✅ 责任人与黑子对照表已生成: {out_excel} (共 {len(df_parsed)} 组映射)")

# 2. 导出 Markdown 文档
out_md = DESKTOP_TARGET / "清一武道馆_内部排查责任人与被调查黑子精准对照表.md"
md_lines = [
    "# 🎯 清一武道馆 · 内部排查责任人（自己人）与被调查黑子（坏人）精准对照表",
    "> **业务逻辑彻底澄清**：",
    "> 1. **【己方排查责任人（自己人）】**：指当时参与取证的学堂弟子、教练与家长战友（如 郑婉芳、许冰、魏台龙、谭琛怡、蔡凯琪、赵刚、盛静美、马超 等），**绝非黑子，严禁误列为攻击者**！",
    "> 2. **【真正被调查的外部黑子（坏人）】**：指该成员负责盯防、取证的知乎恶意攻击黑号（如 守其黑、五湖散人、乐山乐水、茅箴、大王、逸尘、所谓高人皆为凡人 等）！",
    f"> **编制时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "---",
    "",
    "| 序号 | Excel原始表单名 | 己方排查责任人 (自己人) | 真正被调查的外部黑子 / 黑号 (坏人) | 侵权篇数 | 调查目标知乎直达链接 |",
    "| :---: | :--- | :---: | :--- | :---: | :--- |"
]

for r in parsed_sheets:
    url_cell = f"[{r['真正被调查的外部黑子/黑号 (坏人)']}]({r['知乎主页直达链接']})" if r["知乎主页直达链接"] else "暂无"
    md_lines.append(f"| {r['序号']} | `{r['Excel原始表单名']}` | **{r['己方排查责任人 (自己人)']}** | **{r['真正被调查的外部黑子/黑号 (坏人)']}** | {r['该黑子在库侵权文章篇数']} 篇 | {url_cell} |")

out_md.write_text("\n".join(md_lines), encoding="utf-8")
print(f"✅ 对照表 Markdown 已生成: {out_md}")
