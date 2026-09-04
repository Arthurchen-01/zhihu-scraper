"""Reporter: Exports structured Excel spreadsheets and Markdown evidence reports.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
import pandas as pd


class EvidenceReporter:
    def __init__(self, output_dir: Path):
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def export_all(self, brand: str, evidence_list: list[dict[str, Any]], suspects_dict: dict[str, dict[str, Any]]) -> dict[str, str]:
        """Export Excel, CSV and Markdown reports."""
        now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
        files_created = {}

        # 1. 证据明细表 (Excel + CSV)
        df_evidence = pd.DataFrame([
            {
                "序号": idx,
                "来源形式": it.get("source_type", ""),
                "父级标题/问题": it.get("parent_title", ""),
                "原帖/回答URL": it.get("parent_url", ""),
                "言论发布者": it.get("author_name", ""),
                "作者UID/Token": it.get("author_token", ""),
                "作者主页": it.get("author_url", ""),
                "发布时间": it.get("created_at", ""),
                "点赞数": it.get("voteup_count", 0),
                "风险级别": it.get("risk_level", ""),
                "负面分类": "、".join(it.get("category", [])),
                "核心实锤摘要/引证": it.get("evidence", ""),
                "完整言论原文": it.get("content", ""),
            }
            for idx, it in enumerate(evidence_list, 1)
        ])

        excel_path = self.output_dir / f"知乎负面证据清单_{now_str}.xlsx"
        csv_path = self.output_dir / f"知乎负面证据清单_{now_str}.csv"
        
        try:
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                df_evidence.to_excel(writer, sheet_name="负面证据明细", index=False)
            files_created["evidence_excel"] = str(excel_path)
        except Exception as e:
            print(f"[警告] 导出 Excel 失败，回退保存 CSV: {e}")

        df_evidence.to_csv(csv_path, index=False, encoding="utf-8-sig")
        files_created["evidence_csv"] = str(csv_path)

        # 2. 可疑人员画像表 (Excel / CSV)
        suspects_rows = []
        for token, u in suspects_dict.items():
            suspects_rows.append({
                "用户昵称": u.get("name", ""),
                "url_token": token,
                "主页链接": u.get("user_url", ""),
                "一句话介绍": u.get("headline", ""),
                "粉丝数": u.get("follower_count", 0),
                "知乎总回答数": u.get("total_answers", 0),
                "知乎总文章数": u.get("total_articles", 0),
                "累计命中负面言论数": u.get("negative_count", 0),
                "是否多帖持续攻击": "⚠️ 是 (频繁攻击)" if u.get("is_frequent_attacker") else "否",
                "全网历史攻击言论摘要": " || ".join([f"[{it['type']}] {it['title']}: {it['evidence']}" for it in u.get("negative_items", [])[:5]])
            })

        df_suspects = pd.DataFrame(suspects_rows)
        suspects_csv = self.output_dir / f"重点可疑人员画像表_{now_str}.csv"
        df_suspects.to_csv(suspects_csv, index=False, encoding="utf-8-sig")
        files_created["suspects_csv"] = str(suspects_csv)

        # 3. 汇总 Markdown 报告
        md_path = self.output_dir / f"知乎舆情排查与证据卷宗_{now_str}.md"
        md_content = self._generate_markdown_report(brand, evidence_list, suspects_dict, now_str)
        md_path.write_text(md_content, encoding="utf-8")
        files_created["report_md"] = str(md_path)

        return files_created

    def _generate_markdown_report(self, brand: str, evidence: list[dict[str, Any]], suspects: dict[str, dict[str, Any]], now_str: str) -> str:
        high_risk = sum(1 for e in evidence if e.get("risk_level") == "HIGH")
        med_risk = sum(1 for e in evidence if e.get("risk_level") == "MEDIUM")
        
        # 统计负面分类分布
        category_counts: dict[str, int] = {}
        for e in evidence:
            for cat in e.get("category", []):
                category_counts[cat] = category_counts.get(cat, 0) + 1

        lines = [
            f"# 【{brand}】知乎全网负面证据排查与人员穿透报告",
            f"\n> **排查时间**：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **排查范围**：知乎问答正文、文章专栏、全量评论区及楼中楼、可疑人员全网历史动态  ",
            f"\n---\n",
            f"## 一、 核心排查结论与大盘概览\n",
            f"* **累计发现负面/攻击言论**：**{len(evidence)}** 条",
            f"  * 🔴 **高风险指控** (骗子/假武术/误人子弟等实锤指控)：**{high_risk}** 条",
            f"  * 🟡 **中风险质疑** (体验不佳/态度质疑/一般吐槽)：**{med_risk}** 条",
            f"* **识别重点关联人员**：**{len(suspects)}** 人",
            f"  * ⚠️ **多帖/全网持续攻击者**：**{sum(1 for s in suspects.values() if s.get('is_frequent_attacker'))}** 人\n",
            f"### 争议指控核心分布：\n",
        ]

        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"- **{cat}**：{count} 条")

        lines.extend([
            f"\n---\n",
            f"## 二、 重点可疑人员深度画像 (Top Suspects)\n",
        ])

        if suspects:
            for idx, (token, u) in enumerate(suspects.items(), 1):
                flag = "【⚠️ 频繁攻击者】" if u.get("is_frequent_attacker") else ""
                lines.append(f"### {idx}. {u.get('name')} {flag}")
                lines.append(f"- **主页链接**：[{u.get('user_url')}]({u.get('user_url')})")
                lines.append(f"- **账号简介**：{u.get('headline') or '无'}")
                lines.append(f"- **全网累计负面发言**：`{u.get('negative_count')}` 条")
                if u.get("negative_items"):
                    lines.append(f"- **历史攻击言论记录**：")
                    for neg in u["negative_items"][:5]:
                        lines.append(f"  * **[{neg['type']}]** [{neg['title']}]({neg['url']})：{neg['evidence'] or neg['content'][:80]}")
                lines.append("")
        else:
            lines.append("*暂无重点可疑人员*")

        lines.extend([
            f"\n---\n",
            f"## 三、 负面证据详细清单 (前 20 条示例)\n",
            f"| 序号 | 来源 | 发帖人 | 风险 | 核心分类 | 言论摘要/证据 | 原始链接 |",
            f"| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])

        for idx, e in enumerate(evidence[:20], 1):
            author_display = f"[{e.get('author_name')}]({e.get('author_url')})" if e.get('author_url') else e.get('author_name', '匿名')
            cats = "、".join(e.get("category", []))
            ev = (e.get("evidence") or e.get("content", ""))[:45].replace("\n", " ").replace("|", " ")
            lines.append(f"| {idx} | {e.get('source_type')} | {author_display} | {e.get('risk_level')} | {cats} | {ev} | [查看原帖]({e.get('parent_url')}) |")

        lines.extend([
            f"\n\n> 完整全部 {len(evidence)} 条证据及原文已同步导出至 Excel/CSV 报表文件。",
            f"\n---\n*本报告由知乎负面证据取证自动化系统独立生成。*"
        ])

        return "\n".join(lines)
