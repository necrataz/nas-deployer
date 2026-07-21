# ==============================================================================
# NAS Deployer v1.1 - 多 NAS Profile 管理 + keyring 密码存储
# ==============================================================================

import json
import uuid
from pathlib import Path
from typing import Dict, List, Optional

try:
    import keyring
    import keyring.errors
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

# 配置文件位置 (跨平台兼容)
# Windows: %USERPROFILE%\.nas_deployer\profiles.json (典型 C:\Users\<user>\.nas_deployer\)
# Mac/Linux: ~/.nas_deployer/profiles.json
CONFIG_DIR = Path.home() / ".nas_deployer"
PROFILES_FILE = CONFIG_DIR / "profiles.json"
KEYRING_SERVICE = "NASDeployer"


class NASProfile:
    """单个 NAS 连接配置 (不含密码, 密码单独存 keyring)"""

    def __init__(
        self,
        id: str,
        name: str,
        host: str,
        port: int = 22,
        user: str = "",
        os_type: str = "fnos",
    ):
        self.id = id
        self.name = name
        self.host = host
        self.port = port
        self.user = user
        self.os_type = os_type  # 'fnos' / 'zspace'

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "host": self.host,
            "port": self.port,
            "user": self.user,
            "os_type": self.os_type,
        }

    @classmethod
    def from_dict(cls, d: dict):
        return cls(
            id=d.get("id") or str(uuid.uuid4())[:8],
            name=d.get("name", "未命名"),
            host=d.get("host", ""),
            port=int(d.get("port", 22)),
            user=d.get("user", ""),
            os_type=d.get("os_type", "fnos"),
        )

    def __repr__(self):
        return f"<NASProfile {self.name} ({self.user}@{self.host}:{self.port})>"


class ProfileManager:
    """多 NAS profile 管理 + 密码 keyring 集成"""

    def __init__(self):
        self.profiles: Dict[str, NASProfile] = {}
        self.current_id: Optional[str] = None
        self._load()

    # ---- 持久化 ----
    def _load(self):
        """从 JSON 加载 profile 列表 + 当前选中的 ID"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            if PROFILES_FILE.exists():
                data = json.loads(PROFILES_FILE.read_text(encoding="utf-8"))
                self.profiles = {
                    p["id"]: NASProfile.from_dict(p)
                    for p in data.get("profiles", [])
                }
                cur = data.get("current_id")
                # 校验 current_id 是否还存在 (否则清掉)
                if cur and cur in self.profiles:
                    self.current_id = cur
                else:
                    self.current_id = next(iter(self.profiles), None)
        except (json.JSONDecodeError, KeyError, OSError) as e:
            # 配置文件损坏: 不抛异常, 重置为空
            print(f"[ProfileManager] 加载配置失败: {e}, 重置为空")
            self.profiles = {}
            self.current_id = None

    def _save(self):
        """保存到 JSON"""
        try:
            CONFIG_DIR.mkdir(parents=True, exist_ok=True)
            data = {
                "profiles": [p.to_dict() for p in self.profiles.values()],
                "current_id": self.current_id,
            }
            PROFILES_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError as e:
            print(f"[ProfileManager] 保存失败: {e}")

    # ---- CRUD ----
    def add(self, profile: NASProfile):
        """新增 profile"""
        self.profiles[profile.id] = profile
        if self.current_id is None:
            self.current_id = profile.id
        self._save()

    def update(self, profile: NASProfile):
        """更新已存在的 profile"""
        self.profiles[profile.id] = profile
        self._save()

    def remove(self, profile_id: str):
        """删除 profile + 清掉 keyring 里的密码"""
        if profile_id not in self.profiles:
            return
        del self.profiles[profile_id]
        self.delete_password(profile_id)
        if self.current_id == profile_id:
            self.current_id = next(iter(self.profiles), None)
            self._save()

    def set_current(self, profile_id: str):
        """切换当前 NAS"""
        if profile_id in self.profiles:
            self.current_id = profile_id
            self._save()

    def get_current(self) -> Optional[NASProfile]:
        """获取当前选中的 NAS profile"""
        if self.current_id and self.current_id in self.profiles:
            return self.profiles[self.current_id]
        return None

    def list_profiles(self) -> List[NASProfile]:
        """返回所有 profile 列表"""
        return list(self.profiles.values())

    # ---- keyring 集成 ----
    def save_password(self, profile_id: str, password: str) -> bool:
        """保存密码到系统 keyring (Windows = Credential Manager)"""
        if not KEYRING_AVAILABLE:
            return False
        try:
            keyring.set_password(KEYRING_SERVICE, profile_id, password)
            return True
        except keyring.errors.KeyringError as e:
            print(f"[ProfileManager] keyring save failed: {e}")
            return False

    def get_password(self, profile_id: str) -> Optional[str]:
        """从 keyring 取密码, 没有返回 None"""
        if not KEYRING_AVAILABLE:
            return None
        try:
            return keyring.get_password(KEYRING_SERVICE, profile_id)
        except keyring.errors.KeyringError as e:
            print(f"[ProfileManager] keyring get failed: {e}")
            return None

    def has_password(self, profile_id: str) -> bool:
        """检查 keyring 里是否有这个 profile 的密码"""
        return self.get_password(profile_id) is not None

    def delete_password(self, profile_id: str):
        """清掉 keyring 里的密码"""
        if not KEYRING_AVAILABLE:
            return
        try:
            keyring.delete_password(KEYRING_SERVICE, profile_id)
        except keyring.errors.PasswordDeleteError:
            pass  # 本来就没有, 不报错
        except keyring.errors.KeyringError as e:
            print(f"[ProfileManager] keyring delete failed: {e}")

    @staticmethod
    def new_id() -> str:
        """生成新 profile ID (UUID 前 8 位)"""
        return str(uuid.uuid4())[:8]
