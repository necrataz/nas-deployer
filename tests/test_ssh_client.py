# ==============================================================================
# NASDeployer - SSH 客户端逻辑测试 (mock paramiko, 不连真 NAS)
# ==============================================================================

import sys
import os
from unittest.mock import MagicMock, patch
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_connection_success():
    """测试成功连接"""
    from ssh_client import NASConnection

    conn = NASConnection()

    with patch("paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        # 模拟 uname
        uname_stdout = MagicMock()
        uname_stdout.read.return_value = b"Linux fnos 6.18.18"
        uname_stderr = MagicMock()
        uname_stderr.read.return_value = b""

        # 模拟 docker --version
        docker_stdout = MagicMock()
        docker_stdout.read.return_value = b"Docker version 24.0.7"
        docker_stderr = MagicMock()
        docker_stderr.read.return_value = b""

        # 模拟 docker compose version
        compose_stdout = MagicMock()
        compose_stdout.read.return_value = b"Docker Compose version v2.21.0"
        compose_stderr = MagicMock()
        compose_stderr.read.return_value = b""

        # exec_command 第一次返回 uname, 第二次 docker, 第三次 docker compose
        mock_client.exec_command.side_effect = [
            (MagicMock(), uname_stdout, uname_stderr),
            (MagicMock(), docker_stdout, docker_stderr),
            (MagicMock(), compose_stdout, compose_stderr),
        ]
        uname_stdout.channel.recv_exit_status.return_value = 0
        docker_stdout.channel.recv_exit_status.return_value = 0
        compose_stdout.channel.recv_exit_status.return_value = 0

        ok, msg = conn.connect("192.168.3.88", 22, "necrata", "testpwd", "fnos")

        assert ok is True, f"Expected True, got {ok}"
        assert "fnos" in msg or "一切就绪" in msg, f"Got: {msg}"
        assert conn.host == "192.168.3.88"
        assert conn.user == "necrata"
        print("✅ test_connection_success")


def test_connection_auth_failure():
    """测试认证失败"""
    from ssh_client import NASConnection
    import paramiko

    conn = NASConnection()

    with patch("paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client
        mock_client.connect.side_effect = paramiko.AuthenticationException("auth failed")

        ok, msg = conn.connect("192.168.3.88", 22, "necrata", "wrongpwd", "fnos")

        assert ok is False
        assert "认证失败" in msg
        print("✅ test_connection_auth_failure")


def test_connection_no_docker():
    """测试连接成功但 docker 不可用"""
    from ssh_client import NASConnection

    conn = NASConnection()

    with patch("paramiko.SSHClient") as mock_cls:
        mock_client = MagicMock()
        mock_cls.return_value = mock_client

        uname_stdout = MagicMock()
        uname_stdout.read.return_value = b"Linux"
        uname_stderr = MagicMock()
        uname_stderr.read.return_value = b""
        uname_stdout.channel.recv_exit_status.return_value = 0

        docker_stdout = MagicMock()
        docker_stdout.read.return_value = b""
        docker_stderr = MagicMock()
        docker_stderr.read.return_value = b"command not found"
        docker_stdout.channel.recv_exit_status.return_value = 127

        mock_client.exec_command.side_effect = [
            (MagicMock(), uname_stdout, uname_stderr),
            (MagicMock(), docker_stdout, docker_stderr),
        ]

        ok, msg = conn.connect("192.168.3.88", 22, "necrata", "testpwd", "fnos")

        assert ok is False
        assert "Docker" in msg
        print("✅ test_connection_no_docker")


def test_run_command_with_sudo():
    """测试 sudo 命令执行 (v1.6: 包进 sh -c 让 cd 等 builtin 能跑)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = b"output"
    stderr = MagicMock()
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0

    mock_stdin = MagicMock()
    conn.client.exec_command.return_value = (mock_stdin, stdout, stderr)

    exit_code, output = conn.run_command("docker ps", sudo=True, timeout=10)

    # v1.6 fix: 应该包进 sh -c 让 cd 等 shell builtin 也能跑
    call_args = conn.client.exec_command.call_args
    actual_cmd = call_args[0][0]
    assert actual_cmd == "sudo -S sh -c 'docker ps'", f"Got: {actual_cmd}"
    # 应该写入密码
    mock_stdin.write.assert_called_with("testpwd\n")
    assert exit_code == 0
    assert "output" in output
    print("✅ test_run_command_with_sudo (v1.6: sh -c wrapper)")


def test_run_command_sudo_with_cd():
    """v1.6 fix: sudo + cd 现在能正常跑了 (包进 sh -c)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = b"OK"
    stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), stdout, MagicMock())

    # 类似 install_apps 的命令: cd /tmp/nas_deploy && docker compose pull
    cmd = "cd /tmp/nas_deploy && docker compose --profile movie pull"
    exit_code, output = conn.run_command(cmd, sudo=True, timeout=10)

    call_args = conn.client.exec_command.call_args
    actual_cmd = call_args[0][0]
    # 关键: 必须包进 sh -c 让 cd 能跑
    assert "sh -c" in actual_cmd, f"v1.6 fix: should wrap in sh -c, got: {actual_cmd}"
    assert "cd /tmp/nas_deploy" in actual_cmd
    assert "--profile movie" in actual_cmd
    print("✅ test_run_command_sudo_with_cd (v1.6 fix)")


