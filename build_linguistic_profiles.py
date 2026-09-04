import json
import re
from pathlib import Path
from collections import defaultdict
import pandas as pd
import sys

sys.stdout.reconfigure(encoding="utf-8")

file_path = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
xl = pd.ExcelFile(file_path)

person_profiles = []

for sheet in xl.sheet_names:
    if "备用" in sheet or "空白" in sheet:
        continue
    df = xl.parse(sheet)
    if df.empty:
        continue
    
    # Extract Person Name and Primary Account from sheet title
    # e.g. "60.王乐乐，future2035" -> Person: 王乐乐, Account: future2035
    # "63.佳惠，嘲笑鸟 今日学堂（小红书）" -> Person: 佳惠, Account: 嘲笑鸟 今日学堂
    sheet_clean = sheet.strip()
    match = re.match(r"^(\d+)\.\s*([^，,]+)[，,]\s*(.+)$", sheet_clean)
    if match:
        sheet_id = match.group(1)
        real_person = match.group(2).strip()
        account_name = match.group(3).strip()
    else:
        sheet_id = ""
        real_person = sheet_clean
        account_name = sheet_clean

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
    
    for _, row in df_renamed.iterrows():
        acc = str(row.get("author_account", "")).strip()
        t = str(row.get("title", "")).strip()
        l = str(row.get("link", "")).strip()
        r = str(row.get("reason", "")).strip()
        
        if acc and acc != "nan":
            accounts.add(acc)
        if t and t != "nan":
            titles.append(t)
        if r and r != "nan":
            reasons.append(r)
        if l and l != "nan":
            links.append(l)

    # Linguistic pattern analysis for this person
    all_text = " ".join(titles + reasons)
    
    # Detect target platforms
    platforms = set()
    for l in links:
        if "zhihu.com" in l:
            platforms.add("知乎")
        elif "xiaohongshu.com" in l or "xhslink" in l:
            platforms.add("小红书")
        elif "douyin.com" in l:
            platforms.add("抖音")
        elif "bilibili.com" in l:
            platforms.add("B站")
        elif "weibo.com" in l:
            platforms.add("微博")
        elif "weixin" in l or "mp.weixin" in l:
            platforms.add("微信公众号")
    if not platforms:
        if "小红书" in sheet_clean:
            platforms.add("小红书")
        elif "抖音" in sheet_clean:
            platforms.add("抖音")
        elif "知乎" in sheet_clean:
            platforms.add("知乎")
        else:
            platforms.add("全网/知乎")

    # Detect attack angles
    angles = []
    if any(k in all_text for k in ["武道", "功夫", "武术", "格斗", "实战", "泰拳", "散打", "比赛", "运动员", "赛事"]):
        angles.append("武道馆/武术实战/运动员抹黑")
    if any(k in all_text for k in ["邪教", "宗教", "洗脑", "精神控制", "神棍", "教主"]):
        angles.append("邪教化/洗脑精神操控控诉")
    if any(k in all_text for k in ["骗子", "骗局", "割韭菜", "敛财", "画饼", "传销"]):
        angles.append("经济诈骗/传销圈钱指控")
    if any(k in all_text for k in ["以偏概全", "春秋笔法", "断章取义", "造谣", "歪曲", "暗指"]):
        angles.append("隐蔽隐喻/春秋笔法暗讽")
    if any(k in all_text for k in ["自考", "考不上", "出路", "废了", "害了孩子", "误人子弟"]):
        angles.append("升学失败/毁人前途叙事")

    person_profiles.append({
        "sheet_name": sheet_clean,
        "person_name": real_person,
        "main_account": account_name,
        "accounts": list(accounts) or [account_name],
        "total_articles": len(titles) or len(df_renamed),
        "platforms": list(platforms),
        "attack_angles": angles or ["综合抹黑"],
        "sample_titles": titles[:5],
        "sample_reasons": reasons[:5],
        "all_reasons": reasons,
        "all_titles": titles
    })

print(f"Generated profiles for {len(person_profiles)} individuals/groups.")
Path("outputs/person_profiles.json").write_text(json.dumps(person_profiles, ensure_ascii=False, indent=2), encoding="utf-8")
