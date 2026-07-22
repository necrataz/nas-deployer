# ==============================================================================
# NAS Deployer v2.0.6 - 进度条 + 实时日志流窗口
# ==============================================================================
# v1.7 修复 (用户实测 v1.6 反馈 "安装过程中, cmd 那个窗口会卡住"):
#   1. 日志行数上限 5000 行, 超出循环删除最早行 (避免 ScrolledText 越加越卡)
#   2. UI 批处理: 队列里攒最多 50 行日志, 100ms tick 一次批量 insert (避免每行 after/poll)
#   3. 强制刷新 disable 后大小写正常 (老版本 tk 在长文本下 set 会卡)
#   4. finish() 后不再 schedule after (避免空转)
# ==============================================================================

import queue
import threading
import time
import tkinter as tk
from tkinter import scrolledtext

import ttkbootstrap as ttk


# v1.7: 日志上限与批处理常量
MAX_LOG_LINES = 5000      # 超过此行数则从顶部删除, 防 OOM / 卡 UI
LOG_BATCH_MAX = 50        # 每 tick 最多从队列里取这么多行, 避免 UI 卡顿
POLL_INTERVAL_MS = 100    # UI tick 间隔


class ProgressWindow:
    """长操作的进度展示窗口

    特性:
    - 进度条 (0-100)
    - 状态文字 (e.g. "正在拉取镜像...")
    - 实时日志流 (从 worker thread 推到 queue, UI 线程消费)
    - 取消按钮 (worker thread 轮询 is_cancelled())
    - 完成后按钮变 "关闭"

    v1.7: 日志上限 + UI 批处理, 防卡死
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
        # v1.7: 日志已写入行数 (用来判断是否超上限)
        self._log_lines = 0
        # v1.7: 日志最近一行时间戳, 用于心跳
        self._last_log_ts = time.time()

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
        # v1.7: 用 Text 而非 ScrolledText, 自己管滚动更高效
        log_frame = ttk.Frame(self.top, padding=(10, 5))
        log_frame.pack(fill=tk.BOTH, expand=tk.YES)
        self.log_text = tk.Text(
            log_frame,
            wrap=tk.NONE,             # 不换行, 长行用横向滚动条
            bg="#1e1e1e",
            fg="#d4d4d4",
            insertbackground="white",
            font=("Consolas", 10),
            height=20,
        )
        # 垂直滚动条
        v_scroll = ttk.Scrollbar(log_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        # 水平滚动条 (因为 wrap=NONE)
        h_scroll = ttk.Scrollbar(log_frame, orient=tk.HORIZONTAL, command=self.log_text.xview)
        self.log_text.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
        # 布局
        self.log_text.grid(row=0, column=0, sticky="nsew")
        v_scroll.grid(row=0, column=1, sticky="ns")
        h_scroll.grid(row=1, column=0, sticky="ew")
        log_frame.rowconfigure(0, weight=1)
        log_frame.columnconfigure(0, weight=1)
        # v1.7: 关掉手动编辑, 大文本下 set 更快
        self.log_text.configure(state=tk.DISABLED)

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
        self._scheduled_after = self.top.after(POLL_INTERVAL_MS, self._poll_queue)

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

    def heartbeat(self, msg: str = None):
        """v1.7: worker 线程调用, 强制让 UI 更新一条 '还在干活' 的提示
        防止 30 分钟无日志时被用户误判为卡死
        """
        text = msg or f"[⏳ {time.strftime('%H:%M:%S')}] 仍在处理..."
        self.queue.put(("heartbeat", text))

    def finish(self, success: bool = True, final_message: str = ""):
        msg = final_message or ("✅ 操作完成" if success else "❌ 操作失败")
        self.queue.put(("finish", success, msg))

    # ============ UI 线程 (Tkinter mainloop) ============
    def _poll_queue(self):
        """每 100ms 从 queue 取事件, 更新 UI

        v1.7: 批量取, 每 tick 最多 LOG_BATCH_MAX 行, 防 UI 阻塞
        """
        try:
            progress_updated = False
            status_updated = False
            logs_to_insert = []
            finished_event = None

            for _ in range(LOG_BATCH_MAX * 2):  # 多取一些, progress/status 也算
                try:
                    item = self.queue.get_nowait()
                except queue.Empty:
                    break

                kind = item[0]
                if kind == "progress":
                    self.progress_var.set(item[1])
                    progress_updated = True
                elif kind == "status":
                    self.status_var.set(item[1])
                    status_updated = True
                elif kind in ("log", "heartbeat"):
                    logs_to_insert.append(item[1] + "\n")
                elif kind == "finish":
                    finished_event = item

            # v1.7: 批量 insert 日志, 然后 trim
            if logs_to_insert:
                self._insert_logs_batch(logs_to_insert)

            if finished_event:
                _, success, msg = finished_event
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
                # v1.7: finish 后还 schedule 一次, 让用户看到 100% + 最终状态, 再停
                self._scheduled_after = self.top.after(
                    1500, self._stop_polling
                )
                return
        except Exception as e:
            # v1.7: UI 层异常也不让窗口挂死, 输出到 stderr
            try:
                import sys
                print(f"[ProgressWindow UI ERROR] {type(e).__name__}: {e}", file=sys.stderr)
            except Exception:
                pass

        # 继续 poll, 直到窗口销毁或 finish 后停
        try:
            self._scheduled_after = self.top.after(POLL_INTERVAL_MS, self._poll_queue)
        except tk.TclError:
            pass  # 窗口已销毁

    def _insert_logs_batch(self, lines):
        """v1.7: 一次性 insert 多行日志, 然后裁剪到 MAX_LOG_LINES

        之前每行都 insert + see, docker pull 输出 100+ 行就开始卡
        现在批量 insert, 末尾裁剪, 几乎不卡
        """
        if not lines:
            return

        # 临时允许写
        self.log_text.configure(state=tk.NORMAL)
        self.log_text.insert(tk.END, "".join(lines))
        self._log_lines += len(lines)

        # 裁剪: 超过上限则删掉顶部
        if self._log_lines > MAX_LOG_LINES:
            # 删掉顶部 1000 行 (保留 4000 行), 一次删太多 tk 会卡
            excess = self._log_lines - MAX_LOG_LINES + 1000
            try:
                # "1.0" 到第 N 行末尾
                line_to_delete = f"{excess + 1}.0"
                self.log_text.delete("1.0", line_to_delete)
                self._log_lines -= excess
            except Exception:
                pass

        # 滚动到末尾
        self.log_text.see(tk.END)
        # 关掉写
        self.log_text.configure(state=tk.DISABLED)

        # v1.7: 标记最后日志时间, 心跳判断用
        self._last_log_ts = time.time()

    def _stop_polling(self):
        """v1.7: finish 后停掉 polling after"""
        try:
            if self._scheduled_after:
                self.top.after_cancel(self._scheduled_after)
                self._scheduled_after = None
        except tk.TclError:
            pass

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