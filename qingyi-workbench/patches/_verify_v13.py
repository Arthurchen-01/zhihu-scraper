# -*- coding: utf-8 -*-
import subprocess


def sh(c, t=90):
    r = subprocess.run(['ssh', 'server3', c], capture_output=True, timeout=t,
                       encoding='utf-8', errors='replace')
    return (r.stdout or '')


print('--- 样式层标记 ---')
print(sh("cd /opt/zhihu-scraper && python3 -c \"import io;s=io.open('zhihu_scraper/app/qingyi_page.py',encoding='utf-8').read();print('style_blocks',s.count('<style'));print('close_style',s.count('</style>'));print('layer_v13',s.count('v13 ' + chr(183) + ' '));print('layer_fix',s.count('v13.1'));print('enhance_js',s.count('v13 ' + chr(20132) + chr(20114) + chr(22686) + chr(24378)))\""))

print('--- 下载端点（带 key）---')
print(sh("curl -s -o /dev/null -w 'exe=%{http_code} size=%{size_download}\\n' -H 'X-API-Key: guanjun2026' http://127.0.0.1:8775/api/qy/download/windows"))
print(sh("curl -s -o /dev/null -w 'ext=%{http_code} size=%{size_download}\\n' -H 'X-API-Key: guanjun2026' http://127.0.0.1:8775/api/qy/download/extension"))
