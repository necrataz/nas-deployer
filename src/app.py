# ==============================================================================
# NAS Deployer v1.1 - 主 GUI (ttkbootstrap)
# 新增: 多 NAS profile 切换 / keyring 密码存储 / 进度窗口 / 应用搜索
# ==============================================================================

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog, simpledialog
from pathlib import Path
from datetime import datetime

import ttkbootstrap as ttk
from ttkbootstrap.constants import *


# 兼容 PyInstaller 打包后的资源访问
def resource_path(relative_path: str) -> str:
    """获取资源的绝对路径（兼容开发模式和 PyInstaller 打包）"""
    if hasattr(sys, "_MEIPASS"):
        return os.path.join(sys._MEIPASS, relative_path)
    return os.path.join(os.path.dirname(__file__), relative_path)


from ssh_client import NASConnection
from apps import APPS, PROFILES, get_visible_apps, get_apps_by_profile, total_memory_mb
from compose_data import DOCKER_COMPOSE_YML
from nas_profile import ProfileManager, NASProfile, KEYRING_AVAILABLE
from progress_window import ProgressWindow
from host_utils import clean_host, extract_port_from_host  # v1.3: host 字段清洗


# 全局常量
APP_VERSION = "1.7.0"
APP_NAME = "NAS 一键部署工具"

# 旧版单 NAS 配置 (v1.0), 仅用于一次性迁移
LEGACY_CONFIG_FILE = Path.home() / ".nas_deployer" / "config.json"


