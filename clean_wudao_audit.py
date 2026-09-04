import pandas as pd
import json
import re
from pathlib import Path
from ai_deep_audit import audit_stance
import sys

sys.stdout.reconfigure(encoding="utf-8")

raw_excel = Path(r"C:\Users\25472\Desktop\AI brain storming\工具栏\zhihu-black\outputs\清一武道馆_专属黑帖证据清单_20260825_160430.xlsx")
df = pd.read_excel(raw_excel)

true_attacks = []
friendly_whitelisted = []

# Expanded pro-brand tokens & names
PRO_TOKENS = {
    "shan-chang-qing-yi", "shan-chang-tou-zi-hao", "jin-ji-de-qing-fen",
    "ellaqing-yi-gong-zhu-no1", "cai-kai-qi-88", "ming-xiao-wen-ren-ge-dou",
    "chang-sha-shi-zhi-xiong", "lu-jia-yi-10", "tan-chen-yi-wen-ren-ge-dou",
    "lu-yun-ru-wen-ren-ge-dou", "chen-yue-yi", "chen-shi-yi", "ge-cong", "zhao-gang"
}

PRO_NAME_KEYWORDS = [
    "山长", "清一", "清粉", "文人格斗", "Ella", "明晓", "明仪", "明德", "今日学堂",
    "今日塾", "蔡凯琪", "陆韵如", "谭琛怡", "陈玥伊", "陈诗宜", "葛琮", "司启彤", "魏台龙"
]

for _, row in df.iterrows():
    author = str(row.get("发帖人昵称", "")).strip()
    author_token = str(row.get("发帖人Token", "")).strip()
    content = str(row.get("攻击原句", "")).strip()
    title = str(row.get("标题/问题", "")).strip()
    source = str(row.get("来源类型", "")).strip()
    link = str(row.get("链接", "")).strip()

    # Clean HTML tags
    author_clean = re.sub(r"<[^>]+>", "", author)
    content_clean = re.sub(r"<[^>]+>", "", content)
    title_clean = re.sub(r"<[^>]+>", "", title)

    # Check whitelist
    is_pro = False
    if author_token in PRO_TOKENS:
        is_pro = True
    elif any(k in author_clean for k in PRO_NAME_KEYWORDS) and not any(k in author_clean for k in ["老贼", "神棍", "假", "黑"]):
        # Verify if defending or writing student logs
        if any(w in content_clean for w in ["清一太极", "泰拳锦标赛", "我们班", "山长帮", "写好诉讼信", "清一木兰", "比赛视频", "清一大学"]):
            is_pro = True

    if is_pro:
        friendly_whitelisted.append({
            "类型": "己方/学员/支持者(白名单保护)",
            "作者昵称": author_clean,
            "作者Token": author_token,
            "来源类型": source,
            "标题/问题": title_clean,
            "言论内容摘录": content_clean[:120],
            "链接": link
        })
        continue

    # Semantic audit
    res = audit_stance({
        "言论发布者": author_clean,
        "作者UID/Token": author_token,
        "父级标题/问题": title_clean,
        "完整言论原文": content_clean
    })

    if res["is_true_negative"] or any(k in content_clean for k in ["骗子", "吹牛", "打成一个林妹妹", "功利化", "动静", "质疑", "马保国"]):
        true_attacks.append({
            "真实黑子昵称": author_clean,
            "知乎Token/UID": author_token,
            "来源类型": source,
            "相关问题/文章标题": title_clean,
            "针对武道馆的核心攻击原句": content_clean,
            "判定依据与风险标签": res["reason"] if res["is_true_negative"] else "武道馆实战能力与师承质疑/攻击",
            "原始链接": link
        })
    else:
        friendly_whitelisted.append({
            "类型": "中立讨论/无确凿武道攻击",
            "作者昵称": author_clean,
            "作者Token": author_token,
            "来源类型": source,
            "标题/问题": title_clean,
            "言论内容摘录": content_clean[:120],
            "链接": link
        })

df_attacks = pd.DataFrame(true_attacks).drop_duplicates(subset=["知乎Token/UID", "针对武道馆的核心攻击原句"])
df_white = pd.DataFrame(friendly_whitelisted).drop_duplicates(subset=["作者Token", "言论内容摘录"])

out_excel = Path(r"C:\Users\25472\Desktop\清一武道馆\清一武道馆_专属真实黑帖与攻击者卷宗_精确版.xlsx")
with pd.ExcelWriter(out_excel, engine="openpyxl") as writer:
    df_attacks.to_excel(writer, sheet_name="真实武道黑帖证据清单", index=False)
    df_white.to_excel(writer, sheet_name="己方学员与白名单排除", index=False)

print(f"✅ 精确清洗完成！")
print(f"  - 🔴 真实武道黑帖证据: {len(df_attacks)} 条")
print(f"  - 🛡️ 己方学员与白名单排除: {len(df_white)} 条")
print(f"  - 📁 精确版 Excel 已保存至: {out_excel}")
