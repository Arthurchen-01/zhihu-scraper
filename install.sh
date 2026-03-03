#!/bin/bash
# =============================================================================
# zhihu-scraper 一键安装脚本
# =============================================================================
# 用法: ./install.sh
#
# 会自动完成:
# 1. 创建/激活虚拟环境
# 2. 安装所有 Python 依赖
# 3. 安装 Playwright 浏览器
# =============================================================================

set -e  # 遇错即停

echo "========================================"
echo "  🕷️ zhihu-scraper 一键安装"
echo "========================================"
echo ""

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 检测 Python
echo "📌 检测 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON=$(which python3)
    VER=$(python3 --version)
    echo "   ✅ $VER ($PYTHON)"
else
    echo -e "   ❌ 未找到 Python 3，请先安装: https://www.python.org/downloads/"
    exit 1
fi

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

# 虚拟环境目录
VENV_DIR="$PROJECT_DIR/.venv"

# 创建或激活虚拟环境
echo ""
echo "📌 配置虚拟环境..."
if [ -d "$VENV_DIR" ]; then
    echo "   ℹ️  发现已有虚拟环境: .venv"
    read -p "   是否重新创建? (y/n): " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        echo "   🗑️  删除旧环境..."
        rm -rf "$VENV_DIR"
        python3 -m venv "$VENV_DIR"
        echo "   ✅ 已创建新环境"
    fi
else
    echo "   🔧 创建虚拟环境..."
    python3 -m venv "$VENV_DIR"
    echo "   ✅ 已创建"
fi

# 激活虚拟环境
source "$VENV_DIR/bin/activate"
echo "   ✅ 虚拟环境已激活"

# 升级 pip
echo ""
echo "📌 升级 pip..."
pip install --upgrade pip -q
echo "   ✅ pip $(pip --version | cut -d' ' -f1)"

# 安装项目依赖
echo ""
echo "📌 安装项目依赖..."
pip install -e ".[full]" -q
echo "   ✅ 项目依赖安装完成"

# 安装 Playwright 浏览器
echo ""
echo "📌 安装 Playwright 浏览器..."
echo "   (这是浏览器降级模式需要的，API 模式不需要)"
playwright install chromium 2>/dev/null || {
    echo "   ⚠️  playwright install 失败，继续安装..."
    pip install playwright
    playwright install chromium
}
echo "   ✅ Playwright Chromium 已安装"

# 检查配置文件
echo ""
echo "📌 检查配置..."
if [ ! -f "cookies.json" ]; then
    echo "   ⚠️  未找到 cookies.json"
    echo "   💡 如果不配置 Cookie，可以游客身份运行"
    echo "   📖 获取方法: 浏览器登录知乎 → F12 → Network → 复制 Cookie"
else
    if grep -q "YOUR_Z_C0_HERE" cookies.json; then
        echo "   ⚠️  cookies.json 未配置 (使用占位符)"
    else
        echo "   ✅ cookies.json 已配置"
    fi
fi

# 完成
echo ""
echo "========================================"
echo -e "  ${GREEN}✅ 安装完成！${NC}"
echo "========================================"
echo ""
echo "运行命令:"
echo ""
echo "  # 激活环境"
echo "  source .venv/bin/activate"
echo ""
echo "  # 抓取单个链接"
echo "  ./zhihu fetch \"https://www.zhihu.com/p/123456\""
echo ""
echo "  # 交互式界面"
echo "  ./zhihu interactive"
echo ""
echo "========================================"