def test_run_command_without_sudo():
    """测试普通命令执行 (不需要 sudo)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = b"hello"
    stderr = MagicMock()
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    mock_stdin = MagicMock()
    conn.client.exec_command.return_value = (mock_stdin, stdout, stderr)

    exit_code, output = conn.run_command("ls -la", sudo=False)

    call_args = conn.client.exec_command.call_args
    actual_cmd = call_args[0][0]
    assert actual_cmd == "ls -la", f"Got: {actual_cmd}"
    mock_stdin.write.assert_not_called()
    assert exit_code == 0
    print("✅ test_run_command_without_sudo")


def test_docker_cmd_uses_sudo():
    """v1.5 fix: _docker_cmd helper 自动加 sudo (v1.6 也包进 sh -c)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = b"OK"
    stdout.channel.recv_exit_status.return_value = 0
    mock_stdin = MagicMock()
    conn.client.exec_command.return_value = (mock_stdin, stdout, MagicMock())

    # _docker_cmd 内部调 run_command(sudo=True)
    exit_code, output = conn._docker_cmd("docker ps")

    # 验证命令: v1.6 包进 sh -c
    call_args = conn.client.exec_command.call_args
    actual_cmd = call_args[0][0]
    assert actual_cmd == "sudo -S sh -c 'docker ps'", f"v1.6 wrap, got: {actual_cmd}"

    # 验证 get_pty=True (sudo 需要 PTY)
    get_pty = call_args.kwargs.get("get_pty", call_args[1].get("get_pty") if len(call_args) > 1 else None)
    assert get_pty is True, f"sudo requires get_pty=True, got: {get_pty}"

    # 验证密码通过 stdin 发送了
    mock_stdin.write.assert_called_with("testpwd\n")
    print("✅ test_docker_cmd_uses_sudo (v1.5 sudo + v1.6 sh -c)")


def test_docker_cmd_skips_sudo_for_root():
    """_docker_cmd 不会给 root 加 sudo (不需要)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "root"  # root 用户
    conn.password = "x"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = b"OK"
    stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), stdout, MagicMock())

    conn._docker_cmd("docker ps")

    call_args = conn.client.exec_command.call_args
    actual_cmd = call_args[0][0]
    assert actual_cmd == "docker ps", f"root should skip sudo, got: {actual_cmd}"
    print("✅ test_docker_cmd_skips_sudo_for_root")


def test_install_apps_profile_mapping():
    """测试安装时正确解析 profile + v1.4 SFTP fix + v1.5 sudo"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"
    conn.client = MagicMock()
    conn.transport = MagicMock()
    conn.is_connected = MagicMock(return_value=True)

    # v1.4 fix: mock paramiko.SFTPClient.from_transport
    with patch("paramiko.SFTPClient.from_transport") as mock_from_transport:
        mock_sftp = MagicMock()
        mock_from_transport.return_value = mock_sftp
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__.return_value = mock_file

        # 模拟所有 docker 命令成功 (包括 mkdir)
        stdout = MagicMock()
        stdout.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        conn.client.exec_command.return_value = (MagicMock(), stdout, MagicMock())

        selected = ["moviepilot", "qbittorrent", "libretv", "dashy"]  # movie + nav profile
        ok, msg = conn.install_apps(selected, "dummy compose")

        assert ok is True, f"Got: {msg}"
        # 验证 compose 上传走的是 from_transport
        mock_from_transport.assert_called()

        # v1.5 fix: 验证 docker compose pull/up 命令都加 sudo
        all_cmds = [str(call.args[0]) for call in conn.client.exec_command.call_args_list]
        docker_cmds = [c for c in all_cmds if "docker compose" in c]
        assert len(docker_cmds) >= 2, f"Expected docker compose commands, got: {all_cmds}"
        for cmd in docker_cmds:
            assert "sudo -S " in cmd, \
                f"v1.5 fix: docker compose command should use sudo, got: {cmd}"

        # 验证执行的命令包含正确 profile
        cmd_str = " ".join(all_cmds)
        assert "--profile movie" in cmd_str, f"Missing movie profile in: {cmd_str}"
        assert "--profile nav" in cmd_str, f"Missing nav profile in: {cmd_str}"
        print("✅ test_install_apps_profile_mapping (v1.4 SFTP + v1.5 sudo)")


