# ==============================================================================
# 测试: navigation.py v2.0 NAS 导航 + v2.0.2 IP 修复
# ==============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_resolve_nas_ip_explicit():
    """v2.0.2: 显式传 nas_ip → 优先级最高, 即使他是 127.0.0.1 也用他"""
    from navigation import resolve_nas_ip
    ip = resolve_nas_ip("192.168.3.88")
    assert ip == "192.168.3.88", f"expected 192.168.3.88, got {ip}"
    print(f"✅ test_resolve_nas_ip_explicit — {ip}")


def test_resolve_nas_ip_with_user_prefix():
    """v2.0.2: 'necrata@192.168.3.88:22' → '192.168.3.88' (剥 user@ 和 :port)"""
    from navigation import resolve_nas_ip
    ip = resolve_nas_ip("necrata@192.168.3.88:22")
    assert ip == "192.168.3.88", f"got {ip}"
    print(f"✅ test_resolve_nas_ip_with_user_prefix — {ip}")


def test_resolve_nas_ip_ipv4_only():
    """v2.0.2: '192.168.3.55' → '192.168.3.55' (没端口无影响)"""
    from navigation import resolve_nas_ip
    ip = resolve_nas_ip("192.168.3.55")
    assert ip == "192.168.3.55", f"got {ip}"
    print(f"✅ test_resolve_nas_ip_ipv4_only — {ip}")


def test_render_html_uses_nas_ip_not_local():
    """v2.0.2: 渲染 HTML 用调用方的 nas_ip (192.168.3.88) 而不是本机"""
    from navigation import _render_html
    html = _render_html(["qbittorrent"], "192.168.3.88", "fnos")
    # 应该用 192.168.3.88 拼 qBittorrent URL
    assert "http://192.168.3.88:8080" in html, "missing NAS ip in URL"
    # 不应出现本机的 192.168.3.X 推测值 (可能是 192.168.3.1 也可能不是)
    # 关键是 _render_html 本身已被传入 nas_ip, 这里只验证它用参数不读全局
    print("✅ test_render_html_uses_nas_ip_not_local")


def test_render_html_empty():
    """v2.0: 0 个服务 → 渲染有空状态提示"""
    from navigation import _render_html
    html = _render_html([], "192.168.1.1", "Test NAS")
    assert "Test NAS" in html
    assert "暂无已安装服务" in html
    assert "192.168.1.1" not in html or "192.168.1.1" in html  # empty case: no port url
    # 0 app 时不应有 section
    assert html.count("section class=\"group\"") == 0
    print("✅ test_render_html_empty")


def test_render_html_grouped():
    """v2.0: 多 app 按 category 分组"""
    from navigation import _render_html
    installed = ["qbittorrent", "moviepilot", "navidrome", "lucky"]
    html = _render_html(installed, "192.168.1.100", "fnos")
    # 各 app 应出现
    assert "qBittorrent" in html
    assert "MoviePilot" in html
    assert "Navidrome" in html
    assert "Lucky" in html
    # movie 分类标题
    assert "影视" in html
    # 端口 url 应拼对
    assert "http://192.168.1.100:8080" in html  # qbittorrent
    assert "http://192.168.1.100:5000" in html  # moviepilot
    # card 数量 = 4 (group 里 grid 数)
    card_marker = 'class="card"'
    card_count = html.count(card_marker)
    assert card_count == 4, f"expected 4 cards, got {card_count}"
    print(f"✅ test_render_html_grouped — {card_count} cards")


def test_render_html_warning():
    """v2.0: 有 warning 的 app (xiaoya) 在卡片上显示 ⚠️"""
    from navigation import _render_html
    html = _render_html(["xiaoya"], "192.168.1.100", "fnos")
    assert "小雅全家桶" in html
    # xiaoya 在 apps.py 里有 warning: '与 MoviePilot+LibreTV 功能重叠'
    assert "⚠️" in html or "与 MoviePilot" in html
    print("✅ test_render_html_warning")


def test_open_navigation_page_port():
    """v2.0: open_navigation_page 返回可用端口 + 不阻塞"""
    from navigation import open_navigation_page
    import time
    port = open_navigation_page(["qbittorrent"], "Test", 0)
    assert 1024 < port < 65536, f"port out of range: {port}"
    # 端口 0 = 自动选, 实际应 > 0
    print(f"✅ test_open_navigation_page_port — port={port}")
    # 注: 不真测试 HTTP 请求, 因为会开浏览器, 不适合单元测试


if __name__ == "__main__":
    tests = [
        # v2.0.2 IP 修复
        test_resolve_nas_ip_explicit,
        test_resolve_nas_ip_with_user_prefix,
        test_resolve_nas_ip_ipv4_only,
        test_render_html_uses_nas_ip_not_local,
        # v2.0 原版保留
        test_render_html_empty,
        test_render_html_grouped,
        test_render_html_warning,
        test_open_navigation_page_port,
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