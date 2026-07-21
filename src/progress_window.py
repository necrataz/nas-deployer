# ==============================================================================
# NAS Deployer v1.1 - 进度条 + 实时日志流窗口
# ==============================================================================

import queue
import threading
import tkinter as tk
from tkinter import scrolledtext

import ttkbootstrap as ttk


class ProgressWindow:
    """长操作的进度展示窗口

    特性:
    - 进度条 (0-100)
    - 状态文字 (e.g. "正在拉取镜像...")
    - 实时日志流 (从 worker thread 推到 queue, UI 线程消费)
    - 取消按钮 (worker thread 轮询 is_cancelled())
    - 完成后按钮变 "关闭"
    """

    def __init__(self, parent, title: str = "操作进度", can_cancel: bool = True):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.geometry("850x520")
        self.top.transient(parent)

        # 取消标志 (thread-safe)
        self.cancel_event = threading.Event()
        # queue 用于 worker -> UI 通信
        self.queue: queue.Queue = queue.Queue()
        # 已完成标志 (UI 用来切按钮文字)
        self.finished = False
        self.success = False

        # ---- 进度条 ----
        self.progress_var = tk.DoubleVar(value=0)
        progress_frame = ttk.Frame(self.top, padding=(10, 10, 10, 5))
        progress_frame.pack(fill=tk.X)
        self.progress = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            bootstyle="success-striped",
            length=800,
        )
        self.progress.pack(fill=tk.X)

        # ---- 状态文字 ----
        self.status_var = tk.StringVar(value="准备中...")
        status_frame = ttk.Frame(self.top, padding=(10, 0))
        status_frame.pack(fill=tk.X)
        self.status_label = ttk.Label(
            status_frame, textvariable=self.status_var, font=("Helvetica", 10)
        )
        self.status_label.pack(side=tk.LEFT)

        # ---- 日志区 (深色, 等宽字体, 适合看 docker compose 输出) ----
        log_frame = ttk.Frame(self.top, padding=(10, 5))
        log_frame.pack(fill=tk.BOTH, expand=tk.YES)
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 10),
        )
        self.log_text.pack(fill=tk.BOTH, expand=tk.YES)

        # ---- 按钮区 ----
        btn_frame = ttk.Frame(self.top, padding=(10, 5, 10, 10))
        btn_frame.pack(fill=tk.X)
        self.cancel_btn = ttk.Button(
            btn_frame,
            text="⏹ 取消" if can_cancel else "关闭",
            command=self._on_cancel,
            bootstyle="danger" if can_cancel else "secondary",
        )
        self.cancel_btn.pack(side=tk.RIGHT)

        if not can_cancel:
            self.cancel_btn.config(state=tk.DISABLED)

        self.top.protocol("WM_DELETE_WINDOW", self._on_close_window)

        # 启动 UI 更新循环 (每 100ms poll queue)
        self.top.after(100, self._poll_queue)

    # ============ Worker thread 调用的 API ============
    def is_cancelled(self) -> bool:
        return self.cancel_event.is_set()

    def update_progress(self, percent: float, status: str = None):
        self.queue.put(("progress", percent))
        if status is not None:
            self.queue.put(("status", status))

    def append_log(self, line: str):
        self.queue.put(("log", line))

    def append_log_lines(self, lines: list):
        """批量追加多行日志"""
        for line in lines:
            self.queue.put(("log", line))

    def finish(self, success: bool = True, final_message: str = ""):
        msg = final_message or ("✅ 操作完成" if success else "❌ 操作失败")
        self.queue.put(("finish", success, msg))

    # ============ UI 线程 (Tkinter mainloop) ============
    def _poll_queue(self):
        """每 100ms 从 queue 取事件, 更新 UI"""
        try:
            while True:
                item = self.queue.get_nowait()
                kind = item[0]
                if kind == "progress":
                    self.progress_var.set(item[1])
                elif kind == "status":
                    self.status_var.set(item[1])
                elif kind == "log":
                    self.log_text.insert(tk.END, item[1] + "\n")
                    self.log_text.see(tk.END)
                elif kind == "finish":
                    _, success, msg = item
                    self.finished = True
                    self.success = success
                    self.status_var.set(msg)
                    self.progress_var.set(100 if success else 0)
                    # 切按钮: 取消 → 关闭
                    self.cancel_btn.config(text="关闭", command=self.top.destroy)
                    # 进度条颜色
                    try:
                        style = "success" if success else "danger"
                        self.progress.configure(bootstyle=style)
                    except Exception:
                        pass
        except queue.Empty:
            pass

        # 继续 poll, 直到窗口销毁
        try:
            self.top.after(100, self._poll_queue)
        except tk.TclError:
            pass  # 窗口已销毁

    def _on_cancel(self):
        if self.finished:
            # 已完成 → 关闭窗口
            self.top.destroy()
        else:
            # 用户取消
            self.cancel_event.set()
            self.status_var.set("正在取消, 请稍候...")
            self.cancel_btn.config(state=tk.DISABLED)

    def _on_close_window(self):
        if self.finished:
            self.top.destroy()
        else:
            # 窗口关闭等同于取消
            self.cancel_event.set()
            self.status_var.set("正在取消, 请稍候...")

    # ============ 同步阻塞 (主线程调, 等所有操作完成) ============
    def wait_for_close(self):
        """阻塞直到窗口被销毁"""
        self.top.wait_window()

    def was_successful(self) -> bool:
        return self.success
