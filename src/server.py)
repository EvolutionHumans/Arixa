from mcp.server.fastmcp import FastMCP
from .vivado_driver import VivadoDriver
import os

# 初始化 Arixa MCP 服务
mcp = FastMCP("Arixa Vivado Assistant")
driver = VivadoDriver()

@mcp.tool()
def create_fpga_project(name: str, location: str, part: str) -> str:
    """
    创建一个新的 Vivado FPGA 项目。
    Args:
        name: 项目名称 (例如: blink_led)
        location: 项目文件夹的完整路径
        part: FPGA 芯片型号 (例如: xc7z020clg400-1)
    """
    return driver.create_project(name, location, part)

@mcp.tool()
def add_verilog_file(project_path: str, file_content: str, file_name: str) -> str:
    """
    创建并添加一个 Verilog 文件到项目中。
    Args:
        project_path: .xpr 项目文件的完整路径
        file_content: Verilog 源代码内容
        file_name: 文件名 (例如: top.v)
    """
    # 1. 将 AI 生成的代码写入本地文件
    source_dir = os.path.dirname(project_path)
    file_full_path = os.path.join(source_dir, file_name)
    
    try:
        with open(file_full_path, "w") as f:
            f.write(file_content)
    except Exception as e:
        return f"Failed to write file locally: {str(e)}"

    # 2. 调用 Vivado 添加文件
    return driver.add_source(project_path, file_full_path)

@mcp.tool()
def run_synthesis(project_path: str) -> str:
    """
    对指定的项目运行综合 (Synthesis)。这可能需要几分钟。
    """
    return driver.run_flow(project_path, step="synth")

@mcp.tool()
def run_implementation_and_bitstream(project_path: str) -> str:
    """
    运行实现 (Implementation) 并生成比特流 (Bitstream)。必须先完成综合。
    """
    return driver.run_flow(project_path, step="bitstream")

@mcp.tool()
def check_project_status(project_path: str) -> str:
    """
    检查当前项目的综合或实现状态。
    """
    return driver.get_run_status(project_path)

if __name__ == "__main__":
    # 使用 stdio 模式运行，这是 MCP 的标准本地通信方式
    mcp.run()
