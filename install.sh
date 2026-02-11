#!/bin/bash

# Arixa 一键安装脚本 (Linux/macOS)

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# 打印函数
print_header() {
    echo -e "${BLUE}"
    echo "╔══════════════════════════════════════════════════════════╗"
    echo "║                                                          ║"
    echo "║       Arixa - AI-Powered FPGA Development Assistant      ║"
    echo "║                    一键安装程序                          ║"
    echo "║                                                          ║"
    echo "╚══════════════════════════════════════════════════════════╝"
    echo -e "${NC}"
}

print_success() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# 获取脚本所在目录
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
INSTALL_PATH="$HOME/.arixa"

print_header

# 检查 Python
echo "[1/5] 检查 Python 环境..."
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version 2>&1 | awk '{print $2}')
    print_success "检测到 Python $PYTHON_VERSION"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
    PYTHON_VERSION=$(python --version 2>&1 | awk '{print $2}')
    print_success "检测到 Python $PYTHON_VERSION"
else
    print_error "Python 未安装！"
    echo "请安装 Python 3.8+："
    if [[ "$OSTYPE" == "darwin"* ]]; then
        echo "  brew install python3"
    else
        echo "  sudo apt install python3 python3-pip python3-venv  # Ubuntu/Debian"
        echo "  sudo dnf install python3 python3-pip              # Fedora"
    fi
    exit 1
fi

# 检查 Python 版本
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 8 ]); then
    print_error "需要 Python 3.8 或更高版本，当前版本: $PYTHON_VERSION"
    exit 1
fi

# 检查 pip
echo ""
echo "[2/5] 检查 pip..."
if ! $PYTHON_CMD -m pip --version &> /dev/null; then
    print_warning "pip 未安装，正在安装..."
    $PYTHON_CMD -m ensurepip --upgrade
fi
print_success "pip 可用"

# 创建虚拟环境
echo ""
echo "[3/5] 创建虚拟环境..."
VENV_PATH="$INSTALL_PATH/venv"

if [ -d "$VENV_PATH" ]; then
    echo "虚拟环境已存在，跳过创建"
else
    $PYTHON_CMD -m venv "$VENV_PATH"
fi
print_success "虚拟环境就绪"

# 激活虚拟环境并安装依赖
echo ""
echo "[4/5] 安装依赖..."
source "$VENV_PATH/bin/activate"

pip install --upgrade pip > /dev/null 2>&1
pip install anthropic openai google-generativeai requests > /dev/null 2>&1 || {
    print_warning "部分依赖安装失败，但核心功能仍可使用"
}
print_success "依赖安装完成"

# 复制文件到安装目录
echo ""
echo "[5/5] 安装 Arixa..."
mkdir -p "$INSTALL_PATH/src"

# 复制源文件
cp -r "$SCRIPT_DIR/src/"* "$INSTALL_PATH/src/" 2>/dev/null || true
cp "$SCRIPT_DIR/arixa.py" "$INSTALL_PATH/" 2>/dev/null || true
cp "$SCRIPT_DIR/requirements.txt" "$INSTALL_PATH/" 2>/dev/null || true

# 创建启动脚本
cat > "$INSTALL_PATH/arixa" << 'EOF'
#!/bin/bash
ARIXA_HOME="$HOME/.arixa"
source "$ARIXA_HOME/venv/bin/activate"
python "$ARIXA_HOME/arixa.py" "$@"
EOF

chmod +x "$INSTALL_PATH/arixa"

# 创建符号链接到 /usr/local/bin (可选)
echo ""
read -p "是否将 arixa 命令添加到系统? (需要 sudo) [Y/n]: " ADD_TO_PATH
if [[ ! "$ADD_TO_PATH" =~ ^[Nn]$ ]]; then
    if [ -d "/usr/local/bin" ]; then
        sudo ln -sf "$INSTALL_PATH/arixa" /usr/local/bin/arixa 2>/dev/null && {
            print_success "已创建 /usr/local/bin/arixa"
        } || {
            print_warning "无法创建系统链接，请手动添加到 PATH"
            echo "  添加到 ~/.bashrc 或 ~/.zshrc:"
            echo "  export PATH=\"\$HOME/.arixa:\$PATH\""
        }
    fi
else
    echo ""
    echo "请手动添加到 PATH:"
    echo "  export PATH=\"\$HOME/.arixa:\$PATH\""
fi

echo ""
echo -e "${GREEN}"
echo "╔══════════════════════════════════════════════════════════╗"
echo "║                    ✅ 安装完成！                         ║"
echo "╚══════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""
echo "使用方法:"
echo "  1. 运行 arixa --setup 进行首次配置"
echo "  2. 运行 arixa --chat 开始使用"
echo "  3. 运行 arixa --gui  启动图形界面"
echo ""
echo "或者直接运行: $INSTALL_PATH/arixa"
echo ""

# 询问是否立即配置
read -p "是否立即进行首次配置? [Y/n]: " SETUP_NOW
if [[ ! "$SETUP_NOW" =~ ^[Nn]$ ]]; then
    "$INSTALL_PATH/arixa" --setup
fi
