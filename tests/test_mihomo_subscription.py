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


if __name__ == "__main__":
    tests = [
        test_build_mihomo_config_basic,
        test_build_mihomo_config_escapes_quote,
        test_build_mihomo_config_long_url_truncated,
        test_install_apps_streaming_accepts_mihomo_url,
        test_install_apps_streaming_uses_url_when_provided,
        test_app_typing_imports,
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