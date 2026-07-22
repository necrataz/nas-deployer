# ==============================================================================
# NAS Deployer v2.0.3 - 默认凭证查询
# ==============================================================================
# 列出每个 Docker 服务的默认账号/密码 (compose 文件里硬编码的 + 公认默认)
# 用法: 菜单 "🔑 默认凭证" → 弹窗选应用 → 显示凭证 + 首次登录提示
# ==============================================================================

from typing import Dict, List, Optional, Tuple


# 结构:
#   "app_key": {
#     "username": "..." | "first_setup" | "none"
#     "password": "..." | "first_setup" | "none"
#     "note": "首次登录提示 / 怎么从 logs 拿"
#     "url": "/admin/login"
#     "confidence": "high" | "medium" | "low"
#   }
#
# 可信度分级:
#   high:   compose 硬编码 OR 文档明确默认
#   medium: 公认默认, 但不同版本可能改过
#   low:    不确定, 用户应核对官方文档

CREDENTIALS = {
    # ============ MOVIE PROFILE ============
    "moviepilot": {
        "username": "admin",
        "password": "ChangeMe123!",
        "note": "compose 中硬编码 SUPERUSER/SUPERPASS。登录后右上角 → 设置 → 改密",
        "url": "/",
        "confidence": "high",
    },
    "qbittorrent": {
        "username": "admin",
        "password": "<random>",
        "note": "首次启动随机生成。容器日志查看: docker logs qbittorrent 2>&1 | grep -i 'temporary password'",
        "url": "/",
        "confidence": "high",
    },
    "libretv": {
        "username": "none",
        "password": "none",
        "note": "LibreTV 默认无密码, 直接进入。高级设置里改 admin 密码",
        "url": "/",
        "confidence": "high",
    },
    "xiaoya": {
        "username": "guest",
        "password": "guest",
        "note": "alist 默认账号。完整功能需 mytoken.txt (见 NASDeployer v2.0 占位文件)",
        "url": "/",
        "confidence": "high",
    },

    # ============ READ PROFILE ============
    "immich": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问创建管理员账号 (邮箱+密码)。照片备份前必做",
        "url": "/auth/login",
        "confidence": "high",
    },
    "calibre_web": {
        "username": "admin",
        "password": "admin123",
        "note": "compose 未硬编码, calibre-web 公认默认。若不行: docker logs calibre_web | grep -i password",
        "url": "/",
        "confidence": "medium",
    },
    "audiobookshelf": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问 /config 引导设置管理员",
        "url": "/",
        "confidence": "high",
    },
    "siyuan": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问设置访问密码 (Settings → About → Access Auth Code)",
        "url": "/",
        "confidence": "high",
    },

    # ============ PT PROFILE ============
    "navidrome": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问创建管理员",
        "url": "/",
        "confidence": "high",
    },
    "mimusic": {
        "username": "none",
        "password": "none",
        "note": "MiMusic 无密码, 配小米账号扫码登录",
        "url": "/",
        "confidence": "high",
    },
    "iyuu": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问注册 (IYUU+ 免费版 ≤ 5 个站点)",
        "url": "/",
        "confidence": "high",
    },

    # ============ NAV PROFILE ============
    "dashy": {
        "username": "none",
        "password": "none",
        "note": "Dashy 默认无密码, 可在 conf.yml 配 auth",
        "url": "/",
        "confidence": "high",
    },
    "lucky": {
        "username": "none",
        "password": "none",
        "note": "Lucky 默认无登录, 需在配置里设置 username/password",
        "url": "/",
        "confidence": "medium",
    },

    # ============ AI PROFILE ============
    "hivision": {
        "username": "none",
        "password": "none",
        "note": "HivisionIDPhotos 无密码, 公开访问",
        "url": "/",
        "confidence": "high",
    },
    "edge_tts": {
        "username": "none",
        "password": "none",
        "note": "edge-tts-web-ui 无密码",
        "url": "/",
        "confidence": "high",
    },
    "yt_dlp_web": {
        "username": "none",
        "password": "none",
        "note": "me-tube 无密码, 下载功能可用",
        "url": "/",
        "confidence": "high",
    },

    # ============ DRAW PROFILE ============
    "excalidraw": {
        "username": "none",
        "password": "none",
        "note": "Excalidraw 无密码, 协作需自部署 collab server",
        "url": "/",
        "confidence": "high",
    },
    "photopea": {
        "username": "none",
        "password": "none",
        "note": "Photopea 完全公开, 无密码无账号",
        "url": "/",
        "confidence": "high",
    },
    "onlyoffice": {
        "username": "admin",
        "password": "admin",
        "note": "OnlyOffice 默认账号, 首次登录强制改密",
        "url": "/",
        "confidence": "high",
    },

    # ============ NEWS PROFILE ============
    "rsshub": {
        "username": "none",
        "password": "none",
        "note": "RSSHub 默认公开, 无密码 (生产建议配 access_key)",
        "url": "/",
        "confidence": "high",
    },
    "freshrss": {
        "username": "admin",
        "password": "freshrss",
        "note": "compose 未硬编码, 公认默认是 admin/freshrss。若不行: 容器 logs 找 init 阶段密码",
        "url": "/",
        "confidence": "medium",
    },
    "pansearch": {
        "username": "none",
        "password": "none",
        "note": "PanSearch 无密码, 公开网盘搜索",
        "url": "/",
        "confidence": "high",
    },

    # ============ TV PROFILE ============
    "m3u_manager": {
        "username": "first_setup",
        "password": "first_setup",
        "note": "首次访问 /admin 注册",
        "url": "/admin",
        "confidence": "medium",
    },
    "iptv_auto": {
        "username": "none",
        "password": "none",
        "note": "iptv-auto-update 是后台 cron, 无 Web UI",
        "url": "",
        "confidence": "high",
    },

    # ============ TOOLS PROFILE ============
    "insdown": {
        "username": "none",
        "password": "none",
        "note": "insdown 无密码, 公开 API",
        "url": "/",
        "confidence": "high",
    },
    "stirling_pdf": {
        "username": "none",
        "password": "none",
        "note": "Stirling PDF 默认无登录 (2.0+ 加 security config 默认开)",
        "url": "/",
        "confidence": "medium",
    },
    "bilibili_tool": {
        "username": "none",
        "password": "none",
        "note": "BiliBiliTool 需扫码登录 B 站账号, 容器内 B 站 cookie 持久化",
        "url": "",
        "confidence": "high",
    },

    # ============ NET PROFILE ============
    "mihomo": {
        "username": "none",
        "password": "none",
        "note": "mihomo 本身无密码, 控制台 9091 默认无 auth (生产建议配 secret)",
        "url": "/ui",
        "confidence": "high",
    },
}


