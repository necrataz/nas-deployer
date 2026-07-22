# ==============================================================================
# 测试: credentials.py v2.0.3 默认凭证查询
# ==============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_get_credentials_moviepilot():
    """v2.0.3: MoviePilot compose 硬编码 admin/ChangeMe123!"""
    from credentials import get_credentials
    cred = get_credentials("moviepilot")
    assert cred["username"] == "admin"
    assert cred["password"] == "ChangeMe123!"
    assert cred["confidence"] == "high"
    print("✅ test_get_credentials_moviepilot")


def test_get_credentials_qbittorrent_random():
    """v2.0.3: qBittorrent 是 <random>, note 提示从 logs 拿"""
    from credentials import get_credentials
    cred = get_credentials("qbittorrent")
    assert cred["password"] == "<random>"
    assert "docker logs" in cred["note"]
    print("✅ test_get_credentials_qbittorrent_random")


def test_get_credentials_xiaoya_guest():
    """v2.0.3: xiaoya = alist 默认 guest/guest"""
    from credentials import get_credentials
    cred = get_credentials("xiaoya")
    assert cred["username"] == "guest"
    assert cred["password"] == "guest"
    print("✅ test_get_credentials_xiaoya_guest")


def test_get_credentials_first_setup():
    """v2.0.3: Immich 是 first_setup (首次访问注册)"""
    from credentials import get_credentials
    cred = get_credentials("immich")
    assert cred["username"] == "first_setup"
    assert "首次访问" in cred["note"]
    print("✅ test_get_credentials_first_setup")


def test_get_credentials_none_auth():
    """v2.0.3: excalidraw / photopea 等公开服务 = none"""
    from credentials import get_credentials
    for key in ["excalidraw", "photopea", "hivision", "mihomo"]:
        cred = get_credentials(key)
        assert cred["username"] == "none", f"{key} should be none auth, got {cred}"
    print("✅ test_get_credentials_none_auth")


def test_get_credentials_unknown():
    """v2.0.3: 查不到的应用返 None"""
    from credentials import get_credentials
    assert get_credentials("notexist_app_xyz") is None
    print("✅ test_get_credentials_unknown")


def test_format_credentials_display():
    """v2.0.3: format_credentials_display 输出包含关键字段"""
    from credentials import format_credentials_display
    out = format_credentials_display("moviepilot", "MoviePilot", 5000, "192.168.3.88")
    assert "MoviePilot" in out
    assert "http://192.168.3.88:5000" in out
    assert "admin" in out
    assert "ChangeMe123!" in out
    assert "high" in out
    print("✅ test_format_credentials_display")


def test_format_credentials_no_port():
    """v2.0.3: 无端口应用 (iptv_auto) 显示 '无 Web UI'"""
    from credentials import format_credentials_display
    out = format_credentials_display("iptv_auto", "IPTV Auto", 0, "192.168.3.88")
    assert "无 Web UI" in out
    print("✅ test_format_credentials_no_port")


def test_format_credentials_unknown():
    """v2.0.3: 未知应用给提示"""
    from credentials import format_credentials_display
    out = format_credentials_display("fakething", "Fake", 8000, "192.168.3.88")
    assert "⚠️" in out
    assert "官方文档" in out
    print("✅ test_format_credentials_unknown")


def test_list_all_credentials_count():
    """v2.0.3: 28 个应用都列得出 (apps.py 里 26 个可见 + 2 个特殊)"""
    from credentials import list_all_credentials
    rows = list_all_credentials()
    assert len(rows) >= 25, f"expected >=25 apps, got {len(rows)}"
    # 每行格式: (key, name, port)
    for row in rows:
        assert len(row) == 3
    print(f"✅ test_list_all_credentials_count — {len(rows)} apps")


def test_credentials_confidence_levels():
    """v2.0.3: confidence 都是 high/medium/low, 没缺失"""
    from credentials import CREDENTIALS
    valid = {"high", "medium", "low"}
    for key, cred in CREDENTIALS.items():
        c = cred.get("confidence")
        assert c in valid, f"{key} confidence = {c} (invalid)"
    print(f"✅ test_credentials_confidence_levels — {len(CREDENTIALS)} apps, all valid")


if __name__ == "__main__":
    tests = [
        test_get_credentials_moviepilot,
        test_get_credentials_qbittorrent_random,
        test_get_credentials_xiaoya_guest,
        test_get_credentials_first_setup,
        test_get_credentials_none_auth,
        test_get_credentials_unknown,
        test_format_credentials_display,
        test_format_credentials_no_port,
        test_format_credentials_unknown,
        test_list_all_credentials_count,
        test_credentials_confidence_levels,
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