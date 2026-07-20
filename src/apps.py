# ==============================================================================
# NAS 一键部署工具 - 应用定义
# ==============================================================================

# 26 个服务 + 依赖 (Immich Postgres/Redis 是依赖, 不在前端展示)
APPS = {
    'moviepilot': {
        'name': 'MoviePilot',
        'desc': '影视资源自动订阅',
        'port': 5000,
        'profile': 'movie',
        'memory_mb': 1024,
        'category': 'movie',
    },
    'qbittorrent': {
        'name': 'qBittorrent',
        'desc': 'BT 下载',
        'port': 8080,
        'profile': 'movie',
        'memory_mb': 200,
        'category': 'movie',
    },
    'libretv': {
        'name': 'LibreTV',
        'desc': '在线影视聚合',
        'port': 8081,
        'profile': 'movie',
        'memory_mb': 200,
        'category': 'movie',
    },
    'xiaoya': {
        'name': '小雅全家桶',
        'desc': 'Alist+Emby+aria2 一体化',
        'port': 5678,
        'profile': 'movie',
        'memory_mb': 2048,
        'category': 'movie',
        'warning': '与 MoviePilot+LibreTV 功能重叠',
    },
    'immich': {
        'name': 'Immich',
        'desc': '照片备份',
        'port': 2283,
        'profile': 'read',
        'memory_mb': 2048,
        'category': 'read',
    },
    'immich_postgres': {
        'name': 'Immich Postgres (依赖)',
        'desc': '数据库',
        'port': None,
        'profile': 'read',
        'memory_mb': 256,
        'category': 'read',
        'hidden': True,
    },
    'immich_redis': {
        'name': 'Immich Redis (依赖)',
        'desc': '缓存',
        'port': None,
        'profile': 'read',
        'memory_mb': 64,
        'category': 'read',
        'hidden': True,
    },
    'calibre_web': {
        'name': 'Calibre-Web',
        'desc': '电子书库',
        'port': 8083,
        'profile': 'read',
        'memory_mb': 256,
        'category': 'read',
    },
    'audiobookshelf': {
        'name': 'Audiobookshelf',
        'desc': '有声书架',
        'port': 13378,
        'profile': 'read',
        'memory_mb': 300,
        'category': 'read',
    },
    'siyuan': {
        'name': 'SiYuan',
        'desc': '双链笔记',
        'port': 6806,
        'profile': 'read',
        'memory_mb': 300,
        'category': 'read',
    },
    'navidrome': {
        'name': 'Navidrome',
        'desc': '音乐服务器',
        'port': 4533,
        'profile': 'pt',
        'memory_mb': 200,
        'category': 'pt',
    },
    'mimusic': {
        'name': 'MiMusic',
        'desc': '小爱音箱音乐',
        'port': 8181,
        'profile': 'pt',
        'memory_mb': 300,
        'category': 'pt',
        'warning': '无小米音箱 = Navidrome 副本',
    },
    'iyuu': {
        'name': 'IYUU',
        'desc': 'PT 辅种',
        'port': 8787,
        'profile': 'pt',
        'memory_mb': 200,
        'category': 'pt',
    },
    'dashy': {
        'name': 'Dashy',
        'desc': 'NAS 导航',
        'port': 8082,
        'profile': 'nav',
        'memory_mb': 100,
        'category': 'nav',
    },
    'lucky': {
        'name': 'Lucky',
        'desc': '反向代理',
        'port': 16601,
        'profile': 'nav',
        'memory_mb': 100,
        'category': 'nav',
    },
    'hivision': {
        'name': 'HivisionIDPhotos',
        'desc': 'AI 证件照',
        'port': 7860,
        'profile': 'ai',
        'memory_mb': 1024,
        'category': 'ai',
    },
    'edge_tts': {
        'name': 'edge-tts',
        'desc': '文本转语音',
        'port': 8089,
        'profile': 'ai',
        'memory_mb': 100,
        'category': 'ai',
    },
    'yt_dlp_web': {
        'name': 'yt-dlp',
        'desc': 'YouTube 下载',
        'port': 8091,
        'profile': 'ai',
        'memory_mb': 300,
        'category': 'ai',
    },
    'excalidraw': {
        'name': 'Excalidraw',
        'desc': '在线绘图',
        'port': 5001,
        'profile': 'draw',
        'memory_mb': 200,
        'category': 'draw',
    },
    'photopea': {
        'name': 'Photopea',
        'desc': '在线图片编辑',
        'port': 8085,
        'profile': 'draw',
        'memory_mb': 200,
        'category': 'draw',
    },
    'onlyoffice': {
        'name': 'OnlyOffice',
        'desc': 'Office 网页版',
        'port': 8087,
        'profile': 'draw',
        'memory_mb': 1024,
        'category': 'draw',
    },
    'rsshub': {
        'name': 'RSSHub',
        'desc': 'RSS 源',
        'port': 1200,
        'profile': 'news',
        'memory_mb': 512,
        'category': 'news',
    },
    'freshrss': {
        'name': 'FreshRSS',
        'desc': 'RSS 阅读器',
        'port': 8086,
        'profile': 'news',
        'memory_mb': 200,
        'category': 'news',
    },
    'pansearch': {
        'name': 'PanSearch',
        'desc': '网盘搜索',
        'port': 5522,
        'profile': 'news',
        'memory_mb': 200,
        'category': 'news',
    },
    'm3u_manager': {
        'name': 'm3u Manager',
        'desc': '直播 TV 管理',
        'port': 8088,
        'profile': 'tv',
        'memory_mb': 100,
        'category': 'tv',
    },
    'iptv_auto': {
        'name': 'IPTV Auto',
        'desc': 'EPG 自动维护',
        'port': None,
        'profile': 'tv',
        'memory_mb': 50,
        'category': 'tv',
    },
    'insdown': {
        'name': 'insdown',
        'desc': 'Instagram 图/视下载',
        'port': 8888,
        'profile': 'tools',
        'memory_mb': 200,
        'category': 'tools',
    },
    'stirling_pdf': {
        'name': 'Stirling PDF',
        'desc': 'PDF 工具',
        'port': 8084,
        'profile': 'tools',
        'memory_mb': 300,
        'category': 'tools',
    },
    'bilibili_tool': {
        'name': 'BiliBiliTool',
        'desc': 'B 站下载',
        'port': 8090,
        'profile': 'tools',
        'memory_mb': 300,
        'category': 'tools',
    },
}

