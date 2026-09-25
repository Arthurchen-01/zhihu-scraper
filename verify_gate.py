#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
归档核对与硬门禁检查器 (Archive Gatekeeper & Verifier)
作用：
在进入任何 P1 操作前，对归档目录的每篇文章进行 100% 完整性核对与 SHA-256 校验。
如果有任何一篇文章缺失文件、文件大小为 0、或图片未完全下载，返回退出码 1 并阻止下一步。
"""

import sys
import json
import hashlib
from pathlib import Path


def compute_sha256(filepath: Path) -> str:
    if not filepath.exists() or filepath.is_dir():
        return ""
    h = hashlib.sha256()
    with open(filepath, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def verify_gate(output_dir: Path) -> bool:
    manifest_path = output_dir / "manifest.json"
    if not manifest_path.exists():
        print(f"[门禁拦截 ✗] 未找到 manifest.json: {manifest_path}")
        return False

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"[门禁拦截 ✗] 解析 manifest.json 失败: {e}")
        return False

    items = manifest.get("items", [])
    if not items:
        print("[门禁拦截 ✗] manifest.json 中没有文章记录！")
        return False

    print(f"[*] 开始进行 P0 归档门禁核验（共 {len(items)} 篇文章）...")

    all_passed = True
    failed_items = []

    for it in items:
        aid = it.get("id")
        title = it.get("title")
        art_dir = output_dir / "articles" / aid
        files = it.get("files", {})

        errors = []

        # 1. 检查各核心文件是否存在且非空
        for fname in ["meta.json", "original.json", "body.html", "body.docx", "comments.json"]:
            fpath = art_dir / fname
            if not fpath.exists():
                errors.append(f"缺失文件 {fname}")
            elif fpath.stat().st_size == 0:
                errors.append(f"空文件 {fname}")
            else:
                expected_sha = files.get(fname, {}).get("sha256")
                actual_sha = compute_sha256(fpath)
                if expected_sha and expected_sha != actual_sha:
                    errors.append(f"哈希不匹配 {fname} (期望 {expected_sha[:8]} 实测 {actual_sha[:8]})")

        # 2. 检查截图
        shot_path = art_dir / "screenshot.png"
        if not shot_path.exists() or shot_path.stat().st_size < 5000:
            errors.append("缺失有效截图或截图文件异常 (<5KB)")

        # 3. 检查图片下载完整度
        img_total = files.get("images_count", 0)
        img_dl = files.get("images_downloaded", 0)
        if img_total > 0:
            if img_dl != img_total:
                errors.append(f"图片未完全下载 (共 {img_total} 张，只下载到 {img_dl} 张)")
            img_dir = art_dir / "images"
            if not img_dir.exists():
                errors.append("缺失 images 目录")

        if errors:
            all_passed = False
            failed_items.append((aid, title, errors))
            print(f"  [✗ 失败] 文章 {aid} 《{title}》: {'; '.join(errors)}")
        else:
            print(f"  [✓ 合格] 文章 {aid} 《{title}》 校验通过")

    print("=" * 60)
    if all_passed:
        print(f"[门禁结论 🟢 PASS] 全部 {len(items)} 篇文章 100% 完整无缺，哈希校验全部通过！")
        print("准许进入后续阶段。")
        return True
    else:
        print(f"[门禁结论 🔴 REJECT] 存在 {len(failed_items)} 篇不合格文章！严禁进入 P1！")
        for aid, title, errs in failed_items:
            print(f"  - [{aid}] {title}: {errs}")
        return False


def main():
    import argparse
    parser = argparse.ArgumentParser(description="P0 归档门禁核验工具")
    parser.add_argument("--output", default="./archive_output", help="归档输出目录")
    args = parser.parse_args()

    out_p = Path(args.output).resolve()
    passed = verify_gate(out_p)
    sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
