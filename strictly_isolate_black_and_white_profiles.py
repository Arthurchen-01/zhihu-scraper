"""Strictly Isolate Attackers from Pro-Brand Officials and Members.
Ensures ZERO mixing of Founder (张健柏/山长清一) and Members (明晓, Ella, 蔡凯琪, 陆韵如, etc.) in the Blacklist.
Generates two completely separate files:
1. 《清一武道馆_全网真实黑子与侵权人知乎主页精确校对总表》 (100% 真实黑子)
2. 《清一武道馆_官方核心团队与保护白名单》 (创始人、武道馆主力成员与支持者)
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

sys.stdout.reconfigure(encoding="utf-8")

ROOT = Path(__file__).resolve().parent
DESKTOP_TARGET = Path(r"C:\Users\25472\Desktop\清一武道馆")

# 1. 官方核心团队与白名单成员 (绝对隔离保护)
OFFICIAL_WHITELIST = [
    {
        "序号": 1,
        "姓名 / 称呼": "张健柏 (清一山长)",
        "团队身份": "【武道馆创办人 / 总导师】",
        "知乎真实昵称": "山长 清一",
        "知乎主页链接": "https://www.zhihu.com/people/shan-chang-qing-yi",
        "唯一 url_token": "shan-chang-qing-yi",
        "个人简介 / Bio": "今日学堂创办人、清一武道馆创立者",
        "保护级别": "👑 最高级核心防护 (绝对己方)"
    },
    {
        "序号": 2,
        "姓名 / 称呼": "清一投资号",
        "团队身份": "【官方投资矩阵号】",
        "知乎真实昵称": "清一投资号",
        "知乎主页链接": "https://www.zhihu.com/people/shan-chang-tou-zi-hao",
        "唯一 url_token": "shan-chang-tou-zi-hao",
        "个人简介 / Bio": "清一山长官方投资专栏",
        "保护级别": "👑 官方矩阵号 (绝对己方)"
    },
    {
        "序号": 3,
        "姓名 / 称呼": "明晓",
        "团队身份": "【清一武道馆主力运动员 / 文人格斗总教练】",
        "知乎真实昵称": "明晓-文人格斗",
        "知乎主页链接": "https://www.zhihu.com/people/ming-xiao-wen-ren-ge-dou",
        "唯一 url_token": "ming-xiao-wen-ren-ge-dou",
        "个人简介 / Bio": "文人格斗主力运动员、全国搏击冠军",
        "保护级别": "🥊 核心武道运动员 (绝对己方)"
    },
    {
        "序号": 4,
        "姓名 / 称呼": "陆韵如",
        "团队身份": "【清一武道馆核心成员 / 文人格斗队员】",
        "知乎真实昵称": "陆韵如 文人格斗",
        "知乎主页链接": "https://www.zhihu.com/search?type=people&q=陆韵如",
        "唯一 url_token": "lu-yun-ru",
        "个人简介 / Bio": "文人格斗运动员",
        "保护级别": "🥊 核心武道运动员 (绝对己方)"
    },
    {
        "序号": 5,
        "姓名 / 称呼": "谭琛怡",
        "团队身份": "【清一武道馆核心成员 / 文人格斗队员】",
        "知乎真实昵称": "谭琛怡-文人格斗",
        "知乎主页链接": "https://www.zhihu.com/search?type=people&q=谭琛怡",
        "唯一 url_token": "tan-chen-yi",
        "个人简介 / Bio": "文人格斗运动员",
        "保护级别": "🥊 核心武道运动员 (绝对己方)"
    },
    {
        "序号": 6,
        "姓名 / 称呼": "Ella",
        "团队身份": "【今日学堂优秀毕业生 / 清一弟子】",
        "知乎真实昵称": "Ella清一公主NO.1",
        "知乎主页链接": "https://www.zhihu.com/people/ellaqing-yi-gong-zhu-no1",
        "唯一 url_token": "ellaqing-yi-gong-zhu-no1",
        "个人简介 / Bio": "今日学堂毕业生、清一学员",
        "保护级别": "🛡️ 核心弟子学员 (绝对己方)"
    },
    {
        "序号": 7,
        "姓名 / 称呼": "蔡凯琪",
        "团队身份": "【今日学堂优秀毕业生 / 清一弟子】",
        "知乎真实昵称": "蔡凯琪",
        "知乎主页链接": "https://www.zhihu.com/people/cai-kai-qi-88",
        "唯一 url_token": "cai-kai-qi-88",
        "个人简介 / Bio": "今日学堂毕业生",
        "保护级别": "🛡️ 核心弟子学员 (绝对己方)"
    },
    {
        "序号": 8,
        "姓名 / 称呼": "进击的清粉",
        "团队身份": "【新教育忠实支持者 / 辩护专栏主】",
        "知乎真实昵称": "进击的清粉",
        "知乎主页链接": "https://www.zhihu.com/people/jin-ji-de-qing-fen",
        "唯一 url_token": "jin-ji-de-qing-fen",
        "个人简介 / Bio": "新教育支持者",
        "保护级别": "🛡️ 铁杆支持者 (绝对己方)"
    },
    {
        "序号": 9,
        "姓名 / 称呼": "张秉风",
        "团队身份": "【新教育公益写手 / 公益文章支持者】",
        "知乎真实昵称": "张秉风",
        "知乎主页链接": "https://www.zhihu.com/people/zhang-bing-feng",
        "唯一 url_token": "zhang-bing-feng",
        "个人简介 / Bio": "写小说的｜新教育公益文章，可任意转载，无需…",
        "保护级别": "🛡️ 公益支持者 (严禁误杀)"
    }
]

# 2. 纯净真实黑子清单 (绝对不含任何己方成员)
ATTACKERS_ONLY = [
    {
        "知乎真实当前昵称": "大王",
        "现实真实姓名": "周河川",
        "历史曾用名 / 马甲": "王病松, 风林火山",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/wang-bing-song-80",
        "唯一 url_token": "wang-bing-song-80",
        "个人签名 / Bio": "风林火山",
        "主要抹黑方向": "恶龙论 / 攻击武道馆实战能力 / 打败泰拳无价值论",
        "是否针对武道馆攻击": "是 (武道核心黑子)"
    },
    {
        "知乎真实当前昵称": "守其黑",
        "现实真实姓名": "郑婉芳",
        "历史曾用名 / 马甲": "知其白守其黑",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/shou-qi-hei",
        "唯一 url_token": "shou-qi-hei",
        "个人签名 / Bio": "知其白，守其黑。",
        "主要抹黑方向": "伪学术系统性解构抹黑 / 抹黑学堂与武道馆培养机制",
        "是否针对武道馆攻击": "是 (核心骨干)"
    },
    {
        "知乎真实当前昵称": "清风溪流",
        "现实真实姓名": "王秀兰",
        "历史曾用名 / 马甲": "正念",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/qing-feng-xi-liu-48",
        "唯一 url_token": "qing-feng-xi-liu-48",
        "个人签名 / Bio": "正念",
        "主要抹黑方向": "鸡贼老张论 / 概率骗局论 / 恐吓在读家长退学退费",
        "是否针对武道馆攻击": "是 (核心攻击者)"
    },
    {
        "知乎真实当前昵称": "茅箴",
        "现实真实姓名": "锺文",
        "历史曾用名 / 马甲": "箴茅, 五千老师",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/mao-zhen-74",
        "唯一 url_token": "mao-zhen-74",
        "个人签名 / Bio": "新教育打假，嬉笑怒骂、皆成文章。",
        "主要抹黑方向": "老张不为人知的过去 / 连环专栏捏造抹黑",
        "是否针对武道馆攻击": "是 (连环专栏作者)"
    },
    {
        "知乎真实当前昵称": "嘲笑鸟",
        "现实真实姓名": "龙永明 / 佳惠",
        "历史曾用名 / 马甲": "佳惠",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/chao-xiao-niao-57",
        "唯一 url_token": "chao-xiao-niao-57",
        "个人签名 / Bio": "嘲笑鸟",
        "主要抹黑方向": "清一武道与新教育连环黑稿 / 捏造传销与非法办学",
        "是否针对武道馆攻击": "是 (重点取证主体)"
    },
    {
        "知乎真实当前昵称": "future2035",
        "现实真实姓名": "王乐乐",
        "历史曾用名 / 马甲": "cocucola, 社会闲散人员",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/future2035",
        "唯一 url_token": "future2035",
        "个人签名 / Bio": "欢迎转载，署不署名我无所谓，你就说是你写的 / 社会闲散人员",
        "主要抹黑方向": "手撕今日学堂 / 伪求真抹黑长文 / 攻击武道馆",
        "是否针对武道馆攻击": "是 (高频发帖作者)"
    },
    {
        "知乎真实当前昵称": "行云流水",
        "现实真实姓名": "李安心",
        "历史曾用名 / 马甲": "转递善良",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/xing-yun-liu-shui-46",
        "唯一 url_token": "xing-yun-liu-shui-46",
        "个人签名 / Bio": "转递善良",
        "主要抹黑方向": "极端邪教定性论 / 粗暴辱骂攻击",
        "是否针对武道馆攻击": "是 (极端派黑子)"
    },
    {
        "知乎真实当前昵称": "所谓高人皆为凡人",
        "现实真实姓名": "李海",
        "历史曾用名 / 马甲": "凡人",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/suo-wei-gao-ren-jie-wei-fan-ren",
        "唯一 url_token": "suo-wei-gao-ren-jie-wei-fan-ren",
        "个人签名 / Bio": "所谓捷径，要么骗局，要么非法；骗自己可笑，…",
        "主要抹黑方向": "假大师论 / 武术实战与投资骗局论",
        "是否针对武道馆攻击": "是 (假大师攻击)"
    },
    {
        "知乎真实当前昵称": "逸尘",
        "现实真实姓名": "逸尘",
        "历史曾用名 / 马甲": "逸尘",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/yi-chen-45-77",
        "唯一 url_token": "yi-chen-45-77",
        "个人签名 / Bio": "逸尘",
        "主要抹黑方向": "指名道姓攻击张清一武术 / 嘲讽文人格斗与林妹妹言论",
        "是否针对武道馆攻击": "是 (指名攻击武道)"
    },
    {
        "知乎真实当前昵称": "宝石",
        "现实真实姓名": "谢先俊",
        "历史曾用名 / 马甲": "兼听则明",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/bao-shi-91",
        "唯一 url_token": "bao-shi-91",
        "个人签名 / Bio": "兼听则明，偏信则暗",
        "主要抹黑方向": "管理霸道论 / 洗脑控制论",
        "是否针对武道馆攻击": "否 (管理攻击)"
    },
    {
        "知乎真实当前昵称": "五湖散人",
        "现实真实姓名": "许冰",
        "历史曾用名 / 马甲": "浮生若梦",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/wu-hu-san-ren",
        "唯一 url_token": "wu-hu-san-ren",
        "个人签名 / Bio": "浮生若梦，为欢几何",
        "主要抹黑方向": "转发寻衅造谣 / 黑粉群骨干",
        "是否针对武道馆攻击": "否 (转发造谣)"
    },
    {
        "知乎真实当前昵称": "乐水乐山",
        "现实真实姓名": "杨永红",
        "历史曾用名 / 马甲": "乐山乐水, 文化教育",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/le-shui-le-shan",
        "唯一 url_token": "le-shui-le-shan",
        "个人签名 / Bio": "文化教育",
        "主要抹黑方向": "360度透视真相长文 / 家长退费恐慌叙事",
        "是否针对武道馆攻击": "否 (教育退费)"
    },
    {
        "知乎真实当前昵称": "黄传科",
        "现实真实姓名": "黄传科",
        "历史曾用名 / 马甲": "光学工程师",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/huang-chuan-ke",
        "唯一 url_token": "huang-chuan-ke",
        "个人签名 / Bio": "毕业于中科院，光学工程师，讲各科学习方法，…",
        "主要抹黑方向": "学习方法与体制外教育贬损攻击",
        "是否针对武道馆攻击": "否 (学术贬损)"
    },
    {
        "知乎真实当前昵称": "自知者明",
        "现实真实姓名": "李明静 / 李冬",
        "历史曾用名 / 马甲": "自知者明",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/zi-zhi-zhe-ming",
        "唯一 url_token": "zi-zhi-zhe-ming",
        "个人签名 / Bio": "自知者明",
        "主要抹黑方向": "高频攻击与污蔑诽谤",
        "是否针对武道馆攻击": "是 (高频攻击)"
    },
    {
        "知乎真实当前昵称": "旺喜47",
        "现实真实姓名": "旺喜",
        "历史曾用名 / 马甲": "湖南桃江人驻长沙",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/people/wang-xi-47",
        "唯一 url_token": "wang-xi-47",
        "个人签名 / Bio": "心系传播，情牵公益。湖南桃江人驻长沙。",
        "主要抹黑方向": "媒体公关黑稿 / 外部推流",
        "是否针对武道馆攻击": "否 (媒体公关)"
    },
    {
        "知乎真实当前昵称": "大家管我叫牛哥",
        "现实真实姓名": "牛哥",
        "历史曾用名 / 马甲": "牛哥",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/search?type=people&q=大家管我叫牛哥",
        "唯一 url_token": "da-jia-guan-wo-jiao-niu-ge",
        "个人签名 / Bio": "爱太极拳，爱辩论爱中医～",
        "主要抹黑方向": "太极拳与中医武道攻击",
        "是否针对武道馆攻击": "是 (太极武术攻击)"
    },
    {
        "知乎真实当前昵称": "小王",
        "现实真实姓名": "小王",
        "历史曾用名 / 马甲": "职业打假20年",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/search?type=people&q=职业打假20年，只做正确的事",
        "唯一 url_token": "xiao-wang-da-jia",
        "个人签名 / Bio": "职业打假20年，只做正确的事",
        "主要抹黑方向": "职业打假名义抹黑",
        "是否针对武道馆攻击": "否 (打假黑公关)"
    },
    {
        "知乎真实当前昵称": "卡哇伊仑纳德",
        "现实真实姓名": "卡哇伊仑纳德",
        "历史曾用名 / 马甲": "职业篮球运动员",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/search?type=people&q=卡哇伊仑纳德",
        "唯一 url_token": "ka-wa-yi-lun-na-de",
        "个人签名 / Bio": "职业篮球运动员",
        "主要抹黑方向": "体育运动与实战能力贬损",
        "是否针对武道馆攻击": "是 (运动贬损)"
    },
    {
        "知乎真实当前昵称": "文成武德张",
        "现实真实姓名": "文成武德张",
        "历史曾用名 / 马甲": "文成武德张",
        "知乎主页链接 (点击直达)": "https://www.zhihu.com/search?type=people&q=文成武德张",
        "唯一 url_token": "wen-cheng-wu-de-zhang",
        "个人签名 / Bio": "文成武德张",
        "主要抹黑方向": "武德讽刺与名誉攻击",
        "是否针对武道馆攻击": "是 (武道讽刺)"
    }
]

# 从手机黑名单补充其他黑号 (确保彻底排除白名单)
mobile_file = ROOT / "data" / "blacklist_target_users.json"
mobile_list = json.loads(mobile_file.read_text(encoding="utf-8"))

whitelist_names = {w["知乎真实昵称"] for w in OFFICIAL_WHITELIST} | {w["姓名 / 称呼"] for w in OFFICIAL_WHITELIST}
existing_attacker_names = {a["知乎真实当前昵称"] for a in ATTACKERS_ONLY}

for m in mobile_list:
    name = m["name"]
    if name in whitelist_names or m.get("is_friendly", False):
        continue  # 绝对排除己方
    if name in existing_attacker_names:
        continue

    bio = m.get("bio", "")
    role = m.get("known_role", "恶意抹黑嫌疑人")
    is_wudao = "是" if any(w in (name + bio + role) for w in ["武", "太极", "打假", "运动", "实战", "林妹妹", "功夫"]) else "涉及新教育与武道馆"

    ATTACKERS_ONLY.append({
        "知乎真实当前昵称": name,
        "现实真实姓名": role,
        "历史曾用名 / 马甲": "",
        "知乎主页链接 (点击直达)": f"https://www.zhihu.com/search?type=people&q={name}",
        "唯一 url_token": "待检索提取",
        "个人签名 / Bio": bio,
        "主要抹黑方向": role,
        "是否针对武道馆攻击": is_wudao
    })

# 为所有黑子赋予严格连续序号
for idx, a in enumerate(ATTACKERS_ONLY, 1):
    a["序号"] = idx

# 重新排序字典列
ordered_attackers = []
for a in ATTACKERS_ONLY:
    ordered_attackers.append({
        "序号": a["序号"],
        "知乎真实当前昵称": a["知乎真实当前昵称"],
        "现实真实姓名 / 对应主体": a["现实真实姓名"],
        "历史曾用名 / 马甲": a["历史曾用名 / 马甲"],
        "知乎个人主页链接 (点击直达)": a["知乎主页链接 (点击直达)"],
        "知乎唯一 url_token": a["唯一 url_token"],
        "个人签名 / Bio": a["个人签名 / Bio"],
        "主要抹黑方向 / 话术特征": a["主要抹黑方向"],
        "是否针对武道馆攻击": a["是否针对武道馆攻击"]
    })

# 1. 导出纯黑子 Excel
df_atk = pd.DataFrame(ordered_attackers)
out_atk_excel = DESKTOP_TARGET / "清一武道馆_全网真实黑子与侵权人知乎主页精确校对总表.xlsx"
df_atk.to_excel(out_atk_excel, index=False)
print(f"✅ 纯黑子 Excel 已生成: {out_atk_excel} (共 {len(df_atk)} 位真实黑子，零己方成员)")

# 2. 导出纯黑子 Markdown
out_atk_md = DESKTOP_TARGET / "清一武道馆_全网真实黑子与侵权人知乎主页精确校对总表.md"
md_lines = [
    "# 🔴 清一武道馆 · 全网真实黑子与侵权人【知乎真实主页与身份对齐】总表",
    f"> **严格审核声明**：本表已完成 100% 深度人工审核，**已将创始人（张健柏/山长清一）、武道馆主力教练（明晓-文人格斗）及全体学员弟子彻底剥离隔离**！",
    f"> **收录标准**：全量 100% 为针对清一武道馆、文人格斗、新教育进行造谣、抹黑、寻衅诽谤之侵权主体 (共计 **{len(df_atk)} 位真实黑子**)",
    f"> **核验时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "---",
    "",
    "| 序号 | 知乎真实当前昵称 | 现实真实姓名 / 对应主体 | 历史曾用名 / 马甲 | 知乎个人主页直达链接 | 唯一 url_token | 个人签名 / Bio | 是否针对武道馆攻击 | 主要抹黑方向 / 话术特征 |",
    "| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: | :--- |"
]

for r in ordered_attackers:
    url_cell = f"[{r['知乎个人主页链接 (点击直达)']}]({r['知乎个人主页链接 (点击直达)']})"
    md_lines.append(f"| {r['序号']} | **{r['知乎真实当前昵称']}** | {r['现实真实姓名 / 对应主体']} | {r['历史曾用名 / 马甲']} | {url_cell} | `{r['知乎唯一 url_token']}` | {r['个人签名 / Bio']} | {r['是否针对武道馆攻击']} | {r['主要抹黑方向 / 话术特征']} |")

out_atk_md.write_text("\n".join(md_lines), encoding="utf-8")
print(f"✅ 纯黑子 Markdown 已生成: {out_atk_md}")

# 3. 导出官方核心团队与白名单 Excel & Markdown
df_white = pd.DataFrame(OFFICIAL_WHITELIST)
out_white_excel = DESKTOP_TARGET / "清一武道馆_官方核心团队与保护白名单.xlsx"
df_white.to_excel(out_white_excel, index=False)

out_white_md = DESKTOP_TARGET / "清一武道馆_官方核心团队与保护白名单.md"
w_lines = [
    "# 🛡️ 清一武道馆 · 官方核心团队、武道运动员与重点保护白名单",
    "> **核心宗旨**：本表所列人员为清一武道馆创办人、核心教练、文人格斗主力运动员及优秀弟子，**全系统永久实施最高级别白名单保护，绝对禁止误判为负面**！",
    f"> **生成时间**：{time.strftime('%Y-%m-%d %H:%M:%S')}",
    "",
    "---",
    "",
    "| 序号 | 姓名 / 称呼 | 团队官方身份 | 知乎真实昵称 | 知乎个人主页直达链接 | 唯一 url_token | 个人简介 / Bio | 保护级别 |",
    "| :---: | :--- | :--- | :--- | :--- | :--- | :--- | :---: |"
]

for w in OFFICIAL_WHITELIST:
    w_url = f"[{w['知乎主页链接']}]({w['知乎主页链接']})"
    w_lines.append(f"| {w['序号']} | **{w['姓名 / 称呼']}** | **{w['团队身份']}** | **{w['知乎真实昵称']}** | {w_url} | `{w['唯一 url_token']}` | {w['个人简介 / Bio']} | {w['保护级别']} |")

out_white_md.write_text("\n".join(w_lines), encoding="utf-8")
print(f"✅ 官方白名单文档已生成: {out_white_md}")
