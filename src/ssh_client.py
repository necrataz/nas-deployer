# ==============================================================================
# NAS Deployer v1.8 - SSH + Docker 编排
# v1.7 新增:
#   1. run_command_streaming 新增 on_progress / progress_min / progress_max 参数
#   2. 解析 docker compose v2 输出 "Pulling X/Y" / "Downloading X MB / Y MB"
#   3. _size_unit helper 处理字节单位换算
# v1.8 新增:
#   1. pull_apps_streaming / install_apps_streaming 改 per-service pull, 失败 service 跳过
#   2. install 阶段只 up 成功拉到的 service
# ==============================================================================

import paramiko
from scp import SCPClient
from typing import Tuple, Optional, List, Dict
import io


# v1.7: 字节单位换算 (用于解析 docker compose 下载进度 "5MB/20MB")
def _size_unit(unit: str) -> int:
    """KB/MB/GB → 字节倍数, 未知单位返回 1 (避免除零)"""
    u = (unit or "").upper()
    if u == "KB":
        return 1024
    if u == "MB":
        return 1024 * 1024
    if u == "GB":
        return 1024 * 1024 * 1024
    return 1


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
    def _docker_cmd(self, cmd: str, timeout: int = 60) -> Tuple[int, str]:
        """跑 docker 命令, 自动 sudo (因为 docker socket 普通用户访问不了)

        v1.5 fix: 之前所有 docker 命令都没 sudo, fnOS 上 necrata 账号无 docker 组权限
        → 'dial unix /var/run/docker.sock: connect: permission denied'
        集中走这个 helper, 所有 docker 操作都自动加 sudo=True

        例外:
        - test_environment() 里的 'docker --version' / 'docker compose version' 不走这里
          (版本查询普通用户能跑, 加上 sudo 反而可能要求 TTY password)
        """
        return self.run_command(cmd, sudo=True, timeout=timeout)

    def run_command(self, command: str, sudo: bool = False, timeout: int = 60) -> Tuple[int, str]:
        """在远程执行命令, 可选 sudo

        v1.6 fix: sudo=True 时包进 sh -c '...' (让 cd 等 shell builtin 能运行)
        之前 'sudo -S cd /path && cmd' 会报 'cd: command not found'
        因为 sudo 不能直接执行 shell builtin
        """
        if not self.client:
            return -1, "未连接"

        use_sudo = sudo and self.user != "root"
        if use_sudo:
            # shell-escape 单引号: ' -> '"'"'
            escaped = command.replace("'", "'\"'\"'")
            actual_cmd = f"sudo -S sh -c '{escaped}'"
        else:
            actual_cmd = command

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

    def run_command_streaming(
        self,
        command: str,
        on_line,
        is_cancelled=None,
        sudo: bool = False,
        timeout: int = 60,
        on_progress=None,
        progress_min: float = 0.0,
        progress_max: float = 100.0,
    ) -> int:
        """流式执行命令, 每行通过 on_line 回调实时推送

        用于 v1.1+ 进度窗口的实时日志展示:
        - on_line(line: str) - 每收到一行输出调用一次
        - is_cancelled() -> bool - worker 线程轮询, 返回 True 时主动关闭 channel 中断命令
        - sudo - 是否用 sudo (v1.6 fix: 自动包进 sh -c 让 cd 等 builtin 跑)
        - timeout - 单行最长等待时间 (秒), 超时也退出循环

        v1.7 新增:
        - on_progress(percent, stage) - 可选回调, 解析 docker compose 输出中的
          "Pulling X/Y" / "X/Y MB" / "Downloading" 等行推算进度 (在 progress_min-max 内)
        - heartbeat: 长时间无新行时 (10s+) 不强制写, 但 on_line 应该外部调用 heartbeat()

        返回: 命令 exit_code (取消时返回 -1)
        """
        if not self.client:
            on_line("[ERROR] 未连接")
            return -1

        use_sudo = sudo and self.user != "root"
        if use_sudo:
            # v1.6 fix: 同 run_command, sudo 时包进 sh -c
            escaped = command.replace("'", "'\"'\"'")
            actual_cmd = f"sudo -S sh -c '{escaped}'"
        else:
            actual_cmd = command

        try:
            import re
            import time
            stdin, stdout, stderr = self.client.exec_command(
                actual_cmd, timeout=timeout, get_pty=use_sudo
            )

            if use_sudo:
                stdin.write(self.password + "\n")
                stdin.flush()

            # 逐行读 stdout (阻塞, 但 worker 线程所以不会冻 UI)
            start = time.time()
            exit_code = -1
            cancelled = False

            # v1.7: 进度解析状态
            pull_total = 0      # docker compose pull 输出 "Pulling fs layer" 总数
            pull_done = 0       # 已完成的 layer 数
            last_progress_pct = -1.0  # 上次推过的 percent, 避免重复推

            # docker compose 输出示例:
            #   "Pulling 3 / 4"                       (compose v2)
            #   "Pulling fs layer"                     (compose v1 / pull 阶段)
            #   "Downloading [==>     ]  5MB/20MB"     (compose pull)
            #   "Extracting [===>     ]  5MB/20MB"     (compose pull)
            #   "Pull complete"                        (完成一个 layer)
            RE_PULLING_V2 = re.compile(r"^\s*(\d+)\s*/\s*(\d+)\s*$")  # "3 / 4"
            RE_DL_PCT = re.compile(r"(\d+(?:\.\d+)?)\s*([KMG]?B)\s*/\s*(\d+(?:\.\d+)?)\s*([KMG]?B)")

            def _emit_progress(pct: float, stage: str):
                nonlocal last_progress_pct
                if on_progress is None:
                    return
                # 映射到 [progress_min, progress_max] 区间
                mapped = progress_min + (progress_max - progress_min) * (pct / 100.0)
                mapped = max(progress_min, min(progress_max, mapped))
                # 避免抖动 (相同 percent 不重复推)
                if abs(mapped - last_progress_pct) < 0.5:
                    return
                last_progress_pct = mapped
                try:
                    on_progress(mapped, stage)
                except Exception:
                    pass

            for line in iter(stdout.readline, ""):
                # 取消检查 (在每行之间)
                if is_cancelled and is_cancelled():
                    try:
                        stdout.channel.close()
                    except Exception:
                        pass
                    on_line("[INFO] 命令已被用户取消")
                    cancelled = True
                    break
                stripped = line.rstrip("\n")
                on_line(stripped)

                # v1.7: 解析 docker compose v2 的 "Pulling X / Y" 进度
                if on_progress is not None and pull_total > 0:
                    pass  # 状态走 pull_done / pull_total

                # "Pulling X / Y" — docker compose v2 主进度信号
                if "Pulling" in stripped and "/" in stripped:
                    m = RE_PULLING_V2.search(stripped.split("Pulling", 1)[-1])
                    if m:
                        cur, total = int(m.group(1)), int(m.group(2))
                        if total > pull_total:
                            pull_total = total
                        pct = (cur / total) * 100 if total else 0
                        # 镜像进度用 60% 区间, 留给后面 "启动容器" 阶段
                        _emit_progress(pct * 0.6, f"拉取镜像 {cur}/{total}")
                        # v1.7: 把 pull_done 同步到 cur (避免后面 Pull complete 倒退)
                        if cur > pull_done:
                            pull_done = cur

                # "Pull complete" / "Already up to date" — 单 layer 完成, 但不要倒退
                if ("Pull complete" in stripped or "Already up to date" in stripped) and pull_total > 0:
                    if pull_done < pull_total:
                        pull_done += 1
                    pct = (pull_done / pull_total) * 100
                    _emit_progress(pct * 0.6, f"拉取完成 {pull_done}/{pull_total}")

                # 下载/解压百分比 (单 layer 内部进度)
                if "Downloading" in stripped or "Extracting" in stripped:
                    m = RE_DL_PCT.search(stripped)
                    if m:
                        cur_v = float(m.group(1)) * _size_unit(m.group(2))
                        total_v = float(m.group(3)) * _size_unit(m.group(4))
                        if total_v > 0:
                            layer_pct = (cur_v / total_v) * 100
                            # 单 layer 进度作为辅助显示 (不覆盖 pulling X/Y)
                            _emit_progress(min(60, layer_pct * 0.6), stripped[:50])

                # 单行超时保护
                if time.time() - start > timeout:
                    on_line(f"[WARN] 命令超过 {timeout}s 超时, 中断读取")
                    try:
                        stdout.channel.close()
                    except Exception:
                        pass
                    break

            if not cancelled:
                # 尝试取 exit_code (可能因 channel 关闭而抛异常)
                try:
                    exit_code = stdout.channel.recv_exit_status()
                except Exception:
                    exit_code = -1

                # stderr 也读一下
                try:
                    for line in iter(stderr.readline, ""):
                        if line.strip():
                            on_line(f"[STDERR] {line.rstrip(chr(10))}")
                except Exception:
                    pass

            return exit_code

        except Exception as e:
            on_line(f"[EXCEPTION] {type(e).__name__}: {e}")
            return -1

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
        """直接上传字符串内容到远程文件

        v1.4 fix: 改用 paramiko.SFTPClient.from_transport(transport)
        之前用 self.transport.open_sftp() 是错的, paramiko Transport 没有这方法
        """
        if not self.transport:
            return False, "未连接"
        try:
            sftp = paramiko.SFTPClient.from_transport(self.transport)
            with sftp.open(remote_path, "w") as f:
                f.write(content)
            sftp.close()
            return True, f"已写入 {remote_path}"
        except Exception as e:
            return False, f"上传失败: {type(e).__name__}: {e}"

    # -------------------- Docker 操作 --------------------
    def get_installed_containers(self) -> List[Dict[str, str]]:
        """列出正在运行的容器 (v1.5: 走 sudo 因为 docker socket 权限)"""
        exit_code, output = self._docker_cmd(
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
        """列出所有容器（含停止的）, 用于状态展示 (v1.5: 走 sudo)"""
        exit_code, output = self._docker_cmd(
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

    def pull_apps_streaming(
        self,
        selected_apps: List[str],
        compose_content: str,
        on_line,
        on_progress,
        is_cancelled=None,
        profile_overrides: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """流式版 pull_apps, 只跑 docker compose pull 不启动容器

        用于 v1.1+ 进度窗口的实时日志展示
        (v1.4 拆自 install_apps_streaming, 之前 _pull_thread 用 echo 写假 compose 被 docker 当 YAML 解析崩)

        v1.8 fix: per-service 单独 pull, 失败的服务跳过不影响其他服务
        之前用 `docker compose --profile X pull` 一次性拉, 任一服务镜像拉不到 (网络慢/源挂)
        → 整批 abort, 后面已经 Pulled 的服务也不能用. 现在按 selected_apps 逐个 service 拉,
        失败的进 skipped 列表, 仍返回 True 让用户继续后续操作.

        on_line(line: str) - 每行输出
        on_progress(percent: float, stage: str) - 阶段进度
        is_cancelled() -> bool - worker 线程轮询
        """
        if not self.is_connected():
            return False, "未连接"

        # 1. 创建临时目录 + 上传真实 compose (v1.4 fix: 不能用 placeholder)
        on_progress(5, "准备远程目录...")
        remote_dir = "/tmp/nas_deploy"
        remote_compose = f"{remote_dir}/docker-compose.yml"

        exit_code, output = self.run_command(f"mkdir -p {remote_dir}")
        if exit_code != 0:
            return False, f"创建目录失败: {output}"

        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, f"上传 compose 失败: {msg}"

        # 2. 解析要拉取的 service (每个 app 一个 service)
        from apps import APPS
        services_to_pull = list(selected_apps)  # apps dict 的 key 就是 service 名
        if not services_to_pull:
            return False, "没有需要拉取的应用"

        # 3. 逐个 service 拉取 (v1.8)
        skipped = []   # 拉失败/取消的
        succeeded = []  # 拉成功的
        total = len(services_to_pull)
        for idx, svc in enumerate(services_to_pull):
            if is_cancelled and is_cancelled():
                return False, "用户取消"

            on_progress(5 + (idx / total) * 90, f"拉取 {svc} ({idx+1}/{total})...")
            on_line(f"\n=== 拉取 {svc} ({idx+1}/{total}) ===")

            pull_cmd = f"cd {remote_dir} && docker compose pull {svc}"
            exit_code = self.run_command_streaming(
                pull_cmd,
                on_line=on_line,
                is_cancelled=is_cancelled,
                sudo=True,
                timeout=600,
            )
            if is_cancelled and is_cancelled():
                return False, "用户取消"
            if exit_code != 0:
                on_line(f"[WARN] {svc} 拉取失败, 跳过")
                skipped.append(svc)
            else:
                succeeded.append(svc)

        on_progress(100, "完成")
        # 即便有 skipped 也返回 True (用户能继续操作已拉到的服务)
        # 但 msg 要明确告知哪些跳过
        if skipped:
            msg = (
                f"已拉取 {len(succeeded)} 个, 跳过 {len(skipped)} 个: "
                f"{', '.join(skipped)}"
            )
            return True, msg
        return True, f"已拉取 {len(succeeded)} 个: {', '.join(succeeded)}"

    def install_apps_streaming(
        self,
        selected_apps: List[str],
        compose_content: str,
        on_line,
        on_progress,
        is_cancelled=None,
        profile_overrides: Optional[List[str]] = None,
    ) -> Tuple[bool, str]:
        """流式版 install_apps, 用于 v1.1+ 进度窗口实时日志

        流程:
        1. 上传 docker-compose.yml (快)
        2. docker compose pull (慢, 实时日志, 失败 service 跳过)  ← v1.8 改 per-service
        3. docker compose up -d 已拉到镜像的 service (慢, 实时日志)

        on_line(line: str) - 每行输出
        on_progress(percent: float, stage: str) - 阶段进度 (0-100)
        is_cancelled() -> bool - worker 线程轮询
        """
        if not self.is_connected():
            return False, "未连接"

        # 1. 创建临时目录
        on_progress(5, "准备远程目录...")
        remote_dir = "/tmp/nas_deploy"
        exit_code, output = self.run_command(f"mkdir -p {remote_dir}")
        if exit_code != 0:
            return False, f"创建目录失败: {output}"

        # 2. 上传 compose 文件
        on_progress(10, "上传 docker-compose.yml...")
        remote_compose = f"{remote_dir}/docker-compose.yml"
        ok, msg = self.upload_content(compose_content, remote_compose)
        if not ok:
            return False, f"上传 compose 失败: {msg}"

        # 3. 解析需要启用的 profile (v1.8: 改成逐 service)
        from apps import APPS
        services_to_install = list(selected_apps)
        if not services_to_install:
            return False, "没有需要安装的应用"

        # 4. 拉取镜像 (10%-60%) (v1.8 per-service, 失败跳过)
        on_progress(15, f"拉取 {len(services_to_install)} 个服务...")
        skipped = []
        succeeded_pull = []
        total = len(services_to_install)
        for idx, svc in enumerate(services_to_install):
            if is_cancelled and is_cancelled():
                return False, "用户取消"
            on_line(f"\n=== 拉取 {svc} ({idx+1}/{total}) ===")
            pull_cmd = f"cd {remote_dir} && docker compose pull {svc}"
            exit_code = self.run_command_streaming(
                pull_cmd,
                on_line=on_line,
                is_cancelled=is_cancelled,
                sudo=True,
                timeout=600,
            )
            if is_cancelled and is_cancelled():
                return False, "用户取消"
            if exit_code != 0:
                on_line(f"[WARN] {svc} 拉取失败, 跳过")
                skipped.append(svc)
            else:
                succeeded_pull.append(svc)

        if not succeeded_pull:
            on_progress(100, "全部镜像拉取失败")
            return False, f"全部 {len(skipped)} 个服务镜像拉取都失败: {', '.join(skipped)}"

        # 5. 启动容器 (60%-95%) (v1.8: 只 up 成功拉到的 service)
        on_progress(60, "启动容器...")
        services_str = " ".join(succeeded_pull)
        up_cmd = f"cd {remote_dir} && docker compose up -d {services_str}"
        exit_code = self.run_command_streaming(
            up_cmd,
            on_line=on_line,
            is_cancelled=is_cancelled,
            sudo=True,
            timeout=600,
            on_progress=on_progress,
            progress_min=60.0,
            progress_max=95.0,
        )
        if is_cancelled and is_cancelled():
            return False, "用户取消"
        if exit_code != 0:
            return False, f"启动失败 (exit={exit_code})"

        on_progress(100, "完成")
        msg = f"已启动 {len(succeeded_pull)} 个服务"
        if skipped:
            msg += f", 跳过 {len(skipped)} 个 (镜像拉取失败): {', '.join(skipped)}"
        # v1.8: 即便有 skipped 也返回 True (用户拿到的是「能用的部分」)
        return True, msg

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

        # 4. 拉取镜像 (后台执行, 加快启动) (v1.5: sudo)
        profiles_str = " ".join(f"--profile {p}" for p in profiles_to_enable)
        pull_cmd = f"cd {remote_dir} && docker compose {profiles_str} pull"
        exit_code, output = self._docker_cmd(pull_cmd, timeout=900)
        if exit_code != 0:
            return False, f"拉取镜像失败: {output}"

        # 5. 启动容器 (v1.5: sudo)
        up_cmd = f"cd {remote_dir} && docker compose {profiles_str} up -d"
        exit_code, output = self._docker_cmd(up_cmd, timeout=600)
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
        exit_code, output = self._docker_cmd(stop_cmd, timeout=300)
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
        exit_code, output = self._docker_cmd(restart_cmd, timeout=300)
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
        exit_code, output = self._docker_cmd(pull_cmd, timeout=1800)
        return exit_code == 0, output

    def get_container_logs(self, container_name: str, tail: int = 100) -> str:
        """获取容器最近 N 行日志 (v1.5: 走 sudo)"""
        exit_code, output = self._docker_cmd(f"docker logs --tail {tail} {container_name}", timeout=30)
        return output if exit_code == 0 else f"获取日志失败: {output}"

    def check_disk_space(self) -> Tuple[int, int, int]:
        """返回最大文件系统的 (used_gb, total_gb, percent)

        v1.4 fix: 之前用 "df -BG /" 只看根分区 (e.g. 系统盘 63G),
        但 NAS 大容量硬盘通常挂载在 /vol1, /vol2, /mnt/disk1 等
        → 现在扫所有 mount 取最大的, 才是用户真正关心的容量
        """
        exit_code, output = self.run_command("df -BG", timeout=10)
        if exit_code != 0:
            return 0, 0, 0

        best_used = best_total = best_percent = 0
        for line in output.strip().split("\n"):
            parts = line.split()
            if len(parts) < 5:
                continue
            # 跳 header
            if parts[0].lower() == "filesystem":
                continue
            # 跳虚拟 / tmpfs / overlay (e.g. Docker overlay2)
            mount = parts[5] if len(parts) > 5 else ""
            if mount.startswith("/proc") or mount.startswith("/sys") or mount == "/dev" or mount == "/dev/shm":
                continue
            # 跳 tmpfs / overlay / squashfs
            fstype_hint = parts[0]
            if any(fs in fstype_hint.lower() for fs in ["tmpfs", "overlay", "squashfs", "devtmpfs"]):
                continue
            try:
                total = int(parts[1].rstrip("G"))
                used = int(parts[2].rstrip("G"))
                percent_str = parts[4].rstrip("%")
                percent = int(percent_str)
                if total > best_total:
                    best_total = total
                    best_used = used
                    best_percent = percent
            except (ValueError, IndexError):
                continue

        return best_used, best_total, best_percent

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