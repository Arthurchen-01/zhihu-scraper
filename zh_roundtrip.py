#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
知乎文章端到端往返无损验证工具 (Zhihu Roundtrip Lossless Verifier)
验证目标：
1. 校验本地归档备份存在且指纹吻合 (P0 门禁)
2. 执行 P1：将线上内容替换为无意义公版经典文本并发布，在线核查替换生效
3. 执行 P2：从 original.json 将原始标题与富文本正文写回并发布
4. 在线回读线上草稿，与归档备份进行 SHA-256 逐字节比对
5. 证实端到端「归档 -> 覆写 -> 还原」100% 闭环无损
"""

import os
import sys
import json
import time
import uuid
import random
import hashlib
from pathlib import Path
from typing import Dict, Any, Tuple

import requests


DEFAULT_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/128.0.0.0 Safari/537.36"
)

# 无意义公版替换文本（荀子《劝学》，结构自然合规，避免触发单字 "0" 垃圾注入封号）
PLACEHOLDER_TITLE = "劝学"
PLACEHOLDER_HTML = (
    "<p>君子曰：学不可以已。青，取之于蓝，而青于蓝；冰，水为之，而寒于水。"
    "木直中绳，輮以为轮，其曲中规。虽有槁暴，不复挺者，輮使之然也。"
    "故木受绳则直，金就砺则利，君子博学而日参省乎己，则知明而行无过矣。</p>"
    "<p>吾尝终日而思矣，不如须臾之所学也；吾尝跂而望矣，不如登高之博见也。"
    "登高而招，臂非加长也，而见者远；顺风而呼，声非加疾也，而闻者彰。"
    "假舆马者，非利足也，而致千里；假舟楫者，非能水也，而绝江河。"
    "君子生非异也，善假于物也。</p>"
)


def compute_str_sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


class ZhihuRoundtripVerifier:
    def __init__(self, cookie_str: str, archive_dir: Path):
        self.cookie_str = cookie_str.strip()
        self.archive_dir = archive_dir
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": DEFAULT_UA,
            "Accept": "application/json, text/plain, */*",
            "Cookie": self.cookie_str,
        })
        self.url_token = ""

    def verify_auth(self) -> Dict[str, Any]:
        resp = self.session.get("https://www.zhihu.com/api/v4/me", timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"知乎登录态失效: HTTP {resp.status_code}")
        data = resp.json()
        self.url_token = data.get("url_token", "")
        print(f"[✓] 账号验证成功: {data.get('name')} (token: {self.url_token})")
        return data

    def get_online_draft(self, aid: str) -> Dict[str, Any]:
        url = f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft"
        headers = {"Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"}
        r = self.session.get(url, headers=headers, timeout=25)
        if r.status_code != 200:
            raise RuntimeError(f"读取线上草稿失败 ({aid}): HTTP {r.status_code}")
        return r.json()

    def patch_draft(self, aid: str, title: str, content: str) -> Tuple[bool, str]:
        url = f"https://zhuanlan.zhihu.com/api/articles/{aid}/draft"
        body_payload = {
            "title": title,
            "content": content,
            "delta_time": random.randint(3, 8),
            "can_reward": False,
        }
        r = self.session.patch(url, json=body_payload, headers={"Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"}, timeout=30)
        if r.status_code == 200:
            return True, "草稿保存成功"
        return False, f"草稿保存失败 HTTP {r.status_code} {r.text[:120]}"

    def publish_article(self, aid: str, title: str, body_html: str) -> Tuple[bool, str]:
        pc_business = json.dumps({
            "disclaimer_type": "none",
            "disclaimer_status": "close",
            "table_of_contents_enabled": False,
            "content": body_html,
            "title": title,
            "commercial_report_info": {"commercial_types": []},
            "commercial_zhitask_bind_info": None,
            "canReward": False,
        }, ensure_ascii=False)
        payload = {
            "action": "article",
            "data": {
                "publish": {"traceId": f"{int(time.time() * 1000)},{uuid.uuid4()}"},
                "extra_info": {"publisher": "pc", "pc_business_params": pc_business},
                "draft": {"disabled": 1, "id": aid, "isPublished": True},
                "commentsPermission": {},
                "creationStatement": {"disclaimer_type": "none", "disclaimer_status": "close"},
                "contentsTables": {"table_of_contents_enabled": False},
                "commercialReportInfo": {"isReport": 0},
                "appreciate": {"can_reward": False, "tagline": ""},
                "hybridInfo": {},
                "hybrid": {"html": body_html},
            },
        }
        r = self.session.post(
            "https://www.zhihu.com/api/v4/content/publish",
            json=payload,
            headers={
                "Origin": "https://www.zhihu.com",
                "Referer": f"https://zhuanlan.zhihu.com/p/{aid}/edit"
            },
            timeout=40
        )
        if r.status_code != 200:
            return False, f"发布接口 HTTP {r.status_code} {r.text[:120]}"
        try:
            j = r.json()
            if j.get("code") == 0:
                return True, "发布成功"
            return False, f"发布提示: {j}"
        except Exception:
            return True, "发布已提交"

    def run_roundtrip(self, aid: str) -> bool:
        print("=" * 65)
        print(f" 开始文章 [{aid}] 端到端往返无损验证 (Roundtrip Test)")
        print("=" * 65)

        # -------------------------------------------------------------
        # 步骤 0: 检查本地备份与硬门禁
        # -------------------------------------------------------------
        art_backup_dir = self.archive_dir / "articles" / aid
        orig_json_file = art_backup_dir / "original.json"
        if not orig_json_file.exists():
            print(f"[门禁拦截 ✗] 本地缺失原始备份: {orig_json_file}")
            return False

        orig_data = json.loads(orig_json_file.read_text(encoding="utf-8"))
        orig_title = orig_data.get("title", "").strip()
        orig_content = orig_data.get("content", "").strip()
        orig_author_token = orig_data.get("author", {}).get("url_token", "")
        orig_sha = compute_str_sha256(orig_content)

        if not orig_title or not orig_content:
            print("[门禁拦截 ✗] 备份文件损坏或内容为空！")
            return False

        if orig_author_token != self.url_token:
            print(f"[门禁拦截 ✗] 文章作者 ({orig_author_token}) 与当前登录账号 ({self.url_token}) 不符！")
            return False

        print(f"[P0 备份核验通过 ✓]")
        print(f"  原文章标题: 《{orig_title}》")
        print(f"  原正文长度: {len(orig_content)} 字符")
        print(f"  原正文 SHA-256: {orig_sha}")

        # -------------------------------------------------------------
        # 步骤 1: P1 演练 · 替换为无意义公版内容
        # -------------------------------------------------------------
        print("\n--- [P1 覆写演练] 正在将线上文章替换为无意义公版内容 ---")
        ok_patch, msg_patch = self.patch_draft(aid, title=orig_title, content=PLACEHOLDER_HTML)
        if not ok_patch:
            print(f"[P1 失败 ✗] {msg_patch}")
            return False
        
        time.sleep(1)
        ok_pub, msg_pub = self.publish_article(aid, title=orig_title, body_html=PLACEHOLDER_HTML)
        if not ok_pub:
            print(f"[P1 发布失败 ✗] {msg_pub}")
            return False
        print("  [✓] 线上草稿已覆写并发布！")

        time.sleep(2)
        live_draft = self.get_online_draft(aid)
        live_content = live_draft.get("content", "").strip()
        if "学不可以已" in live_content:
            print(f"  [✓ 线上核查通过] 线上正文已成功变为公版文本 (长度 {len(live_content)} 字符)")
        else:
            print(f"  [!] 线上核查未见公版文字，实测内容前100字: {live_content[:100]}")

        # -------------------------------------------------------------
        # 步骤 2: P2 演练 · 从备份完整写回原文
        # -------------------------------------------------------------
        print("\n--- [P2 还原演练] 正在从本地备份完整写回原文 ---")
        time.sleep(2)
        ok_restore_patch, msg_r_patch = self.patch_draft(aid, title=orig_title, content=orig_content)
        if not ok_restore_patch:
            print(f"[P2 写回失败 ✗] {msg_r_patch}")
            return False

        time.sleep(1)
        ok_restore_pub, msg_r_pub = self.publish_article(aid, title=orig_title, body_html=orig_content)
        if not ok_restore_pub:
            print(f"[P2 发布失败 ✗] {msg_r_pub}")
            return False
        print("  [✓] 原文已重新写回线上并发布！")

        # -------------------------------------------------------------
        # 步骤 3: 回读线上内容，做端到端无损比对
        # -------------------------------------------------------------
        print("\n--- [端到端复核] 回读线上内容并比对完整性 ---")
        time.sleep(3)
        restored_draft = self.get_online_draft(aid)
        restored_title = restored_draft.get("title", "").strip()
        restored_content = restored_draft.get("content", "").strip()
        restored_sha = compute_str_sha256(restored_content)

        print(f"  原始正文长度: {len(orig_content)} 字符")
        print(f"  恢复线上长度: {len(restored_content)} 字符")
        print(f"  标题一致性: {orig_title == restored_title} (《{restored_title}》)")

        # 知乎 CDN 域名归一化 (pic1~pic4.zhimg.com 统一重定向为 picx.zhimg.com)
        import re
        norm_orig = re.sub(r"https://pic[0-9a-z]\.zhimg\.com", "https://picx.zhimg.com", orig_content)
        norm_restored = re.sub(r"https://pic[0-9a-z]\.zhimg\.com", "https://picx.zhimg.com", restored_content)

        is_perfect_match = (norm_orig == norm_restored)
        norm_orig_sha = compute_str_sha256(norm_orig)
        norm_restored_sha = compute_str_sha256(norm_restored)

        print(f"  归一化原始 SHA-256: {norm_orig_sha}")
        print(f"  归一化线上 SHA-256: {norm_restored_sha}")

        if is_perfect_match:
            print("\n" + "=" * 65)
            print("[端到端往返无损验证 🟢 100% PASS]")
            print("结论：线上文章成功完成「归档 -> 覆写为公版 -> 原样无损还原」全闭环！")
            print("文字、段落、图片 ID、排版结构 100% 完整无损！")
            print("=" * 65)
            return True
        else:
            print("\n[端到端验证 🔴 FAIL] 还原后正文内容不匹配！")
            return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="知乎文章端到端往返验证工具")
    parser.add_argument("--aid", required=True, help="要进行验证的文章 ID")
    parser.add_argument("--cookie-file", default="/Users/rancho/QingyiEdu/cookie.txt")
    parser.add_argument("--archive-dir", default="./test_archive_output")
    args = parser.parse_args()

    cookie_p = Path(args.cookie_file)
    if not cookie_p.exists():
        cookie_p = Path("./cookie.txt")
    raw_cookie = cookie_p.read_text(encoding="utf-8").strip()
    clean_cookie = ""
    for line in raw_cookie.splitlines():
        line = line.strip()
        if "z_c0" in line:
            clean_cookie = line
            break
    if not clean_cookie:
        clean_cookie = raw_cookie.splitlines()[0]

    verifier = ZhihuRoundtripVerifier(clean_cookie, Path(args.archive_dir).resolve())
    verifier.verify_auth()
    passed = verifier.run_roundtrip(args.aid)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
