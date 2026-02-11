#!/usr/bin/env python3
"""
Arixa Client - 客户端核心模块
处理用户交互和 AI 通信
"""

import json
import os
import sys
from typing import Dict, Any, List, Optional
import logging

logger = logging.getLogger(__name__)


class ArixaClient:
    """Arixa 客户端 - 处理用户交互和 AI 通信"""
    
    def __init__(self, config, ai_provider: str = "claude"):
        self.config = config
        self.ai_provider = ai_provider
        self.conversation_history = []
        self.mcp_server = None
        
        # 初始化 AI 提供商
        self._init_ai_provider()
        
        # 初始化本地 MCP 服务器
        self._init_mcp_server()
        
    def _init_ai_provider(self):
        """初始化 AI 提供商"""
        from src.ai_providers.provider_factory import AIProviderFactory
        
        api_key = self.config.get(f"ai.{self.ai_provider}.api_key")
        self.ai = AIProviderFactory.create(self.ai_provider, api_key)
        
        logger.info(f"AI 提供商初始化: {self.ai_provider}")
    
    def _init_mcp_server(self):
        """初始化本地 MCP 服务器实例（不启动网络服务）"""
        from src.mcp_server.server import MCPServer
        self.mcp_server = MCPServer(self.config)
        logger.info("MCP 服务器实例已创建")
    
    def get_system_prompt(self) -> str:
        """获取系统提示词"""
        tools_schema = self.mcp_server.get_tools_schema()
        tools_desc = "\n".join([
            f"- {t['name']}: {t['description']}" for t in tools_schema
        ])
        
        return f"""你是 Arixa，一个专业的 FPGA 开发智能助手。你可以帮助用户完成 Vivado 项目开发的全流程工作。

## 你的能力
你可以使用以下工具来帮助用户：

{tools_desc}

## 工作原则
1. 理解用户的自然语言指令，转换为具体的操作
2. 在执行危险操作前，向用户确认
3. 提供清晰的操作反馈和进度信息
4. 遇到错误时，提供详细的诊断和解决建议
5. 主动提供 FPGA 开发的最佳实践建议

## 响应格式
当需要调用工具时，使用以下 JSON 格式：
```json
{{
    "action": "tool_call",
    "tool": "工具名称",
    "parameters": {{
        "参数名": "参数值"
    }}
}}
```

当只需要回复文本时：
```json
{{
    "action": "reply",
    "message": "你的回复内容"
}}
```

当需要执行多个步骤时：
```json
{{
    "action": "multi_step",
    "steps": [
        {{"tool": "工具1", "parameters": {{}}}},
        {{"tool": "工具2", "parameters": {{}}}}
    ]
}}
```

## 用户配置信息
- 已配置的程序: {list(self.config.get('programs', {}).keys())}
- 默认项目路径: {self.config.get('default_project_path', '未设置')}
"""

    def execute(self, user_input: str) -> str:
        """执行用户命令"""
        logger.info(f"执行命令: {user_input}")
        
        # 添加到对话历史
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        # 调用 AI
        system_prompt = self.get_system_prompt()
        ai_response = self.ai.chat(
            messages=self.conversation_history,
            system_prompt=system_prompt
        )
        
        # 解析 AI 响应
        result = self._process_ai_response(ai_response)
        
        # 添加到对话历史
        self.conversation_history.append({
            "role": "assistant",
            "content": result
        })
        
        return result
    
    def _process_ai_response(self, response: str) -> str:
        """处理 AI 响应"""
        # 尝试解析 JSON 响应
        try:
            # 提取 JSON 块
            import re
            json_match = re.search(r'```json\s*(.*?)\s*```', response, re.DOTALL)
            
            if json_match:
                action_data = json.loads(json_match.group(1))
            else:
                # 尝试直接解析
                action_data = json.loads(response)
            
            return self._execute_action(action_data)
            
        except json.JSONDecodeError:
            # 如果不是 JSON，直接返回文本
            return response
    
    def _execute_action(self, action_data: Dict) -> str:
        """执行 AI 指定的动作"""
        action = action_data.get("action", "reply")
        
        if action == "reply":
            return action_data.get("message", "")
        
        elif action == "tool_call":
            tool_name = action_data.get("tool")
            params = action_data.get("parameters", {})
            return self._call_tool(tool_name, params)
        
        elif action == "multi_step":
            steps = action_data.get("steps", [])
            results = []
            
            for i, step in enumerate(steps):
                print(f"📌 执行步骤 {i+1}/{len(steps)}: {step.get('tool')}")
                result = self._call_tool(step.get("tool"), step.get("parameters", {}))
                results.append(f"步骤 {i+1}: {result}")
                
                # 如果某步骤失败，停止执行
                if "失败" in result or "错误" in result:
                    results.append("⚠️ 执行中断，后续步骤已取消")
                    break
            
            return "\n".join(results)
        
        else:
            return f"未知动作类型: {action}"
    
    def _call_tool(self, tool_name: str, params: Dict) -> str:
        """调用 MCP 工具"""
        import asyncio
        from src.mcp_server.server import MCPRequest
        
        logger.info(f"调用工具: {tool_name} 参数: {params}")
        
        request = MCPRequest(
            id="local",
            method="tools/call",
            params={"name": tool_name, "arguments": params}
        )
        
        # 同步调用异步方法
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            response = loop.run_until_complete(self.mcp_server.handle_request(request))
        finally:
            loop.close()
        
        if response.error:
            return f"❌ 工具执行失败: {response.error.get('message', '未知错误')}"
        
        result = response.result
        if isinstance(result, dict):
            if result.get("success"):
                return f"✅ 执行成功\n{json.dumps(result, ensure_ascii=False, indent=2)}"
            else:
                return f"❌ 执行失败: {result.get('error', '未知错误')}"
        
        return str(result)
    
    def chat_mode(self):
        """交互式聊天模式"""
        print("\n" + "="*60)
        print("🤖 Arixa - AI-Powered FPGA Development Assistant")
        print("="*60)
        print(f"AI 提供商: {self.ai_provider}")
        print("输入 'exit' 或 'quit' 退出")
        print("输入 'clear' 清除对话历史")
        print("输入 'help' 查看帮助")
        print("="*60 + "\n")
        
        while True:
            try:
                user_input = input("你: ").strip()
                
                if not user_input:
                    continue
                
                if user_input.lower() in ['exit', 'quit', 'q']:
                    print("👋 再见！")
                    break
                
                if user_input.lower() == 'clear':
                    self.conversation_history = []
                    print("🗑️ 对话历史已清除")
                    continue
                
                if user_input.lower() == 'help':
                    self._show_help()
                    continue
                
                # 执行命令
                print("\n🔄 处理中...\n")
                result = self.execute(user_input)
                print(f"Arixa: {result}\n")
                
            except KeyboardInterrupt:
                print("\n👋 再见！")
                break
            except Exception as e:
                logger.error(f"错误: {e}")
                print(f"❌ 发生错误: {e}\n")
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
📚 Arixa 帮助

常用命令示例:
  - "创建一个新项目，名称为 led_blink，使用 xc7a35t 芯片"
  - "打开项目 /path/to/project.xpr"
  - "添加 Verilog 源文件 top.v"
  - "运行综合"
  - "运行实现"
  - "生成比特流"
  - "烧录到 FPGA"
  - "显示时序报告"
  - "创建一个 LED 流水灯的 Verilog 代码"
  - "帮我写一个 UART 发送模块"

系统命令:
  - exit/quit: 退出程序
  - clear: 清除对话历史
  - help: 显示此帮助

更多信息请访问: https://github.com/EvolutionHumans/Arixa
"""
        print(help_text)
