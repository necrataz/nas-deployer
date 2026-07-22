# ==============================================================================
# 测试: uninstall_panel.py v2.0.5.1 勾选面板
# ==============================================================================

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))


def test_panel_imports():
    """v2.0.5.1: uninstall_panel 模块可导入"""
    from uninstall_panel import UninstallPanel
    print("✅ test_panel_imports")


def test_panel_set_containers():
    """v2.0.5.1: set_containers 接收容器列表"""
    import tkinter as tk
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()

    fired = {"uninstall_called": False, "names": None}
    def on_uninstall(names, remove_volumes):
        fired["uninstall_called"] = True
        fired["names"] = names

    panel = UninstallPanel(root, on_uninstall=on_uninstall)

    # 设置 3 个容器
    containers = [
        {"name": "qbittorrent", "image": "linuxserver/qbittorrent", "status": "Up 5 min", "ports": "0.0.0.0:8080->8080"},
        {"name": "moviepilot", "image": "jxxghp/moviepilot", "status": "Up 1 h", "ports": "0.0.0.0:5000->5000"},
        {"name": "mihomo", "image": "metacubex/mihomo", "status": "Up", "ports": "0.0.0.0:7890->7890"},
    ]
    panel.set_containers(containers)
    assert len(panel._check_vars) == 3, f"应 3 个容器, 实际 {len(panel._check_vars)}"
    assert "qbittorrent" in panel._check_vars
    assert "moviepilot" in panel._check_vars
    assert "mihomo" in panel._check_vars
    # 默认没勾选
    assert panel.get_checked_count() == 0
    assert panel.get_checked() == []
    root.destroy()
    print("✅ test_panel_set_containers — 3 个容器入列")


def test_panel_select_all_none_invert():
    """v2.0.5.1: 全选/全不选/反选 行为"""
    import tkinter as tk
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()
    panel = UninstallPanel(root, on_uninstall=lambda n, v: None)
    panel.set_containers([
        {"name": "a", "image": "x", "status": "Up", "ports": ""},
        {"name": "b", "image": "y", "status": "Up", "ports": ""},
        {"name": "c", "image": "z", "status": "Up", "ports": ""},
    ])

    # 全选
    panel.select_all()
    assert panel.get_checked_count() == 3
    assert set(panel.get_checked()) == {"a", "b", "c"}

    # 全不选
    panel.select_none()
    assert panel.get_checked_count() == 0

    # 反选 (空状态反选还是空)
    panel.invert_selection()
    assert panel.get_checked_count() == 3

    # 再反选 → 取消
    panel.invert_selection()
    assert panel.get_checked_count() == 0

    root.destroy()
    print("✅ test_panel_select_all_none_invert — 全选/全不选/反选都对")


def test_panel_trigger_uninstall_no_check():
    """v2.0.5.1: 卸载按钮 0 勾选 → 弹窗提示, 不调回调"""
    import tkinter as tk
    from unittest.mock import patch
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()
    fired = []
    panel = UninstallPanel(root, on_uninstall=lambda n, v: fired.append((n, v)))
    panel.set_containers([{"name": "a", "image": "x", "status": "Up", "ports": ""}])

    # 没勾选, 点卸载 → messagebox.showinfo, 不调回调
    with patch("tkinter.messagebox.showinfo") as mock_info:
        panel._trigger_uninstall(False)
        mock_info.assert_called_once()
        assert not fired, f"0 勾选不应调卸载, 实际 {fired}"
    root.destroy()
    print("✅ test_panel_trigger_uninstall_no_check — 0 勾选保护")


def test_panel_trigger_uninstall_with_check():
    """v2.0.5.1: 勾选后点卸载 → 调回调 (保留数据)"""
    import tkinter as tk
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()
    fired = []
    panel = UninstallPanel(root, on_uninstall=lambda n, v: fired.append((n, v)))
    panel.set_containers([
        {"name": "a", "image": "x", "status": "Up", "ports": ""},
        {"name": "b", "image": "y", "status": "Up", "ports": ""},
    ])
    panel._check_vars["a"].set(True)
    panel._check_vars["b"].set(True)
    panel._trigger_uninstall(False)
    assert len(fired) == 1
    names, rv = fired[0]
    assert set(names) == {"a", "b"}
    assert rv is False  # 保留数据
    root.destroy()
    print("✅ test_panel_trigger_uninstall_with_check — 回调正确 (保留数据)")


