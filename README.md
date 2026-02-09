# Arixa
使用MCP协议开发的一款AI智能开发FPGA的插件
以下是你可以放入 GitHub README 的使用说明：
🚀 安装 (Installation)
1. 克隆本仓库。
2. 运行 install.bat (Windows) 或 install.sh (Linux)。
3. 打开生成的 config.json，将 vivado_binary_path 修改为你本机 Vivado 的实际路径。
🔗 连接到 AI (Configuration)
针对 Claude Desktop (推荐):
1. 下载并安装 Claude Desktop App。
2. 打开配置文件 (通常位于 %APPDATA%\Claude\claude_desktop_config.json 或 ~/Library/Application Support/Claude/claude_desktop_config.json)。
3. 添加 Arixa 服务器配置：
JSON
复制代码
{
  "mcpServers"
: {
    "arixa"
: {
      "command": "path/to/Arixa/venv/Scripts/python"
,
      "args": ["path/to/Arixa/src/server.py"
]
    }
  }
}
注意：请使用绝对路径。
🗣️ 自然语言交互示例
连接成功后，你可以直接对 AI 说：
"请在 D:/FPGA_Work 目录下创建一个名为 led_blink 的 Vivado 项目，芯片型号是 xc7z020clg400-1。"
"帮我写一个 LED 闪烁的 Verilog 模块，频率 50MHz，周期 1秒，然后把它添加到刚才的项目里。"
"现在帮我运行综合，如果不报错的话，直接生成 Bitstream。"
