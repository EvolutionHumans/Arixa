#!/usr/bin/env python3
"""
AI Provider Factory - AI 提供商工厂
支持多种 AI 服务的统一接口

支持的 AI 提供商:
- Claude (Anthropic)
- ChatGPT (OpenAI)
- Gemini (Google)
- Ollama (本地模型)
- DeepSeek
- 自定义 OpenAI 兼容接口

工作原理:
1. 用户输入自然语言
2. 发送给选定的 AI API
3. AI 返回包含工具调用的响应
4. 解析响应并在本地执行
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any
import json
import os
import logging

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """AI 提供商基类"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
    
    @abstractmethod
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        """
        发送聊天请求
        
        Args:
            messages: 对话历史 [{"role": "user/assistant", "content": "..."}]
            system_prompt: 系统提示词
            tools: 可用工具列表（用于 function calling）
        
        Returns:
            {
                "content": "AI的文本回复",
                "tool_calls": [{"name": "工具名", "arguments": {...}}],  # 可选
                "raw_response": ...  # 原始响应
            }
        """
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass
    
    def get_name(self) -> str:
        """获取提供商名称"""
        return self.__class__.__name__.replace("Provider", "")


class ClaudeProvider(AIProvider):
    """Claude (Anthropic) 提供商"""
    
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL)
        self.client = None
        
        # 尝试从环境变量获取 API Key
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        if self.api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
                logger.info(f"Claude 客户端初始化成功，模型: {self.model}")
            except ImportError:
                logger.warning("anthropic 库未安装，运行: pip install anthropic")
            except Exception as e:
                logger.error(f"Claude 客户端初始化失败: {e}")
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        if not self.client:
            return {"content": "错误: Claude API 客户端未初始化，请检查 API Key", "tool_calls": []}
        
        try:
            # 构建请求参数
            params = {
                "model": self.model,
                "max_tokens": 4096,
                "messages": messages
            }
            
            if system_prompt:
                params["system"] = system_prompt
            
            # 添加工具定义（如果有）
            if tools:
                params["tools"] = self._convert_tools_to_claude_format(tools)
            
            response = self.client.messages.create(**params)
            
            # 解析响应
            result = {"content": "", "tool_calls": [], "raw_response": response}
            
            for block in response.content:
                if block.type == "text":
                    result["content"] += block.text
                elif block.type == "tool_use":
                    result["tool_calls"].append({
                        "name": block.name,
                        "arguments": block.input
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"Claude API 错误: {e}")
            return {"content": f"API 错误: {e}", "tool_calls": []}
    
    def _convert_tools_to_claude_format(self, tools: List[Dict]) -> List[Dict]:
        """转换工具格式为 Claude 格式"""
        claude_tools = []
        for tool in tools:
            claude_tools.append({
                "name": tool["name"],
                "description": tool["description"],
                "input_schema": {
                    "type": "object",
                    "properties": tool.get("parameters", {}),
                    "required": [k for k, v in tool.get("parameters", {}).items() if v.get("required")]
                }
            })
        return claude_tools
    
    def is_available(self) -> bool:
        return self.client is not None


class ChatGPTProvider(AIProvider):
    """ChatGPT (OpenAI) 提供商"""
    
    DEFAULT_MODEL = "gpt-4-turbo-preview"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, base_url)
        self.client = None
        
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        
        if self.api_key:
            try:
                from openai import OpenAI
                client_kwargs = {"api_key": self.api_key}
                if base_url:
                    client_kwargs["base_url"] = base_url
                self.client = OpenAI(**client_kwargs)
                logger.info(f"OpenAI 客户端初始化成功，模型: {self.model}")
            except ImportError:
                logger.warning("openai 库未安装，运行: pip install openai")
            except Exception as e:
                logger.error(f"OpenAI 客户端初始化失败: {e}")
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        if not self.client:
            return {"content": "错误: OpenAI API 客户端未初始化，请检查 API Key", "tool_calls": []}
        
        try:
            # 构建消息列表
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            
            # 构建请求参数
            params = {
                "model": self.model,
                "messages": full_messages,
                "max_tokens": 4096
            }
            
            # 添加工具定义
            if tools:
                params["tools"] = self._convert_tools_to_openai_format(tools)
                params["tool_choice"] = "auto"
            
            response = self.client.chat.completions.create(**params)
            
            # 解析响应
            result = {"content": "", "tool_calls": [], "raw_response": response}
            
            message = response.choices[0].message
            result["content"] = message.content or ""
            
            if message.tool_calls:
                for tool_call in message.tool_calls:
                    result["tool_calls"].append({
                        "name": tool_call.function.name,
                        "arguments": json.loads(tool_call.function.arguments)
                    })
            
            return result
            
        except Exception as e:
            logger.error(f"OpenAI API 错误: {e}")
            return {"content": f"API 错误: {e}", "tool_calls": []}
    
    def _convert_tools_to_openai_format(self, tools: List[Dict]) -> List[Dict]:
        """转换工具格式为 OpenAI 格式"""
        openai_tools = []
        for tool in tools:
            openai_tools.append({
                "type": "function",
                "function": {
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": {
                        "type": "object",
                        "properties": tool.get("parameters", {}),
                        "required": [k for k, v in tool.get("parameters", {}).items() if v.get("required")]
                    }
                }
            })
        return openai_tools
    
    def is_available(self) -> bool:
        return self.client is not None


