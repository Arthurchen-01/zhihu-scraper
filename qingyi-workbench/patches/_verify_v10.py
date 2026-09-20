# -*- coding: utf-8 -*-
"""线上状态总核对。"""
import subprocess

SH = r'''
K=guanjun2026
echo "service      : $(systemctl is-active zhihu-scraper)"
curl -s -o /dev/null -w 'console      : %{http_code}\n' http://127.0.0.1:8775/api/qy/console
curl -s -H "X-API-Key: $K" -o /tmp/e.exe -w 'download exe : %{http_code} %{size_download}\n' http://127.0.0.1:8775/api/qy/download/windows
md5sum /tmp/e.exe
curl -s -H "X-API-Key: $K" -o /dev/null -w 'download ext : %{http_code} %{size_download}\n' http://127.0.0.1:8775/api/qy/download/extension
curl -s -H "X-API-Key: $K" http://127.0.0.1:8775/api/qy/jobs?limit=1 -o /tmp/j1.json -w 'jobs         : %{http_code}\n'
python3 -c "import json;d=json.load(open('/tmp/j1.json'));j=d['jobs'][0];print('latest job   :',j['job_id'],j['status'],(j.get('summary') or {}).get('pending'),'pending')"
cd /opt/zhihu-scraper
echo "git HEAD     : $(git rev-parse --short HEAD)"
echo "git origin   : $(git rev-parse --short origin/main)"
echo "dirty files  : $(git status --porcelain | wc -l)"
grep -c "async function renderHowto" zhihu_scraper/app/qingyi_page.py
grep -c "六道体检" zhihu_scraper/app/qingyi_page.py
ls -la clients/qingyi_deploy.py
'''

r = subprocess.run(['ssh', 'server3', SH], capture_output=True, timeout=180,
                   encoding='utf-8', errors='replace')
print(r.stdout)
if r.stderr.strip():
    print('STDERR:', r.stderr.strip()[-300:])
