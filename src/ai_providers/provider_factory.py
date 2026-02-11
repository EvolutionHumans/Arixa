#!/usr/bin/env python3
"""
AI Provider Factory - AI 提供商工厂
支持多种 AI 服务: Claude, ChatGPT, Gemini, 本地模型
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class AIProvider(ABC):
    """AI 提供商基类"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
    
    @abstractmethod
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        """发送聊天请求"""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """检查是否可用"""
        pass


class ClaudeProvider(AIProvider):
    """Claude (Anthropic) 提供商"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.model = "claude-sonnet-4-20250514"
        self.client = None
        
        if api_key:
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=api_key)
            except ImportError:
                logger.warning("anthropic 库未安装，运行: pip install anthropic")
    
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        if not self.client:
            return "错误: Claude API 客户端未初始化"
        
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system_prompt,
                messages=messages
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f"Claude API 错误: {e}")
            return f"API 错误: {e}"
    
    def is_available(self) -> bool:
        return self.client is not None


class ChatGPTProvider(AIProvider):
    """ChatGPT (OpenAI) 提供商"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.model = "gpt-4-turbo-preview"
        self.client = None
        
        if api_key:
            try:
                from openai import OpenAI
                self.client = OpenAI(api_key=api_key)
            except ImportError:
                logger.warning("openai 库未安装，运行: pip install openai")
    
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        if not self.client:
            return "错误: OpenAI API 客户端未初始化"
        
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
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"OpenAI API 错误: {e}")
            return f"API 错误: {e}"
    
    def is_available(self) -> bool:
        return self.client is not None


class GeminiProvider(AIProvider):
    """Gemini (Google) 提供商"""
    
    def __init__(self, api_key: Optional[str] = None):
        super().__init__(api_key)
        self.model = None
        
        if api_key:
            try:
                import google.generativeai as genai
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel('gemini-pro')
            except ImportError:
                logger.warning("google-generativeai 库未安装，运行: pip install google-generativeai")
    
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        if not self.model:
            return "错误: Gemini API 客户端未初始化"
        
        try:
            # 转换消息格式
            prompt = ""
            if system_prompt:
                prompt = f"System: {system_prompt}\n\n"
            
            for msg in messages:
                role = "User" if msg["role"] == "user" else "Assistant"
                prompt += f"{role}: {msg['content']}\n\n"
            
            prompt += "Assistant:"
            
            response = self.model.generate_content(prompt)
            return response.text
        except Exception as e:
            logger.error(f"Gemini API 错误: {e}")
            return f"API 错误: {e}"
    
    def is_available(self) -> bool:
        return self.model is not None


class LocalProvider(AIProvider):
    """本地模型提供商 (Ollama)"""
    
    def __init__(self, api_key: Optional[str] = None, base_url: str = "http://localhost:11434", model: str = "llama2"):
        super().__init__(api_key)
        self.base_url = base_url
        self.model = model
    
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        try:
            import requests
            
            # 构建 Ollama 请求
            full_messages = []
            if system_prompt:
                full_messages.append({"role": "system", "content": system_prompt})
            full_messages.extend(messages)
            
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": full_messages,
                    "stream": False
                },
                timeout=120
            )
            
            if response.status_code == 200:
                return response.json()["message"]["content"]
            else:
                return f"Ollama 错误: {response.status_code}"
                
        except requests.exceptions.ConnectionError:
            return "错误: 无法连接到 Ollama 服务，请确保 Ollama 正在运行"
        except Exception as e:
            logger.error(f"Ollama 错误: {e}")
            return f"错误: {e}"
    
    def is_available(self) -> bool:
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except:
            return False


class MockProvider(AIProvider):
    """模拟提供商 (用于测试)"""
    
    def chat(self, messages: List[Dict], system_prompt: str = "") -> str:
        last_message = messages[-1]["content"] if messages else ""
        
        # 简单的模式匹配响应
        if "创建" in last_message and "项目" in last_message:
            return '''```json
{
    "action": "tool_call",
    "tool": "vivado_create_project",
    "parameters": {
        "project_name": "new_project",
        "project_path": "~/fpga_projects/new_project",
        "part": "xc7a35tcsg324-1"
    }
}
```'''
        
        return '''```json
{
    "action": "reply",
    "message": "我是 Arixa 测试模式。请配置 AI 提供商以使用完整功能。"
}
```'''
    
    def is_available(self) -> bool:
        return True


class AIProviderFactory:
    """AI 提供商工厂"""
    
    _providers = {
        "claude": ClaudeProvider,
        "chatgpt": ChatGPTProvider,
        "gemini": GeminiProvider,
        "local": LocalProvider,
        "mock": MockProvider
    }
    
    @classmethod
    def create(cls, provider_name: str, api_key: Optional[str] = None, **kwargs) -> AIProvider:
        """创建 AI 提供商实例"""
        provider_class = cls._providers.get(provider_name.lower())
        
        if not provider_class:
            logger.warning(f"未知提供商 '{provider_name}'，使用模拟模式")
            return MockProvider()
        
        provider = provider_class(api_key, **kwargs) if kwargs else provider_class(api_key)
        
        if not provider.is_available():
            logger.warning(f"{provider_name} 不可用，使用模拟模式")
            return MockProvider()
        
        return provider
    
    @classmethod
    def list_providers(cls) -> List[str]:
        """列出所有支持的提供商"""
        return list(cls._providers.keys())
