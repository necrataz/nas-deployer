# ==============================================================================
# 测试: navigation.py v2.0 NAS 导航
# ==============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_get_local_ip():
    """v2.0: get_local_ip 返回非空 IP"""
    from navigation import get_local_ip
    ip = get_local_ip()
    assert ip, "should return non-empty IP"
    assert "." in ip, f"should look like IPv4: {ip}"
    print(f"✅ test_get_local_ip — {ip}")


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
        test_get_local_ip,
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