#!/usr/bin/env python3
"""
Arixa - AI-Powered FPGA Development Assistant
智能 FPGA 开发助手，通过 MCP 协议连接 AI 与本地程序

核心功能：
1. 接入多种 AI API（Claude、ChatGPT、Gemini、Ollama本地模型）
2. 将 AI 的回复解析为可执行命令
3. 通过 MCP 协议在本地执行命令
4. 所有操作在本地完成，代码不上传云端

Author: EvolutionHumans
License: MIT
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

__version__ = "1.0.0"
__author__ = "EvolutionHumans"


def main():
    """主入口函数"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Arixa - AI-Powered FPGA Development Assistant",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  arixa --setup              # 首次配置（配置AI API和Vivado路径）
  arixa --chat               # 启动交互式聊天
  arixa --run "创建一个LED闪烁项目"  # 直接执行命令
  arixa --server             # 启动 MCP 服务器
  arixa --gui                # 启动图形界面
  arixa --list-tools         # 列出所有可用工具
        """
    )
    
    parser.add_argument('--version', action='version', version=f'Arixa v{__version__}')
    parser.add_argument('--setup', action='store_true', help='首次配置向导')
    parser.add_argument('--chat', action='store_true', help='启动交互式聊天模式')
    parser.add_argument('--run', type=str, help='直接执行自然语言命令')
    parser.add_argument('--server', action='store_true', help='启动 MCP 服务器')
    parser.add_argument('--gui', action='store_true', help='启动图形界面')
    parser.add_argument('--list-tools', action='store_true', help='列出所有可用工具')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    parser.add_argument('--ai', type=str, choices=['claude', 'chatgpt', 'gemini', 'ollama', 'deepseek'], 
                        default='claude', help='选择 AI 提供商')
    parser.add_argument('--model', type=str, help='指定模型名称')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 设置日志
    from src.utils.logger import setup_logger
    logger = setup_logger(debug=args.debug)
    logger.info(f"Arixa v{__version__} 启动中...")
    
    # 加载配置
    from src.utils.config_manager import ConfigManager
    config_path = args.config or os.path.expanduser("~/.arixa/config.json")
    config = ConfigManager(config_path)
    
    # 首次配置
    if args.setup:
        from src.client.setup_wizard import SetupWizard
        wizard = SetupWizard(config)
        wizard.run()
        return
    
    # 列出工具
    if args.list_tools:
        from src.mcp_server.server import MCPServer
        server = MCPServer(config)
        tools = server.get_tools_schema()
        print("\n📋 可用工具列表:\n" + "="*50)
        for tool in tools:
            print(f"\n🔧 {tool['name']}")
            print(f"   描述: {tool['description']}")
            print(f"   分类: {tool['category']}")
        return
    
    # 检查是否已配置
    if not config.is_configured() and not args.server:
        print("⚠️  Arixa 尚未配置，请先运行: arixa --setup")
        print("   或设置环境变量: ANTHROPIC_API_KEY / OPENAI_API_KEY / GOOGLE_API_KEY")
        return
    
    # 创建客户端
    from src.client.arixa_client import ArixaClient
    
    # 确定使用的 AI 提供商
    ai_provider = args.ai or config.get("ai.default_provider", "claude")
    model = args.model
    
    client = ArixaClient(config, ai_provider=ai_provider, model=model)
    
    if args.server:
        # 启动 MCP 服务器
        from src.mcp_server.server import MCPServer
        server = MCPServer(config)
        server.start()
    elif args.gui:
        # 启动图形界面
        from src.client.gui import ArixaGUI
        gui = ArixaGUI(client)
        gui.run()
    elif args.run:
        # 直接执行命令
        result = client.execute(args.run)
        print(result)
    else:
        # 默认启动交互式聊天
        client.chat_mode()


if __name__ == "__main__":
    main()