class GeminiProvider(AIProvider):
    """Gemini (Google) 提供商"""
    
    DEFAULT_MODEL = "gemini-pro"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL)
        self.genai = None
        self.gen_model = None
        
        self.api_key = api_key or os.environ.get("GOOGLE_API_KEY")
        
        if self.api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self.genai = genai
                self.gen_model = genai.GenerativeModel(self.model)
                logger.info(f"Gemini 客户端初始化成功，模型: {self.model}")
            except ImportError:
                logger.warning("google-generativeai 库未安装，运行: pip install google-generativeai")
            except Exception as e:
                logger.error(f"Gemini 客户端初始化失败: {e}")
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        if not self.gen_model:
            return {"content": "错误: Gemini API 客户端未初始化，请检查 API Key", "tool_calls": []}
        
        try:
            # 转换消息格式为 Gemini 格式
            gemini_messages = []
            for msg in messages:
                role = "user" if msg["role"] == "user" else "model"
                gemini_messages.append({
                    "role": role,
                    "parts": [msg["content"]]
                })
            
            # 如果有系统提示，添加到第一条用户消息
            if system_prompt and gemini_messages:
                gemini_messages[0]["parts"].insert(0, f"[系统指令]: {system_prompt}\n\n")
            
            chat = self.gen_model.start_chat(history=gemini_messages[:-1] if len(gemini_messages) > 1 else [])
            response = chat.send_message(gemini_messages[-1]["parts"][0] if gemini_messages else "")
            
            # 解析响应
            result = {"content": response.text, "tool_calls": [], "raw_response": response}
            
            # 尝试从响应中提取工具调用（Gemini 的 function calling）
            result["tool_calls"] = self._extract_tool_calls(response.text)
            
            return result
            
        except Exception as e:
            logger.error(f"Gemini API 错误: {e}")
            return {"content": f"API 错误: {e}", "tool_calls": []}
    
    def _extract_tool_calls(self, text: str) -> List[Dict]:
        """从文本中提取工具调用（解析 JSON 块）"""
        import re
        tool_calls = []
        
        # 查找 JSON 代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and "action" in data:
                    if data["action"] == "tool_call":
                        tool_calls.append({
                            "name": data.get("tool"),
                            "arguments": data.get("parameters", {})
                        })
                    elif data["action"] == "multi_step":
                        for step in data.get("steps", []):
                            tool_calls.append({
                                "name": step.get("tool"),
                                "arguments": step.get("parameters", {})
                            })
            except json.JSONDecodeError:
                pass
        
        return tool_calls
    
    def is_available(self) -> bool:
        return self.gen_model is not None


class OllamaProvider(AIProvider):
    """Ollama 本地模型提供商"""
    
    DEFAULT_MODEL = "llama3"
    DEFAULT_URL = "http://localhost:11434"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, 
                 base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, base_url or self.DEFAULT_URL)
        self._available = None
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        try:
            import requests
            
            # 构建消息
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            
            # 发送请求
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.7,
                        "num_predict": 4096
                    }
                },
                timeout=120
            )
            
            if response.status_code == 200:
                data = response.json()
                content = data.get("message", {}).get("content", "")
                
                result = {"content": content, "tool_calls": [], "raw_response": data}
                
                # 尝试提取工具调用
                result["tool_calls"] = self._extract_tool_calls(content)
                
                return result
            else:
                return {"content": f"Ollama 错误: HTTP {response.status_code}", "tool_calls": []}
                
        except requests.exceptions.ConnectionError:
            return {"content": "错误: 无法连接到 Ollama 服务，请确保 Ollama 正在运行\n运行: ollama serve", "tool_calls": []}
        except Exception as e:
            logger.error(f"Ollama 错误: {e}")
            return {"content": f"错误: {e}", "tool_calls": []}
    
    def _extract_tool_calls(self, text: str) -> List[Dict]:
        """从文本中提取工具调用"""
        import re
        tool_calls = []
        
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    if data.get("action") == "tool_call":
                        tool_calls.append({
                            "name": data.get("tool"),
                            "arguments": data.get("parameters", {})
                        })
                    elif data.get("action") == "multi_step":
                        for step in data.get("steps", []):
                            tool_calls.append({
                                "name": step.get("tool"),
                                "arguments": step.get("parameters", {})
                            })
            except json.JSONDecodeError:
                pass
        
        return tool_calls
    
    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            self._available = response.status_code == 200
        except:
            self._available = False
        
        return self._available


