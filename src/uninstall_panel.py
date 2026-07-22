# ==============================================================================
# NAS Deployer v2.0.6 - 卸载勾选面板
# ==============================================================================
# 自包含 ttk widget: 顶部全选/反选/全不选 + 滚动区勾选容器列表 + 底部卸载按钮
# 用法:
#     panel = UninstallPanel(parent_frame, on_uninstall=cb, on_select_change=cb)
#     panel.frame.pack(...)
#     panel.set_containers([{"name":"qb",...}, ...])  # 刷新容器
#     panel.get_checked() -> ["qb", "moviepilot"]
# ==============================================================================

import tkinter as tk
import ttkbootstrap as ttk
from ttkbootstrap.constants import *
from typing import Dict, List, Callable, Optional


class UninstallPanel:
    """状态 Tab 顶部的卸载勾选面板

    设计:
    - 顶部: 全选/全不选/反选 + 计数显示
    - 中部: 滚动区 Checkbutton 列表 (☐/☑)
    - 底部: 卸载 (保留数据) / 卸载 (删数据!)
    """

    def __init__(self, parent, on_uninstall: Callable, on_select_change: Optional[Callable] = None):
        """
        Args:
            parent: 父容器 (status Tab frame)
            on_uninstall: 回调函数 (names: List[str], remove_volumes: bool) -> None
            on_select_change: 勾选变化回调 (count: int) -> None
        """
        self.on_uninstall = on_uninstall
        self.on_select_change = on_select_change or (lambda c: None)

        # 状态: name -> (tk.BooleanVar, container_meta)
        self._items: Dict[str, Dict] = {}
        self._check_vars: Dict[str, tk.BooleanVar] = {}
        self._row_frames: List[ttk.Frame] = []

        # 主 frame
        self.frame = ttk.LabelFrame(parent, text="📦 卸载 (勾选)", padding=8)

        # 顶部工具栏
        toolbar = ttk.Frame(self.frame)
        toolbar.pack(fill=X, pady=(0, 5))

        ttk.Button(toolbar, text="☑ 全选", command=self.select_all,
                   bootstyle="success-outline", width=8).pack(side=LEFT, padx=2)
        ttk.Button(toolbar, text="☐ 全不选", command=self.select_none,
                   bootstyle="secondary-outline", width=8).pack(side=LEFT, padx=2)
        ttk.Button(toolbar, text="🔄 反选", command=self.invert_selection,
                   bootstyle="info-outline", width=8).pack(side=LEFT, padx=2)

        self.count_label = ttk.Label(toolbar, text="已选 0 / 0", foreground="gray")
        self.count_label.pack(side=LEFT, padx=15)

        # 中部: 滚动 Checkbutton 列表
        list_outer = ttk.Frame(self.frame, relief="sunken", borderwidth=1)
        list_outer.pack(fill=X, pady=2, ipady=2)

        # Canvas + scrollbar (固定高度, 超出滚动)
        self.canvas = tk.Canvas(list_outer, height=120, highlightthickness=0)
        scrollbar = ttk.Scrollbar(list_outer, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=scrollbar.set)
        self.canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        self.list_inner = ttk.Frame(self.canvas)
        self.canvas_window = self.canvas.create_window((0, 0), window=self.list_inner, anchor="nw")
        # 让 list_inner 跟随 canvas 宽度
        self.list_inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.canvas_window, width=e.width))
        # 鼠标滚轮
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        # 底部: 卸载按钮
        action_bar = ttk.Frame(self.frame)
        action_bar.pack(fill=X, pady=(5, 0))
        ttk.Button(action_bar, text="🗑 卸载勾选 (保留数据)",
                   command=lambda: self._trigger_uninstall(False),
                   bootstyle="warning").pack(side=LEFT, padx=2)
        ttk.Button(action_bar, text="🗑💥 卸载勾选 (删数据!)",
                   command=lambda: self._trigger_uninstall(True),
                   bootstyle="danger").pack(side=LEFT, padx=2)

        # 空状态
        self._show_empty_state()

    def _on_mousewheel(self, event):
        """鼠标滚轮在 canvas 上时滚动"""
        # 只有当鼠标在 canvas 区域内才响应
        if self.canvas.winfo_containing(event.x_root, event.y_root) is None:
            return
        self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _show_empty_state(self):
        """显示空状态提示"""
        for w in self.list_inner.winfo_children():
            w.destroy()
        self._row_frames = []
        ttk.Label(self.list_inner, text="(无容器, 点 🔄 刷新状态 获取列表)",
                  foreground="gray", padding=10).pack()

    def set_containers(self, containers: List[Dict]):
        """刷新容器列表

        Args:
            containers: [{"name": "qbittorrent", "image": "...", "status": "Up", "ports": "..."}, ...]
        """
        # 保留之前勾选状态 (按 name)
        old_checked = set(self._check_vars.keys())

        # 清空重建
        for w in self.list_inner.winfo_children():
            w.destroy()
        self._items.clear()
        self._check_vars.clear()
        self._row_frames = []

        if not containers:
            self._show_empty_state()
            self._update_count()
            return

        # 按 name 排序
        sorted_c = sorted(containers, key=lambda c: c.get("name", ""))

        for c in sorted_c:
            name = c.get("name", "?")
            image = c.get("image", "")
            status = c.get("status", "")
            ports = c.get("ports", "")

            row = ttk.Frame(self.list_inner)
            row.pack(fill=X, padx=5, pady=1)
            self._row_frames.append(row)

            var = tk.BooleanVar(value=False)
            self._check_vars[name] = var

            # Checkbutton + 容器信息
            chk = ttk.Checkbutton(
                row,
                variable=var,
                text=f"  {name}   |   {status}   |   {ports or '(无端口)'}",
                command=self._on_item_toggle,
            )
            chk.pack(side=LEFT, fill=X, expand=YES)

            self._items[name] = c

        self._update_count()

    def _on_item_toggle(self):
        self._update_count()
        self.on_select_change(self.get_checked_count())

    def _update_count(self):
        total = len(self._check_vars)
        checked = self.get_checked_count()
        self.count_label.config(text=f"已选 {checked} / {total}")

    def get_checked(self) -> List[str]:
        """返回勾选的容器名列表"""
        return [name for name, var in self._check_vars.items() if var.get()]

    def get_checked_count(self) -> int:
        return sum(1 for var in self._check_vars.values() if var.get())

    def select_all(self):
        for var in self._check_vars.values():
            var.set(True)
        self._on_item_toggle()

    def select_none(self):
        for var in self._check_vars.values():
            var.set(False)
        self._on_item_toggle()

    def invert_selection(self):
        for var in self._check_vars.values():
            var.set(not var.get())
        self._on_item_toggle()

    def _trigger_uninstall(self, remove_volumes: bool):
        """点击卸载按钮: 收集勾选 → 回调"""
        names = self.get_checked()
        if not names:
            from tkinter import messagebox
            messagebox.showinfo("提示", "请先勾选要卸载的服务")
            return
        self.on_uninstall(names, remove_volumes)