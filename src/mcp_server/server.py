#!/usr/bin/env python3
"""
Arixa MCP Server - Model Context Protocol 服务器
核心功能：将 AI 的指令转换为本地命令执行

工作流程:
1. 接收 AI 的工具调用请求
2. 验证和解析参数
3. 在本地执行相应操作
4. 返回执行结果

支持的操作:
- Vivado 项目管理和编译
- 文件操作
- 本地程序调用
- 系统命令执行
"""

import json
import asyncio
import subprocess
import os
import sys
import shutil
import glob
from typing import Dict, Any, List, Optional, Callable
from dataclasses import dataclass, asdict, field
from enum import Enum
import logging
import tempfile

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
    CODE_GEN = "code_generation"


@dataclass
class MCPTool:
    """MCP 工具定义"""
    name: str
    description: str
    category: ToolCategory
    parameters: Dict[str, Any]
    handler: Optional[Callable] = field(default=None, repr=False)
    
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
    """
    MCP 服务器 - AI 与本地程序的桥梁
    
    主要功能:
    1. 注册和管理可用工具
    2. 处理 AI 的工具调用请求
    3. 在本地执行命令并返回结果
    """
    
    def __init__(self, config):
        self.config = config
        self.tools: Dict[str, MCPTool] = {}
        self.running = False
        self.current_project = None  # 当前打开的项目
        self._register_all_tools()
        
    def _register_all_tools(self):
        """注册所有工具"""
        self._register_vivado_tools()
        self._register_file_tools()
        self._register_system_tools()
        self._register_code_gen_tools()

    # ==================== Vivado 工具注册 ====================
    
    def _register_vivado_tools(self):
        """注册 Vivado 相关工具"""
        
        self.register_tool(MCPTool(
            name="vivado_create_project",
            description="创建新的 Vivado FPGA 项目",
            category=ToolCategory.PROJECT,
            parameters={
                "project_name": {"type": "string", "description": "项目名称", "required": True},
                "project_path": {"type": "string", "description": "项目保存路径", "required": True},
                "part": {"type": "string", "description": "FPGA 芯片型号，如 xc7a35tcsg324-1", "required": True},
                "board": {"type": "string", "description": "开发板型号（可选）", "required": False}
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
            name="vivado_close_project",
            description="关闭当前项目",
            category=ToolCategory.PROJECT,
            parameters={},
            handler=self._handle_vivado_close_project
        ))
        
        self.register_tool(MCPTool(
            name="vivado_add_sources",
            description="添加源文件到项目（Verilog/VHDL/约束文件）",
            category=ToolCategory.PROJECT,
            parameters={
                "files": {"type": "array", "description": "文件路径列表", "required": True},
                "fileset": {"type": "string", "description": "文件集 (sources_1/constrs_1/sim_1)", "required": False}
            },
            handler=self._handle_vivado_add_sources
        ))
        
        self.register_tool(MCPTool(
            name="vivado_set_top",
            description="设置顶层模块",
            category=ToolCategory.PROJECT,
            parameters={
                "top_module": {"type": "string", "description": "顶层模块名称", "required": True}
            },
            handler=self._handle_vivado_set_top
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_synthesis",
            description="运行综合",
            category=ToolCategory.SYNTHESIS,
            parameters={
                "jobs": {"type": "integer", "description": "并行任务数", "required": False},
                "directive": {"type": "string", "description": "综合策略", "required": False}
            },
            handler=self._handle_vivado_synthesis
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_implementation",
            description="运行实现（布局布线）",
            category=ToolCategory.IMPLEMENTATION,
            parameters={
                "jobs": {"type": "integer", "description": "并行任务数", "required": False},
                "directive": {"type": "string", "description": "实现策略", "required": False}
            },
            handler=self._handle_vivado_implementation
        ))
        
        self.register_tool(MCPTool(
            name="vivado_generate_bitstream",
            description="生成比特流文件",
            category=ToolCategory.BITSTREAM,
            parameters={
                "bin_file": {"type": "boolean", "description": "同时生成 .bin 文件", "required": False},
                "compress": {"type": "boolean", "description": "压缩比特流", "required": False}
            },
            handler=self._handle_vivado_bitstream
        ))
        
        self.register_tool(MCPTool(
            name="vivado_program_device",
            description="将比特流烧录到 FPGA 设备",
            category=ToolCategory.BITSTREAM,
            parameters={
                "bitstream_path": {"type": "string", "description": "比特流文件路径", "required": False}
            },
            handler=self._handle_vivado_program
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_simulation",
            description="运行行为仿真",
            category=ToolCategory.SIMULATION,
            parameters={
                "testbench": {"type": "string", "description": "测试台模块名", "required": True},
                "sim_time": {"type": "string", "description": "仿真时间，如 1us", "required": False}
            },
            handler=self._handle_vivado_simulation
        ))
        
        self.register_tool(MCPTool(
            name="vivado_get_report",
            description="获取综合/实现报告",
            category=ToolCategory.PROJECT,
            parameters={
                "report_type": {"type": "string", "description": "报告类型: utilization/timing/power/drc", "required": True}
            },
            handler=self._handle_vivado_report
        ))
        
        self.register_tool(MCPTool(
            name="vivado_run_tcl",
            description="执行自定义 Vivado TCL 命令",
            category=ToolCategory.VIVADO,
            parameters={
                "commands": {"type": "array", "description": "TCL 命令列表", "required": True}
            },
            handler=self._handle_vivado_tcl
        ))

    # ==================== 文件工具注册 ====================
    
    def _register_file_tools(self):
        """注册文件操作工具"""
        
        self.register_tool(MCPTool(
            name="file_create",
            description="创建新文件并写入内容",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "content": {"type": "string", "description": "文件内容", "required": True},
                "overwrite": {"type": "boolean", "description": "是否覆盖已存在的文件", "required": False}
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
            description="修改文件中的指定内容",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "old_content": {"type": "string", "description": "要替换的原内容", "required": True},
                "new_content": {"type": "string", "description": "新内容", "required": True}
            },
            handler=self._handle_file_modify
        ))
        
        self.register_tool(MCPTool(
            name="file_append",
            description="在文件末尾追加内容",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "content": {"type": "string", "description": "要追加的内容", "required": True}
            },
            handler=self._handle_file_append
        ))
        
        self.register_tool(MCPTool(
            name="file_delete",
            description="删除文件",
            category=ToolCategory.FILE,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True}
            },
            handler=self._handle_file_delete
        ))
        
        self.register_tool(MCPTool(
            name="file_list",
            description="列出目录中的文件",
            category=ToolCategory.FILE,
            parameters={
                "dir_path": {"type": "string", "description": "目录路径", "required": True},
                "pattern": {"type": "string", "description": "文件匹配模式，如 *.v", "required": False},
                "recursive": {"type": "boolean", "description": "是否递归搜索", "required": False}
            },
            handler=self._handle_file_list
        ))
        
        self.register_tool(MCPTool(
            name="file_copy",
            description="复制文件",
            category=ToolCategory.FILE,
            parameters={
                "source": {"type": "string", "description": "源文件路径", "required": True},
                "destination": {"type": "string", "description": "目标路径", "required": True}
            },
            handler=self._handle_file_copy
        ))
        
        self.register_tool(MCPTool(
            name="dir_create",
            description="创建目录",
            category=ToolCategory.FILE,
            parameters={
                "dir_path": {"type": "string", "description": "目录路径", "required": True}
            },
            handler=self._handle_dir_create
        ))

    # ==================== 系统工具注册 ====================
    
    def _register_system_tools(self):
        """注册系统工具"""
        
        self.register_tool(MCPTool(
            name="run_program",
            description="运行已配置的本地程序",
            category=ToolCategory.SYSTEM,
            parameters={
                "program_name": {"type": "string", "description": "程序名称（在配置中注册的）", "required": True},
                "arguments": {"type": "array", "description": "命令行参数列表", "required": False},
                "wait": {"type": "boolean", "description": "是否等待程序结束", "required": False}
            },
            handler=self._handle_run_program
        ))
        
        self.register_tool(MCPTool(
            name="run_command",
            description="运行系统命令（在安全范围内）",
            category=ToolCategory.SYSTEM,
            parameters={
                "command": {"type": "string", "description": "要执行的命令", "required": True},
                "working_dir": {"type": "string", "description": "工作目录", "required": False},
                "timeout": {"type": "integer", "description": "超时时间（秒）", "required": False}
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
        
        self.register_tool(MCPTool(
            name="list_registered_programs",
            description="列出所有已注册的本地程序",
            category=ToolCategory.SYSTEM,
            parameters={},
            handler=self._handle_list_programs
        ))
        
        self.register_tool(MCPTool(
            name="open_in_editor",
            description="在编辑器中打开文件",
            category=ToolCategory.SYSTEM,
            parameters={
                "file_path": {"type": "string", "description": "文件路径", "required": True},
                "editor": {"type": "string", "description": "编辑器名称（需要已注册）", "required": False}
            },
            handler=self._handle_open_in_editor
        ))

    # ==================== 代码生成工具注册 ====================
    
    def _register_code_gen_tools(self):
        """注册代码生成工具"""
        
        self.register_tool(MCPTool(
            name="create_verilog_module",
            description="创建 Verilog 模块文件",
            category=ToolCategory.CODE_GEN,
            parameters={
                "module_name": {"type": "string", "description": "模块名称", "required": True},
                "file_path": {"type": "string", "description": "保存路径", "required": True},
                "ports": {"type": "object", "description": "端口定义", "required": False},
                "code": {"type": "string", "description": "模块代码", "required": True}
            },
            handler=self._handle_create_verilog
        ))
        
        self.register_tool(MCPTool(
            name="create_testbench",
            description="为模块创建测试台",
            category=ToolCategory.CODE_GEN,
            parameters={
                "module_name": {"type": "string", "description": "被测模块名称", "required": True},
                "file_path": {"type": "string", "description": "保存路径", "required": True},
                "code": {"type": "string", "description": "测试台代码", "required": True}
            },
            handler=self._handle_create_testbench
        ))
        
        self.register_tool(MCPTool(
            name="create_constraints",
            description="创建约束文件 (.xdc)",
            category=ToolCategory.CODE_GEN,
            parameters={
                "file_path": {"type": "string", "description": "保存路径", "required": True},
                "constraints": {"type": "string", "description": "约束内容", "required": True}
            },
            handler=self._handle_create_constraints
        ))

    # ==================== 工具管理 ====================
    
    def register_tool(self, tool: MCPTool):
        """注册工具"""
        self.tools[tool.name] = tool
        logger.debug(f"注册工具: {tool.name}")
        
    def get_tools_schema(self) -> List[Dict]:
        """获取所有工具的 schema（用于 AI）"""
        return [tool.to_dict() for tool in self.tools.values()]
    
    def get_tools_for_ai(self) -> List[Dict]:
        """获取 AI function calling 格式的工具定义"""
        tools = []
        for tool in self.tools.values():
            tools.append({
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters
            })
        return tools

    # ==================== 请求处理 ====================
    
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
                        error={"code": -32603, "message": f"工具 {tool_name} 未实现处理函数"}
                    )
            
            else:
                return MCPResponse(
                    id=request.id,
                    error={"code": -32601, "message": f"未知方法: {request.method}"}
                )
                
        except Exception as e:
            logger.error(f"请求处理错误: {e}", exc_info=True)
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
            # 尝试自动检测
            if sys.platform == "win32":
                possible = glob.glob("C:/Xilinx/Vivado/*/bin/vivado.bat")
            else:
                possible = glob.glob("/opt/Xilinx/Vivado/*/bin/vivado") + \
                          glob.glob("/tools/Xilinx/Vivado/*/bin/vivado")
            
            if possible:
                vivado_path = sorted(possible)[-1]  # 使用最新版本
                logger.info(f"自动检测到 Vivado: {vivado_path}")
            else:
                raise Exception("Vivado 路径未配置且未能自动检测，请运行 arixa --setup")
        
        return vivado_path
    
    def _run_vivado_tcl(self, tcl_commands: List[str], batch: bool = True) -> Dict:
        """执行 Vivado TCL 命令"""
        vivado_path = self._get_vivado_path()
        
        # 创建临时 TCL 脚本
        temp_dir = self.config.get("temp_dir") or tempfile.gettempdir()
        os.makedirs(temp_dir, exist_ok=True)
        tcl_file = os.path.join(temp_dir, "arixa_temp.tcl")
        
        # 写入 TCL 脚本
        tcl_script = "\n".join(tcl_commands)
        with open(tcl_file, 'w', encoding='utf-8') as f:
            f.write(tcl_script)
        
        logger.info(f"执行 TCL 脚本:\n{tcl_script}")
        
        # 构建命令
        cmd = [vivado_path, "-mode", "batch" if batch else "tcl", "-source", tcl_file]
        
        try:
            result = subprocess.run(
                cmd, 
                capture_output=True, 
                text=True, 
                timeout=3600,
                cwd=os.path.dirname(tcl_file)
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "tcl_script": tcl_script
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Vivado 执行超时（1小时）"}
        except FileNotFoundError:
            return {"success": False, "error": f"找不到 Vivado: {vivado_path}"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_vivado_create_project(self, params: Dict) -> Dict:
        """创建 Vivado 项目"""
        project_name = params["project_name"]
        project_path = os.path.expanduser(params["project_path"])
        part = params["part"]
        board = params.get("board", "")
        
        # 创建项目目录
        os.makedirs(project_path, exist_ok=True)
        
        tcl_commands = [
            f'create_project {project_name} "{project_path}/{project_name}" -part {part} -force',
        ]
        
        if board:
            tcl_commands.append(f'set_property board_part {board} [current_project]')
        
        # 创建基本目录结构
        tcl_commands.extend([
            'file mkdir src',
            'file mkdir sim', 
            'file mkdir constrs',
            'close_project',
            'exit'
        ])
        
        result = self._run_vivado_tcl(tcl_commands)
        
        if result["success"]:
            xpr_path = os.path.join(project_path, project_name, f"{project_name}.xpr")
            self.current_project = xpr_path
            result["project_path"] = xpr_path
            result["message"] = f"项目创建成功: {xpr_path}"
        
        return result
    
    def _handle_vivado_open_project(self, params: Dict) -> Dict:
        """打开项目"""
        project_path = os.path.expanduser(params["project_path"])
        
        if not os.path.exists(project_path):
            return {"success": False, "error": f"项目文件不存在: {project_path}"}
        
        self.current_project = project_path
        
        return {
            "success": True,
            "message": f"项目已打开: {project_path}",
            "project_path": project_path
        }
    
    def _handle_vivado_close_project(self, params: Dict) -> Dict:
        """关闭项目"""
        self.current_project = None
        return {"success": True, "message": "项目已关闭"}
    
    def _handle_vivado_add_sources(self, params: Dict) -> Dict:
        """添加源文件"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        files = params["files"]
        fileset = params.get("fileset", "sources_1")
        
        tcl_commands = [f'open_project "{self.current_project}"']
        
        for file_path in files:
            file_path = os.path.expanduser(file_path)
            if file_path.endswith(".xdc"):
                tcl_commands.append(f'add_files -fileset constrs_1 "{file_path}"')
            elif file_path.endswith((".v", ".sv", ".vhd")):
                tcl_commands.append(f'add_files -fileset {fileset} "{file_path}"')
            else:
                tcl_commands.append(f'add_files "{file_path}"')
        
        tcl_commands.extend(['close_project', 'exit'])
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_set_top(self, params: Dict) -> Dict:
        """设置顶层模块"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        top_module = params["top_module"]
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            f'set_property top {top_module} [current_fileset]',
            'update_compile_order -fileset sources_1',
            'close_project',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_synthesis(self, params: Dict) -> Dict:
        """运行综合"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        jobs = params.get("jobs", 4)
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            'reset_run synth_1',
            f'launch_runs synth_1 -jobs {jobs}',
            'wait_on_run synth_1',
            'close_project',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_implementation(self, params: Dict) -> Dict:
        """运行实现"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        jobs = params.get("jobs", 4)
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            f'launch_runs impl_1 -jobs {jobs}',
            'wait_on_run impl_1',
            'close_project',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_bitstream(self, params: Dict) -> Dict:
        """生成比特流"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        compress = params.get("compress", True)
        bin_file = params.get("bin_file", False)
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            'open_run impl_1',
        ]
        
        if compress:
            tcl_commands.append('set_property BITSTREAM.GENERAL.COMPRESS TRUE [current_design]')
        
        if bin_file:
            tcl_commands.append('write_cfgmem -format bin -interface spix4 -size 16 -loadbit "up 0x0 [get_property DIRECTORY [current_run]]/[get_property top [current_fileset]].bit" -file output.bin -force')
        
        tcl_commands.extend([
            'write_bitstream -force [get_property DIRECTORY [current_run]]/[get_property top [current_fileset]].bit',
            'close_project',
            'exit'
        ])
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_program(self, params: Dict) -> Dict:
        """烧录设备"""
        bitstream_path = params.get("bitstream_path", "")
        
        if not bitstream_path and self.current_project:
            # 尝试自动找到比特流文件
            project_dir = os.path.dirname(self.current_project)
            bit_files = glob.glob(os.path.join(project_dir, "**/*.bit"), recursive=True)
            if bit_files:
                bitstream_path = sorted(bit_files)[-1]
        
        if not bitstream_path or not os.path.exists(bitstream_path):
            return {"success": False, "error": "找不到比特流文件，请先生成比特流"}
        
        tcl_commands = [
            'open_hw_manager',
            'connect_hw_server -allow_non_jtag',
            'open_hw_target',
            'set device [lindex [get_hw_devices] 0]',
            'current_hw_device $device',
            f'set_property PROGRAM.FILE {{{bitstream_path}}} $device',
            'program_hw_devices $device',
            'close_hw_manager',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_simulation(self, params: Dict) -> Dict:
        """运行仿真"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        testbench = params["testbench"]
        sim_time = params.get("sim_time", "1us")
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            f'set_property top {testbench} [get_filesets sim_1]',
            'launch_simulation',
            f'run {sim_time}',
            'close_sim',
            'close_project',
            'exit'
        ]
        
        return self._run_vivado_tcl(tcl_commands)
    
    def _handle_vivado_report(self, params: Dict) -> Dict:
        """获取报告"""
        if not self.current_project:
            return {"success": False, "error": "没有打开的项目"}
        
        report_type = params["report_type"]
        
        report_commands = {
            "utilization": "report_utilization -return_string",
            "timing": "report_timing_summary -return_string",
            "power": "report_power -return_string",
            "drc": "report_drc -return_string"
        }
        
        if report_type not in report_commands:
            return {"success": False, "error": f"未知报告类型: {report_type}，支持: {list(report_commands.keys())}"}
        
        tcl_commands = [
            f'open_project "{self.current_project}"',
            'open_run impl_1',
            f'puts [' + report_commands[report_type] + ']',
            'close_project',
            'exit'
        ]
        
        result = self._run_vivado_tcl(tcl_commands)
        
        if result["success"]:
            result["report"] = result.get("stdout", "")
        
        return result
    
    def _handle_vivado_tcl(self, params: Dict) -> Dict:
        """执行自定义 TCL 命令"""
        commands = params["commands"]
        
        if self.current_project:
            commands.insert(0, f'open_project "{self.current_project}"')
            commands.append('close_project')
        
        commands.append('exit')
        
        return self._run_vivado_tcl(commands)

    # ==================== 文件操作处理函数 ====================
    
    def _handle_file_create(self, params: Dict) -> Dict:
        """创建文件"""
        file_path = os.path.expanduser(params["file_path"])
        content = params["content"]
        overwrite = params.get("overwrite", True)
        
        if os.path.exists(file_path) and not overwrite:
            return {"success": False, "error": f"文件已存在: {file_path}"}
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": f"文件已创建: {file_path}",
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_read(self, params: Dict) -> Dict:
        """读取文件"""
        file_path = os.path.expanduser(params["file_path"])
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            return {
                "success": True,
                "content": content,
                "file_path": file_path,
                "size": len(content)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_modify(self, params: Dict) -> Dict:
        """修改文件"""
        file_path = os.path.expanduser(params["file_path"])
        old_content = params["old_content"]
        new_content = params["new_content"]
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            if old_content not in content:
                return {"success": False, "error": "未找到要替换的内容"}
            
            new_file_content = content.replace(old_content, new_content, 1)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(new_file_content)
            
            return {
                "success": True,
                "message": "文件已修改",
                "file_path": file_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_append(self, params: Dict) -> Dict:
        """追加内容到文件"""
        file_path = os.path.expanduser(params["file_path"])
        content = params["content"]
        
        try:
            with open(file_path, 'a', encoding='utf-8') as f:
                f.write(content)
            
            return {
                "success": True,
                "message": "内容已追加",
                "file_path": file_path
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_delete(self, params: Dict) -> Dict:
        """删除文件"""
        file_path = os.path.expanduser(params["file_path"])
        
        if not os.path.exists(file_path):
            return {"success": False, "error": f"文件不存在: {file_path}"}
        
        try:
            os.remove(file_path)
            return {
                "success": True,
                "message": f"文件已删除: {file_path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_list(self, params: Dict) -> Dict:
        """列出目录内容"""
        dir_path = os.path.expanduser(params["dir_path"])
        pattern = params.get("pattern", "*")
        recursive = params.get("recursive", False)
        
        if not os.path.exists(dir_path):
            return {"success": False, "error": f"目录不存在: {dir_path}"}
        
        try:
            if recursive:
                search_pattern = os.path.join(dir_path, "**", pattern)
                files = glob.glob(search_pattern, recursive=True)
            else:
                search_pattern = os.path.join(dir_path, pattern)
                files = glob.glob(search_pattern)
            
            file_list = []
            for f in files:
                file_list.append({
                    "path": f,
                    "name": os.path.basename(f),
                    "is_dir": os.path.isdir(f),
                    "size": os.path.getsize(f) if os.path.isfile(f) else 0
                })
            
            return {
                "success": True,
                "files": file_list,
                "count": len(file_list)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_file_copy(self, params: Dict) -> Dict:
        """复制文件"""
        source = os.path.expanduser(params["source"])
        destination = os.path.expanduser(params["destination"])
        
        if not os.path.exists(source):
            return {"success": False, "error": f"源文件不存在: {source}"}
        
        try:
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            if os.path.isdir(source):
                shutil.copytree(source, destination)
            else:
                shutil.copy2(source, destination)
            
            return {
                "success": True,
                "message": f"已复制到: {destination}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_dir_create(self, params: Dict) -> Dict:
        """创建目录"""
        dir_path = os.path.expanduser(params["dir_path"])
        
        try:
            os.makedirs(dir_path, exist_ok=True)
            return {
                "success": True,
                "message": f"目录已创建: {dir_path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 系统工具处理函数 ====================
    
    def _handle_run_program(self, params: Dict) -> Dict:
        """运行已注册的程序"""
        program_name = params["program_name"]
        arguments = params.get("arguments", [])
        wait = params.get("wait", True)
        
        # 从配置获取程序路径
        program_path = self.config.get(f"programs.{program_name}.path")
        
        if not program_path:
            available = list(self.config.get("programs", {}).keys())
            return {
                "success": False, 
                "error": f"程序 '{program_name}' 未注册",
                "available_programs": available
            }
        
        program_path = os.path.expanduser(program_path)
        
        if not os.path.exists(program_path):
            return {"success": False, "error": f"程序路径不存在: {program_path}"}
        
        try:
            cmd = [program_path] + list(arguments)
            logger.info(f"运行程序: {' '.join(cmd)}")
            
            if wait:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
                return {
                    "success": result.returncode == 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "return_code": result.returncode
                }
            else:
                subprocess.Popen(cmd)
                return {
                    "success": True,
                    "message": f"程序已启动: {program_name}"
                }
                
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "程序执行超时"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def _handle_run_command(self, params: Dict) -> Dict:
        """运行系统命令"""
        command = params["command"]
        working_dir = params.get("working_dir", os.getcwd())
        timeout = params.get("timeout", 120)
        
        working_dir = os.path.expanduser(working_dir)
        
        # 安全检查 - 禁止危险命令
        dangerous_patterns = [
            'rm -rf /', 'rm -rf ~', 'rm -rf *',
            'format', 'mkfs',
            'dd if=/dev/zero',
            'del /s /q c:\\',
            ':(){ :|:& };:'  # fork bomb
        ]
        
        for pattern in dangerous_patterns:
            if pattern in command.lower():
                return {"success": False, "error": "安全限制: 不允许执行此命令"}
        
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                cwd=working_dir,
                timeout=timeout
            )
            
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
                "command": command
            }
        except subprocess.TimeoutExpired:
            return {"success": False, "error": f"命令执行超时 ({timeout}秒)"}
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
            "python_version": platform.python_version(),
            "current_dir": os.getcwd(),
            "home_dir": os.path.expanduser("~")
        }
    
    def _handle_list_programs(self, params: Dict) -> Dict:
        """列出已注册的程序"""
        programs = self.config.get("programs", {})
        
        program_list = []
        for name, info in programs.items():
            path = info.get("path", "") if isinstance(info, dict) else info
            exists = os.path.exists(os.path.expanduser(path)) if path else False
            program_list.append({
                "name": name,
                "path": path,
                "exists": exists
            })
        
        return {
            "success": True,
            "programs": program_list,
            "count": len(program_list)
        }
    
    def _handle_open_in_editor(self, params: Dict) -> Dict:
        """在编辑器中打开文件"""
        file_path = os.path.expanduser(params["file_path"])
        editor = params.get("editor", "vscode")
        
        # 获取编辑器路径
        editor_path = self.config.get(f"programs.{editor}.path")
        
        if not editor_path:
            # 尝试常见编辑器
            if sys.platform == "win32":
                default_editors = ["code", "notepad++", "notepad"]
            else:
                default_editors = ["code", "vim", "nano", "gedit"]
            
            for ed in default_editors:
                if shutil.which(ed):
                    editor_path = ed
                    break
        
        if not editor_path:
            return {"success": False, "error": "找不到可用的编辑器"}
        
        try:
            subprocess.Popen([editor_path, file_path])
            return {
                "success": True,
                "message": f"已在 {editor} 中打开: {file_path}"
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ==================== 代码生成处理函数 ====================
    
    def _handle_create_verilog(self, params: Dict) -> Dict:
        """创建 Verilog 模块"""
        module_name = params["module_name"]
        file_path = os.path.expanduser(params["file_path"])
        code = params["code"]
        
        return self._handle_file_create({
            "file_path": file_path,
            "content": code,
            "overwrite": True
        })
    
    def _handle_create_testbench(self, params: Dict) -> Dict:
        """创建测试台"""
        module_name = params["module_name"]
        file_path = os.path.expanduser(params["file_path"])
        code = params["code"]
        
        return self._handle_file_create({
            "file_path": file_path,
            "content": code,
            "overwrite": True
        })
    
    def _handle_create_constraints(self, params: Dict) -> Dict:
        """创建约束文件"""
        file_path = os.path.expanduser(params["file_path"])
        constraints = params["constraints"]
        
        return self._handle_file_create({
            "file_path": file_path,
            "content": constraints,
            "overwrite": True
        })

    # ==================== 服务器启动 ====================
    
    def start(self, host: str = "localhost", port: int = 8765):
        """启动 MCP 服务器（网络模式）"""
        
        async def handle_client(reader, writer):
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
            
            print(f"""
╔══════════════════════════════════════════════════════════╗
║           Arixa MCP Server 已启动                        ║
╠══════════════════════════════════════════════════════════╣
║  地址: {addr[0]}:{addr[1]:<43}║
║  工具数量: {len(self.tools):<46}║
╠══════════════════════════════════════════════════════════╣
║  按 Ctrl+C 停止服务器                                    ║
╚══════════════════════════════════════════════════════════╝
""")
            
            async with server:
                await server.serve_forever()
        
        try:
            asyncio.run(main())
        except KeyboardInterrupt:
            logger.info("服务器停止")
            print("\n服务器已停止")
