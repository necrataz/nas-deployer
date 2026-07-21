# ==============================================================================
# NAS Deployer v2.0 - NAS 服务导航聚合
# ==============================================================================
# v2.0 新增: 一键打开所有已安装服务的统一导航页
# 原理: 内嵌 HTML 模板 + 内置 HTTP server + webbrowser 打开
# 用法: NASDeployer 菜单 "🧭 NAS 导航" → 自动开浏览器 → 显示已安装服务卡片墙
# ==============================================================================

import threading
import socket
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
from typing import Dict, List, Optional

from apps import APPS


# 分类显示名 + emoji
CATEGORY_DISPLAY = {
    "movie":  ("🎬 影视", "#e74c3c"),
    "read":   ("📚 阅读", "#3498db"),
    "nav":    ("🧭 导航", "#2ecc71"),
    "ai":     ("🤖 AI",   "#9b59b6"),
    "tools":  ("🛠 工具", "#f39c12"),
    "draw":   ("🎨 绘图", "#e67e22"),
    "news":   ("📰 新闻", "#1abc9c"),
    "tv":     ("📺 TV",  "#34495e"),
    "pt":     ("📡 PT",  "#7f8c8d"),
    "office": ("💼 办公", "#16a085"),
}


def get_local_ip() -> str:
    """拿本机局域网 IP (用于拼 NAS 服务的 URL)

    v2.0: 不依赖 socket.gethostbyname — 那个经常返 127.0.0.1
    """
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        # 不会真发包, 只是让 OS 选个 interface
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
    except Exception:
        ip = "127.0.0.1"
    finally:
        s.close()
    return ip


def _render_html(installed_apps: List[str], nas_ip: str, nas_name: str) -> str:
    """生成导航页 HTML"""
    # 按 category 分组
    grouped: Dict[str, list] = {}
    for app_key in installed_apps:
        meta = APPS.get(app_key, {})
        cat = meta.get("category", "tools")
        grouped.setdefault(cat, []).append((app_key, meta))

    # 渲染卡片
    sections_html = ""
    for cat in sorted(grouped.keys()):
        label, color = CATEGORY_DISPLAY.get(cat, (cat, "#999"))
        cards = ""
        for app_key, meta in sorted(grouped[cat], key=lambda x: x[1].get("name", "")):
            port = meta.get("port", "")
            url = f"http://{nas_ip}:{port}" if port else "#"
            name = meta.get("name", app_key)
            desc = meta.get("desc", "")
            warning = meta.get("warning", "")
            warning_html = f'<div class="warning">⚠️ {warning}</div>' if warning else ""
            cards += f'''
            <a href="{url}" target="_blank" class="card">
                <div class="card-name">{name}</div>
                <div class="card-port">:{port}</div>
                <div class="card-desc">{desc}</div>
                {warning_html}
            </a>'''

        sections_html += f'''
        <section class="group">
            <h2 style="border-color: {color};">{label}</h2>
            <div class="grid">{cards}</div>
        </section>'''

    return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>{nas_name} · NAS 服务导航</title>
<style>
    * {{ margin: 0; padding: 0; box-sizing: border-box; }}
    body {{
        font-family: -apple-system, "Helvetica Neue", "PingFang SC", sans-serif;
        background: #f5f6fa;
        color: #2c3e50;
        padding: 30px;
    }}
    header {{
        max-width: 1200px;
        margin: 0 auto 30px;
    }}
    h1 {{
        font-size: 28px;
        color: #2c3e50;
        margin-bottom: 8px;
    }}
    .subtitle {{
        color: #7f8c8d;
        font-size: 14px;
    }}
    main {{
        max-width: 1200px;
        margin: 0 auto;
    }}
    section.group {{
        background: white;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 20px;
        box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    }}
    section.group h2 {{
        font-size: 18px;
        padding-bottom: 10px;
        margin-bottom: 15px;
        border-bottom: 3px solid;
    }}
    .grid {{
        display: grid;
        grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
        gap: 12px;
    }}
    a.card {{
        display: block;
        padding: 16px;
        border: 1px solid #ecf0f1;
        border-radius: 8px;
        text-decoration: none;
        color: inherit;
        transition: all 0.2s;
    }}
    a.card:hover {{
        border-color: #3498db;
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(52,152,219,0.15);
    }}
    .card-name {{
        font-weight: 600;
        font-size: 15px;
        margin-bottom: 4px;
    }}
    .card-port {{
        font-size: 11px;
        color: #95a5a6;
        font-family: monospace;
        margin-bottom: 6px;
    }}
    .card-desc {{
        font-size: 12px;
        color: #7f8c8d;
    }}
    .warning {{
        margin-top: 8px;
        font-size: 11px;
        color: #e74c3c;
    }}
    footer {{
        max-width: 1200px;
        margin: 20px auto;
        text-align: center;
        color: #95a5a6;
        font-size: 12px;
    }}
</style>
</head>
<body>
<header>
    <h1>🧭 {nas_name} · 服务导航</h1>
    <div class="subtitle">{len(installed_apps)} 个已安装服务 · 来自 NASDeployer v2.0</div>
</header>
<main>
    {sections_html if sections_html else '<div style="text-align:center;padding:60px;color:#95a5a6;">暂无已安装服务</div>'}
</main>
<footer>本页面由 NASDeployer v2.0 内嵌 HTTP 服务提供</footer>
</body>
</html>"""


class _NavHandler(BaseHTTPRequestHandler):
    """导航页 HTTP handler (单次 serve)"""
    html_content: bytes = b""
    nas_ip: str = ""

    def do_GET(self):
        # 主页面
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(self.html_content)))
        self.end_headers()
        self.wfile.write(self.html_content)

    def log_message(self, format, *args):
        # 静音 HTTP server 的 stdout 日志
        pass


def open_navigation_page(installed_apps: List[str], nas_name: str = "NAS", port: int = 0) -> int:
    """开 NAS 导航页

    Args:
        installed_apps: 已安装的 service 名列表 (e.g. ['qbittorrent', 'xiaoya'])
        nas_name: NAS 名 (显示在页面标题)
        port: 0 = 自动选可用端口

    Returns:
        实际绑定的端口 (用于诊断)

    用法:
        from navigation import open_navigation_page
        threading.Thread(
            target=lambda: open_navigation_page(['qbittorrent'], 'fnos', 0),
            daemon=True
        ).start()
        # 然后 webbrowser.open(f'http://127.0.0.1:{port}')
    """
    nas_ip = get_local_ip()
    html = _render_html(installed_apps, nas_ip, nas_name)

    _NavHandler.html_content = html.encode("utf-8")

    # 找可用端口
    server = HTTPServer(("127.0.0.1", port), _NavHandler)
    actual_port = server.server_address[1]

    def serve_once():
        server.handle_request()  # 只处理 1 个请求就关
        server.server_close()

    t = threading.Thread(target=serve_once, daemon=True)
    t.start()

    # 浏览器开
    webbrowser.open(f"http://127.0.0.1:{actual_port}")

    return actual_port