PROFILES = {
    'movie': {
        'name': '🎬 电影组',
        'memory_mb': 3472,
        'apps': ['moviepilot', 'qbittorrent', 'libretv', 'xiaoya'],
    },
    'read': {
        'name': '📚 阅读组',
        'memory_mb': 3224,
        'apps': ['immich', 'immich_postgres', 'immich_redis', 'calibre_web', 'audiobookshelf', 'siyuan'],
    },
    'pt': {
        'name': '🎵 音乐 PT',
        'memory_mb': 700,
        'apps': ['navidrome', 'mimusic', 'iyuu'],
    },
    'nav': {
        'name': '🧭 导航组',
        'memory_mb': 200,
        'apps': ['dashy', 'lucky'],
    },
    'ai': {
        'name': '🤖 AI 组',
        'memory_mb': 1424,
        'apps': ['hivision', 'edge_tts', 'yt_dlp_web'],
    },
    'draw': {
        'name': '🎨 创作组',
        'memory_mb': 1424,
        'apps': ['excalidraw', 'photopea', 'onlyoffice'],
    },
    'news': {
        'name': '📰 新闻组',
        'memory_mb': 912,
        'apps': ['rsshub', 'freshrss', 'pansearch'],
    },
    'tv': {
        'name': '📺 电视组',
        'memory_mb': 150,
        'apps': ['m3u_manager', 'iptv_auto'],
    },
    'tools': {
        'name': '🔧 工具组',
        'memory_mb': 800,
        'apps': ['insdown', 'stirling_pdf', 'bilibili_tool'],
    },
}


def get_visible_apps():
    """返回前端展示的应用列表（排除 hidden=True 的依赖项）"""
    return {k: v for k, v in APPS.items() if not v.get('hidden')}


def get_apps_by_profile(profile_key):
    """返回指定 profile 的所有应用 (含 hidden 依赖)"""
    return PROFILES.get(profile_key, {}).get('apps', [])


def total_memory_mb(app_keys):
    """计算一组应用的预估内存 (MB)"""
    return sum(APPS[k]['memory_mb'] for k in app_keys if k in APPS)