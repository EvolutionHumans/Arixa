#!/bin/bash
# Arixa 一键安装脚本 (Linux/macOS)

set -e

# 颜色
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                                                          ║"
echo "║       Arixa - AI-Powered FPGA Development Assistant      ║"
echo "║                    一键安装程序                          ║"
echo "║                                                          ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_DIR="$HOME/.arixa"

# 检查 Python
echo "[1/4] 检查 Python..."
if command -v python3 &> /dev/null; then
    PYTHON="python3"
elif command -v python &> /dev/null; then
    PYTHON="python"
else
    echo -e "${RED}❌ Python 未安装${NC}"
    echo "请安装 Python 3.8+"
    exit 1
fi
echo -e "${GREEN}✅ Python 已安装${NC}"

# 创建目录
echo ""
echo "[2/4] 创建安装目录..."
mkdir -p "$INSTALL_DIR/src"

# 复制文件
echo ""
echo "[3/4] 安装文件..."
cp -r "$SCRIPT_DIR/src/"* "$INSTALL_DIR/src/" 2>/dev/null || true
cp "$SCRIPT_DIR/arixa.py" "$INSTALL_DIR/" 2>/dev/null || true
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_DIR/" 2>/dev/null || true

# 安装依赖
echo ""
echo "[4/4] 安装 Python 依赖..."
$PYTHON -m pip install -q anthropic openai google-generativeai requests 2>/dev/null || {
    echo -e "${YELLOW}⚠️ 部分依赖安装失败，可稍后手动安装${NC}"
}

# 创建启动脚本
cat > "$INSTALL_DIR/arixa" << EOF
#!/bin/bash
$PYTHON "$INSTALL_DIR/arixa.py" "\$@"
EOF
chmod +x "$INSTALL_DIR/arixa"

# 添加到 PATH
echo ""
read -p "是否添加到 PATH? [Y/n]: " ADD_PATH
if [[ ! "$ADD_PATH" =~ ^[Nn]$ ]]; then
    if [[ -f "$HOME/.bashrc" ]]; then
        echo "export PATH=\"\$HOME/.arixa:\$PATH\"" >> "$HOME/.bashrc"
    fi
    if [[ -f "$HOME/.zshrc" ]]; then
        echo "export PATH=\"\$HOME/.arixa:\$PATH\"" >> "$HOME/.zshrc"
    fi
    echo -e "${GREEN}✅ 已添加到 PATH（重启终端生效）${NC}"
fi

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    ✅ 安装完成！                         ║"
echo "╠══════════════════════════════════════════════════════════╣"
echo "║  使用方法:                                               ║"
echo "║    arixa --setup    首次配置                             ║"
echo "║    arixa --chat     启动对话                             ║"
echo "║    arixa --gui      启动图形界面                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"

read -p "是否立即进行首次配置? [Y/n]: " SETUP
if [[ ! "$SETUP" =~ ^[Nn]$ ]]; then
    "$INSTALL_DIR/arixa" --setup
fi
