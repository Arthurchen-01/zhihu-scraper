# -*- coding: utf-8 -*-
"""v12 验证：处数真的可选、扫描器真的能给多个位置。"""
import subprocess

SH = r'''
cd /opt/zhihu-scraper
systemctl restart zhihu-scraper
sleep 4
echo "service: $(systemctl is-active zhihu-scraper)"
echo

echo '--- /meta 的处数声明 ---'
curl -s -H "X-API-Key: guanjun2026" http://127.0.0.1:8775/api/qy/meta \
 | python3 -c "import sys,json;d=json.load(sys.stdin);print('max_body_hits =',d.get('max_body_hits'));print('scope_statement =',d.get('scope_statement')[:110])"
echo

echo '--- 用真实引擎测：同一篇文章，1 处 vs 3 处 ---'
python3 - <<'PY'
from zhihu_scraper import qy_content as qc
html = "".join(
    f"<p>第{i}段：这是关于学习方法与成长的思考正文，内容足够长以便成为候选。"
    f"这一段在讲如何通过刻意练习提升理解力，并把它用到日常训练里，"
    f"包括复盘、拆解与反复验证，直到真正掌握为止。</p>"
    for i in range(1, 9))
print("_MAX_BODY_HITS =", qc._MAX_BODY_HITS)
for n in (1, 2, 3, 5, 9):
    sc = qc.scan_scenes(html, limit=n)
    print("  limit=%d -> 实际 %d 处, block_no=%s" % (n, len(sc), [s.block_no for s in sc]))
out1 = qc.apply_scenes(html, qc.scan_scenes(html, limit=1))
out3 = qc.apply_scenes(html, qc.scan_scenes(html, limit=3))
print("  1 处后品牌词出现次数 =", qc._ANY_TAG_RE.sub("", out1).count("清一新教育"))
print("  3 处后品牌词出现次数 =", qc._ANY_TAG_RE.sub("", out3).count("清一新教育"))
print("  3 处结果可还原 =", qc.strip_scenes(out3) == html)
print("  幂等（已含品牌词再扫）= ", qc.scan_scenes(out3, limit=3))
PY
echo

echo '--- 页面：处数选择器 ---'
curl -s http://127.0.0.1:8775/api/qy/console -o /tmp/p.html -w 'page %{http_code}\n'
for s in fBodyHits bodyHitsWant "正文植入处数" "1~5 处" "5 处（最多）"; do
  printf '  %-18s ' "$s"; grep -c "$s" /tmp/p.html
done
'''

r = subprocess.run(['ssh', 'server3', SH], capture_output=True, timeout=300,
                   encoding='utf-8', errors='replace')
print(r.stdout)
if r.stderr.strip():
    print('STDERR:', r.stderr.strip()[-500:])
