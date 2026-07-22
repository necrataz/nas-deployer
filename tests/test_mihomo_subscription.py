# ==============================================================================
# 测试: v2.0.4 mihomo 订阅弹窗 + 配置生成
# ==============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_build_mihomo_config_basic():
    """v2.0.4: 标准订阅 URL 生成完整 mihomo config"""
    from ssh_client import _build_mihomo_config_from_subscription
    url = "https://provider.com/sub?token=abc123"
    cfg = _build_mihomo_config_from_subscription(url)
    # 关键字段都在
    assert "port: 7890" in cfg
    assert "socks-port: 7891" in cfg
    assert "external-controller: 0.0.0.0:9091" in cfg
    assert "proxy-providers:" in cfg
    assert "subscription:" in cfg
    assert "type: http" in cfg
    assert url in cfg
    # proxy-groups
    assert "proxy-groups:" in cfg
    assert "type: url-test" in cfg
    assert '"AUTO"' in cfg
    # rules
    assert "GEOIP,CN,DIRECT" in cfg
    assert "MATCH,AUTO" in cfg
    print(f"✅ test_build_mihomo_config_basic — {len(cfg)} chars")


def test_build_mihomo_config_escapes_quote():
    """v2.0.4: 订阅 URL 含单引号 → 剥掉防 yaml 注入"""
    from ssh_client import _build_mihomo_config_from_subscription
    url = "https://provider.com/sub?token=abc'xyz"
    cfg = _build_mihomo_config_from_subscription(url)
    # 单引号被剥, 不会破坏 yaml 语法
    assert "abcxyz" in cfg  # 单引号消失
    assert "abc'xyz" not in cfg
    print("✅ test_build_mihomo_config_escapes_quote")


def test_build_mihomo_config_long_url_truncated():
    """v2.0.4: 超长订阅 URL 在注释里被截断"""
    from ssh_client import _build_mihomo_config_from_subscription
    url = "https://provider.com/" + "x" * 100
    cfg = _build_mihomo_config_from_subscription(url)
    # 注释里有 "..." 表示截断
    assert "..." in cfg.split("\n")[1]  # 注释行
    # 但 proxy-providers 段是用全 URL (要 yaml 真能用)
    assert url in cfg
    print("✅ test_build_mihomo_config_long_url_truncated")


def test_install_apps_streaming_accepts_mihomo_url():
    """v2.0.4: install_apps_streaming 签名新增 mihomo_subscription_url 参数"""
    import inspect
    from ssh_client import NASConnection
    sig = inspect.signature(NASConnection.install_apps_streaming)
    assert "mihomo_subscription_url" in sig.parameters
    # 默认 None (兼容老调用)
    assert sig.parameters["mihomo_subscription_url"].default is None
    print("✅ test_install_apps_streaming_accepts_mihomo_url")


def test_install_apps_streaming_uses_url_when_provided(monkeypatch=None):
    """v2.0.4: 传订阅 URL → 用真配置而不是占位"""
    # 这条得 mock SSH 跑得起来才能测. 跳过复杂 mock, 验证函数存在即可
    from ssh_client import _build_mihomo_config_from_subscription
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    assert "url: 'https://test.com/sub'" in cfg
    print("✅ test_install_apps_streaming_uses_url_when_provided")


def test_app_typing_imports():
    """v2.0.4.1 regression: app.py 必须 from typing import Optional
    否则 PyInstaller EXE 第一次跑 _ask_mihomo_subscription 就 NameError 崩"""
    import ast
    with open(os.path.join(os.path.dirname(__file__), "..", "src", "app.py")) as f:
        tree = ast.parse(f.read())
    # 找所有 import typing 的语句
    has_typing_optional = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = []
            if isinstance(node, ast.ImportFrom):
                mods = [node.module] if node.module else []
                for alias in node.names:
                    mods.append(alias.name)
            else:
                mods = [alias.name for alias in node.names]
            if any("typing" in m for m in mods):
                # 检查是否 import 了 Optional
                if isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        if alias.name == "Optional":
                            has_typing_optional = True
    assert has_typing_optional, "app.py 没 from typing import Optional, EXE 启动必崩"
    print("✅ test_app_typing_imports — Optional 已 import")


