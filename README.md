# 🚀 Arixa - AI-Powered FPGA Development Assistant

<p align="center">
  <img src="docs/logo.png" alt="Arixa Logo" width="200">
</p>

<p align="center">
  <strong>智能 FPGA 开发助手，让 AI 驱动你的硬件开发</strong>
</p>

<p align="center">
  <a href="#功能特性">功能特性</a> •
  <a href="#快速开始">快速开始</a> •
  <a href="#使用示例">使用示例</a> •
  <a href="#配置说明">配置说明</a> •
  <a href="#开发文档">开发文档</a>
</p>

---

## ✨ 功能特性

### 🤖 多 AI 支持
- **Claude** (Anthropic) - 推荐
- **ChatGPT** (OpenAI)
- **Gemini** (Google)
- **本地模型** (Ollama)

### 🔧 FPGA 开发全流程
- 📁 项目管理（创建、打开、配置）
- 📝 代码生成（Verilog/VHDL）
- 🔬 综合与实现
- 📊 时序分析
- 🎯 仿真测试
- 💾 比特流生成与烧录

### 🛡️ 安全与隐私
- ✅ 所有操作在本地执行
- ✅ 代码不上传云端
- ✅ API 密钥本地加密存储

### 🖥️ 多平台支持
- Windows 10/11
- Linux (Ubuntu, Fedora, etc.)
- macOS

---

## 📦 快速开始

### 一键安装

**Windows:**
```batch
# 下载项目后，双击运行
install.bat
```

**Linux/macOS:**
```bash
# 下载项目后
chmod +x install.sh
./install.sh
```

### 手动安装

```bash
# 1. 克隆仓库
git clone https://github.com/EvolutionHumans/Arixa.git
cd Arixa

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/macOS
# 或 venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 首次配置
python arixa.py --setup

# 5. 开始使用
python arixa.py --chat
```

---

## 🎮 使用示例

### 命令行模式

```bash
# 交互式聊天
arixa --chat

# 直接执行命令
arixa --run "创建一个 LED 闪烁项目，使用 xc7a35t 芯片"

# 使用指定 AI
arixa --chat --ai chatgpt

# 启动图形界面
arixa --gui

# 启动 MCP 服务器
arixa --server
```

### 自然语言命令示例

```
你: 创建一个新项目，名称为 led_blink，使用 xc7a35t 芯片
Arixa: ✅ 项目创建成功！路径: ~/fpga_projects/led_blink

你: 帮我写一个 4 位 LED 流水灯的 Verilog 代码
Arixa: 好的，我来为你编写...
       [生成代码并自动添加到项目]

你: 运行综合
Arixa: 🔄 正在运行综合...
       ✅ 综合完成，无错误

你: 显示资源利用率报告
Arixa: 📊 资源利用率:
       - LUT: 45/20800 (0.22%)
       - FF: 36/41600 (0.09%)
       ...

你: 生成比特流并烧录
Arixa: 🔄 生成比特流...
       ✅ 比特流生成完成
       🔄 检测到设备，开始烧录...
       ✅ 烧录成功！
```

---

## ⚙️ 配置说明

### 配置文件位置

```
~/.arixa/
├── config.json     # 主配置文件
├── logs/           # 日志目录
└── temp/           # 临时文件
```

### 配置 AI 提供商

**方式 1: 环境变量（推荐）**
```bash
export ANTHROPIC_API_KEY="your-api-key"  # Claude
export OPENAI_API_KEY="your-api-key"     # ChatGPT
export GOOGLE_API_KEY="your-api-key"     # Gemini
```

**方式 2: 配置向导**
```bash
arixa --setup
```

**方式 3: 直接编辑 config.json**
```json
{
  "ai": {
    "default_provider": "claude",
    "claude": {
      "api_key": "your-api-key"
    }
  }
}
```

### 配置 Vivado 路径

```json
{
  "programs": {
    "vivado": {
      "path": "C:\\Xilinx\\Vivado\\2023.2\\bin\\vivado.bat"
    }
  }
}
```

### 注册其他程序

你可以注册任何本地程序供 AI 调用：

```json
{
  "programs": {
    "vscode": {
      "path": "C:\\Program Files\\VS Code\\Code.exe"
    },
    "gtkwave": {
      "path": "/usr/bin/gtkwave"
    }
  }
}
```

---

## 🔌 MCP 协议

Arixa 使用 Model Context Protocol (MCP) 连接 AI 与本地工具。

### 可用工具列表

| 工具名称 | 描述 |
|---------|------|
| `vivado_create_project` | 创建 Vivado 项目 |
| `vivado_open_project` | 打开项目 |
| `vivado_add_source` | 添加源文件 |
| `vivado_run_synthesis` | 运行综合 |
| `vivado_run_implementation` | 运行实现 |
| `vivado_generate_bitstream` | 生成比特流 |
| `vivado_program_device` | 烧录设备 |
| `vivado_run_simulation` | 运行仿真 |
| `vivado_get_reports` | 获取报告 |
| `file_create` | 创建文件 |
| `file_read` | 读取文件 |
| `file_modify` | 修改文件 |
| `run_program` | 运行已注册的程序 |
| `run_command` | 运行系统命令 |

### 启动 MCP 服务器

```bash
arixa --server
# 服务器默认运行在 localhost:8765
```

---

## 📁 项目结构

```
Arixa/
├── arixa.py              # 主入口
├── install.bat           # Windows 安装脚本
├── install.sh            # Linux/macOS 安装脚本
├── requirements.txt      # Python 依赖
├── README.md
├── src/
│   ├── mcp_server/       # MCP 服务器
│   │   └── server.py
│   ├── client/           # 客户端
│   │   ├── arixa_client.py
│   │   ├── setup_wizard.py
│   │   └── gui.py
│   ├── ai_providers/     # AI 提供商
│   │   └── provider_factory.py
│   └── utils/            # 工具
│       ├── config_manager.py
│       └── logger.py
├── config/               # 配置示例
└── docs/                 # 文档
```

---

## 🛠️ 开发

### 添加新的 AI 提供商

1. 在 `src/ai_providers/provider_factory.py` 中创建新类
2. 继承 `AIProvider` 基类
3. 实现 `chat()` 和 `is_available()` 方法
4. 在 `AIProviderFactory._providers` 中注册

### 添加新的 MCP 工具

1. 在 `src/mcp_server/server.py` 中定义工具
2. 使用 `MCPTool` 数据类
3. 实现处理函数
4. 调用 `register_tool()` 注册

---

## 📝 更新日志

### v1.0.0 (2024-xx-xx)
- 🎉 首次发布
- 支持 Claude, ChatGPT, Gemini, 本地模型
- Vivado 全流程支持
- 一键安装
- 图形界面

---

## 📄 许可证

MIT License

---

## 🤝 贡献

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'Add AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 提交 Pull Request

---

## 📧 联系

- GitHub: [@EvolutionHumans](https://github.com/EvolutionHumans)
- 项目链接: [https://github.com/EvolutionHumans/Arixa](https://github.com/EvolutionHumans/Arixa)

---

<p align="center">
  Made with ❤️ by EvolutionHumans
</p>
