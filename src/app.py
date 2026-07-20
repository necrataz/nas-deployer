# ==============================================================================
# NAS 一键部署工具 - 主 GUI (ttkbootstrap)
# ==============================================================================

import os
import sys
import json
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, filedialog
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


# 全局常量
CONFIG_DIR = Path.home() / ".nas_deployer"
CONFIG_FILE = CONFIG_DIR / "config.json"
APP_VERSION = "1.0.0"
APP_NAME = "NAS 一键部署工具"


class NASDeployerApp:
    def __init__(self):
        self.root = ttk.Window(themename="cosmo")
        self.root.title(f"{APP_NAME} v{APP_VERSION}")
        self.root.geometry("1000x720")
        self.root.minsize(900, 600)

        # State
        self.connection = NASConnection()
        self.profile_vars: dict[str, tk.IntVar] = {}
        self.app_checkboxes: dict[str, tk.IntVar] = {}
        self.status_tree = None

        # Build
        self._build_menu()
        self._build_ui()
        self._load_config()

        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    # -------------------- UI 构建 --------------------
    def _build_menu(self):
        """顶部菜单栏"""
        menubar = tk.Menu(self.root)

        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="导出日志...", command=self._save_logs)
        file_menu.add_separator()
        file_menu.add_command(label="退出", command=self._on_close)
        menubar.add_cascade(label="文件", menu=file_menu)

        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="关于", command=self._show_about)
        menubar.add_cascade(label="帮助", menu=help_menu)

        self.root.config(menu=menubar)

    def _build_ui(self):
        """主界面"""
        # Top bar
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=X)

        ttk.Label(
            top,
            text=f"🚀 {APP_NAME}",
            font=("Helvetica", 16, "bold"),
        ).pack(side=LEFT)

        self.status_label = ttk.Label(top, text="● 未连接", foreground="gray", font=("Helvetica", 11))
        self.status_label.pack(side=RIGHT, padx=10)

        # Tabs
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=BOTH, expand=YES, padx=10, pady=(0, 10))

        self._build_connection_tab()
        self._build_apps_tab()
        self._build_status_tab()
        self._build_logs_tab()

    def _build_connection_tab(self):
        tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(tab, text="📡 连接")

        # NAS Type
        type_frame = ttk.LabelFrame(tab, text="NAS 类型", padding=10)
        type_frame.grid(row=0, column=0, columnspan=3, sticky=EW, pady=(0, 10))
        self.os_type_var = tk.StringVar(value="fnos")
        ttk.Radiobutton(
            type_frame, text="飞牛 OS (fnOS)",
            variable=self.os_type_var, value="fnos", bootstyle="primary"
        ).pack(side=LEFT, padx=20)
        ttk.Radiobutton(
            type_frame, text="极空间 (ZSpace)",
            variable=self.os_type_var, value="zspace", bootstyle="info"
        ).pack(side=LEFT, padx=20)

        # 表单
        form = ttk.Frame(tab)
        form.grid(row=1, column=0, columnspan=3, sticky=EW)

        ttk.Label(form, text="IP 地址:").grid(row=0, column=0, sticky=W, pady=8)
        self.host_var = tk.StringVar(value="192.168.3.88")
        ttk.Entry(form, textvariable=self.host_var, width=30).grid(row=0, column=1, sticky=W)

        ttk.Label(form, text="SSH 端口:").grid(row=0, column=2, sticky=W, padx=(20, 0))
        self.port_var = tk.StringVar(value="22")
        ttk.Entry(form, textvariable=self.port_var, width=10).grid(row=0, column=3, sticky=W)

        ttk.Label(form, text="用户名:").grid(row=1, column=0, sticky=W, pady=8)
        self.user_var = tk.StringVar(value="necrata")
        ttk.Entry(form, textvariable=self.user_var, width=20).grid(row=1, column=1, sticky=W)

        ttk.Label(form, text="密码:").grid(row=2, column=0, sticky=W, pady=8)
        self.password_var = tk.StringVar()
        self.password_entry = ttk.Entry(form, textvariable=self.password_var, width=30, show="•")
        self.password_entry.grid(row=2, column=1, sticky=W)

        # Button row
        btn_frame = ttk.Frame(tab)
        btn_frame.grid(row=3, column=0, columnspan=4, pady=20)

        ttk.Button(
            btn_frame, text="🔌 测试连接",
            command=self._test_connection, bootstyle="success"
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text="💾 保存配置",
            command=self._save_config, bootstyle="secondary"
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            btn_frame, text="🔓 断开",
            command=self._disconnect, bootstyle="danger-outline"
        ).pack(side=LEFT, padx=5)

        # Connection result
        ttk.Label(tab, text="连接结果:", font=("Helvetica", 11)).grid(row=4, column=0, sticky=NW, pady=(10, 0))
        self.connection_result = scrolledtext.ScrolledText(tab, height=12, width=80, wrap=tk.WORD)
        self.connection_result.grid(row=5, column=0, columnspan=4, sticky=EW, pady=5)

        tab.columnconfigure(3, weight=1)

    def _build_apps_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📦 应用")

        # Profile 快速勾选
        profile_frame = ttk.LabelFrame(tab, text="快速勾选 (按 profile)", padding=10)
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

        # 应用详细列表
        apps_frame = ttk.LabelFrame(tab, text="应用列表 (单独勾选)", padding=10)
        apps_frame.pack(fill=BOTH, expand=YES, pady=(0, 10))

        # Scrollable
        canvas = tk.Canvas(apps_frame, height=300)
        scrollbar = ttk.Scrollbar(apps_frame, orient=VERTICAL, command=canvas.yview)
        scrollable_frame = ttk.Frame(canvas)

        scrollable_frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        canvas.create_window((0, 0), window=scrollable_frame, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=LEFT, fill=BOTH, expand=YES)
        scrollbar.pack(side=RIGHT, fill=Y)

        # 应用列表
        sorted_apps = sorted(get_visible_apps().items(), key=lambda x: (x[1]["category"], x[0]))
        for i, (app_key, app_data) in enumerate(sorted_apps):
            var = tk.IntVar()
            self.app_checkboxes[app_key] = var

            port_str = f" :{app_data['port']}" if app_data.get("port") else ""
            warning = " ⚠️" if app_data.get("warning") else ""
            text = f"  {app_data['name']}{port_str}  —  {app_data['desc']}{warning}"

            ttk.Checkbutton(scrollable_frame, text=text, variable=var).grid(
                row=i, column=0, sticky=W, padx=10, pady=2
            )

        # 操作按钮
        action_frame = ttk.Frame(tab)
        action_frame.pack(fill=X, pady=5)

        ttk.Button(
            action_frame, text="▶ 安装选中",
            command=self._install_selected, bootstyle="success"
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            action_frame, text="⏹ 停止选中",
            command=self._stop_selected, bootstyle="warning"
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            action_frame, text="🔄 重启选中",
            command=self._restart_selected, bootstyle="info"
        ).pack(side=LEFT, padx=5)

        ttk.Button(
            action_frame, text="📥 拉取镜像",
            command=self._pull_images, bootstyle="secondary-outline"
        ).pack(side=LEFT, padx=5)

        self.mem_label = ttk.Label(action_frame, text="预估内存: 0 MB")
        self.mem_label.pack(side=RIGHT, padx=10)

        # Bind checkbox changes to update memory
        for var in self.app_checkboxes.values():
            var.trace_add("write", self._update_mem_label)

    def _build_status_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="📊 状态")

        # NAS 资源
        info_frame = ttk.LabelFrame(tab, text="NAS 资源", padding=10)
        info_frame.pack(fill=X, pady=(0, 10))

        self.disk_label = ttk.Label(info_frame, text="磁盘: --")
        self.disk_label.pack(side=LEFT, padx=20)

        self.mem_remote_label = ttk.Label(info_frame, text="内存: --")
        self.mem_remote_label.pack(side=LEFT, padx=20)

        # 操作按钮
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=X, pady=5)
        ttk.Button(btn_frame, text="🔄 刷新状态", command=self._refresh_status, bootstyle="primary").pack(side=LEFT, padx=5)

        # Treeview
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

        # 右键菜单
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

    # -------------------- 事件处理 --------------------
    def _log(self, msg: str):
        """日志输出"""
        ts = datetime.now().strftime("%H:%M:%S")
        line = f"[{ts}] {msg}"
        self.log_text.insert(tk.END, line + "\n")
        self.log_text.see(tk.END)
        self.root.update_idletasks()

    def _update_mem_label(self, *args):
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        mem_mb = total_memory_mb(selected)
        self.mem_label.config(text=f"预估内存: {mem_mb} MB ({mem_mb/1024:.1f} GB)")

    def _on_profile_toggle(self, prof_key: str):
        """profile 勾选时, 自动勾选/取消该组所有应用"""
        var = self.profile_vars[prof_key]
        for app_key in get_apps_by_profile(prof_key):
            if app_key in self.app_checkboxes:
                self.app_checkboxes[app_key].set(var.get())

    def _test_connection(self):
        host = self.host_var.get().strip()
        port_str = self.port_var.get().strip()
        user = self.user_var.get().strip()
        pwd = self.password_var.get()
        os_type = self.os_type_var.get()

        if not host or not user or not pwd:
            messagebox.showerror("错误", "请填写 IP、用户名、密码")
            return
        try:
            port = int(port_str)
        except ValueError:
            messagebox.showerror("错误", "端口必须是数字")
            return

        self._log(f"测试连接到 {user}@{host}:{port} ({os_type})...")
        threading.Thread(
            target=self._test_connection_thread,
            args=(host, port, user, pwd, os_type),
            daemon=True,
        ).start()

    def _test_connection_thread(self, host, port, user, pwd, os_type):
        try:
            ok, msg = self.connection.connect(host, port, user, pwd, os_type)
            self.connection_result.delete("1.0", tk.END)
            self.connection_result.insert("1.0", msg)
            if ok:
                self.status_label.config(text=f"● 已连接: {user}@{host}", foreground="green")
                self._log(f"✅ 连接成功\n{msg}")
            else:
                self.status_label.config(text="● 连接失败", foreground="red")
                self._log(f"❌ {msg}")
        except Exception as e:
            self._log(f"❌ 异常: {type(e).__name__}: {e}")
            self.status_label.config(text="● 连接异常", foreground="red")

    def _disconnect(self):
        self.connection.disconnect()
        self.status_label.config(text="● 未连接", foreground="gray")
        self._log("已断开连接")

    def _install_selected(self):
        if not self.connection.is_connected():
            messagebox.showerror("错误", "请先测试连接")
            return
        selected = [k for k, v in self.app_checkboxes.items() if v.get()]
        if not selected:
            messagebox.showinfo("提示", "请选择要安装的应用")
            return

        mem_mb = total_memory_mb(selected)
        if not messagebox.askyesno("确认", f"将安装 {len(selected)} 个应用, 预估内存 {mem_mb/1024:.1f}GB\n\n确认?"):
            return

        self._log(f"=== 开始安装: {', '.join(selected)} ===")
        threading.Thread(target=self._install_thread, args=(selected,), daemon=True).start()

    def _install_thread(self, apps):
        ok, msg = self.connection.install_apps(apps, DOCKER_COMPOSE_YML)
        if ok:
            self._log(f"✅ 安装成功\n{msg[:2000]}")
        else:
            self._log(f"❌ 安装失败\n{msg[:2000]}")

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
        ok, msg = self.connection.stop_apps(apps, DOCKER_COMPOSE_YML)
        self._log(f"{'✅' if ok else '❌'} 停止\n{msg[:1000]}")

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
        ok, msg = self.connection.restart_apps(apps, DOCKER_COMPOSE_YML)
        self._log(f"{'✅' if ok else '❌'} 重启\n{msg[:1000]}")

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
        ok, msg = self.connection.pull_images(apps, DOCKER_COMPOSE_YML)
        self._log(f"{'✅' if ok else '❌'} 拉取\n{msg[:2000]}")

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

        # 资源
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
        # 弹窗显示
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
        threading.Thread(target=lambda: self.connection.run_command(f"docker restart {name}")).start()
        self._log(f"重启容器: {name}")

    def _stop_container(self):
        sel = self.status_tree.selection()
        if not sel:
            return
        name = self.status_tree.item(sel[0])["values"][0]
        if messagebox.askyesno("确认", f"停止容器 {name}?"):
            threading.Thread(target=lambda: self.connection.run_command(f"docker stop {name}")).start()
            self._log(f"停止容器: {name}")

    # -------------------- 配置 --------------------
    def _save_config(self):
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        config = {
            "host": self.host_var.get(),
            "port": self.port_var.get(),
            "user": self.user_var.get(),
            "os_type": self.os_type_var.get(),
        }
        CONFIG_FILE.write_text(json.dumps(config, indent=2, ensure_ascii=False))
        self._log(f"配置已保存: {CONFIG_FILE}")

    def _load_config(self):
        if CONFIG_FILE.exists():
            try:
                config = json.loads(CONFIG_FILE.read_text())
                self.host_var.set(config.get("host", "192.168.3.88"))
                self.port_var.set(config.get("port", "22"))
                self.user_var.set(config.get("user", "necrata"))
                self.os_type_var.set(config.get("os_type", "fnos"))
                self._log(f"已加载配置: {config.get('host')}")
            except Exception as e:
                self._log(f"加载配置失败: {e}")

    # -------------------- 工具 --------------------
    def _clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _save_logs(self):
        path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            initialfile=f"nas_deploy_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
        )
        if path:
            Path(path).write_text(self.log_text.get("1.0", tk.END))
            self._log(f"日志已保存: {path}")

    def _show_about(self):
        messagebox.showinfo(
            "关于",
            f"{APP_NAME} v{APP_VERSION}\n\n"
            f"一键部署 26 个 Docker 应用到飞牛 OS / 极空间\n\n"
            f"依赖: paramiko + scp + ttkbootstrap\n"
            f"打包: PyInstaller → Windows EXE",
        )

    def _on_close(self):
        self.connection.disconnect()
        self.root.destroy()

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    app = NASDeployerApp()
    app.run()