def test_install_apps_no_selection():
    """测试没选应用时的处理 + v1.4 SFTP fix + v1.5 sudo"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"  # v1.5: sudo 需要密码
    conn.client = MagicMock()
    conn.transport = MagicMock()
    conn.is_connected = MagicMock(return_value=True)

    # v1.4 fix: mock paramiko.SFTPClient.from_transport
    with patch("paramiko.SFTPClient.from_transport") as mock_from_transport:
        # mock mkdir 命令成功
        stdout = MagicMock()
        stdout.read.return_value = b""
        stdout.channel.recv_exit_status.return_value = 0
        conn.client.exec_command.return_value = (MagicMock(), stdout, MagicMock())
        mock_sftp = MagicMock()
        mock_from_transport.return_value = mock_sftp
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__.return_value = mock_file

        ok, msg = conn.install_apps([], "dummy")
        assert ok is False
        assert "没有需要启用" in msg
        print("✅ test_install_apps_no_selection (v1.4 fix)")


def test_container_parsing():
    """测试 docker ps 输出解析 (v1.5: docker 命令走 sudo, 需要 conn.password)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.password = "testpwd"  # v1.5: sudo 需要密码
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = (
        b"moviepilot|ghcr.io/...|Up 5 minutes|0.0.0.0:5000->5000/tcp\n"
        b"qbittorrent|linuxserver/qbittorrent:latest|Up 3 minutes|0.0.0.0:8080->8080/tcp"
    )
    stderr = MagicMock()
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), stdout, stderr)

    containers = conn.get_installed_containers()
    assert len(containers) == 2
    assert containers[0]["name"] == "moviepilot"
    assert containers[0]["ports"] == "0.0.0.0:5000->5000/tcp"
    assert containers[1]["name"] == "qbittorrent"
    print("✅ test_container_parsing")


def test_disk_space_parsing():
    """v1.4 fix: 测扫描所有 mount 取最大, 不再只看根分区"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.client = MagicMock()

    # 模拟 NAS 多 mount: 根 63G + vol1 1800G + 几个 tmpfs/overlay
    df_stdout = MagicMock()
    df_stdout.read.return_value = (
        b"Filesystem      1G-blocks  Used Available Use% Mounted on\n"
        b"/dev/sda1           63G   15G       48G  24% /\n"
        b"tmpfs               16G    1G       15G   6% /tmp\n"
        b"/dev/sda2         1800G  450G     1350G  25% /vol1\n"
        b"overlay            100G   20G       80G  20% /var/lib/docker/overlay2/...\n"
    )
    df_stderr = MagicMock()
    df_stderr.read.return_value = b""
    df_stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), df_stdout, df_stderr)

    used, total, percent = conn.check_disk_space()
    # v1.4 应该返回 vol1 (1800G) 而不是 root (63G)
    assert total == 1800, f"Expected 1800 (largest mount), got {total}"
    assert used == 450
    assert percent == 25
    print("✅ test_disk_space_parsing (v1.4: largest mount)")


def test_disk_space_only_root():
    """只有一个根 mount 时也能工作 (fallback)"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.client = MagicMock()

    df_stdout = MagicMock()
    df_stdout.read.return_value = (
        b"Filesystem      1G-blocks  Used Available Use% Mounted on\n"
        b"/dev/sda1          500G  120G      380G  24% /\n"
    )
    df_stderr = MagicMock()
    df_stderr.read.return_value = b""
    df_stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), df_stdout, df_stderr)

    used, total, percent = conn.check_disk_space()
    assert total == 500
    assert used == 120
    assert percent == 24
    print("✅ test_disk_space_only_root")


