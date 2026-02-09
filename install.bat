@echo off
echo Installing Arixa - AI Vivado Controller...

:: 检查 Python
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH.
    pause
    exit /b
)

:: 创建虚拟环境
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

:: 激活环境并安装依赖
echo Installing dependencies...
call venv\Scripts\activate
pip install -r requirements.txt

:: 生成默认配置文件
if not exist "config.json" (
    echo { "vivado_binary_path": "C:/Xilinx/Vivado/2023.2/bin/vivado.bat" } > config.json
    echo Config file created. Please edit config.json with your actual Vivado path.
)

echo.
echo Arixa installed successfully!
echo.
echo To connect to Claude Desktop or other MCP clients, use the command:
echo %CD%\venv\Scripts\python %CD%\src\server.py
pause
