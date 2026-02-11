#!/usr/bin/env python3
"""
Command Executor - 命令执行器
AI 中介的核心模块：将 AI 的指令转换为本地命令执行

工作流程:
1. 接收 AI 返回的结构化指令（JSON 格式）
2. 解析指令类型和参数
3. 在本地控制台执行相应命令
4. 捕获输出并返回结果

支持的执行方式:
- 直接执行系统命令
- 调用已注册的本地程序
- 执行 Vivado TCL 脚本
- 文件操作
"""

import subprocess
import os
import sys
import json
import shlex
import tempfile
import shutil
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
import re

logger = logging.getLogger(__name__)


class ExecutionMode(Enum):
    """执行模式"""
    SHELL = "shell"           # Shell 命令
    PROGRAM = "program"       # 已注册程序
    TCL = "tcl"              # Vivado TCL
    PYTHON = "python"        # Python 代码
    FILE = "file"            # 文件操作


@dataclass
class ExecutionResult:
    """执行结果"""
    success: bool
    output: str
    error: str = ""
    return_code: int = 0
    data: Dict = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "output": self.output,
            "error": self.error,
            "return_code": self.return_code,
            "data": self.data or {}
        }


class CommandExecutor:
    """
    命令执行器
    
    作为 AI 与本地系统之间的中介，负责：
    1. 安全地执行 AI 发出的命令
    2. 管理已注册的本地程序
    3. 处理 Vivado 等特殊程序的调用
    """
    
    # 危险命令黑名单
    DANGEROUS_COMMANDS = [
        r'rm\s+-rf\s+/',
        r'rm\s+-rf\s+~',
        r'rm\s+-rf\s+\*',
        r'mkfs\.',
        r'dd\s+if=/dev/zero',
        r'format\s+[a-z]:',
        r'del\s+/s\s+/q',
        r':\(\)\{\s*:\|:&\s*\};:',  # fork bomb
        r'>\s*/dev/sd',
    ]
    
    def __init__(self, config):
        """
        初始化执行器
        
        Args:
            config: 配置管理器实例
        """
        self.config = config
        self.registered_programs: Dict[str, str] = {}
        self.working_dir = os.path.expanduser(
            config.get("default_project_path", "~/fpga_projects")
        )
        self.temp_dir = os.path.expanduser(
            config.get("temp_dir", "~/.arixa/temp")
        )
        
        # 加载已注册的程序
        self._load_registered_programs()
        
        # 确保目录存在
        os.makedirs(self.working_dir, exist_ok=True)
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def _load_registered_programs(self):
        """加载已注册的程序"""
        programs = self.config.get("programs", {})
        
        for name, info in programs.items():
            if isinstance(info, dict):
                path = info.get("path", "")
            else:
                path = info
            
            if path:
                self.registered_programs[name] = os.path.expanduser(path)
                logger.debug(f"已注册程序: {name} -> {path}")
    
    def is_safe_command(self, command: str) -> Tuple[bool, str]:
        """
        检查命令是否安全
        
        Args:
            command: 要检查的命令
        
        Returns:
            (是否安全, 原因)
        """
        command_lower = command.lower()
        
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, command_lower):
                return False, f"命令匹配危险模式: {pattern}"
        
        return True, ""
    
    def execute_shell(self, command: str, working_dir: str = None, 
                      timeout: int = 120, capture: bool = True) -> ExecutionResult:
        """
        执行 Shell 命令
        
        Args:
            command: Shell 命令
            working_dir: 工作目录
            timeout: 超时时间（秒）
            capture: 是否捕获输出
        
        Returns:
            ExecutionResult
        """
        # 安全检查
        is_safe, reason = self.is_safe_command(command)
        if not is_safe:
            return ExecutionResult(
                success=False,
                output="",
                error=f"安全检查失败: {reason}"
            )
        
        working_dir = working_dir or self.working_dir
        working_dir = os.path.expanduser(working_dir)
        
        logger.info(f"执行命令: {command}")
        logger.debug(f"工作目录: {working_dir}")
        
        try:
            if capture:
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=working_dir,
                    capture_output=True,
                    text=True,
                    timeout=timeout
                )
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode
                )
            else:
                # 不捕获输出，直接显示在控制台
                result = subprocess.run(
                    command,
                    shell=True,
                    cwd=working_dir,
                    timeout=timeout
                )
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output="(输出已显示在控制台)",
                    return_code=result.returncode
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error=f"命令执行超时 ({timeout}秒)"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def execute_program(self, program_name: str, arguments: List[str] = None,
                        working_dir: str = None, wait: bool = True) -> ExecutionResult:
        """
        执行已注册的程序
        
        Args:
            program_name: 程序名称（在配置中注册的）
            arguments: 命令行参数
            working_dir: 工作目录
            wait: 是否等待程序结束
        
        Returns:
            ExecutionResult
        """
        if program_name not in self.registered_programs:
            return ExecutionResult(
                success=False,
                output="",
                error=f"程序 '{program_name}' 未注册。可用程序: {list(self.registered_programs.keys())}"
            )
        
        program_path = self.registered_programs[program_name]
        
        if not os.path.exists(program_path):
            # 尝试使用 which/where 查找
            found = shutil.which(program_path)
            if found:
                program_path = found
            else:
                return ExecutionResult(
                    success=False,
                    output="",
                    error=f"程序路径不存在: {program_path}"
                )
        
        arguments = arguments or []
        working_dir = os.path.expanduser(working_dir or self.working_dir)
        
        cmd = [program_path] + arguments
        logger.info(f"执行程序: {' '.join(cmd)}")
        
        try:
            if wait:
                result = subprocess.run(
                    cmd,
                    cwd=working_dir,
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                
                return ExecutionResult(
                    success=result.returncode == 0,
                    output=result.stdout,
                    error=result.stderr,
                    return_code=result.returncode
                )
            else:
                # 后台启动
                subprocess.Popen(cmd, cwd=working_dir)
                return ExecutionResult(
                    success=True,
                    output=f"程序已在后台启动: {program_name}"
                )
                
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error="程序执行超时"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def execute_vivado_tcl(self, tcl_commands: List[str], 
                           project_path: str = None) -> ExecutionResult:
        """
        执行 Vivado TCL 命令
        
        Args:
            tcl_commands: TCL 命令列表
            project_path: 项目文件路径（可选）
        
        Returns:
            ExecutionResult
        """
        vivado_path = self.registered_programs.get("vivado")
        
        if not vivado_path:
            return ExecutionResult(
                success=False,
                output="",
                error="Vivado 未配置，请运行 arixa --setup"
            )
        
        # 创建 TCL 脚本
        tcl_script = "\n".join(tcl_commands)
        tcl_file = os.path.join(self.temp_dir, "arixa_cmd.tcl")
        
        with open(tcl_file, 'w', encoding='utf-8') as f:
            f.write(tcl_script)
        
        logger.info(f"执行 Vivado TCL:\n{tcl_script}")
        
        # 构建命令
        cmd = [vivado_path, "-mode", "batch", "-source", tcl_file]
        
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=3600,  # Vivado 可能需要较长时间
                cwd=self.working_dir
            )
            
            return ExecutionResult(
                success=result.returncode == 0,
                output=result.stdout,
                error=result.stderr,
                return_code=result.returncode,
                data={"tcl_script": tcl_script}
            )
            
        except subprocess.TimeoutExpired:
            return ExecutionResult(
                success=False,
                output="",
                error="Vivado 执行超时（1小时）"
            )
        except FileNotFoundError:
            return ExecutionResult(
                success=False,
                output="",
                error=f"找不到 Vivado: {vivado_path}"
            )
        except Exception as e:
            return ExecutionResult(
                success=False,
                output="",
                error=str(e)
            )
    
    def execute_python(self, code: str, globals_dict: Dict = None) -> ExecutionResult:
        """
        执行 Python 代码
        
        Args:
            code: Python 代码
            globals_dict: 全局变量字典
        
        Returns:
            ExecutionResult
        """
        import io
        from contextlib import redirect_stdout, redirect_stderr
        
        stdout_capture = io.StringIO()
        stderr_capture = io.StringIO()
        
        globals_dict = globals_dict or {}
        locals_dict = {}
        
        try:
            with redirect_stdout(stdout_capture), redirect_stderr(stderr_capture):
                exec(code, globals_dict, locals_dict)
            
            return ExecutionResult(
                success=True,
                output=stdout_capture.getvalue(),
                error=stderr_capture.getvalue(),
                data={"locals": {k: str(v) for k, v in locals_dict.items() if not k.startswith('_')}}
            )
            
        except Exception as e:
            return ExecutionResult(
                success=False,
                output=stdout_capture.getvalue(),
                error=f"{type(e).__name__}: {e}"
            )
    
    def execute_from_ai_response(self, ai_response: Dict) -> ExecutionResult:
        """
        根据 AI 的响应执行操作
        
        这是中介功能的核心方法，解析 AI 的结构化响应并执行
        
        Args:
            ai_response: AI 返回的结构化响应，格式如:
                {
                    "action": "tool_call" | "shell" | "program" | "tcl",
                    "tool": "工具名",
                    "command": "命令",
                    "parameters": {...}
                }
        
        Returns:
            ExecutionResult
        """
        action = ai_response.get("action", "")
        
        if action == "tool_call":
            # MCP 工具调用（由 MCP Server 处理）
            return ExecutionResult(
                success=True,
                output="",
                data={"type": "mcp_tool", "tool": ai_response.get("tool")}
            )
        
        elif action == "shell":
            command = ai_response.get("command", "")
            working_dir = ai_response.get("working_dir")
            return self.execute_shell(command, working_dir)
        
        elif action == "program":
            program = ai_response.get("program", "")
            args = ai_response.get("arguments", [])
            wait = ai_response.get("wait", True)
            return self.execute_program(program, args, wait=wait)
        
        elif action == "tcl":
            commands = ai_response.get("commands", [])
            if isinstance(commands, str):
                commands = [commands]
            return self.execute_vivado_tcl(commands)
        
        elif action == "python":
            code = ai_response.get("code", "")
            return self.execute_python(code)
        
        else:
            return ExecutionResult(
                success=False,
                output="",
                error=f"未知的操作类型: {action}"
            )
    
    def get_registered_programs(self) -> Dict[str, Dict]:
        """获取所有已注册程序的信息"""
        programs = {}
        for name, path in self.registered_programs.items():
            programs[name] = {
                "path": path,
                "exists": os.path.exists(path) or shutil.which(path) is not None
            }
        return programs
    
    def register_program(self, name: str, path: str) -> bool:
        """
        注册新程序
        
        Args:
            name: 程序名称
            path: 程序路径
        
        Returns:
            是否成功
        """
        path = os.path.expanduser(path)
        self.registered_programs[name] = path
        self.config.set(f"programs.{name}.path", path)
        self.config.save()
        logger.info(f"已注册程序: {name} -> {path}")
        return True