class NASDeployerApp:
    def __init__(self):
        self.root = ttk.Window(themename="cosmo")
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1100x760")
        self.root.minsize(950, 650)

        # State
        self.profile_mgr = ProfileManager()
        self.connection = NASConnection()
        self.current_password = None  # 已连接 NAS 的密码 (明文, 内存里临时存)

        # 应用 Tab 状态
        self.profile_vars = {}     # profile 快速勾选 checkbox
        self.app_checkboxes = {}   # 单个应用 checkbox
        self.category_frames = {}  # 分组可折叠 frame (key = category)
        self.search_var = tk.StringVar()
        self.show_only_selected_var = tk.BooleanVar(value=False)

        # Build
        self._build_menu()
        self._build_top_bar()
        self._build_tabs()

        # 一次性迁移 v1.0 配置 (单 NAS → 多 NAS)
        self._migrate_legacy_config()

        # 初始化 NAS dropdown
        self._refresh_nas_dropdown()
        self._on_nas_changed()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------------------- 菜单 --------------------
    def _build_menu(self):
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="导出日志...", command=self._save_logs)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        help_menu.add_command(label="重置 NAS 列表", command=self._reset_profiles)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    # -------------------- 顶部栏 (NAS 切换) --------------------
    def _build_top_bar(self):
        """顶部栏: 标题 + NAS dropdown + add/edit/remove + 状态"""
        bar = ttk.Frame(self.root, padding=(10, 10, 10, 5))
        bar.pack(fill=X)

        # 左: 标题
        ttk.Label(
            bar,
            text=f"🚀 {APP_NAME}",
            font=("Helvetica", 16, "bold"),
        ).pack(side=LEFT)

        # 右: NAS 切换控件
        right = ttk.Frame(bar)
        right.pack(side=RIGHT)

        ttk.Label(right, text="当前 NAS:", font=("Helvetica", 10)).pack(side=LEFT, padx=(0, 5))

        self.nas_combo = ttk.Combobox(
            right, state="readonly", width=32, bootstyle="primary"
        )
        self.nas_combo.pack(side=LEFT, padx=5)
        self.nas_combo.bind("<<ComboboxSelected>>", self._on_nas_changed)

        ttk.Button(right, text="➕", command=self._add_nas_profile, width=3, bootstyle="success-outline").pack(side=LEFT, padx=2)
        ttk.Button(right, text="✏️", command=self._edit_nas_profile, width=3, bootstyle="info-outline").pack(side=LEFT, padx=2)
        ttk.Button(right, text="🗑", command=self._remove_nas_profile, width=3, bootstyle="danger-outline").pack(side=LEFT, padx=2)

        # 状态指示
        self.status_label = ttk.Label(
            right, text="● 未连接", foreground="gray", font=("Helvetica", 10)
        )
        self.status_label.pack(side=LEFT, padx=(15, 0))

    # -------------------- Tabs --------------------
    def _build_tabs(self):
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

        self._build_connection_tab()
        self._build_apps_tab()
        self._build_status_tab()
        self._build_logs_tab()

    def _build_connection_tab(self):
        """连接 Tab: 显示当前 NAS 信息 + 密码输入 + 测试/连接/断开"""
        tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(tab, text="📡 连接")

        # 当前 NAS 信息 (只读)
        info_frame = ttk.LabelFrame(tab, text="当前 NAS 信息", padding=15)
        info_frame.grid(row=0, column=0, columnspan=4, sticky=EW, pady=(0, 15))

        ttk.Label(info_frame, text="名称:").grid(row=0, column=0, sticky=W, padx=5, pady=5)
        self.info_name = ttk.Label(info_frame, text="—", font=("Helvetica", 11, "bold"))
        self.info_name.grid(row=0, column=1, sticky=W, padx=5)

        ttk.Label(info_frame, text="类型:").grid(row=0, column=2, sticky=W, padx=(20, 5))
        self.info_os = ttk.Label(info_frame, text="—", font=("Helvetica", 11))
        self.info_os.grid(row=0, column=3, sticky=W, padx=5)

        ttk.Label(info_frame, text="地址:").grid(row=1, column=0, sticky=W, padx=5, pady=5)
        self.info_addr = ttk.Label(info_frame, text="—", font=("Helvetica", 11))
        self.info_addr.grid(row=1, column=1, sticky=W, padx=5)

        ttk.Label(info_frame, text="用户名:").grid(row=1, column=2, sticky=W, padx=(20, 5))
        self.info_user = ttk.Label(info_frame, text="—", font=("Helvetica", 11))
        self.info_user.grid(row=1, column=3, sticky=W, padx=5)

        # 密码输入 + 保存选项
        pwd_frame = ttk.LabelFrame(tab, text="密码", padding=15)
        pwd_frame.grid(row=1, column=0, columnspan=4, sticky=EW, pady=(0, 15))

        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(pwd_frame, textvariable=self.password_var, width=35, show="•")
        self.password_entry.grid(row=0, column=0, sticky=W, padx=5)

        self.save_pwd_var = tk.BooleanVar(value=KEYRING_AVAILABLE)
        save_chk = ttk.Checkbutton(
            pwd_frame,
            text=f"保存到 keyring (Windows Credential Manager){'' if KEYRING_AVAILABLE else ' [未安装]'}",
            variable=self.save_pwd_var,
            bootstyle="round-toggle",
            state="normal" if KEYRING_AVAILABLE else "disabled",
        )
        save_chk.grid(row=0, column=1, sticky=W, padx=15)

        # 按钮区
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=2, column=0, columnspan=4, pady=10)

        ttk.Button(
            btn_frame, text="🔌 测试并连接",
            command=self._test_connection, bootstyle="success",
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text="🔓 断开",
            command=self._disconnect, bootstyle="danger-outline",
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text="🗝 删除保存的密码",
            command=self._delete_saved_password, bootstyle="warning-outline",
        ).pack(side=LEFT, padx=5)

        # 连接结果
        ttk.Label(tab, text="连接结果:", font=("Helvetica", 11)).grid(
            row=3, column=0, sticky=NW, pady=(10, 0)
        )
        self.connection_result = scrolledtext.ScrolledText(tab, height=12, width=80, wrap=tk.WORD)
        self.connection_result.grid(row=4, column=0, columnspan=4, sticky=NSEW, pady=5)

        tab.columnconfigure(3, weight=1)
        tab.rowconfigure(4, weight=1)

    def _build_apps_tab(self):
        """应用 Tab: 搜索 + 分组折叠 + profile 快速勾选 + 操作按钮"""
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📦 应用")

        # 顶部: Profile 快速勾选
        profile_frame = ttk.LabelFrame(tab, text="快速勾选 (按 profile 组)", padding=10)
        profile_frame.pack(fill=X, pady=(0, 10))

        for i, (prof_key, prof_data) in enumerate(PROFILES.items()):
            var = tk.IntVar()
            self.profile_vars[prof_key] = var
            mem_gb = prof_data["memory_mb"] / 1024
            text = f"{prof_data['name']} ({mem_gb:.1f}GB)"
            ttk.Checkbutton(
                profile_frame, text=text, variable=var,
                command=lambda k=prof_key: self._on_profile_toggle(k),
                bootstyle="round-toggle",
            ).grid(row=i // 3, column=i % 3, sticky=W, padx=15, pady=5)

        # 中部: 搜索 + 筛选
        search_frame = ttk.LabelFrame(tab, text="应用列表 (按分组折叠, 可搜索)", padding=10)
        search_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        ctrl_row = ttk.Frame(search_frame)
        ctrl_row.pack(fill=X, pady=(0, 10))

        ttk.Label(ctrl_row, text="🔍 搜索:").pack(side=LEFT, padx=(0, 5))
        self.search_var.trace_add("write", lambda *_: self._apply_filter())
        ttk.Entry(ctrl_row, textvariable=self.search_var, width=25).pack(side=LEFT, padx=5)

        ttk.Checkbutton(
            ctrl_row, text="仅显示已选",
            variable=self.show_only_selected_var,
            command=self._apply_filter,
            bootstyle="round-toggle",
        ).pack(side=LEFT, padx=15)

        ttk.Button(
            ctrl_row, text="全部展开", command=lambda: self._set_all_categories(True),
            bootstyle="secondary-outline", width=10,
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            ctrl_row, text="全部折叠", command=lambda: self._set_all_categories(False),
            bootstyle="secondary-outline", width=10,
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            ctrl_row, text="☑ 全选", command=lambda: self._set_all_apps(True),
            bootstyle="success-outline", width=8,
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            ctrl_row, text="☐ 全不选", command=lambda: self._set_all_apps(False),
            bootstyle="secondary-outline", width=8,
        ).pack(side=LEFT, padx=5)

        # 可滚动容器
        outer = ttk.Frame(search_frame)
        outer.pack(fill=BOTH, expand=YES)

        self.apps_canvas = tk.Canvas(outer, highlightthickness=0)
        scrollbar = ttk.Scrollbar(outer, orient=VERTICAL, command=self.apps_canvas.yview)
        self.apps_scrollable = ttk.Frame(self.apps_canvas)

        self.apps_scrollable.bind(
            "<Configure>",
            lambda e: self.apps_canvas.configure(scrollregion=self.apps_canvas.bbox("all"))
        )
        self.apps_canvas.create_window((0, 0), window=self.apps_scrollable, anchor="nw")
        self.apps_canvas.configure(yscrollcommand=scrollbar.set)

        self.apps_canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 按 category 分组构建
        self._build_category_groups()

        # 底部: 操作按钮
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=X, pady=5)

        ttk.Button(
            action_frame, text="▶ 安装选中",
            command=self._install_selected, bootstyle="success",
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            action_frame, text="⏹ 停止选中",
            command=self._stop_selected, bootstyle="warning",
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            action_frame, text="🔄 重启选中",
            command=self._restart_selected, bootstyle="info",
        ).pack(side=LEFT, padx=5)
        ttk.Button(
            action_frame, text="📥 拉取镜像",
            command=self._pull_images, bootstyle="secondary-outline",
        ).pack(side=LEFT, padx=5)

        self.mem_label = ttk.Label(action_frame, text="预估内存: 0 MB")
        self.mem_label.pack(side=RIGHT, padx=10)

        # 监听 checkbox 变化
        for var in self.app_checkboxes.values():
            var.trace_add("write", lambda *_: self._update_mem_label())

    def _build_category_groups(self):
        """按 category 分组构建可折叠的应用列表"""
        from collections import defaultdict
        cats = defaultdict(list)
        for app_key, app_data in get_visible_apps().items():
            cat = app_data.get("category", "other")
            cats[cat].append((app_key, app_data))

        cat_names = {pk: pd["name"] for pk, pd in PROFILES.items()}

        # app_key → Checkbutton widget (供 filter 显隐)
        self._app_widgets = {}

        row = 0
        for cat_key in sorted(cats.keys()):
            apps_in_cat = cats[cat_key]
            cat_name = cat_names.get(cat_key, cat_key)

            cat_frame = ttk.LabelFrame(
                self.apps_scrollable,
                text=f"  {cat_name} ({len(apps_in_cat)} 个应用)  ",
                padding=8,
            )
            cat_frame.grid(row=row, column=0, sticky=EW, padx=5, pady=3)
            self.category_frames[cat_key] = cat_frame

            for i, (app_key, app_data) in enumerate(sorted(apps_in_cat, key=lambda x: x[0])):
                var = tk.IntVar()
                self.app_checkboxes[app_key] = var

                port_str = f" :{app_data['port']}" if app_data.get("port") else ""
                warning = " ⚠️" if app_data.get("warning") else ""
                text = f"{app_data['name']}{port_str}  —  {app_data['desc']}{warning}"

                cb = ttk.Checkbutton(cat_frame, text=text, variable=var)
                cb.grid(row=i, column=0, sticky=W, padx=10, pady=2)
                self._app_widgets[app_key] = cb

            row += 1

        self.apps_scrollable.columnconfigure(0, weight=1)

    def _set_all_categories(self, expanded: bool):
        """LabelFrame 没有直接 expand/collapse, 用 padding 模拟"""
        # LabelFrame 不能真正折叠, 这里改成显隐所有 checkbox
        # 简化: 全选/全不选时直接控制每个 app var
        pass  # 暂不实现, 用户用搜索 + 全选按钮够用

    def _set_all_apps(self, checked: bool):
        """全选 / 全不选所有应用 (受当前 filter 影响)"""
        for app_key, var in self.app_checkboxes.items():
            if self._should_show_app(app_key):
                var.set(1 if checked else 0)

    def _should_show_app(self, app_key: str) -> bool:
        """检查 app 是否应显示 (搜索 + 仅显示已选 过滤)"""
        query = self.search_var.get().strip().lower()
        if query:
            data = APPS.get(app_key, {})
            haystack = f"{data.get('name', '')} {data.get('desc', '')} {app_key}".lower()
            if query not in haystack:
                return False
        if self.show_only_selected_var.get():
            if not self.app_checkboxes[app_key].get():
                return False
        return True

    def _apply_filter(self):
        """应用搜索/筛选, 隐藏不匹配的应用"""
        for app_key, cb in self._app_widgets.items():
            if self._should_show_app(app_key):
                cb.grid()
            else:
                cb.grid_remove()

    def _build_status_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📊 状态")

        info_frame = ttk.LabelFrame(tab, text="NAS 资源", padding=10)
        info_frame.pack(fill=X, pady=(0, 10))

        self.disk_label = ttk.Label(info_frame, text="磁盘: --")
        self.disk_label.pack(side=LEFT, padx=20)

        self.mem_remote_label = ttk.Label(info_frame, text="内存: --")
        self.mem_remote_label.pack(side=LEFT, padx=20)

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=X, pady=5)
        ttk.Button(btn_frame, text="🔄 刷新状态", command=self._refresh_status, bootstyle="primary").pack(side=LEFT, padx=5)

        columns = ("name", "image", "status", "ports")
        self.status_tree = ttk.Treeview(tab, columns=columns, show="headings", height=15)
        self.status_tree.heading("name", text="容器名")
        self.status_tree.heading("image", text="镜像")
        self.status_tree.heading("status", text="状态")
        self.status_tree.heading("ports", text="端口")
        self.status_tree.column("name", width=200)
        self.status_tree.column("image", width=300)
        self.status_tree.column("status", width=200)
        self.status_tree.column("ports", width=200)
        self.status_tree.pack(fill=BOTH, expand=YES, pady=5)

        self.tree_menu = tk.Menu(self.root, tearoff=0)
        self.tree_menu.add_command(label="查看日志", command=self._show_container_logs)
        self.tree_menu.add_command(label="重启容器", command=self._restart_container)
        self.tree_menu.add_command(label="停止容器", command=self._stop_container)
        self.status_tree.bind("<Button-3>", self._show_tree_menu)

    def _build_logs_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📝 日志")

        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=X, pady=5)
        ttk.Button(btn_frame, text="清空", command=self._clear_logs, bootstyle="secondary").pack(side=LEFT, padx=5)
        ttk.Button(btn_frame, text="导出...", command=self._save_logs, bootstyle="secondary").pack(side=LEFT, padx=5)

        self.log_text = scrolledtext.ScrolledText(tab, height=30, width=110, wrap=tk.WORD)
        self.log_text.pack(fill=BOTH, expand=YES, pady=5)

    # -------------------- NAS Profile 管理 --------------------
    def _refresh_nas_dropdown(self):
        """刷新 NAS dropdown 列表"""
        profiles = self.profile_mgr.list_profiles()
        if profiles:
            display = [f"{p.name}  ({p.user}@{p.host})" for p in profiles]
            self.nas_combo["values"] = display
            # 选中当前
            current = self.profile_mgr.get_current()
            if current:
                for i, p in enumerate(profiles):
                    if p.id == current.id:
                        self.nas_combo.current(i)
                        break
        else:
            self.nas_combo["values"] = ["(暂无 NAS, 点 ➕ 添加)"]
            self.nas_combo.current(0)

    def _on_nas_changed(self, event=None):
        """NAS dropdown 切换时: 1. 设置 current_id 2. 自动填表单 3. 自动填密码"""
        profiles = self.profile_mgr.list_profiles()
        if not profiles:
            self._clear_connection_form()
            return

        idx = self.nas_combo.current()
        if idx < 0 or idx >= len(profiles):
            return
        new_profile = profiles[idx]
        self.profile_mgr.set_current(new_profile.id)

        # 自动填密码 (keyring)
        if self.profile_mgr.has_password(new_profile.id):
            pwd = self.profile_mgr.get_password(new_profile.id)
            self.password_var.set(pwd)
            self._log(f"🔑 已从 keyring 自动填入密码 (NAS: {new_profile.name})")
        else:
            self.password_var.set("")

        # 更新连接 Tab 显示
        self.info_name.config(text=new_profile.name)
        self.info_os.config(text="飞牛 OS" if new_profile.os_type == "fnos" else "极空间")
        self.info_addr.config(text=f"{new_profile.host}:{new_profile.port}")
        self.info_user.config(text=new_profile.user)

    def _clear_connection_form(self):
        self.info_name.config(text="—")
        self.info_os.config(text="—")
        self.info_addr.config(text="—")
        self.info_user.config(text="—")
        self.password_var.set("")

    def _add_nas_profile(self):
        """添加新 NAS profile"""
        dialog = NASProfileDialog(self.root)
        result = dialog.show()
        if result:
            new_p = NASProfile(
                id=ProfileManager.new_id(),
                name=result["name"],
                host=result["host"],
                port=result["port"],
                user=result["user"],
                os_type=result["os_type"],
            )
            self.profile_mgr.add(new_p)
            self._refresh_nas_dropdown()
            # 选中新加的
            profiles = self.profile_mgr.list_profiles()
            for i, p in enumerate(profiles):
                if p.id == new_p.id:
                    self.nas_combo.current(i)
                    break
            self._on_nas_changed()
            self._log(f"➕ 已添加 NAS: {new_p.name}")

    def _edit_nas_profile(self):
        """编辑当前 NAS"""
        current = self.profile_mgr.get_current()
        if not current:
            messagebox.showwarning("提示", "请先选择 NAS")
            return
        dialog = NASProfileDialog(self.root, profile=current)
        result = dialog.show()
        if result:
            current.name = result["name"]
            current.host = result["host"]
            current.port = result["port"]
            current.user = result["user"]
            current.os_type = result["os_type"]
            self.profile_mgr.update(current)
            self._refresh_nas_dropdown()
            self._on_nas_changed()
            self._log(f"✏️ 已更新 NAS: {current.name}")

    def _remove_nas_profile(self):
        """删除当前 NAS"""
        current = self.profile_mgr.get_current()
        if not current:
            messagebox.showwarning("提示", "请先选择 NAS")
            return
        if not messagebox.askyesno("确认", f"删除 NAS '{current.name}'?\n(同时删除 keyring 里保存的密码)"):
            return
        self.profile_mgr.remove(current.id)
        self._refresh_nas_dropdown()
        self._on_nas_changed()
        self._log(f"🗑 已删除 NAS: {current.name}")

    def _reset_profiles(self):
        """重置: 清空所有 NAS (调试用)"""
        if messagebox.askyesno("确认重置", "将删除所有 NAS 配置和 keyring 密码, 确认?"):
            for p in list(self.profile_mgr.profiles.keys()):
                self.profile_mgr.remove(p)
            self._refresh_nas_dropdown()
            self._on_nas_changed()

    def _migrate_legacy_config(self):
        """v1.0 单 NAS 配置 → v1.1+ 多 NAS (一次性)

        v1.3: 同步清洗 host 字段 (去 scheme/userinfo/path), 兼容 v1.0 污染数据
        """
        if not LEGACY_CONFIG_FILE.exists():
            return
        if self.profile_mgr.profiles:
            return  # 已经有 profile, 不迁移
        try:
            data = json.loads(LEGACY_CONFIG_FILE.read_text(encoding="utf-8"))
            # v1.3 清洗: 复用同样的清洗规则
            host, port_from_host = extract_port_from_host(data.get("host", "192.168.3.88"))
            # v1.0 config 有 port 字段, 优先用; 没有就用 host 里提取的
            stored_port = data.get("port")
            if stored_port:
                port = int(stored_port)
            elif port_from_host:
                port = port_from_host
            else:
                port = 22

            new_id = ProfileManager.new_id()
            profile = NASProfile(
                id=new_id,
                name=data.get("name", "默认 NAS"),
                host=host,
                port=port,
                user=data.get("user", "necrata"),
                os_type=data.get("os_type", "fnos"),
            )
            self.profile_mgr.add(profile)
            self.profile_mgr.set_current(new_id)
            self._log(f"🔄 已从 v1.0 配置迁移: {profile.name} (host={host}, port={port})")
            # 不删旧文件, 留着作为参考
        except Exception as e:
            print(f"[Migration] 失败: {e}")

    # -------------------- 连接 --------------------
    def _test_connection(self):
        current = self.profile_mgr.get_current()
        if not current:
            messagebox.showerror("错误", "请先在顶部选择一个 NAS (或 ➕ 添加)")
            return
        pwd = self.password_var.get()
        if not pwd:
            # 尝试从 keyring 再取一次
            pwd = self.profile_mgr.get_password(current.id) or ""
            if pwd:
                self.password_var.set(pwd)
        if not pwd:
            messagebox.showerror("错误", "请输入密码")
            return

        self._log(f"测试连接到 {current.user}@{current.host}:{current.port} ({current.os_type})...")
        threading.Thread(
            target=self._test_connection_thread,
            args=(current, pwd),
            daemon=True,
        ).start()

    def _test_connection_thread(self, profile, pwd):
        try:
            ok, msg = self.connection.connect(
                profile.host, profile.port, profile.user, pwd, profile.os_type
            )
            self.connection_result.delete("1.0", tk.END)
            self.connection_result.insert("1.0", msg)
            if ok:
                self.status_label.config(text=f"● 已连接: {profile.name}", foreground="green")
                self._log(f"✅ 连接成功: {profile.name}\n{msg}")
                self.current_password = pwd
                # 保存密码到 keyring
                if self.save_pwd_var.get() and KEYRING_AVAILABLE:
                    if self.profile_mgr.save_password(profile.id, pwd):
                        self._log(f"🔑 密码已保存到 keyring")
            else:
                self.status_label.config(text="● 连接失败", foreground="red")
                self._log(f"❌ {msg}")
        except Exception as e:
            self._log(f"❌ 异常: {type(e).__name__}: {e}")
            self.status_label.config(text="● 连接异常", foreground="red")

    def _delete_saved_password(self):
        current = self.profile_mgr.get_current()
        if not current:
            return
        self.profile_mgr.delete_password(current.id)
        self._log(f"🗝 已删除 keyring 里的密码 (NAS: {current.name})")

    def _disconnect(self):
        self.connection.disconnect()
        self.current_password = None
        self.status_label.config(text="● 未连接", foreground="gray")
        self._log("已断开连接")

    # -------------------- 安装/停止/重启/拉取 (用进度窗口) --------------------
    def _install_selected(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先连接")
            return
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请选择要安装的应用")
            return

        mem_mb = total_memory_mb(selected)
        if not messagebox.askyesno(
            "确认",
            f"将安装 {len(selected)} 个应用, 预估内存 {mem_mb/1024:.1f}GB\n\n确认?"
        ):
            return

        self._log(f"=== 开始安装: {', '.join(selected)} ===")
        threading.Thread(target=self._install_thread, args=(selected,), daemon=True).start()

    def _install_thread(self, apps):
        progress = ProgressWindow(self.root, title="安装进度 (实时日志)")
        # v1.7: 后台 heartbeat thread, 每 15s 推一条 "⏳ 仍在处理"
        # 防止 docker compose pull 长时间无日志时用户误判为卡死
        import threading as _th
        stop_heartbeat = _th.Event()
        def _hb():
            while not stop_heartbeat.is_set():
                if stop_heartbeat.wait(15):
                    return
                try:
                    progress.heartbeat("⏳ 仍在处理中, 请稍候...")
                except Exception:
                    pass
        hb_thread = _th.Thread(target=_hb, daemon=True)
        hb_thread.start()
        try:
            ok, msg = self.connection.install_apps_streaming(
                apps,
                DOCKER_COMPOSE_YML,
                on_line=progress.append_log,
                on_progress=progress.update_progress,
                is_cancelled=progress.is_cancelled,
            )
            progress.finish(ok, msg if ok else f"❌ {msg}")
        except Exception as e:
            progress.finish(False, f"异常: {type(e).__name__}: {e}")
        finally:
            stop_heartbeat.set()
            progress.wait_for_close()

    def _stop_selected(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先连接")
            return
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请选择要停止的应用")
            return
        if not messagebox.askyesno("确认", f"将停止 {len(selected)} 个应用\n\n确认?"):
            return
        self._log(f"=== 停止: {', '.join(selected)} ===")
        threading.Thread(target=self._stop_thread, args=(selected,), daemon=True).start()

    def _stop_thread(self, apps):
        progress = ProgressWindow(self.root, title="停止进度")
        try:
            progress.update_progress(30, f"正在停止 {len(apps)} 个应用...")
            ok, msg = self.connection.stop_apps(apps, DOCKER_COMPOSE_YML)
            progress.finish(ok, f"{'✅' if ok else '❌'} {msg[:500]}")
            self._log(f"{'✅' if ok else '❌'} 停止\n{msg[:1000]}")
        except Exception as e:
            progress.finish(False, f"异常: {e}")
        finally:
            progress.wait_for_close()

    def _restart_selected(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先连接")
            return
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请选择要重启的应用")
            return
        self._log(f"=== 重启: {', '.join(selected)} ===")
        threading.Thread(target=self._restart_thread, args=(selected,), daemon=True).start()

    def _restart_thread(self, apps):
        progress = ProgressWindow(self.root, title="重启进度")
        try:
            progress.update_progress(30, f"正在重启 {len(apps)} 个应用...")
            ok, msg = self.connection.restart_apps(apps, DOCKER_COMPOSE_YML)
            progress.finish(ok, f"{'✅' if ok else '❌'} {msg[:500]}")
            self._log(f"{'✅' if ok else '❌'} 重启\n{msg[:1000]}")
        except Exception as e:
            progress.finish(False, f"异常: {e}")
        finally:
            progress.wait_for_close()

    def _pull_images(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先连接")
            return
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请选择要拉取的应用")
            return
        self._log(f"=== 拉取镜像: {', '.join(selected)} ===")
        threading.Thread(target=self._pull_thread, args=(selected,), daemon=True).start()

    def _pull_thread(self, apps):
        """v1.4 fix: 用真实 compose 上传 (之前 echo placeholder 被 docker 当 YAML 解析崩)"""
        progress = ProgressWindow(self.root, title="拉取镜像")
        try:
            ok, msg = self.connection.pull_apps_streaming(
                apps,
                DOCKER_COMPOSE_YML,
                on_line=progress.append_log,
                on_progress=progress.update_progress,
                is_cancelled=progress.is_cancelled,
            )
            progress.finish(ok, f"{'✅' if ok else '❌'} {msg[:500]}")
            self._log(f"{'✅' if ok else '❌'} 拉取\n{msg[:1000]}")
        except Exception as e:
            progress.finish(False, f"异常: {type(e).__name__}: {e}")
        finally:
            progress.wait_for_close()

    # -------------------- 状态 --------------------
    def _refresh_status(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先连接")
            return
        threading.Thread(target=self._refresh_status_thread, daemon=True).start()

    def _refresh_status_thread(self):
        containers = self.connection.get_all_apps_status()
        self.status_tree.delete(*self.status_tree.get_children())
        for c in containers:
            self.status_tree.insert("", tk.END, values=(c["name"], c["image"], c["status"], c["ports"]))

        used_gb, total_gb, percent = self.connection.check_disk_space()
        if total_gb > 0:
            self.disk_label.config(text=f"磁盘: {used_gb}G / {total_gb}G ({percent}%)")
        used_mb, total_mb, percent = self.connection.check_memory()
        if total_mb > 0:
            self.mem_remote_label.config(text=f"内存: {used_mb}MB / {total_mb}MB ({percent}%)")

        self._log(f"刷新状态: {len(containers)} 个容器")

    def _show_tree_menu(self, event):
        item = self.status_tree.identify_row(event.y)
        if item:
            self.status_tree.selection_set(item)
            self.tree_menu.tk_popup(event.x_root, event.y_root)

    def _show_container_logs(self):
        sel = self.status_tree.selection()
        if not sel:
            return
        name = self.status_tree.item(sel[0])["values"][0]
        logs = self.connection.get_container_logs(str(name), tail=200)
        top = tk.Toplevel(self.root)
        top.title(f"日志: {name}")
        top.geometry("800x500")
        text = scrolledtext.ScrolledText(top, wrap=tk.WORD)
        text.pack(fill=BOTH, expand=YES, padx=10, pady=10)
        text.insert("1.0", logs)

    def _restart_container(self):
        sel = self.status_tree.selection()
        if not sel:
            return
        name = self.status_tree.item(sel[0])["values"][0]
        # v1.5: sudo (docker socket 权限)
        threading.Thread(target=lambda: self.connection._docker_cmd(f"docker restart {name}")).start()
        self._log(f"重启容器: {name}")

    def _stop_container(self):
        sel = self.status_tree.selection()
        if not sel:
            return
        name = self.status_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("确认", f"停止容器 {name}?"):
            # v1.5: sudo (docker socket 权限)
            threading.Thread(target=lambda: self.connection._docker_cmd(f"docker stop {name}")).start()
            self._log(f"停止容器: {name}")

    # -------------------- 应用 Tab 事件 --------------------
    def _log(self, msg: str):
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _update_mem_label(self):
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        mem_mb = total_memory_mb(selected)
        self.mem_label.config(text=f"预估内存: {mem_mb} MB ({mem_mb/1024:.1f} GB)")

    def _on_profile_toggle(self, prof_key: str):
        var = self.profile_vars[prof_key]
        for app_key in get_apps_by_profile(prof_key):
            if app_key in self.app_checkboxes:
                self.app_checkboxes[app_key].set(var.get())

    # -------------------- 日志操作 --------------------
    def _clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _save_logs(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
        )
        if path:
            Path(path).write_text(self.log_text.get("1.0", tk.END), encoding="utf-8")
            self._log(f"日志已导出: {path}")

    def _show_about(self):
        about_text = (
            f"{APP_NAME} v{APP_VERSION}\n\n"
            "一键 SSH 到 NAS, 部署 Docker 应用\n\n"
            "v1.1 新功能:\n"
            "• 多 NAS profile 切换\n"
            "• keyring 密码自动保存\n"
            "• 实时进度窗口\n"
            "• 应用搜索 + 分组折叠\n\n"
            f"keyring 支持: {'✅' if KEYRING_AVAILABLE else '❌ (需 pip install keyring)'}"
        )
        messagebox.showinfo("关于", about_text)

    def _on_close(self):
        if self.connection.is_connected():
            self.connection.disconnect()
        self.root.destroy()


class NASProfileDialog:
    """添加/编辑 NAS profile 的对话框"""

    def __init__(self, parent, profile: NASProfile = None):
        self.result = None
        self.profile = profile
        self.top = tk.Toplevel(parent)
        self.top.title("编辑 NAS" if profile else "添加 NAS")
        self.top.geometry("420x320")
        self.top.transient(parent)
        self.top.grab_set()  # 模态

        frame = ttk.Frame(self.top, padding=20)
        frame.pack(fill=BOTH, expand=YES)

        ttk.Label(frame, text="名称:").grid(row=0, column=0, sticky=W, pady=8)
        self.name_var = tk.StringVar(value=profile.name if profile else "")
        ttk.Entry(frame, textvariable=self.name_var, width=30).grid(row=0, column=1, sticky=W)

        ttk.Label(frame, text="类型:").grid(row=1, column=0, sticky=W, pady=8)
        self.os_type_var = tk.StringVar(value=profile.os_type if profile else "fnos")
        ttk.Radiobutton(frame, text="飞牛 OS", variable=self.os_type_var, value="fnos").grid(row=1, column=1, sticky=W)
        ttk.Radiobutton(frame, text="极空间", variable=self.os_type_var, value="zspace").grid(row=1, column=2, sticky=W)

        ttk.Label(frame, text="IP 地址:").grid(row=2, column=0, sticky=W, pady=8)
        self.host_var = tk.StringVar(value=profile.host if profile else "")
        ttk.Entry(frame, textvariable=self.host_var, width=30).grid(row=2, column=1, sticky=W)

        ttk.Label(frame, text="SSH 端口:").grid(row=3, column=0, sticky=W, pady=8)
        self.port_var = tk.StringVar(value=str(profile.port) if profile else "22")
        ttk.Entry(frame, textvariable=self.port_var, width=10).grid(row=3, column=1, sticky=W)

        ttk.Label(frame, text="用户名:").grid(row=4, column=0, sticky=W, pady=8)
        self.user_var = tk.StringVar(value=profile.user if profile else "")
        ttk.Entry(frame, textvariable=self.user_var, width=20).grid(row=4, column=1, sticky=W)

        btn_frame = ttk.Frame(self.top, padding=(20, 0, 20, 20))
        btn_frame.pack(fill=X)
        ttk.Button(btn_frame, text="保存", command=self._on_save, bootstyle="success").pack(side=RIGHT, padx=5)
        ttk.Button(btn_frame, text="取消", command=self.top.destroy, bootstyle="secondary").pack(side=RIGHT)

    def _on_save(self):
        name = self.name_var.get().strip()
        host_raw = self.host_var.get().strip()
        port_str = self.port_var.get().strip()
        user = self.user_var.get().strip()

        if not name or not host_raw or not user:
            messagebox.showerror("错误", "名称、IP、用户名不能为空", parent=self.top)
            return

        # v1.3 清洗 host + 提取可能粘在 host 里的端口
        host, port_from_host = extract_port_from_host(host_raw)
        if not host:
            messagebox.showerror("错误", "host 清洗后为空, 请检查输入", parent=self.top)
            return

        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字", parent=self.top)
            return

        # 如果用户没改 port 字段 (默认 22) 且 host 里提取到端口, 提示用 host 里的
        if port == 22 and port_from_host and port_from_host != 22:
            if messagebox.askyesno(
                "端口提示",
                f"检测到 host 里带端口 {port_from_host}, 但 SSH 端口字段是默认 22.\n"
                f"用 host 里的端口 {port_from_host} 吗?",
                parent=self.top,
            ):
                port = port_from_host

        self.result = {
            "name": name,
            "host": host,
            "port": port,
            "user": user,
            "os_type": self.os_type_var.get(),
        }
        self.top.destroy()

    def show(self):
        """模态显示, 阻塞直到对话框关闭. 返回 dict 或 None"""
        self.top.wait_window()
        return self.result


def main():
    app = NASDeployerApp()
    app.root.mainloop()


if __name__ == "__main__":
    main()
