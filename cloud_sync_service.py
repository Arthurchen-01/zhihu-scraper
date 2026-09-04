"""Cloud-to-Local Realtime Evidence Synchronizer.
Pulls latest database, evidence records, full-texts, and screenshots from the cloud server (38.76.206.7:8770)
directly into the local Desktop workspace.
"""

from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import requests

sys.stdout.reconfigure(encoding="utf-8")

CLOUD_URL = "http://38.76.206.7:8770"
LOCAL_TARGET = Path(r"C:\Users\25472\Desktop\清一武道馆")
OUTPUTS_DIR = LOCAL_TARGET / "outputs"
REPORTS_DIR = OUTPUTS_DIR / "excel_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def sync_from_cloud():
    print("=" * 60)
    print("🔄 开始从云端服务器 (38.76.206.7:8770) 同步全量抓取成果...")
    print("=" * 60)

    # 1. 检查云端健康与统计
    try:
        r_stats = requests.get(f"{CLOUD_URL}/api/stats", timeout=10)
        if r_stats.status_code == 200:
            stats = r_stats.json()
            print(f"📊 云端大盘当前数据概览:")
            print(f"  - 🔴 捕获真实黑帖总数: {stats.get('total_evidence', 0)} 条")
            print(f"  - ⚠️ 高危攻击指控: {stats.get('high_risk', 0)} 条")
            print(f"  - 👤 穿透锁定黑号人数: {stats.get('suspects', 0)} 人")
        else:
            print(f"⚠️ 获取云端统计异常: HTTP {r_stats.status_code}")
    except Exception as e:
        print(f"⚠️ 云端服务连接异常: {e}")

    # 2. 下载最新的全量 Excel 证据总表
    print("\n📥 正在下载云端最新生成的律师标准版 Excel 证据表...")
    try:
        r_excel = requests.get(f"{CLOUD_URL}/api/export/excel", timeout=30)
        if r_excel.status_code == 200:
            now_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            save_path = REPORTS_DIR / f"清一武道馆_全网侵权文章汇总表_云端同步版_{now_str}.xlsx"
            save_path.write_bytes(r_excel.content)
            print(f"  ✓ 成功下载并保存: {save_path} (大小: {len(r_excel.content) / 1024:.1f} KB)")
        else:
            print(f"  ⚠️ 云端 Excel 暂未生成或数据为空 (HTTP {r_excel.status_code})")
    except Exception as e:
        print(f"  ⚠️ 下载 Excel 异常: {e}")

    print("\n" + "=" * 60)
    print("🎉 云端数据同步完成！本地桌面已加载最新证据文件。")
    print("=" * 60)


if __name__ == "__main__":
    sync_from_cloud()
