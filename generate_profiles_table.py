"""Resolve all Blacklist & Lawyer Target Users to Zhihu Profile Links and User Tokens.
Outputs comprehensive Excel & Markdown tables to Desktop.
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
CONFIG_PATH = ROOT / "config.json"

config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
client = ZhihuClient(cookie=config.get("cookie", ""))

# 1. 读取手机黑名单 64 用户
blacklist_file = ROOT / "data" / "blacklist_target_users.json"
mobile_users = []
if blacklist_file.exists():
    mobile_users = json.loads(blacklist_file.read_text(encoding="utf-8"))

# 2. 读取律师定版 67 表单中的知名攻击者
lawyer_excel = Path(r"C:\Users\25472\Desktop\清一武道馆\和律师商定版-收集清黑文章链接汇总表-最终.xlsx")
excel_attackers = []
if lawyer_excel.exists():
    xl = pd.ExcelFile(lawyer_excel)
    for sname in xl.sheet_names:
        clean_s = sname.strip()
        if clean_s not in ["全网清黑文章汇总表", "Sheet1", "总览"]:
            excel_attackers.append(clean_s)

# 合并所有目标主体
all_target_names = []
seen = set()

# 核心大黑子预置已知 url_token / 主页映射
KNOWN_PROFILES = {
    "大王": {"url_token": "wang-bing-song-80", "real_name": "周河川", "profile": "https://www.zhihu.com/people/wang-bing-song-80", "wudao": "是 (恶龙论/打败泰拳无价值论)"},
    "守其黑": {"url_token": "shou-qi-hei", "real_name": "郑婉芳", "profile": "https://www.zhihu.com/people/shou-qi-hei", "wudao": "是 (伪学术系统性抹黑)"},
    "清风溪流": {"url_token": "qing-feng-xi-liu-48", "real_name": "王秀兰", "profile": "https://www.zhihu.com/people/qing-feng-xi-liu-48", "wudao": "是 (鸡贼老张/概率骗局论)"},
    "茅箴": {"url_token": "mao-zhen-74", "real_name": "锺文", "profile": "https://www.zhihu.com/people/mao-zhen-74", "wudao": "是 (伪尽调/老张不为人知的过去)"},
    "箴茅": {"url_token": "mao-zhen-74", "real_name": "锺文", "profile": "https://www.zhihu.com/people/mao-zhen-74", "wudao": "是 (伪尽调/老张不为人知的过去)"},
    "嘲笑鸟": {"url_token": "chao-xiao-niao-57", "real_name": "龙永明/佳惠", "profile": "https://www.zhihu.com/people/chao-xiao-niao-57", "wudao": "是 (清一武道与新教育连环黑稿)"},
    "行云流水": {"url_token": "xing-yun-liu-shui-46", "real_name": "李安心", "profile": "https://www.zhihu.com/people/xing-yun-liu-shui-46", "wudao": "是 (邪教论/粗暴辱骂)"},
    "所谓高人皆为凡人": {"url_token": "suo-wei-gao-ren-jie-wei-fan-ren", "real_name": "李海", "profile": "https://www.zhihu.com/people/suo-wei-gao-ren-jie-wei-fan-ren", "wudao": "是 (假大师/实战与投资骗局论)"},
    "逸尘": {"url_token": "yi-chen-45-77", "real_name": "逸尘", "profile": "https://www.zhihu.com/people/yi-chen-45-77", "wudao": "是 (指名道姓攻击张清一武术/林妹妹言论)"},
    "宝石": {"url_token": "bao-shi-91", "real_name": "谢先俊", "profile": "https://www.zhihu.com/people/bao-shi-91", "wudao": "否 (管理霸道/洗脑论)"},
    "cocucola": {"url_token": "future2035", "real_name": "王乐乐", "profile": "https://www.zhihu.com/people/future2035", "wudao": "是 (连续发帖攻击学堂与武道)"},
    "future2035": {"url_token": "future2035", "real_name": "王乐乐", "profile": "https://www.zhihu.com/people/future2035", "wudao": "是 (连续发帖攻击学堂与武道)"},
    "FAFN": {"url_token": "fafn-88", "real_name": "FAFN", "profile": "https://www.zhihu.com/people/fafn-88", "wudao": "否 (脏山长/非法办学造谣)"},
    "五湖散人": {"url_token": "wu-hu-san-ren", "real_name": "许冰", "profile": "https://www.zhihu.com/people/wu-hu-san-ren", "wudao": "否 (转发寻衅造谣)"},
    "乐水乐山": {"url_token": "le-shui-le-shan", "real_name": "杨永红", "profile": "https://www.zhihu.com/people/le-shui-le-shan", "wudao": "否 (360度透视真相长文)"},
    "乐山乐水": {"url_token": "le-shui-le-shan", "real_name": "杨永红", "profile": "https://www.zhihu.com/people/le-shui-le-shan", "wudao": "否 (360度透视真相长文)"},
    "黄传科": {"url_token": "huang-chuan-ke", "real_name": "黄传科", "profile": "https://www.zhihu.com/people/huang-chuan-ke", "wudao": "否 (中科院光学工程师/学习法贬损)"},
    "自知者明": {"url_token": "zi-zhi-zhe-ming", "real_name": "李明静/李冬", "profile": "https://www.zhihu.com/people/zi-zhi-zhe-ming", "wudao": "是 (高频攻击与污蔑)"},
    "旺喜47": {"url_token": "wang-xi-47", "real_name": "旺喜47", "profile": "https://www.zhihu.com/people/wang-xi-47", "wudao": "否 (媒体公益黑公关)"},
    "张秉风": {"url_token": "zhang-bing-feng", "real_name": "张秉风", "profile": "https://www.zhihu.com/people/zhang-bing-feng", "wudao": "【白名单】新教育支持者/公益写手", "is_friendly": True},
    "山长 清一": {"url_token": "shan-chang-qing-yi", "real_name": "张健柏", "profile": "https://www.zhihu.com/people/shan-chang-qing-yi", "wudao": "【白名单】官方主号", "is_friendly": True},
    "进击的清粉": {"url_token": "jin-ji-de-qing-fen", "real_name": "支持者", "profile": "https://www.zhihu.com/people/jin-ji-de-qing-fen", "wudao": "【白名单】官方支持者", "is_friendly": True},
    "Ella清一公主NO.1": {"url_token": "ellaqing-yi-gong-zhu-no1", "real_name": "弟子/学员", "profile": "https://www.zhihu.com/people/ellaqing-yi-gong-zhu-no1", "wudao": "【白名单】官方弟子", "is_friendly": True},
    "明晓-文人格斗": {"url_token": "ming-xiao-wen-ren-ge-dou", "real_name": "明晓", "profile": "https://www.zhihu.com/people/ming-xiao-wen-ren-ge-dou", "wudao": "【白名单】文人格斗/武道馆主力", "is_friendly": True}
}

final_list = []

# 处理手机黑名单
for u in mobile_users:
    name = u["name"]
    if name in seen:
        continue
    seen.add(name)
    
    known = KNOWN_PROFILES.get(name, {})
    url_token = known.get("url_token", "")
    profile_url = known.get("profile", "")
    real_name = known.get("real_name", u.get("known_role", "待查实"))
    wudao_flag = known.get("wudao", "待判定")
    is_friendly = u.get("is_friendly", False) or known.get("is_friendly", False)

    # 若暂无主页，尝试从知乎搜索用户接口解析
    if not profile_url:
        try:
            # 搜索知乎用户
            search_res = client.search(name, search_type="people", limit=1)
            if search_res.get("data"):
                p_item = search_res["data"][0].get("object", {})
                url_token = p_item.get("url_token", "")
                if url_token:
                    profile_url = f"https://www.zhihu.com/people/{url_token}"
        except Exception:
            pass

    if not profile_url:
        profile_url = f"https://www.zhihu.com/search?type=people&q={name}"

    final_list.append({
        "知乎昵称 / 账号名称": name,
        "签名 / 简介": u.get("bio", ""),
        "对应真实身份 / 攻击流派": real_name,
        "知乎个人主页链接": profile_url,
        "知乎唯一标识 (url_token)": url_token or "以主页为准",
        "是否为武道专精攻击": wudao_flag,
        "身份属性": "🛡️ 己方白名单 (严禁攻击)" if is_friendly else "🔴 重点监控黑号"
    })

# 处理律师表单中的其他黑子
for a_name in excel_attackers:
    # 提取纯昵称
    clean_name = re.sub(r"（.*?）|\(.*?\)", "", a_name).strip()
    if clean_name in seen or a_name in seen:
        continue
    seen.add(clean_name)
    seen.add(a_name)

    known = KNOWN_PROFILES.get(clean_name, KNOWN_PROFILES.get(a_name, {}))
    url_token = known.get("url_token", "")
    profile_url = known.get("profile", "")
    real_name = known.get("real_name", a_name)
    wudao_flag = known.get("wudao", "涉及新教育与武道馆")

    if not profile_url:
        profile_url = f"https://www.zhihu.com/search?type=people&q={clean_name}"

    final_list.append({
        "知乎昵称 / 账号名称": a_name,
        "签名 / 简介": "《和律师商定版》立案取证主体",
        "对应真实身份 / 攻击流派": real_name,
        "知乎个人主页链接": profile_url,
        "知乎唯一标识 (url_token)": url_token or "以主页为准",
        "是否为武道专精攻击": wudao_flag,
        "身份属性": "🔴 律师立案重点黑号"
    })

# 生成 Excel 报表
df_out = pd.DataFrame(final_list)
excel_out = DESKTOP_TARGET / "清一武道馆_全网黑子与相关人员知乎主页链接总汇表.xlsx"
df_out.to_excel(excel_out, index=False)
print(f"✅ Excel 主页总汇表已生成: {excel_out} (共 {len(df_out)} 人)")

# 生成 Markdown 报表
md_out = DESKTOP_TARGET / "清一武道馆_全网黑子与相关人员知乎主页链接总汇表.md"
md_lines = [
    "# 👤 清一武道馆 · 全网黑子与相关人员知乎主页链接总汇表",
    f"> **数据统计**：涵盖手机黑名单 64 人 + 律师定版 66 位立案主体，共计 **{len(df_out)} 位关联人员**",
    f"> **生成时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "---",
    "",
    "| 序号 | 知乎昵称 / 账号 | 真实身份 / 攻击流派 | 知乎个人主页链接 | 是否为武道专精攻击 | 身份属性 |",
    "| :---: | :--- | :--- | :--- | :--- | :---: |"
]

for idx, r in enumerate(final_list, 1):
    link_md = f"[{r['知乎个人主页链接']}]({r['知乎个人主页链接']})"
    md_lines.append(f"| {idx} | **{r['知乎昵称 / 账号名称']}** | {r['对应真实身份 / 攻击流派']} | {link_md} | {r['是否为武道专精攻击']} | {r['身份属性']} |")

md_out.write_text("\n".join(md_lines), encoding="utf-8")
print(f"✅ Markdown 主页总汇表已生成: {md_out}")
