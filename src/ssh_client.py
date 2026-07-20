# ==============================================================================
# NAS 一键部署工具 - SSH + Docker 编排
# ==============================================================================

import paramiko
from scp import SCPClient
from typing import Tuple, Optional, List, Dict
import io


class NASConnection:
    """管理到 NAS 的 SSH 连接和 Docker 命令执行"""

    def __init__(self):
        self.client: Optional[paramiko.SSHClient] = None
        self.transport: Optional[paramiko.Transport] = None
        self.host: Optional[str] = None
        self.port: int = 22
        self.user: Optional[str] = None
        self.password: Optional[str] = None
        self.os_type: str = "fnos"  # 'fnos' or 'zspace'

    # -------------------- 连接 --------------------
    def connect(self, host: str, port: int, user: str, password: str, os_type: str = "fnos") -> Tuple[bool, str]:
        """建立 SSH 连接并验证 Docker 可用性"""
        try:
            self.client = paramiko.SSHClient()
            self.client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.client.connect(
                hostname=host,
                port=port,
                username=user,
                password=password,
                timeout=15,
                look_for_keys=False,
                allow_agent=False,
                banner_timeout=30,
            )
            self.transport = self.client.get_transport()
            self.host = host
            self.port = port
            self.user = user
            self.password = password
            self.os_type = os_type

            return self.test_environment()
        except paramiko.AuthenticationException:
            return False, "认证失败: 用户名或密码错误"
        except paramiko.SSHException as e:
            return False, f"SSH 错误: {e}"
        except Exception as e:
            return False, f"连接失败: {type(e).__name__}: {e}"

    def disconnect(self):
        """关闭连接"""
        try:
            if self.client:
                self.client.close()
        except Exception:
            pass
        self.client = None
        self.transport = None
        self.host = None
        self.user = None
        self.password = None

    def is_connected(self) -> bool:
        return self.client is not None and self.transport is not None and self.transport.is_active()

    # -------------------- 环境检测 --------------------
    def test_environment(self) -> Tuple[bool, str]:
        """检测 uname + docker + docker compose"""
        if not self.client:
            return False, "未连接"

        # 1. uname
        exit_code, output = self.run_command("uname -a", timeout=10)
        if exit_code != 0:
            return False, f"uname 失败: {output}"
        uname_out = output.strip().split('\n')[0] if output.strip() else "unknown"

        # 2. docker
        exit_code, output = self.run_command("docker --version", timeout=10)
        docker_out = ""
        if exit_code == 0:
            docker_out = output.strip().split('\n')[0]
        else:
            # 尝试 sudo
            exit_code, output = self.run_command("docker --version", sudo=True, timeout=10)
            if exit_code == 0:
                docker_out = output.strip().split('\n')[0]
            else:
                return False, "Docker 未安装或不可用"

        # 3. docker compose
        exit_code, output = self.run_command("docker compose version", timeout=10)
        compose_out = ""
        if exit_code == 0:
            compose_out = output.strip().split('\n')[0]
        else:
            # 尝试 legacy docker-compose
            exit_code, output = self.run_command("docker-compose --version", timeout=10)
            if exit_code == 0:
                compose_out = output.strip().split('\n')[0]
            else:
                return False, "Docker Compose 未安装"

        return True, f"✅ 一切就绪\nOS: {uname_out}\nDocker: {docker_out}\nCompose: {compose_out}"

    # -------------------- 命令执行 --------------------
    def run_command(self, command: str, sudo: bool = False, timeout: int = 60) -> Tuple[int, str]:
        """在远程执行命令, 可选 sudo"""
        if not self.client:
            return -1, "未连接"

        use_sudo = sudo and self.user != "root"
        actual_cmd = f"sudo -S {command}" if use_sudo else command

        try:
            stdin, stdout, stderr = self.client.exec_command(actual_cmd, timeout=timeout, get_pty=use_sudo)

            # sudo 需要通过 stdin 提供密码
            if use_sudo:
                stdin.write(self.password + "\n")
                stdin.flush()

            out = stdout.read().decode("utf-8", errors="replace")
            err = stderr.read().decode("utf-8", errors="replace")
            exit_code = stdout.channel.recv_exit_status()
            return exit_code, out + (("\n" + err) if err else "")
        except Exception as e:
            return -1, f"执行异常: {type(e).__name__}: {e}"

    # -------------------- 文件传输 --------------------
    def upload_file(self, local_path: str, remote_path: str) -> Tuple[bool, str]:
        """SCP 上传文件"""
        if not self.transport:
            return False, "未连接"
        try:
            with SCPClient(self.transport) as scp:
                scp.put(local_path, remote_path)
            return True, f"已上传 {remote_path}"
        except Exception as e:
            return False, f"上传失败: {e}"

    def upload_content(self, content: str, remote_path: str) -> Tuple[bool, str]:
        """直接上传字符串内容到远程文件"""
        if not self.transport:
            return False, "未连接"
        try:
            sftp = self.transport.open_sftp()
            with sftp.open(remote_path, "w") as f:
                f.write(content)
            sftp.close()
            return True, f"已写入 {remote_path}"
        except Exception as e:
            return False, f"上传失败: {e}"

    # -------------------- Docker 操作 --------------------
    def get_installed_containers(self) -> List[Dict[str, str]]:
        """列出正在运行的容器"""
        exit_code, output = self.run_command(
            'docker ps --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"'
        )
        containers = []
        if exit_code != 0:
            return containers

        for line in output.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            containers.append({
                "name": parts[0] if len(parts) > 0 else "",
                "image": parts[1] if len(parts) > 1 else "",
                "status": parts[2] if len(parts) > 2 else "",
                "ports": parts[3] if len(parts) > 3 else "",
            })
        return containers

    def get_all_apps_status(self) -> List[Dict[str, str]]:
        """列出所有容器（含停止的）, 用于状态展示"""
        exit_code, output = self.run_command(
            'docker ps -a --format "{{.Names}}|{{.Image}}|{{.Status}}|{{.Ports}}"'
        )
        containers = []
        if exit_code != 0:
            return containers
        for line in output.strip().split("\n"):
            if not line or "|" not in line:
                continue
            parts = line.split("|")
            containers.append({
                "name": parts[0] if len(parts) > 0 else "",
                "image": parts[1] if len(parts) > 1 else "",
                "status": parts[2] if len(parts) > 2 else "",
                "ports": parts[3] if len(parts) > 3 else "",
            })
        return containers

    def install_apps(self, selected_apps: List[str], compose_content: str, profile_overrides: Optional[List[str]] = None) -> Tuple[bool, str]:
        """通过 docker compose 部署选中的应用

        流程:
        1. 上传 docker-compose.yml 到远程临时目录
        2. 解析选中的应用对应的 profile 列表
        3. 用 docker compose --profile X up -d 启动
        """
        if not self.is_connected():
            return False, "未连接"

        # 1. 创建临时目录
        remote_dir = "/tmp/nas_deploy"
        exit_code, output = self.run_command(f"mkdir -p {remote_dir}")
        if exit_code != 0:
            return False, f"创建目录失败: {output}"

        # 2. 上传 compose 文件
        remote_compose = f"{remote_dir}/docker-compose.yml"
        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, f"上传 compose 失败: {msg}"

        # 3. 解析需要启用的 profile
        from apps import APPS, PROFILES
        profiles_to_enable = set()
        if profile_overrides:
            profiles_to_enable.update(profile_overrides)
        else:
            for app_key in selected_apps:
                if app_key in APPS:
                    profiles_to_enable.add(APPS[app_key]["profile"])

        if not profiles_to_enable:
            return False, "没有需要启用的 profile"

        # 4. 拉取镜像 (后台执行, 加快启动)
        profiles_str = " ".join(f"--profile {p}" for p in profiles_to_enable)
        pull_cmd = f"cd {remote_dir} && docker compose {profiles_str} pull"
        exit_code, output = self.run_command(pull_cmd, timeout=900)
        if exit_code != 0:
            return False, f"拉取镜像失败: {output}"

        # 5. 启动容器
        up_cmd = f"cd {remote_dir} && docker compose {profiles_str} up -d"
        exit_code, output = self.run_command(up_cmd, timeout=600)
        if exit_code != 0:
            return False, f"启动失败: {output}"

        # 6. 清理 (可选 - 保留 compose 便于后续修改)
        # self.run_command(f"rm -rf {remote_dir}")

        return True, f"已启动 profiles: {', '.join(sorted(profiles_to_enable))}\n\n{output}"

    def stop_apps(self, selected_apps: List[str], compose_content: str) -> Tuple[bool, str]:
        """停止选中的应用 (profile 级别)"""
        if not self.is_connected():
            return False, "未连接"

        from apps import APPS
        profiles_to_stop = set()
        for app_key in selected_apps:
            if app_key in APPS:
                profiles_to_stop.add(APPS[app_key]["profile"])

        if not profiles_to_stop:
            return False, "没有选中的应用"

        remote_dir = "/tmp/nas_deploy"
        remote_compose = f"{remote_dir}/docker-compose.yml"
        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, msg

        profiles_str = " ".join(f"--profile {p}" for p in profiles_to_stop)
        stop_cmd = f"cd {remote_dir} && docker compose {profiles_str} stop"
        exit_code, output = self.run_command(stop_cmd, timeout=300)
        return exit_code == 0, output

    def restart_apps(self, selected_apps: List[str], compose_content: str) -> Tuple[bool, str]:
        """重启选中的应用"""
        if not self.is_connected():
            return False, "未连接"

        from apps import APPS
        profiles_to_restart = set()
        for app_key in selected_apps:
            if app_key in APPS:
                profiles_to_restart.add(APPS[app_key]["profile"])

        if not profiles_to_restart:
            return False, "没有选中的应用"

        remote_dir = "/tmp/nas_deploy"
        remote_compose = f"{remote_dir}/docker-compose.yml"
        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, msg

        profiles_str = " ".join(f"--profile {p}" for p in profiles_to_restart)
        restart_cmd = f"cd {remote_dir} && docker compose {profiles_str} restart"
        exit_code, output = self.run_command(restart_cmd, timeout=300)
        return exit_code == 0, output

    def pull_images(self, selected_apps: List[str], compose_content: str) -> Tuple[bool, str]:
        """拉取最新镜像"""
        if not self.is_connected():
            return False, "未连接"

        from apps import APPS
        profiles_to_pull = set()
        for app_key in selected_apps:
            if app_key in APPS:
                profiles_to_pull.add(APPS[app_key]["profile"])

        if not profiles_to_pull:
            return False, "没有选中的应用"

        remote_dir = "/tmp/nas_deploy"
        remote_compose = f"{remote_dir}/docker-compose.yml"
        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, msg

        profiles_str = " ".join(f"--profile {p}" for p in profiles_to_pull)
        pull_cmd = f"cd {remote_dir} && docker compose {profiles_str} pull"
        exit_code, output = self.run_command(pull_cmd, timeout=1800)
        return exit_code == 0, output

    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """获取容器最近 N 行日志"""
        exit_code, output = self.run_command(f"docker logs --tail {tail} {container_name}", timeout=30)
        return output if exit_code == 0 else f"获取日志失败: {output}"

    def check_disk_space(self) -> Tuple[int, int, int]:
        """返回 (used_gb, total_gb, percent)"""
        exit_code, output = self.run_command("df -BG / | tail -1", timeout=10)
        if exit_code != 0:
            return 0, 0, 0
        # 解析最后一行: /dev/sda1  100G  50G  50G  50%  /
        # 必须取最后一行 (不要被 header line 污染)
        last_line = output.strip().split("\n")[-1]
        parts = last_line.split()
        if len(parts) >= 5:
            try:
                total = int(parts[1].rstrip("G"))
                used = int(parts[2].rstrip("G"))
                percent = int(parts[4].rstrip("%"))
                return used, total, percent
            except (ValueError, IndexError):
                pass
        return 0, 0, 0

    def check_memory(self) -> Tuple[int, int, int]:
        """返回 (used_mb, total_mb, percent)"""
        exit_code, output = self.run_command("free -m | grep Mem", timeout=10)
        if exit_code != 0:
            return 0, 0, 0
        parts = output.split()
        if len(parts) >= 3:
            try:
                total = int(parts[1])
                used = int(parts[2])
                percent = int(used * 100 / total) if total > 0 else 0
                return used, total, percent
            except (ValueError, IndexError):
                pass
        return 0, 0, 0