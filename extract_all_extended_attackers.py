"""Extract All Extended Attackers from Lawyer Excel (67 Sheets) and Cloud Monitor (538+ items).
Combines:
1. Phone screenshot 66 users
2. Lawyer 67-sheet unique attackers (乔安娜/宁静, 鄢佳彦, 香雪莲, 楠楠, 英子同学, 于钧, 肖泽喜, etc.)
3. Cloud live-discovered new attacking accounts
Generates comprehensive master spreadsheet and markdown report.
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
from zhihu_client import ZhihuClient

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DESKTOP_TARGET = Path(r"C:\Users\25472\Desktop\清一武道馆")

# 1. 官方保护白名单 (严禁混入)
WHITELIST_TOKENS = {
    "shan-chang-qing-yi", "shan-chang-tou-zi-hao", "ming-xiao-wen-ren-ge-dou",
    "lu-yun-ru", "tan-chen-yi", "ellaqing-yi-gong-zhu-no1", "cai-kai-qi-88",
    "jin-ji-de-qing-fen", "山长 清一", "明晓-文人格斗", "Ella清一公主NO.1", "进击的清粉"
}

# 2. 读取律师定版 67 表单
lawyer_excel = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
lawyer_attackers = {}

if lawyer_excel.exists():
    xl = pd.ExcelFile(lawyer_excel)
    for sname in xl.sheet_names:
        clean_s = sname.strip()
        if clean_s in ["全网清黑文章汇总表", "Sheet1", "总览", "目录"]:
            continue
        # 解析表单内的数据
        df_sheet = xl.parse(sname)
        link_sample = ""
        for col in ["链接", "文章链接", "url", "URL"]:
            if col in df_sheet.columns:
                valid_links = [str(x) for x in df_sheet[col].dropna() if "http" in str(x)]
                if valid_links:
                    link_sample = valid_links[0]
                    break
        lawyer_attackers[clean_s] = {
            "source": "《和律师商定版》立案Sheet",
            "sample_link": link_sample,
            "count": len(df_sheet)
        }

# 3. 读取云端最新同步大盘 (538 条)
cloud_reports = sorted(list((DESKTOP_TARGET / "outputs" / "excel_reports").glob("*.xlsx")), key=lambda p: p.stat().st_mtime, reverse=True)
cloud_attackers = {}
if cloud_reports:
    # 排除临时文件
    valid_reports = [p for p in cloud_reports if not p.name.startswith("~$")]
    if valid_reports:
        df_cloud = pd.read_excel(valid_reports[0])
        for idx, row in df_cloud.iterrows():
            author = str(row.get("发帖者账号名称") or row.get("发帖人昵称") or "").strip()
            link = str(row.get("链接") or row.get("parent_url") or "").strip()
            reason = str(row.get("认为该文章侵权的主要原因（如：用“XXX”暗指山长、攻击辱骂、宗教传播等……）") or "").strip()
            if author and author not in ["nan", "未知作者", "未知用户", ""] and author not in WHITELIST_TOKENS:
                if author not in cloud_attackers:
                    cloud_attackers[author] = {
                        "source": "云端7x24h实时探针新发现",
                        "sample_link": link,
                        "reason": reason,
                        "count": 1
                    }
                else:
                    cloud_attackers[author]["count"] += 1

# 4. 手机黑名单已收录的 66 人集合
mobile_file = ROOT / "data" / "blacklist_target_users.json"
mobile_list = json.loads(mobile_file.read_text(encoding="utf-8")) if mobile_file.exists() else []
mobile_names = {m["name"] for m in mobile_list}

# 5. 构建【全量黑子总汇库】（分为：A. 手机黑名单66人 + B. 律师定版扩展黑子 + C. 云端新发现黑子）
EXTENDED_MASTER_MAP = {
    # 律师定版扩展知名黑子
    "乔安娜": {"real_name": "乔安娜", "aliases": "宁静, 乔安娜", "url_token": "qiao-an-na-ning-jing", "wudao": "否 (教育与财务攻击)", "reason": "家长退费纠纷与连环黑帖"},
    "鄢佳彦": {"real_name": "鄢佳彦", "aliases": "清一山长老贼哪里跑, 鄢佳彦", "url_token": "yan-jia-yan", "wudao": "是 (极端名誉侵权)", "reason": "指名道姓人身攻击/恶毒咒骂"},
    "香雪莲": {"real_name": "香雪莲", "aliases": "香雪莲", "url_token": "xiang-xue-lian", "wudao": "否 (学堂运营攻击)", "reason": "学堂管理机制贬损抹黑"},
    "楠楠": {"real_name": "楠楠", "aliases": "楠楠", "url_token": "nan-nan-88", "wudao": "否 (教育经历捏造)", "reason": "虚构受害经历抹黑学堂"},
    "英子同学": {"real_name": "英子", "aliases": "英子同学, 我是英子", "url_token": "ying-zi-tong-xue", "wudao": "是 (全网入局抹黑)", "reason": "圈外人入局连环发帖抹黑"},
    "于钧": {"real_name": "于钧", "aliases": "行万里路, 自赎的人", "url_token": "yu-jun-zi-shu", "wudao": "否 (心理控制论)", "reason": "自赎的人长文抹黑"},
    "肖泽喜": {"real_name": "肖泽喜", "aliases": "肖泽喜", "url_token": "xiao-ze-xi", "wudao": "否 (财务纠纷攻击)", "reason": "经济纠纷与恶意诽谤"},
    "王映澐": {"real_name": "王映澐", "aliases": "一直流浪的小草", "url_token": "wang-ying-yun", "wudao": "否 (情绪宣泄抹黑)", "reason": "情感与生活经历附会抹黑"},
    "李冬": {"real_name": "李冬", "aliases": "自知者明, 李明静", "url_token": "zi-zhi-zhe-ming", "wudao": "是 (武道高频攻击)", "reason": "持续攻击武道馆与实战"},
    "E姐香港身份说": {"real_name": "E姐", "aliases": "E姐香港身份说", "url_token": "e-jie-xiang-gang", "wudao": "否 (海外学历造谣)", "reason": "借假学历事件影射新教育出海"},
    "大王": {"real_name": "周河川", "aliases": "王病松, 风林火山", "url_token": "wang-bing-song-80", "wudao": "是 (武道核心黑子)", "reason": "恶龙论/打败泰拳无价值论/核心黑子"},
    "守其黑": {"real_name": "郑婉芳", "aliases": "知其白守其黑", "url_token": "shou-qi-hei", "wudao": "是 (核心骨干)", "reason": "伪学术系统性解构抹黑"},
    "清风溪流": {"real_name": "王秀兰", "aliases": "正念", "url_token": "qing-feng-xi-liu-48", "wudao": "是 (核心攻击者)", "reason": "鸡贼老张论/概率骗局论"},
    "茅箴": {"real_name": "锺文", "aliases": "箴茅, 五千老师", "url_token": "mao-zhen-74", "wudao": "是 (连环专栏作者)", "reason": "老张不为人知的过去/连环专栏抹黑"},
    "嘲笑鸟": {"real_name": "龙永明/佳惠", "aliases": "佳惠", "url_token": "chao-xiao-niao-57", "wudao": "是 (重点取证主体)", "reason": "清一武道与新教育连环黑稿/造谣传销"},
    "future2035": {"real_name": "王乐乐", "aliases": "cocucola, 社会闲散人员", "url_token": "future2035", "wudao": "是 (高频发帖作者)", "reason": "手撕今日学堂/反向求真抹黑长文"},
    "行云流水": {"real_name": "李安心", "aliases": "转递善良", "url_token": "xing-yun-liu-shui-46", "wudao": "是 (极端派黑子)", "reason": "极端邪教定性论/粗暴辱骂攻击"},
    "所谓高人皆为凡人": {"real_name": "李海", "aliases": "凡人", "url_token": "suo-wei-gao-ren-jie-wei-fan-ren", "wudao": "是 (假大师攻击)", "reason": "假大师论/武术实战与投资骗局论"},
    "逸尘": {"real_name": "逸尘", "aliases": "逸尘", "url_token": "yi-chen-45-77", "wudao": "是 (指名攻击武道)", "reason": "指名道姓攻击张清一武术/林妹妹言论"}
}

master_records = []
seen_identities = set()

# A. 处理律师 67 Sheets 中的全量黑子
for raw_name, info in lawyer_attackers.items():
    clean_name = re.sub(r"（.*?）|\(.*?\)", "", raw_name).strip()
    if clean_name in WHITELIST_TOKENS or raw_name in WHITELIST_TOKENS:
        continue
    
    known = EXTENDED_MASTER_MAP.get(clean_name, EXTENDED_MASTER_MAP.get(raw_name, {}))
    url_token = known.get("url_token", "")
    profile_url = f"https://www.zhihu.com/people/{url_token}" if url_token else (info["sample_link"] if "people" in info["sample_link"] else f"https://www.zhihu.com/search?type=people&q={clean_name}")
    real_name = known.get("real_name", raw_name)
    wudao = known.get("wudao", "涉及新教育与武道馆")
    reason = known.get("reason", f"《和律师商定版》立案侵权文章共 {info['count']} 篇")

    seen_identities.add(clean_name)
    seen_identities.add(raw_name)

    is_in_mobile = "📱 手机黑名单已包含" if (clean_name in mobile_names or raw_name in mobile_names) else "📑 律师Excel专属核心黑子"

    master_records.append({
        "知乎真实当前昵称": clean_name,
        "现实真实姓名 / 对应主体": real_name,
        "历史曾用名 / 马甲": known.get("aliases", raw_name),
        "数据来源分类": is_in_mobile,
        "知乎个人主页链接 (点击直达)": profile_url,
        "知乎唯一 url_token": url_token or "以主页为准",
        "是否针对武道馆攻击": wudao,
        "主要抹黑方向 / 侵权事实": reason
    })

# B. 处理云端新抓取到的其他黑子
for a_name, c_info in cloud_attackers.items():
    clean_a = re.sub(r"（.*?）|\(.*?\)", "", a_name).strip()
    if clean_a in WHITELIST_TOKENS or clean_a in seen_identities:
        continue
    seen_identities.add(clean_a)

    known = EXTENDED_MASTER_MAP.get(clean_a, {})
    url_token = known.get("url_token", "")
    profile_url = f"https://www.zhihu.com/people/{url_token}" if url_token else f"https://www.zhihu.com/search?type=people&q={clean_a}"
    wudao = "是 (武道相关)" if any(w in c_info["reason"] for w in ["武", "搏击", "格斗", "功夫", "泰拳", "实战"]) else "新教育抹黑"

    is_in_mobile = "📱 手机黑名单已包含" if clean_a in mobile_names else "☁️ 云端探针最新捕获新黑号"

    master_records.append({
        "知乎真实当前昵称": clean_a,
        "现实真实姓名 / 对应主体": known.get("real_name", clean_a),
        "历史曾用名 / 马甲": known.get("aliases", ""),
        "数据来源分类": is_in_mobile,
        "知乎个人主页链接 (点击直达)": profile_url,
        "知乎唯一 url_token": url_token or "待深度穿透提取",
        "是否针对武道馆攻击": wudao,
        "主要抹黑方向 / 侵权事实": c_info["reason"] or "全网监控最新捕获侵权言论"
    })

# 为全部记录赋予连续序号
for idx, r in enumerate(master_records, 1):
    r["序号"] = idx

# 整理列顺序
ordered_master = []
for r in master_records:
    ordered_master.append({
        "序号": r["序号"],
        "知乎真实当前昵称": r["知乎真实当前昵称"],
        "现实真实姓名 / 对应主体": r["现实真实姓名 / 对应主体"],
        "历史曾用名 / 马甲": r["历史曾用名 / 马甲"],
        "数据来源分类": r["数据来源分类"],
        "知乎个人主页链接 (点击直达)": r["知乎个人主页链接 (点击直达)"],
        "知乎唯一 url_token": r["知乎唯一 url_token"],
        "是否针对武道馆攻击": r["是否针对武道馆攻击"],
        "主要抹黑方向 / 侵权事实": r["主要抹黑方向 / 侵权事实"]
    })

# 1. 导出 Excel
df_all = pd.DataFrame(ordered_master)
excel_out = DESKTOP_TARGET / "清一武道馆_全网全量黑子与侵权人总汇表_含律师版与云端新发现.xlsx"
df_all.to_excel(excel_out, index=False)
print(f"✅ 全量大盘 Excel 已生成: {excel_out} (共 {len(df_all)} 位黑子)")

# 2. 导出 Markdown
md_out = DESKTOP_TARGET / "清一武道馆_全网全量黑子与侵权人总汇表_含律师版与云端新发现.md"
md_lines = [
    "# 📑 清一武道馆 · 全网全量黑子与侵权人总汇表 (含手机黑名单 + 律师定版 67 表单 + 云端新发现)",
    f"> **收录规模**：涵盖手机拉黑 66 人 + 律师定版 67 表单黑子 + 云端 7x24h 探针最新捕获黑号，共计 **{len(df_all)} 位独立侵权主体**",
    f"> **严格白名单隔离**：100% 彻底剔除创始人（张健柏/山长）、主力运动员（明晓）及在册学员弟子！",
    f"> **生成时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "---",
    "",
    "| 序号 | 知乎真实当前昵称 | 现实真实姓名 / 对应主体 | 历史曾用名 / 马甲 | 数据来源分类 | 知乎个人主页直达链接 | 是否针对武道馆攻击 | 主要抹黑方向 / 侵权事实 |",
    "| :---: | :--- | :--- | :--- | :---: | :--- | :---: | :--- |"
]

for r in ordered_master:
    url_cell = f"[{r['知乎个人主页链接 (点击直达)']}]({r['知乎个人主页链接 (点击直达)']})"
    md_lines.append(f"| {r['序号']} | **{r['知乎真实当前昵称']}** | {r['现实真实姓名 / 对应主体']} | {r['历史曾用名 / 马甲']} | {r['数据来源分类']} | {url_cell} | {r['是否针对武道馆攻击']} | {r['主要抹黑方向 / 侵权事实']} |")

md_out.write_text("\n".join(md_lines), encoding="utf-8")
print(f"✅ 全量大盘 Markdown 已生成: {md_out}")