def test_memory_parsing():
    """测试 free -m 输出解析"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.user = "necrata"
    conn.client = MagicMock()

    stdout = MagicMock()
    stdout.read.return_value = (
        b"Mem:           7800        4200        1500         100        2100        3600"
    )
    stderr = MagicMock()
    stderr.read.return_value = b""
    stdout.channel.recv_exit_status.return_value = 0
    conn.client.exec_command.return_value = (MagicMock(), stdout, stderr)

    used, total, percent = conn.check_memory()
    assert total == 7800
    assert used == 4200
    assert percent == 53  # 4200/7800 ≈ 53
    print("✅ test_memory_parsing")


def test_upload_content():
    """v1.4 fix: 测试上传走 paramiko.SFTPClient.from_transport(transport) 而不是 self.transport.open_sftp()

    (paramiko Transport 没 open_sftp() 方法, 之前 Mock 测试假绿)
    """
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.transport = MagicMock()

    # Mock paramiko.SFTPClient.from_transport 来返回 mock SFTP
    with patch("paramiko.SFTPClient.from_transport") as mock_from_transport:
        mock_sftp = MagicMock()
        mock_from_transport.return_value = mock_sftp
        mock_file = MagicMock()
        mock_sftp.open.return_value.__enter__.return_value = mock_file

        ok, msg = conn.upload_content("test content", "/tmp/test.yml")

        assert ok is True, f"Got: {msg}"
        assert "/tmp/test.yml" in msg
        # 验证走的是 paramiko.SFTPClient.from_transport(transport)
        mock_from_transport.assert_called_once_with(conn.transport)
        mock_sftp.open.assert_called_with("/tmp/test.yml", "w")
        mock_file.write.assert_called_with("test content")
        # 验证 transport.open_sftp() 没被调 (paramiko 没用这个方法)
        conn.transport.open_sftp.assert_not_called()
        print("✅ test_upload_content (v1.4: paramiko.SFTPClient.from_transport)")


def test_disconnect():
    """测试断开连接"""
    from ssh_client import NASConnection

    conn = NASConnection()
    conn.client = MagicMock()
    conn.transport = MagicMock()
    client_ref = conn.client  # 保留引用, 因为 disconnect 后置 None

    conn.disconnect()
    client_ref.close.assert_called_once()  # close 应被调用一次
    assert conn.client is None
    assert conn.transport is None
    print("✅ test_disconnect")


def test_is_connected():
    """测试连接状态检查"""
    from ssh_client import NASConnection

    conn = NASConnection()
    assert conn.is_connected() is False

    conn.client = MagicMock()
    conn.transport = MagicMock()
    conn.transport.is_active.return_value = True
    assert conn.is_connected() is True

    conn.transport.is_active.return_value = False
    assert conn.is_connected() is False
    print("✅ test_is_connected")


if __name__ == "__main__":
    tests = [
        test_connection_success,
        test_connection_auth_failure,
        test_connection_no_docker,
        test_run_command_with_sudo,
        test_run_command_without_sudo,
        test_docker_cmd_uses_sudo,
        test_docker_cmd_skips_sudo_for_root,
        test_install_apps_profile_mapping,
        test_install_apps_no_selection,
        test_container_parsing,
        test_disk_space_parsing,
        test_disk_space_only_root,
        test_memory_parsing,
        test_upload_content,
        test_disconnect,
        test_is_connected,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"❌ {test.__name__}: {type(e).__name__}: {e}")
            failed += 1

    print()
    print(f"=== {passed} passed, {failed} failed, {len(tests)} total ===")
    sys.exit(0 if failed == 0 else 1)