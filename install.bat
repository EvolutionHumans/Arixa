@echo off
chcp 65001 >nul
setlocal EnableDelayedExpansion

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                                                          ║
echo ║       Arixa - AI-Powered FPGA Development Assistant      ║
echo ║                    一键安装程序                          ║
echo ║                                                          ║
echo ╚══════════════════════════════════════════════════════════╝
echo.

:: 检查 Python
echo [1/5] 检查 Python 环境...
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ Python 未安装！
    echo 请从 https://www.python.org/downloads/ 下载并安装 Python 3.8+
    echo 安装时请勾选 "Add Python to PATH"
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%a in ('python --version 2^>^&1') do set PYTHON_VERSION=%%a
echo ✅ 检测到 Python %PYTHON_VERSION%

:: 检查 pip
echo.
echo [2/5] 检查 pip...
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo ❌ pip 未安装，正在安装...
    python -m ensurepip --upgrade
)
echo ✅ pip 可用

:: 创建虚拟环境
echo.
echo [3/5] 创建虚拟环境...
set VENV_PATH=%USERPROFILE%\.arixa\venv

if exist "%VENV_PATH%" (
    echo 虚拟环境已存在，跳过创建
) else (
    python -m venv "%VENV_PATH%"
    if errorlevel 1 (
        echo ❌ 创建虚拟环境失败
        pause
        exit /b 1
    )
)
echo ✅ 虚拟环境就绪

:: 激活虚拟环境并安装依赖
echo.
echo [4/5] 安装依赖...
call "%VENV_PATH%\Scripts\activate.bat"

pip install --upgrade pip >nul 2>&1
pip install anthropic openai google-generativeai requests >nul 2>&1

if errorlevel 1 (
    echo ⚠️ 部分依赖安装失败，但核心功能仍可使用
) else (
    echo ✅ 依赖安装完成
)

:: 复制文件到安装目录
echo.
echo [5/5] 安装 Arixa...
set INSTALL_PATH=%USERPROFILE%\.arixa

if not exist "%INSTALL_PATH%\src" mkdir "%INSTALL_PATH%\src"

:: 复制源文件
xcopy /E /Y /Q "%~dp0src" "%INSTALL_PATH%\src\" >nul 2>&1
copy /Y "%~dp0arixa.py" "%INSTALL_PATH%\" >nul 2>&1
copy /Y "%~dp0requirements.txt" "%INSTALL_PATH%\" >nul 2>&1

:: 创建启动脚本
echo @echo off > "%INSTALL_PATH%\arixa.bat"
echo call "%VENV_PATH%\Scripts\activate.bat" >> "%INSTALL_PATH%\arixa.bat"
echo python "%INSTALL_PATH%\arixa.py" %%* >> "%INSTALL_PATH%\arixa.bat"

:: 添加到 PATH（用户级别）
echo.
echo 是否将 Arixa 添加到系统 PATH？（推荐）
set /p ADD_PATH="添加到 PATH? [Y/n]: "
if /i not "%ADD_PATH%"=="n" (
    setx PATH "%PATH%;%INSTALL_PATH%" >nul 2>&1
    echo ✅ 已添加到 PATH
)

echo.
echo ╔══════════════════════════════════════════════════════════╗
echo ║                    ✅ 安装完成！                         ║
echo ╚══════════════════════════════════════════════════════════╝
echo.
echo 使用方法:
echo   1. 打开新的命令提示符窗口
echo   2. 运行 arixa --setup 进行首次配置
echo   3. 运行 arixa --chat 开始使用
echo.
echo 或者直接运行: "%INSTALL_PATH%\arixa.bat"
echo.

:: 询问是否立即配置
set /p SETUP_NOW="是否立即进行首次配置? [Y/n]: "
if /i not "%SETUP_NOW%"=="n" (
    call "%INSTALL_PATH%\arixa.bat" --setup
)

pause