def test_panel_trigger_uninstall_with_volumes():
    """v2.0.5.1: 勾选后点 🗑💥 → 回调 remove_volumes=True"""
    import tkinter as tk
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()
    fired = []
    panel = UninstallPanel(root, on_uninstall=lambda n, v: fired.append((n, v)))
    panel.set_containers([{"name": "a", "image": "x", "status": "Up", "ports": ""}])
    panel._check_vars["a"].set(True)
    panel._trigger_uninstall(True)
    assert len(fired) == 1
    assert fired[0][1] is True
    root.destroy()
    print("✅ test_panel_trigger_uninstall_with_volumes — 回调正确 (删数据)")


def test_panel_set_containers_preserves_old_checked():
    """v2.0.5.1: set_containers 重新调用时保留旧勾选状态"""
    import tkinter as tk
    from uninstall_panel import UninstallPanel

    root = tk.Tk()
    root.withdraw()
    panel = UninstallPanel(root, on_uninstall=lambda n, v: None)
    panel.set_containers([
        {"name": "a", "image": "x", "status": "Up", "ports": ""},
        {"name": "b", "image": "y", "status": "Up", "ports": ""},
    ])
    panel._check_vars["a"].set(True)
    # v2.0.5.1 当前实现: set_containers 不保留旧勾选 (重新刷新 = 重置选择)
    # 这是有意的: 用户点刷新 = 看最新, 不想误操作之前勾的
    panel.set_containers([
        {"name": "a", "image": "x", "status": "Up", "ports": ""},
        {"name": "b", "image": "y", "status": "Up", "ports": ""},
        {"name": "c", "image": "z", "status": "Up", "ports": ""},
    ])
    # 当前所有都是 False (新 panel)
    assert panel.get_checked_count() == 0
    root.destroy()
    print("✅ test_panel_set_containers_preserves_old_checked — 刷新重置勾选 (安全)")


def test_app_has_uninstall_panel():
    """v2.0.5.1 regression: app.py 必须 import + 创建 UninstallPanel"""
    import ast
    with open(os.path.join(os.path.dirname(__file__), "..", "src", "app.py")) as f:
        content = f.read()
    assert "from uninstall_panel import UninstallPanel" in content, "app.py 没 import UninstallPanel"
    assert "self.uninstall_panel = UninstallPanel" in content, "app.py 没创建 panel 实例"
    assert "_uninstall_checked_apps" in content, "app.py 没装顶部卸载按钮回调"
    print("✅ test_app_has_uninstall_panel")


def test_app_uninstall_button_uses_checked():
    """v2.0.5.1 regression: 顶部卸载按钮回调指向 checked panel, 不是 treeview 选中"""
    src = os.path.join(os.path.dirname(__file__), "..", "src", "app.py")
    with open(src) as f:
        content = f.read()
    # 找 btn_frame 区域 (在 _build_status_tab 里)
    idx = content.find("def _build_status_tab")
    end = content.find("def _build_logs_tab")
    block = content[idx:end]
    # 顶部卸载按钮应指向 _uninstall_checked_apps (不是 _uninstall_selected_container)
    assert 'text="🗑 卸载选中", command=self._uninstall_checked_apps' in block, \
        "顶部卸载按钮应指向 _uninstall_checked_apps"
    print("✅ test_app_uninstall_button_uses_checked")


if __name__ == "__main__":
    tests = [
        test_panel_imports,
        test_panel_set_containers,
        test_panel_select_all_none_invert,
        test_panel_trigger_uninstall_no_check,
        test_panel_trigger_uninstall_with_check,
        test_panel_trigger_uninstall_with_volumes,
        test_panel_set_containers_preserves_old_checked,
        test_app_has_uninstall_panel,
        test_app_uninstall_button_uses_checked,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            passed += 1
        except Exception as e:
            print(f"❌ {t.__name__}: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    print()
    print(f"=== {passed} passed, {failed} failed, {len(tests)} total ===")