# ==============================================================================
# NAS Deployer - host 字段清洗工具
# ==============================================================================

import re


def clean_host(raw: str) -> str:
    """清洗 host 字段: 去 scheme/userinfo/path/尾部斜杠

    兼容用户习惯性粘贴 URL:
        "http://192.168.3.88"      -> "192.168.3.88"
        "https://nas.local/path/"  -> "nas.local"
        "user@192.168.3.88"        -> "192.168.3.88"
        "ssh://admin@nas.local:22" -> "nas.local"  (端口保留, 由调用方处理)

    v1.3 新增: 解决 v1.0/v1.1 host 字段含 http:// 的 bug
    (用户报 "gaierror [Errno 11001] getaddrinfo failed")
    """
    if not raw:
        return ""
    h = raw.strip()
    # 1. 去 scheme (e.g. "http://", "https://", "ssh://")
    h = re.sub(r'^[a-zA-Z][a-zA-Z0-9+.\-]*://', '', h)
    # 2. 去尾部斜杠
    h = h.rstrip("/")
    # 3. 去 path (e.g. "nas.local/admin" -> "nas.local")
    if "/" in h:
        h = h.split("/")[0]
    # 4. 去 userinfo (e.g. "admin@nas.local" -> "nas.local")
    if "@" in h:
        h = h.split("@")[-1]
    # 注: 不去端口. 端口由 ProfileManager / NASProfileDialog 单独处理
    # (migrator 从 v1.0 config 读 port 字段; dialog 让用户确认)
    return h


def extract_port_from_host(host: str) -> tuple:
    """从 host 字符串里提取端口 (如果有)

    返回 (cleaned_host, port_or_None)
    e.g.
        "192.168.3.88:5666"  -> ("192.168.3.88", 5666)
        "nas.local"          -> ("nas.local", None)
        "[2001:db8::1]:22"   -> 保持原样 (IPv6)
    """
    h = clean_host(host)
    # 简单 IPv6 检测: 多个 ":" 视为 IPv6
    if h.count(":") > 1:
        return h, None
    if ":" in h:
        host_part, port_part = h.rsplit(":", 1)
        try:
            port_num = int(port_part)
            return host_part, port_num
        except ValueError:
            return h, None
    return h, None
