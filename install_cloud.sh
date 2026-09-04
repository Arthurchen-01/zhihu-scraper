#!/bin/bash
set -e

echo "======================================================================"
echo "🚀 开始在云端服务器安装部署【知乎全网持续负面舆情监控与人员穿透系统】..."
echo "======================================================================"

INSTALL_DIR="/opt/zhihu-monitor"
mkdir -p ${INSTALL_DIR} ${INSTALL_DIR}/data ${INSTALL_DIR}/logs ${INSTALL_DIR}/outputs

cd ${INSTALL_DIR}

# 1. 检查并创建 Python 虚拟环境
if [ ! -d ".venv" ]; then
    echo "📦 正在创建 Python 虚拟环境 (.venv)..."
    python3 -m venv .venv
fi

# 2. 安装必要依赖
echo "📥 正在安装 Python 依赖库..."
.venv/bin/pip install --upgrade pip
.venv/bin/pip install requests curl-cffi beautifulsoup4 lxml pandas openpyxl fastapi uvicorn

# 3. 安装 Systemd 服务
echo "⚙️ 正在注册并配置 Systemd 守护进程..."
cp ${INSTALL_DIR}/zhihu-monitor.service /etc/systemd/system/zhihu-monitor.service
cp ${INSTALL_DIR}/zhihu-web.service /etc/systemd/system/zhihu-web.service

systemctl daemon-reload
systemctl enable zhihu-monitor.service
systemctl enable zhihu-web.service

systemctl restart zhihu-monitor.service
systemctl restart zhihu-web.service

echo "======================================================================"
echo "🎉 部署完成！"
echo "  - 守护监控服务状态: systemctl status zhihu-monitor"
echo "  - Web大盘服务状态: systemctl status zhihu-web"
echo "  - Web大盘访问入口: http://38.76.206.7:8770"
echo "======================================================================"
