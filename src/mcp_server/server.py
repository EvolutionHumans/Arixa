#!/usr/bin/env python3
"""
Arixa MCP Server - Model Context Protocol 服务器
处理 AI 与本地程序之间的通信
"""

import json
import asyncio
import subprocess
import os
import sys
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ToolCategory(Enum):
    """工具类别"""
    VIVADO = "vivado"
    FILE = "file"
    SYSTEM = "system"
    PROJECT = "project"
    SIMULATION = "simulation"
    SYNTHESIS = "synthesis"
    IMPLEMENTATION = "implementation"
    BITSTREAM = "bitstream"


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]
    handler: Optional[Callable] = None
    
    def to_dict(self) -> Dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category.value,
            "parameters": self.parameters
        }


@dataclass
class MCPRequest:
    """MCP 请求"""
    id: str
    method: str
    params: Dict[str, Any]


@dataclass
class MCPResponse:
    """MCP 响应"""
    id: str
    result: Optional[Any] = None
    error: Optional[Dict[str, Any]] = None


class MCPServer:
    """MCP 服务器 - 处理 AI 与本地程序的通信"""
    
    def __init__(self, config):
        self.config = config
        self.tools: Dict[str, MCPTool] = {}
        self.running = False
        self._register_default_tools()
        
    def _register_default_tools(self):
        """注册默认工具集"""
        
        # ==================== Vivado 工具 ====================
        self.register_tool(MCPTool(
            name="vivado_create_project",
            description="创建新的 Vivado 项目",
            category=ToolCategory.PROJECT,
            parameters={
                "project_name": {"type": "string", "description": "项目名称", "required": True},
                "project_path": {"type": "string", "description": "项目路径", "required": True},
                "part": {"type": "string", "description": "目标器件型号", "required": True},
                "board": {"type": "string", "description": "开发板型号", "required": False}
            },
            handler=self._handle_vivado_create_project
        ))
        
        self.register_tool(MCPTool(
            name="vivado_open_project",
            description="打开现有的 Vivado 项目",
            category=ToolCategory.PROJECT,
            parameters={
                "project_path": {"type": "string", "description": "项目文件路径 (.xpr)", "required": True}
            },
            handler=self._handle_vivado_open_project
        ))
        
        self.register_tool(MCPTool(
            name="vivado_add_source",
            description="添加源文件到项目",
            category=ToolCategory.PROJECT,
            parameters={
                "file_path": {"type": "string", "description": "源文件路径", "required": True},
                "file_type": {"type": "string", "description": "文件类型 (verilog/vhdl/xdc/ip)", "required": False}
            },
            handler=self._handle_vivado_add_source
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_synthesis",
            description="运行综合",
            category=ToolCategory.SYNTHESIS,
            parameters={
                "jobs": {"type": "integer", "description": "并行任务数", "required": False, "default": 4}
            },
            handler=self._handle_vivado_synthesis
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_implementation",
            description="运行实现（布局布线）",
            category=ToolCategory.IMPLEMENTATION,
            parameters={
                "jobs": {"type": "integer", "description": "并行任务数", "required": False, "default": 4}
            },
            handler=self._handle_vivado_implementation
        ))
        
        self.register_tool(MCPTool(
            name="vivado_generate_bitstream",
            description="生成比特流文件",
            category=ToolCategory.BITSTREAM,
            parameters={
                "bin_file": {"type": "boolean", "description": "是否生成 .bin 文件", "required": False}
            },
            handler=self._handle_vivado_bitstream
        ))
        
        self.register_tool(MCPTool(
            name="vivado_program_device",
            description="烧录比特流到 FPGA 设备",
            category=ToolCategory.BITSTREAM,
            parameters={
                "bitstream_path": {"type": "string", "description": "比特流文件路径", "required": True},
                "device": {"type": "string", "description": "目标设备", "required": False}
            },
            handler=self._handle_vivado_program
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_simulation",
            description="运行仿真",
            category=ToolCategory.SIMULATION,
            parameters={
                "testbench": {"type": "string", "description": "测试台顶层模块名", "required": True},
                "sim_time": {"type": "string", "description": "仿真时间 (如 1000ns)", "required": False}
            },
            handler=self._handle_vivado_simulation
        ))
        
        self.register_tool(MCPTool(
            name="vivado_get_reports",
            description="获取综合/实现报告",
            category=ToolCategory.PROJECT,
            parameters={
                "report_type": {"type": "string", "description": "报告类型 (utilization/timing/power)", "required": True}
            },
            handler=self._handle_vivado_reports
        ))
        
        # ==================== 文件操作工具 ====================
        self.register_tool(MCPTool(
            name="file_create",
            description="创建新文件",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "content": {"type": "string", "description": "文件内容", "required": True}
            },
            handler=self._handle_file_create
        ))
        
        self.register_tool(MCPTool(
            name="file_read",
            description="读取文件内容",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True}
            },
            handler=self._handle_file_read
        ))
        
        self.register_tool(MCPTool(
            name="file_modify",
            description="修改文件内容",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "old_content": {"type": "string", "description": "要替换的内容", "required": True},
                "new_content": {"type": "string", "description": "新内容", "required": True}
            },
            handler=self._handle_file_modify
        ))
        
        self.register_tool(MCPTool(
            name="file_list",
            description="列出目录内容",
            category=ToolCategory.FILE,
            parameters={
                "dir_path": {"type": "string", "description": "目录路径", "required": True},
                "pattern": {"type": "string", "description": "文件名匹配模式", "required": False}
            },
            handler=self._handle_file_list
        ))
        
        # ==================== 系统工具 ====================
        self.register_tool(MCPTool(
            name="run_program",
            description="运行本地程序",
            category=ToolCategory.SYSTEM,
            parameters={
                "program_name": {"type": "string", "description": "程序名称（已在配置中注册）", "required": True},
                "arguments": {"type": "array", "description": "命令行参数", "required": False}
            },
            handler=self._handle_run_program
        ))
        
        self.register_tool(MCPTool(
            name="run_command",
            description="运行系统命令",
            category=ToolCategory.SYSTEM,
            parameters={
                "command": {"type": "string", "description": "命令", "required": True},
                "working_dir": {"type": "string", "description": "工作目录", "required": False}
            },
            handler=self._handle_run_command
        ))
        
        self.register_tool(MCPTool(
            name="get_system_info",
            description="获取系统信息",
            category=ToolCategory.SYSTEM,
            parameters={},
            handler=self._handle_system_info
        ))

    def register_tool(self, tool: MCPTool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")
        
    def get_tools_schema(self) -> List[Dict]:
        """获取所有工具的 schema"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    async def handle_request(self, request: MCPRequest) -> MCPResponse:
        """处理 MCP 请求"""
        logger.info(f"处理请求: {request.method}")
        
        try:
            if request.method == "tools/list":
                return MCPResponse(
                    id=request.id,
                    result={"tools": self.get_tools_schema()}
                )
            
            elif request.method == "tools/call":
                tool_name = request.params.get("name")
                tool_params = request.params.get("arguments", {})
                
                if tool_name not in self.tools:
                    return MCPResponse(
                        id=request.id,
                        error={"code": -32601, "message": f"未知工具: {tool_name}"}
                    )
                
                tool = self.tools[tool_name]
                if tool.handler:
                    result = await self._execute_handler(tool.handler, tool_params)
                    return MCPResponse(id=request.id, result=result)
                else:
                    return MCPResponse(
                        id=request.id,
                        error={"code": -32603, "message": f"工具 {tool_name} 未实现"}
                    )
            
            else:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"未知方法: {request.method}"}
                )
                
        except Exception as e:
            logger.error(f"请求处理错误: {e}")
            return MCPResponse(
                id=request.id,
                error={"code": -32603, "message": str(e)}
            )
    
    async def _execute_handler(self, handler: Callable, params: Dict) -> Any:
        """执行工具处理函数"""
        if asyncio.iscoroutinefunction(handler):
            return await handler(params)
        else:
            return handler(params)

    # ==================== Vivado 处理函数 ====================
    
    def _get_vivado_path(self) -> str:
        """获取 Vivado 可执行文件路径"""
        vivado_path = self.config.get("programs.vivado.path")
        if not vivado_path:
            raise Exception("Vivado 路径未配置，请运行 arixa --setup")
        return vivado_path
    
    def _run_vivado_tcl(self, tcl_commands: List[str], batch: bool = True) -> Dict:
        """运行 Vivado TCL 命令"""
        vivado_path = self._get_vivado_path()
        
        # 创建临时 TCL 脚本
        tcl_script = "\n".join(tcl_commands)
        tcl_file = os.path.join(self.config.get("temp_dir", "/tmp"), "arixa_temp.tcl")
        
        with open(tcl_file, 'w') as f:
            f.write(tcl_script)
        
        # 运行 Vivado
        cmd = [vivado_path, "-mode", "batch" if batch else "tcl", "-source", tcl_file]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Vivado 执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_vivado_create_project(self, params: Dict) -> Dict:
        """创建 Vivado 项目"""
        project_name = params["project_name"]
        project_path = params["project_path"]
        part = params["part"]
        board = params.get("board", "")
        
        tcl_commands = [
            f'create_project {project_name} "{project_path}" -part {part}',
        ]
        
        if board:
            tcl_commands.append(f'set_property board_part {board} [current_project]')
        
        tcl_commands.append("exit")
        
        result = self._run_vivado_tcl(tcl_commands)
        result["project_path"] = os.path.join(project_path, f"{project_name}.xpr")
        return result
    
    def _handle_vivado_open_project(self, params: Dict) -> Dict:
        """打开 Vivado 项目"""
        project_path = params["project_path"]
        
        tcl_commands = [
            f'open_project "{project_path}"',
            'puts "Project opened successfully"',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_add_source(self, params: Dict) -> Dict:
        """添加源文件"""
        file_path = params["file_path"]
        file_type = params.get("file_type", "").lower()
        
        if file_type == "xdc" or file_path.endswith(".xdc"):
            tcl_cmd = f'add_files -fileset constrs_1 "{file_path}"'
        elif file_type == "ip" or file_path.endswith(".xci"):
            tcl_cmd = f'import_ip "{file_path}"'
        else:
            tcl_cmd = f'add_files "{file_path}"'
        
        tcl_commands = [tcl_cmd, 'exit']
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_synthesis(self, params: Dict) -> Dict:
        """运行综合"""
        jobs = params.get("jobs", 4)
        
        tcl_commands = [
            f'launch_runs synth_1 -jobs {jobs}',
            'wait_on_run synth_1',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_implementation(self, params: Dict) -> Dict:
        """运行实现"""
        jobs = params.get("jobs", 4)
        
        tcl_commands = [
            f'launch_runs impl_1 -jobs {jobs}',
            'wait_on_run impl_1',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_bitstream(self, params: Dict) -> Dict:
        """生成比特流"""
        bin_file = params.get("bin_file", False)
        
        tcl_commands = [
            'open_run impl_1',
        ]
        
        if bin_file:
            tcl_commands.append('set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]')
        
        tcl_commands.extend([
            'write_bitstream -force design.bit',
            'exit'
        ])
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_program(self, params: Dict) -> Dict:
        """烧录设备"""
        bitstream_path = params["bitstream_path"]
        
        tcl_commands = [
            'open_hw_manager',
            'connect_hw_server -allow_non_jtag',
            'open_hw_target',
            'current_hw_device [lindex [get_hw_devices] 0]',
            f'set_property PROGRAM.FILE {{{bitstream_path}}} [current_hw_device]',
            'program_hw_devices [current_hw_device]',
            'close_hw_manager',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_simulation(self, params: Dict) -> Dict:
        """运行仿真"""
        testbench = params["testbench"]
        sim_time = params.get("sim_time", "1000ns")
        
        tcl_commands = [
            f'set_property top {testbench} [get_filesets sim_1]',
            'launch_simulation',
            f'run {sim_time}',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_reports(self, params: Dict) -> Dict:
        """获取报告"""
        report_type = params["report_type"]
        
        report_commands = {
            "utilization": "report_utilization -file utilization.rpt",
            "timing": "report_timing_summary -file timing.rpt",
            "power": "report_power -file power.rpt"
        }
        
        if report_type not in report_commands:
            return {"success": False, "error": f"未知报告类型: {report_type}"}
        
        tcl_commands = [
            'open_run impl_1',
            report_commands[report_type],
            'exit'
        ]
        
        result = self._run_vivado_tcl(tcl_commands)
        
        # 读取生成的报告
        report_file = f"{report_type}.rpt"
        if os.path.exists(report_file):
            with open(report_file, 'r') as f:
                result["report_content"] = f.read()
        
        return result

    # ==================== 文件操作处理函数 ====================
    
    def _handle_file_create(self, params: Dict) -> Dict:
        """创建文件"""
        file_path = params["file_path"]
        content = params["content"]
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            return {"success": True, "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_read(self, params: Dict) -> Dict:
        """读取文件"""
        file_path = params["file_path"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return {"success": True, "content": content}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_modify(self, params: Dict) -> Dict:
        """修改文件"""
        file_path = params["file_path"]
        old_content = params["old_content"]
        new_content = params["new_content"]
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_content not in content:
                return {"success": False, "error": "未找到要替换的内容"}
            
            content = content.replace(old_content, new_content, 1)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {"success": True, "file_path": file_path}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_list(self, params: Dict) -> Dict:
        """列出目录"""
        dir_path = params["dir_path"]
        pattern = params.get("pattern", "*")
        
        try:
            import glob
            files = glob.glob(os.path.join(dir_path, pattern))
            return {
                "success": True,
                "files": [{"path": f, "is_dir": os.path.isdir(f)} for f in files]
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 系统工具处理函数 ====================
    
    def _handle_run_program(self, params: Dict) -> Dict:
        """运行已注册的程序"""
        program_name = params["program_name"]
        arguments = params.get("arguments", [])
        
        # 从配置获取程序路径
        program_path = self.config.get(f"programs.{program_name}.path")
        
        if not program_path:
            return {"success": False, "error": f"程序 '{program_name}' 未注册，请运行 arixa --setup 配置"}
        
        if not os.path.exists(program_path):
            return {"success": False, "error": f"程序路径不存在: {program_path}"}
        
        try:
            cmd = [program_path] + arguments
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "程序执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_run_command(self, params: Dict) -> Dict:
        """运行系统命令"""
        command = params["command"]
        working_dir = params.get("working_dir", os.getcwd())
        
        # 安全检查 - 禁止危险命令
        dangerous_patterns = ['rm -rf', 'format', 'del /s', 'rmdir /s']
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return {"success": False, "error": f"安全限制: 不允许执行危险命令"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=120
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "命令执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_system_info(self, params: Dict) -> Dict:
        """获取系统信息"""
        import platform
        
        return {
            "success": True,
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version()
        }

    # ==================== 服务器启动 ====================
    
    def start(self, host: str = "localhost", port: int = 8765):
        """启动 MCP 服务器"""
        import asyncio
        
        async def handle_client(reader, writer):
            """处理客户端连接"""
            addr = writer.get_extra_info('peername')
            logger.info(f"客户端连接: {addr}")
            
            try:
                while True:
                    data = await reader.readline()
                    if not data:
                        break
                    
                    try:
                        request_data = json.loads(data.decode())
                        request = MCPRequest(
                            id=request_data.get("id", ""),
                            method=request_data.get("method", ""),
                            params=request_data.get("params", {})
                        )
                        
                        response = await self.handle_request(request)
                        response_data = {
                            "id": response.id,
                            "result": response.result,
                            "error": response.error
                        }
                        
                        writer.write((json.dumps(response_data) + "\n").encode())
                        await writer.drain()
                        
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON 解析错误: {e}")
                        
            except Exception as e:
                logger.error(f"客户端处理错误: {e}")
            finally:
                writer.close()
                await writer.wait_closed()
                logger.info(f"客户端断开: {addr}")
        
        async def main():
            server = await asyncio.start_server(handle_client, host, port)
            addr = server.sockets[0].getsockname()
            logger.info(f"MCP 服务器启动于 {addr}")
            print(f"🚀 Arixa MCP Server 运行中: {addr}")
            print("按 Ctrl+C 停止服务器")
            
            async with server:
                await server.serve_forever()
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("服务器停止")
            print("\n服务器已停止")
