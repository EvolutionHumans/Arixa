#!/usr/bin/env python3
"""
Arixa - AI-Powered FPGA Development Assistant
智能 FPGA 开发助手，通过 MCP 协议连接 AI 与 Vivado

Author: EvolutionHumans
License: MIT
"""

import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.client.arixa_client import ArixaClient
from src.utils.config_manager import ConfigManager
from src.utils.logger import setup_logger

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
  arixa --setup              # 首次配置
  arixa --chat               # 启动交互式聊天
  arixa --run "创建一个LED闪烁项目"  # 直接执行命令
  arixa --server             # 启动 MCP 服务器
  arixa --gui                # 启动图形界面
        """
    )
    
    parser.add_argument('--version', action='version', version=f'Arixa v{__version__}')
    parser.add_argument('--setup', action='store_true', help='首次配置向导')
    parser.add_argument('--chat', action='store_true', help='启动交互式聊天模式')
    parser.add_argument('--run', type=str, help='直接执行自然语言命令')
    parser.add_argument('--server', action='store_true', help='启动 MCP 服务器')
    parser.add_argument('--gui', action='store_true', help='启动图形界面')
    parser.add_argument('--config', type=str, help='指定配置文件路径')
    parser.add_argument('--ai', type=str, choices=['claude', 'chatgpt', 'gemini', 'local'], 
                        default='claude', help='选择 AI 提供商')
    parser.add_argument('--debug', action='store_true', help='启用调试模式')
    
    args = parser.parse_args()
    
    # 设置日志
    logger = setup_logger(debug=args.debug)
    logger.info(f"Arixa v{__version__} 启动中...")
    
    # 加载配置
    config_path = args.config or os.path.expanduser("~/.arixa/config.json")
    config = ConfigManager(config_path)
    
    # 首次配置
    if args.setup:
        from src.client.setup_wizard import SetupWizard
        wizard = SetupWizard(config)
        wizard.run()
        return
    
    # 检查是否已配置
    if not config.is_configured():
        print("⚠️  Arixa 尚未配置，请先运行: arixa --setup")
        return
    
    # 创建客户端
    client = ArixaClient(config, ai_provider=args.ai)
    
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