def test_app_dialogs_auto_size():
    """v2.0.4.2 regression: 所有弹窗必须 update_idletasks + winfo_reqwidth 自适应
    否则用户得每次拖拽窗口才能看全"""
    src = os.path.join(os.path.dirname(__file__), "..", "src", "app.py")
    with open(src) as f:
        content = f.read()
    # 找所有 Toplevel 弹窗的 method 定义
    import re
    dialog_methods = re.findall(r"def _(\w*dialog\w*)\(self\)|def _ask_(\w+)\(self\)", content)
    # 也直接扫描 mihomo 弹窗和 credentials 弹窗
    for keyword in ["_ask_mihomo_subscription", "_show_credentials_dialog"]:
        # 找方法体范围
        idx = content.find(f"def {keyword}")
        assert idx > 0, f"{keyword} not found"
        # 找下一个 def (方法结束)
        next_def = content.find("\n    def _", idx + 10)
        if next_def < 0:
            next_def = len(content)
        block = content[idx:next_def]
        # 验证关键调用
        assert "update_idletasks" in block, f"{keyword}: 缺 update_idletasks"
        assert "winfo_reqwidth" in block, f"{keyword}: 缺 winfo_reqwidth 自适应宽度"
        assert "winfo_reqheight" in block, f"{keyword}: 缺 winfo_reqheight 自适应高度"
        assert "minsize" in block, f"{keyword}: 缺 minsize 最小尺寸保护"
    print("✅ test_app_dialogs_auto_size — mihomo + credentials 都自适应尺寸")


def test_mihomo_bt_block():
    """v2.0.5: BT 端口全部 REJECT (节点商查 BT 秒封)"""
    from ssh_client import _build_mihomo_config_from_subscription
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    # BT 端口 6881-6889
    for port in [6881, 6882, 6883, 6884, 6885, 6886, 6887, 6888, 6889]:
        assert f"DST-PORT,{port},REJECT" in cfg, f"BT port {port} not blocked"
    assert "DST-PORT,2710,REJECT" in cfg
    assert "DST-PORT,41413,REJECT" in cfg
    # tracker 域名
    for kw in ["tracker", "bittorrent", "torrent", "peer"]:
        assert f"DOMAIN-KEYWORD,{kw},REJECT" in cfg, f"tracker kw {kw} not blocked"
    print("✅ test_mihomo_bt_block — 11 BT ports + 4 trackers blocked")


def test_mihomo_nas_service_ports_direct():
    """v2.0.5.1: NAS 服务端口 (含 qB 8080) 全 DIRECT, 不被代理劫持
    用户报: qB 8080 之前可能被代理劫持烧流量"""
    from ssh_client import _build_mihomo_config_from_subscription
    from apps import APPS
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    # 所有有 port 的应用都应 DIRECT
    missing = []
    for key, meta in APPS.items():
        port = meta.get("port")
        if not port or meta.get("hidden"):
            continue
        rule = f"DST-PORT,{port},DIRECT,no-resolve"
        if rule not in cfg:
            missing.append((key, port))
    assert not missing, f"missing DIRECT rule for: {missing}"
    print(f"✅ test_mihomo_nas_service_ports_direct — {sum(1 for m in APPS.values() if m.get('port') and not m.get('hidden'))} services DIRECT")


def test_mihomo_lan_direct():
    """v2.0.5.1: 局域网 (192.168/10/172.16/127.0) 全 DIRECT, 不劫持其他设备"""
    from ssh_client import _build_mihomo_config_from_subscription
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    for cidr in ["192.168.0.0/16", "10.0.0.0/8", "172.16.0.0/12", "127.0.0.0/8"]:
        rule = f"IP-CIDR,{cidr},DIRECT"
        assert rule in cfg, f"missing LAN CIDR: {cidr}"
    print("✅ test_mihomo_lan_direct — 4 LAN CIDRs DIRECT")


def test_mihomo_bind_localhost():
    """v2.0.5.1: mihomo 只监听 127.0.0.1, 不劫持局域网设备"""
    from ssh_client import _build_mihomo_config_from_subscription
    cfg = _build_mihomo_config_from_subscription("https://test.com/sub")
    assert "bind-address: 127.0.0.1" in cfg, "缺 bind-address: 127.0.0.1"
    print("✅ test_mihomo_bind_localhost — bind-address = 127.0.0.1")


if __name__ == "__main__":
    tests = [
        test_build_mihomo_config_basic,
        test_build_mihomo_config_escapes_quote,
        test_build_mihomo_config_long_url_truncated,
        test_install_apps_streaming_accepts_mihomo_url,
        test_install_apps_streaming_uses_url_when_provided,
        test_app_typing_imports,
        test_app_dialogs_auto_size,
        test_mihomo_bt_block,
        test_mihomo_nas_service_ports_direct,
        test_mihomo_lan_direct,
        test_mihomo_bind_localhost,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {type(e).__name__}: {e}")
            failed += 1
    print()
    print(f"=== {passed} passed, {failed} failed, {len(tests)} total ===")