class DeepSeekProvider(AIProvider):
    """DeepSeek 提供商（兼容 OpenAI 接口）"""
    
    DEFAULT_MODEL = "deepseek-chat"
    DEFAULT_URL = "https://api.deepseek.com"
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None, 
                 base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or self.DEFAULT_MODEL, base_url or self.DEFAULT_URL)
        self.client = None
        
        self.api_key = api_key or os.environ.get("DEEPSEEK_API_KEY")
        
        if self.api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"DeepSeek 客户端初始化成功，模型: {self.model}")
            except ImportError:
                logger.warning("openai 库未安装，运行: pip install openai")
            except Exception as e:
                logger.error(f"DeepSeek 客户端初始化失败: {e}")
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        if not self.client:
            return {"content": "错误: DeepSeek API 客户端未初始化，请检查 API Key", "tool_calls": []}
        
        try:
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=4096
            )
            
            content = response.choices[0].message.content or ""
            result = {"content": content, "tool_calls": [], "raw_response": response}
            
            # 提取工具调用
            result["tool_calls"] = self._extract_tool_calls(content)
            
            return result
            
        except Exception as e:
            logger.error(f"DeepSeek API 错误: {e}")
            return {"content": f"API 错误: {e}", "tool_calls": []}
    
    def _extract_tool_calls(self, text: str) -> List[Dict]:
        """从文本中提取工具调用"""
        import re
        tool_calls = []
        
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict) and data.get("action") == "tool_call":
                    tool_calls.append({
                        "name": data.get("tool"),
                        "arguments": data.get("parameters", {})
                    })
            except json.JSONDecodeError:
                pass
        
        return tool_calls
    
    def is_available(self) -> bool:
        return self.client is not None


class CustomOpenAIProvider(AIProvider):
    """自定义 OpenAI 兼容接口提供商"""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None,
                 base_url: Optional[str] = None, **kwargs):
        super().__init__(api_key, model or "gpt-3.5-turbo", base_url)
        self.client = None
        
        if self.api_key and self.base_url:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
                logger.info(f"自定义 OpenAI 客户端初始化成功: {self.base_url}")
            except Exception as e:
                logger.error(f"自定义 OpenAI 客户端初始化失败: {e}")
    
    def chat(self, messages: List[Dict], system_prompt: str = "", tools: List[Dict] = None) -> Dict:
        if not self.client:
            return {"content": "错误: 自定义 API 客户端未初始化", "tool_calls": []}
        
        try:
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            
            response = self.client.chat.completions.create(
                model=self.model,
                messages=full_messages,
                max_tokens=4096
            )
            
            content = response.choices[0].message.content or ""
            return {"content": content, "tool_calls": [], "raw_response": response}
            
        except Exception as e:
            return {"content": f"API 错误: {e}", "tool_calls": []}
    
    def is_available(self) -> bool:
        return self.client is not None


# ==================== 工厂类 ====================

class AIProviderFactory:
    """AI 提供商工厂"""
    
    _providers = {
        "claude": ClaudeProvider,
        "chatgpt": ChatGPTProvider,
        "openai": ChatGPTProvider,
        "gemini": GeminiProvider,
        "google": GeminiProvider,
        "ollama": OllamaProvider,
        "local": OllamaProvider,
        "deepseek": DeepSeekProvider,
        "custom": CustomOpenAIProvider
    }
    
    @classmethod
    def create(cls, provider_name: str, api_key: Optional[str] = None, 
               model: Optional[str] = None, **kwargs) -> AIProvider:
        """
        创建 AI 提供商实例
        
        Args:
            provider_name: 提供商名称 (claude/chatgpt/gemini/ollama/deepseek/custom)
            api_key: API 密钥
            model: 模型名称
            **kwargs: 其他参数（如 base_url）
        
        Returns:
            AIProvider 实例
        """
        provider_name = provider_name.lower()
        provider_class = cls._providers.get(provider_name)
        
        if not provider_class:
            logger.warning(f"未知提供商 '{provider_name}'，可用: {list(cls._providers.keys())}")
            # 默认使用 Ollama
            provider_class = OllamaProvider
        
        provider = provider_class(api_key=api_key, model=model, **kwargs)
        
        if not provider.is_available():
            logger.warning(f"{provider_name} 不可用，请检查配置")
        
        return provider
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有支持的提供商"""
        return list(set(cls._providers.keys()))
    
    @classmethod
    def register_provider(cls, name: str, provider_class: type):
        """注册自定义提供商"""
        cls._providers[name.lower()] = provider_class