def get_credentials(app_key: str) -> Optional[Dict]:
    """取应用的默认凭证, 没找到返 None"""
    return CREDENTIALS.get(app_key)


def format_credentials_display(app_key: str, app_name: str, port: int, nas_ip: str) -> str:
    """生成给用户看的格式化字符串 (给 messagebox.showinfo / 弹窗)"""
    cred = get_credentials(app_key)
    if not cred:
        return f"⚠️ {app_name} 的默认凭证信息缺失\n\n请到 {app_name} 官方文档查询"

    user = cred.get("username", "?")
    pwd = cred.get("password", "?")
    note = cred.get("note", "")
    url_path = cred.get("url", "/")
    confidence = cred.get("confidence", "?")

    full_url = f"http://{nas_ip}:{port}{url_path}" if port else "无 Web UI"

    display = f"""📦 {app_name}

🔗 访问地址:
   {full_url}

👤 用户名: {user}
🔐 密码:   {pwd}

📝 提示:
   {note}

🟢 可信度: {confidence}"""
    return display


def list_all_credentials() -> List[Tuple[str, str, str]]:
    """列出所有有凭证的应用 (app_key, app_name, port)"""
    from apps import APPS
    rows = []
    for key, cred in CREDENTIALS.items():
        meta = APPS.get(key, {})
        rows.append((key, meta.get("name", key), meta.get("port", 0)))
    return sorted(rows, key=lambda x: x[1])