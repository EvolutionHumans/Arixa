#!/usr/bin/env python3
"""
Arixa Client - 客户端核心模块
作为 AI 与本地程序之间的中介

工作流程:
1. 接收用户的自然语言输入
2. 构建系统提示词（包含可用工具列表）
3. 调用选定的 AI API
4. 解析 AI 的响应（可能包含工具调用）
5. 通过 MCP 服务器在本地执行工具
6. 将执行结果返回给 AI 继续对话
7. 输出最终结果给用户
"""

import json
import os
import sys
import asyncio
from typing import Dict, Any, List, Optional
import logging
import re

logger = logging.getLogger(__name__)


class ArixaClient:
    """
    Arixa 客户端 - AI 与本地程序的中介
    
    核心功能:
    - 连接多种 AI API
    - 将 AI 指令转换为本地操作
    - 管理对话上下文
    """
    
    def __init__(self, config, ai_provider: str = "claude", model: Optional[str] = None):
        """
        初始化客户端
        
        Args:
            config: 配置管理器
            ai_provider: AI 提供商名称
            model: 指定模型（可选）
        """
        self.config = config
        self.ai_provider_name = ai_provider
        self.model = model
        self.conversation_history: List[Dict] = []
        self.mcp_server = None
        self.ai = None
        
        # 初始化组件
        self._init_mcp_server()
        self._init_ai_provider()
        
    def _init_ai_provider(self):
        """初始化 AI 提供商"""
        from src.ai_providers.provider_factory import AIProviderFactory
        
        # 获取 API Key（优先从配置，其次从环境变量）
        api_key = self.config.get(f"ai.{self.ai_provider_name}.api_key")
        base_url = self.config.get(f"ai.{self.ai_provider_name}.base_url")
        
        # 创建 AI 提供商实例
        self.ai = AIProviderFactory.create(
            provider_name=self.ai_provider_name,
            api_key=api_key,
            model=self.model,
            base_url=base_url
        )
        
        if self.ai.is_available():
            logger.info(f"AI 提供商初始化成功: {self.ai_provider_name}")
        else:
            logger.warning(f"AI 提供商 {self.ai_provider_name} 不可用，请检查 API Key")
    
    def _init_mcp_server(self):
        """初始化本地 MCP 服务器实例"""
        from src.mcp_server.server import MCPServer
        self.mcp_server = MCPServer(self.config)
        logger.info(f"MCP 服务器初始化完成，已注册 {len(self.mcp_server.tools)} 个工具")
    
    def get_system_prompt(self) -> str:
        """
        生成系统提示词
        包含 AI 的角色定义和可用工具列表
        """
        # 获取工具列表
        tools_schema = self.mcp_server.get_tools_schema()
        
        # 按类别分组工具
        tools_by_category = {}
        for tool in tools_schema:
            category = tool['category']
            if category not in tools_by_category:
                tools_by_category[category] = []
            tools_by_category[category].append(tool)
        
        # 构建工具描述
        tools_desc = ""
        for category, tools in tools_by_category.items():
            tools_desc += f"\n### {category.upper()} 工具\n"
            for t in tools:
                params_desc = ", ".join([f"{k}: {v.get('description', '')}" for k, v in t['parameters'].items()])
                tools_desc += f"- **{t['name']}**: {t['description']}\n"
                if params_desc:
                    tools_desc += f"  参数: {params_desc}\n"
        
        # 获取已注册程序
        programs = list(self.config.get("programs", {}).keys())
        
        return f"""你是 Arixa，一个专业的 FPGA 开发智能助手。你通过 MCP 协议连接本地的 Vivado 和其他开发工具，可以帮助用户完成 FPGA 开发的全流程工作。

## 你的能力

你可以使用以下工具来帮助用户完成各种任务：
{tools_desc}

## 已配置的本地程序
{', '.join(programs) if programs else '暂无（可通过 arixa --setup 配置）'}

## 工作原则

1. **理解意图**: 准确理解用户的自然语言指令
2. **安全优先**: 执行文件删除等危险操作前，先向用户确认
3. **清晰反馈**: 提供操作的详细进度和结果
4. **错误诊断**: 遇到错误时提供详细的分析和解决建议
5. **最佳实践**: 主动提供 FPGA 开发的建议和最佳实践

## 响应格式

当需要调用工具时，使用以下 JSON 格式（放在 ```json 代码块中）：

**单个工具调用:**
```json
{{
    "action": "tool_call",
    "tool": "工具名称",
    "parameters": {{
        "参数名": "参数值"
    }}
}}
```

**多步骤任务:**
```json
{{
    "action": "multi_step",
    "steps": [
        {{"tool": "工具1", "parameters": {{}}}},
        {{"tool": "工具2", "parameters": {{}}}}
    ]
}}
```

**纯文本回复（无需工具时）:**
直接回复文本即可，不需要 JSON 格式。

## 常用工作流示例

1. **创建新项目**: vivado_create_project → 创建源文件 → vivado_add_sources → vivado_set_top
2. **完整编译**: vivado_run_synthesis → vivado_run_implementation → vivado_generate_bitstream
3. **烧录测试**: vivado_generate_bitstream → vivado_program_device

## 注意事项

- 所有文件路径支持 ~ 表示用户主目录
- Vivado 项目路径使用绝对路径更安全
- 运行综合/实现前确保已添加源文件和设置顶层模块
- 生成比特流前需要先完成综合和实现

当前默认项目路径: {self.config.get('default_project_path', '~/fpga_projects')}
"""

    def execute(self, user_input: str, max_iterations: int = 10) -> str:
        """
        执行用户命令
        
        这是核心函数：
        1. 发送用户输入给 AI
        2. 解析 AI 响应中的工具调用
        3. 执行工具并获取结果
        4. 将结果反馈给 AI
        5. 重复直到 AI 给出最终回复
        
        Args:
            user_input: 用户的自然语言输入
            max_iterations: 最大迭代次数（防止无限循环）
        
        Returns:
            最终的响应文本
        """
        logger.info(f"执行命令: {user_input}")
        
        # 添加用户消息到历史
        self.conversation_history.append({
            "role": "user",
            "content": user_input
        })
        
        final_response = ""
        iteration = 0
        
        while iteration < max_iterations:
            iteration += 1
            logger.debug(f"迭代 {iteration}")
            
            # 调用 AI
            system_prompt = self.get_system_prompt()
            tools = self.mcp_server.get_tools_for_ai()
            
            ai_response = self.ai.chat(
                messages=self.conversation_history,
                system_prompt=system_prompt,
                tools=tools
            )
            
            content = ai_response.get("content", "")
            tool_calls = ai_response.get("tool_calls", [])
            
            # 如果没有工具调用，尝试从文本中提取
            if not tool_calls and content:
                tool_calls = self._extract_tool_calls_from_text(content)
            
            # 如果有工具调用，执行它们
            if tool_calls:
                # 执行所有工具调用
                tool_results = []
                for tool_call in tool_calls:
                    tool_name = tool_call.get("name")
                    tool_args = tool_call.get("arguments", {})
                    
                    print(f"🔧 执行: {tool_name}")
                    logger.info(f"调用工具: {tool_name}, 参数: {tool_args}")
                    
                    # 通过 MCP 服务器执行
                    result = self._call_tool(tool_name, tool_args)
                    tool_results.append({
                        "tool": tool_name,
                        "result": result
                    })
                    
                    # 输出执行结果摘要
                    if isinstance(result, dict):
                        if result.get("success"):
                            print(f"   ✅ 成功")
                        else:
                            print(f"   ❌ 失败: {result.get('error', '未知错误')}")
                
                # 构建工具执行结果消息
                result_content = "工具执行结果:\n"
                for tr in tool_results:
                    result_content += f"\n[{tr['tool']}]\n"
                    result_content += json.dumps(tr['result'], ensure_ascii=False, indent=2)
                
                # 将 AI 响应和工具结果添加到历史
                self.conversation_history.append({
                    "role": "assistant",
                    "content": content if content else f"执行工具: {', '.join([tc['name'] for tc in tool_calls])}"
                })
                self.conversation_history.append({
                    "role": "user",
                    "content": result_content
                })
                
                # 继续循环，让 AI 处理工具结果
                continue
            
            # 没有工具调用，这是最终回复
            final_response = content
            
            # 添加到历史
            self.conversation_history.append({
                "role": "assistant",
                "content": final_response
            })
            
            break
        
        if iteration >= max_iterations:
            final_response += "\n\n⚠️ 达到最大执行次数限制"
        
        return final_response
    
    def _extract_tool_calls_from_text(self, text: str) -> List[Dict]:
        """
        从 AI 响应文本中提取工具调用
        支持多种格式
        """
        tool_calls = []
        
        # 查找 JSON 代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                
                if isinstance(data, dict):
                    action = data.get("action", "")
                    
                    if action == "tool_call":
                        tool_calls.append({
                            "name": data.get("tool"),
                            "arguments": data.get("parameters", {})
                        })
                    
                    elif action == "multi_step":
                        for step in data.get("steps", []):
                            tool_calls.append({
                                "name": step.get("tool"),
                                "arguments": step.get("parameters", {})
                            })
                    
                    # 直接的工具调用格式
                    elif "tool" in data and "parameters" in data:
                        tool_calls.append({
                            "name": data.get("tool"),
                            "arguments": data.get("parameters", {})
                        })
                        
            except json.JSONDecodeError:
                logger.debug(f"JSON 解析失败: {match[:100]}...")
        
        return tool_calls
    
    def _call_tool(self, tool_name: str, params: Dict) -> Dict:
        """
        调用 MCP 工具
        
        Args:
            tool_name: 工具名称
            params: 工具参数
        
        Returns:
            工具执行结果
        """
        from src.mcp_server.server import MCPRequest
        
        request = MCPRequest(
            id="local-" + str(id(params)),
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
            return {
                "success": False,
                "error": response.error.get("message", "未知错误")
            }
        
        return response.result if response.result else {"success": True}
    
    def chat_mode(self):
        """
        交互式聊天模式
        这是主要的用户交互界面
        """
        self._print_welcome()
        
        while True:
            try:
                # 获取用户输入
                user_input = input("\n你: ").strip()
                
                if not user_input:
                    continue
                
                # 处理特殊命令
                if user_input.lower() in ['exit', 'quit', 'q', '退出']:
                    print("👋 再见！")
                    break
                
                if user_input.lower() in ['clear', 'cls', '清除']:
                    self.conversation_history = []
                    print("🗑️ 对话历史已清除")
                    continue
                
                if user_input.lower() in ['help', 'h', '帮助', '?']:
                    self._show_help()
                    continue
                
                if user_input.lower() in ['tools', '工具']:
                    self._show_tools()
                    continue
                
                if user_input.lower() in ['status', '状态']:
                    self._show_status()
                    continue
                
                # 执行命令
                print("\n🔄 处理中...\n")
                result = self.execute(user_input)
                print(f"\nArixa: {result}")
                
            except KeyboardInterrupt:
                print("\n\n👋 再见！")
                break
            except Exception as e:
                logger.error(f"错误: {e}", exc_info=True)
                print(f"\n❌ 发生错误: {e}")
    
    def _print_welcome(self):
        """打印欢迎信息"""
        ai_status = "✅ 已连接" if self.ai and self.ai.is_available() else "❌ 未连接"
        
        print(f"""
╔══════════════════════════════════════════════════════════════╗
║                                                              ║
║     🤖 Arixa - AI-Powered FPGA Development Assistant        ║
║                                                              ║
╠══════════════════════════════════════════════════════════════╣
║  AI 提供商: {self.ai_provider_name:<15} {ai_status:<25}║
║  可用工具: {len(self.mcp_server.tools):<15}                              ║
╠══════════════════════════════════════════════════════════════╣
║  输入 'help' 查看帮助  |  输入 'exit' 退出                  ║
╚══════════════════════════════════════════════════════════════╝
""")
    
    def _show_help(self):
        """显示帮助信息"""
        help_text = """
📚 Arixa 帮助
═══════════════════════════════════════════════════

🎯 常用命令示例:

  项目管理:
  • "创建一个新项目，名称为 led_blink，使用 xc7a35t 芯片"
  • "打开项目 ~/fpga_projects/my_project/my_project.xpr"
  
  代码生成:
  • "帮我写一个 4 位 LED 流水灯的 Verilog 代码"
  • "创建一个 UART 发送模块，波特率 115200"
  • "为 led_blink 模块生成测试台"
  
  编译流程:
  • "运行综合"
  • "运行实现"
  • "生成比特流"
  • "烧录到 FPGA"
  
  查看信息:
  • "显示时序报告"
  • "显示资源利用率"
  
  文件操作:
  • "读取 src/top.v 的内容"
  • "列出 src 目录下的所有 Verilog 文件"

🔧 系统命令:
  • help / 帮助     - 显示此帮助
  • tools / 工具    - 列出所有可用工具
  • status / 状态   - 显示当前状态
  • clear / 清除    - 清除对话历史
  • exit / 退出     - 退出程序

📖 更多信息: https://github.com/EvolutionHumans/Arixa
"""
        print(help_text)
    
    def _show_tools(self):
        """显示可用工具"""
        tools = self.mcp_server.get_tools_schema()
        
        # 按类别分组
        by_category = {}
        for tool in tools:
            cat = tool['category']
            if cat not in by_category:
                by_category[cat] = []
            by_category[cat].append(tool)
        
        print("\n🔧 可用工具列表")
        print("═" * 50)
        
        for category, cat_tools in sorted(by_category.items()):
            print(f"\n📂 {category.upper()}")
            for t in cat_tools:
                print(f"   • {t['name']}: {t['description']}")
        
        print(f"\n总计: {len(tools)} 个工具")
    
    def _show_status(self):
        """显示当前状态"""
        print("\n📊 当前状态")
        print("═" * 50)
        print(f"AI 提供商: {self.ai_provider_name}")
        print(f"AI 状态: {'✅ 可用' if self.ai and self.ai.is_available() else '❌ 不可用'}")
        print(f"对话轮次: {len(self.conversation_history) // 2}")
        print(f"当前项目: {self.mcp_server.current_project or '无'}")
        
        # 显示已注册程序
        programs = self.config.get("programs", {})
        print(f"已注册程序: {len(programs)}")
        for name, info in programs.items():
            path = info.get("path", "") if isinstance(info, dict) else info
            exists = "✅" if os.path.exists(os.path.expanduser(path)) else "❌"
            print(f"   {exists} {name}")