class AICommandParser:
    """
    AI 命令解析器
    
    从 AI 的文本响应中提取可执行的命令
    """
    
    @staticmethod
    def parse_response(response_text: str) -> List[Dict]:
        """
        解析 AI 响应，提取命令
        
        支持的格式:
        1. JSON 代码块
        2. 直接的 JSON 对象
        3. 特殊标记的命令
        
        Args:
            response_text: AI 的响应文本
        
        Returns:
            解析出的命令列表
        """
        commands = []
        
        # 1. 查找 JSON 代码块
        json_pattern = r'```json\s*(.*?)\s*```'
        matches = re.findall(json_pattern, response_text, re.DOTALL)
        
        for match in matches:
            try:
                data = json.loads(match)
                if isinstance(data, dict):
                    commands.append(data)
                elif isinstance(data, list):
                    commands.extend(data)
            except json.JSONDecodeError:
                pass
        
        # 2. 查找内联 JSON（以 { 开始，以 } 结束的行）
        if not commands:
            lines = response_text.split('\n')
            for line in lines:
                line = line.strip()
                if line.startswith('{') and line.endswith('}'):
                    try:
                        data = json.loads(line)
                        commands.append(data)
                    except json.JSONDecodeError:
                        pass
        
        # 3. 查找特殊标记
        # [EXECUTE: command]
        exec_pattern = r'\[EXECUTE:\s*(.*?)\]'
        exec_matches = re.findall(exec_pattern, response_text)
        for cmd in exec_matches:
            commands.append({"action": "shell", "command": cmd})
        
        # [RUN_PROGRAM: name arg1 arg2]
        prog_pattern = r'\[RUN_PROGRAM:\s*(\w+)(?:\s+(.*?))?\]'
        prog_matches = re.findall(prog_pattern, response_text)
        for name, args in prog_matches:
            commands.append({
                "action": "program",
                "program": name,
                "arguments": args.split() if args else []
            })
        
        return commands
    
    @staticmethod
    def extract_code_blocks(response_text: str) -> Dict[str, List[str]]:
        """
        提取代码块
        
        Args:
            response_text: AI 响应文本
        
        Returns:
            {语言: [代码块列表]}
        """
        code_blocks = {}
        
        pattern = r'```(\w+)?\s*(.*?)\s*```'
        matches = re.findall(pattern, response_text, re.DOTALL)
        
        for lang, code in matches:
            lang = lang or "text"
            if lang not in code_blocks:
                code_blocks[lang] = []
            code_blocks[lang].append(code)
        
        return code_blocks
