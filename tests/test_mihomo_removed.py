"""
v2.0.6 回归测试: mihomo 已从 APPS 和 PROFILES 移除
- 验证 'mihomo' 不在 apps.APPS dict 里 (UI 勾选列表找不到)
- 验证 'net' 不在 apps.PROFILES dict 里 (profile 列表找不到)
- 验证 mihomo service 仍在 compose_data (供首页 VPN 卡片用)
"""
import sys
from pathlib import Path

# 让 tests/ 能 import src/
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def test_mihomo_not_in_apps():
    from apps import APPS
    assert "mihomo" not in APPS, (
        "v2.0.6: mihomo 应该从 APPS dict 移除, "
        "改走首页 VPN 一键安装卡片 (避免出现在应用勾选列表)"
    )


def test_net_profile_not_in_profiles():
    from apps import PROFILES
    assert "net" not in PROFILES, (
        "v2.0.6: 'net' profile 应该移除, "
        "(mihomo 唯一入口 = 首页 VPN 卡片)"
    )


def test_mihomo_service_in_compose():
    """v2.0.6: mihomo service 仍必须在 compose_data 里 (首页 VPN 卡片依赖)"""
    from compose_data import DOCKER_COMPOSE_YML
    assert "mihomo:" in DOCKER_COMPOSE_YML, (
        "v2.0.6: mihomo service 必须在 compose_data, "
        "供首页 VPN 卡片调 install_apps_streaming(['mihomo']) 使用"
    )
    # 验证 net profile 不再被 mihomo 引用
    # (只允许 'all', 不允许 'net')
    mihomo_block = DOCKER_COMPOSE_YML.split("mihomo:")[1].split("  ")[0:10]
    mihomo_block_str = "\n".join(mihomo_block)
    assert '"net"' not in mihomo_block_str, (
        "v2.0.6: mihomo service 不应再引用 'net' profile"
    )


def test_mihomo_sub_param_still_works():
    """v2.0.6: install_apps_streaming 的 mihomo_subscription_url 参数保留
    (首页 VPN 卡片仍传入订阅 URL)
    """
    import inspect
    from ssh_client import NASConnection
    sig = inspect.signature(NASConnection.install_apps_streaming)
    assert "mihomo_subscription_url" in sig.parameters, (
        "v2.0.6: install_apps_streaming 必须保留 mihomo_subscription_url 参数, "
        "供 _quick_install_vpn 传订阅 URL"
    )


def test_mihomo_yaml_builder_still_works():
    """v2.0.6: mihomo yaml 生成函数仍存在 (首页 VPN 卡片写 config.yaml 用)"""
    from ssh_client import _build_mihomo_config_from_subscription
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    assert "port: 7890" in cfg
    # v2.0.6 新增: BT 端口 49152-65535 屏蔽
    assert "49152-65535" in cfg, (
        "v2.0.6: BT 动态端口 49152-65535 必须 REJECT (防 BT 客户端绕过固定端口屏蔽)"
    )


def test_quick_install_vpn_method_exists():
    """v2.0.6: app.py 必须有 _quick_install_vpn 一键方法"""
    # 不能直接 import app.py (会启动 tkinter mainloop)
    # 改用 ast 静态分析
    import ast
    from pathlib import Path
    src_path = Path(__file__).parent.parent / "src" / "app.py"
    tree = ast.parse(src_path.read_text(encoding="utf-8"))
    method_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    assert "_quick_install_vpn" in method_names, (
        "v2.0.6: app.py 必须有 _quick_install_vpn 一键方法"
    )


def test_uninstall_accepts_mihomo():
    """v2.0.6 回归: 卸载不能因 mihomo 不在 APPS 而拒绝
    (用户报: '卸载识别不到mihomo, 显示没有有效的应用')
    """
    import inspect
    from ssh_client import NASConnection
    src = inspect.getsource(NASConnection.uninstall_apps)
    # 不应再过滤 APPS dict
    assert "if a in APPS" not in src, (
        "v2.0.6: uninstall_apps 不应再用 'if a in APPS' 过滤, "
        "(mihomo 已从 APPS 移除, 但卸载仍要能用)"
    )


def test_uninstall_panel_guess_host_mode():
    """v2.0.6 回归: host 网络模式容器显示端口提示而不是 '(无端口)'
    (用户报: 'mihomo为什么显示无端口')
    """
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

    # 不直接实例化 UninstallPanel (需要 tkinter parent), 用类方法静态分析
    import inspect
    from uninstall_panel import UninstallPanel
    assert hasattr(UninstallPanel, "_guess_network_mode"), (
        "v2.0.6: UninstallPanel 必须有 _guess_network_mode 方法"
    )
    # 方法签名
    sig = inspect.signature(UninstallPanel._guess_network_mode)
    assert "container_name" in sig.parameters


def test_uninstall_panel_host_mode_display():
    """v2.0.6: _guess_network_mode('mihomo') 应返回 host 模式提示"""
    # 不实例化 panel (会触发 ttkbootstrap 初始化, CI 无 display 会挂)
    # 改用 inspect 提取方法逻辑, 直接验证 HOST_MODE_SERVICES 字典内容
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    import inspect
    from uninstall_panel import UninstallPanel

    src = inspect.getsource(UninstallPanel._guess_network_mode)
    assert "mihomo" in src and "7890" in src, (
        "v2.0.6: _guess_network_mode 应 hardcode mihomo 端口提示"
    )
    assert "无端口" in src, (
        "v2.0.6: 未知服务仍应显示 (无端口)"
    )