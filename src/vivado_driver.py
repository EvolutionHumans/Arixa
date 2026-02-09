import subprocess
import os
import json

class VivadoDriver:
    def __init__(self, config_path="config.json"):
        self.vivado_path = "vivado" # 默认假设在 PATH 中
        if os.path.exists(config_path):
            with open(config_path, 'r') as f:
                config = json.load(f)
                self.vivado_path = config.get("vivado_binary_path", "vivado")

    def run_tcl(self, tcl_commands):
        """执行一段 Tcl 脚本"""
        cmd = [
            self.vivado_path, 
            "-mode", "batch", 
            "-nolog", "-nojournal", 
            "-source", "-" 
        ]
        
        try:
            # 将 Tcl 命令通过 stdin 传入
            process = subprocess.run(
                cmd, 
                input=tcl_commands.encode('utf-8'), 
                capture_output=True, 
                check=True
            )
            return process.stdout.decode('utf-8')
        except subprocess.CalledProcessError as e:
            return f"Error executing Vivado: {e.stderr.decode('utf-8')}"
        except FileNotFoundError:
            return "Error: Vivado executable not found. Please check config.json."

    def create_project(self, project_name, dir_path, part):
        tcl = f"""
        create_project {project_name} {dir_path} -part {part} -force
        close_project
        """
        return self.run_tcl(tcl)

    def add_source(self, project_path, file_path):
        tcl = f"""
        open_project {project_path}
        add_files {file_path}
        close_project
        """
        return self.run_tcl(tcl)

    def run_flow(self, project_path, step="all"):
        """运行综合、实现或比特流生成"""
        tcl = f"open_project {project_path}\n"
        
        if step in ["synth", "all"]:
            tcl += "reset_run synth_1\nlaunch_runs synth_1 -jobs 4\nwait_on_run synth_1\n"
        
        if step in ["impl", "all"]:
            tcl += "launch_runs impl_1 -jobs 4\nwait_on_run impl_1\n"
        
        if step in ["bitstream", "all"]:
            tcl += "launch_runs impl_1 -to_step write_bitstream -jobs 4\nwait_on_run impl_1\n"
            
        tcl += "close_project"
        return self.run_tcl(tcl)

    def get_run_status(self, project_path, run_name="synth_1"):
        tcl = f"""
        open_project {project_path}
        set status [get_property STATUS [get_runs {run_name}]]
        puts "STATUS_RESULT: $status"
        close_project
        """
        output = self.run_tcl(tcl)
        # 简单的解析逻辑
        for line in output.splitlines():
            if "STATUS_RESULT:" in line:
                return line.split(":")[1].strip()
        return output
