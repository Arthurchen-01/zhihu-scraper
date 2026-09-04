import json
import re
from pathlib import Path
from collections import defaultdict
import pandas as pd
import sys

sys.stdout.reconfigure(encoding="utf-8")

file_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
xl = pd.ExcelFile(file_path)

all_profiles = []

for sheet in xl.sheet_names:
    if "备用" in sheet or "空白" in sheet or sheet == "目录":
        continue
    df = xl.parse(sheet)
    if df.empty:
        continue
    
    sheet_clean = sheet.strip()
    match = re.match(r"^(\d+)[\.、\s]+([^，,\s]+)[，,\s]+(.+)$", sheet_clean)
    if match:
        idx_num = match.group(1)
        real_person = match.group(2).strip()
        account_info = match.group(3).strip()
    else:
        idx_num = ""
        real_person = sheet_clean
        account_info = sheet_clean

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
    
    titles = []
    reasons = []
    links = []
    accounts = set()
    dates = []
    
    for _, row in df_renamed.iterrows():
        acc = str(row.get("author_account", "")).strip()
        t = str(row.get("title", "")).strip()
        l = str(row.get("link", "")).strip()
        r = str(row.get("reason", "")).strip()
        d = str(row.get("post_date", "")).strip()
        
        if acc and acc != "nan":
            accounts.add(acc)
        if t and t != "nan":
            titles.append(t)
        if r and r != "nan":
            reasons.append(r)
        if l and l != "nan":
            links.append(l)
        if d and d != "nan":
            dates.append(d)

    all_text = " ".join(titles + reasons)
    
    # 提取专属暗语/代词
    code_words = set()
    code_candidates = [
        "老年实控人", "1960年代出生", "实控人", "张某", "老张", "张jb", "老贼", "东方不败", "神棍", "土匪",
        "恶龙", "大师", "掌门", "教主", "某山长", "某学堂", "某机构", "某武道馆", "如是书院", "买家秀",
        "信息茧房", "鸡贼的老张", "洗脑组织", "伪国学", "高端传销"
    ]
    for cw in code_candidates:
        if cw in all_text:
            code_words.add(cw)

    # 提取被攻击的具体成员
    targeted_members = set()
    member_candidates = ["张健柏", "张清一", "山长", "明仪", "明颖", "明晓", "明哲", "刘静慧", "郑婉芳", "安友布", "王聪", "Ella"]
    for m in member_candidates:
        if m in all_text:
            targeted_members.add(m)

    # 风格派系判定
    style_category = "综合散户"
    if any(k in all_text for k in ["系统性分析", "尽职调查", "数据操纵", "学术泡沫", "概率骗局", "深度复盘"]):
        style_category = "伪学术/商业尽调型（长文伪理中客）"
    elif any(k in all_text for k in ["亲历", "校友", "前师生", "朋友孩子", "同事孩子", "昔日校友", "退费"]):
        style_category = "伪受害者/前师生爆料型（亲历者故事化）"
    elif any(k in all_text for k in ["王八蛋", "老贼", "土匪", "神棍", "恶心", "人格分裂", "鸡贼"]):
        style_category = "极端情绪宣泄/泼妇式辱骂型"
    elif any(k in all_text for k in ["邪教", "全能神", "精神控制", "宗教组织", "非法办学", "法办"]):
        style_category = "定性扣帽/法律与邪教大棒型"

    all_profiles.append({
        "id": idx_num,
        "sheet_raw": sheet_clean,
        "person_name": real_person,
        "account_info": account_info,
        "accounts_list": list(accounts) or [account_info],
        "article_count": len(titles) or len(df_renamed),
        "style_category": style_category,
        "code_words": list(code_words),
        "targeted_members": list(targeted_members),
        "sample_titles": titles[:6],
        "sample_reasons": reasons[:6],
        "all_titles": titles,
        "all_reasons": reasons
    })

print(f"Parsed {len(all_profiles)} valid profiles.")

# Export to JSON
Path("outputs/lawyer_profiles_full.json").write_text(json.dumps(all_profiles, ensure_ascii=False, indent=2), encoding="utf-8")
