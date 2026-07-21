# ==============================================================================
# 测试: nas_profile.py 多 NAS profile 管理 + keyring
# ==============================================================================

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# 把 src 加进 path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import nas_profile  # noqa: E402


class TestNASProfile(unittest.TestCase):
    """NASProfile 数据类测试"""

    def test_basic_init(self):
        p = nas_profile.NASProfile(id="abc123", name="测试 NAS", host="192.168.1.1",
                                    port=22, user="admin", os_type="fnos")
        self.assertEqual(p.id, "abc123")
        self.assertEqual(p.name, "测试 NAS")
        self.assertEqual(p.host, "192.168.1.1")
        self.assertEqual(p.port, 22)
        self.assertEqual(p.user, "admin")
        self.assertEqual(p.os_type, "fnos")

    def test_to_dict(self):
        p = nas_profile.NASProfile(id="x", name="n", host="1.2.3.4", port=2222,
                                    user="u", os_type="zspace")
        d = p.to_dict()
        self.assertEqual(d["id"], "x")
        self.assertEqual(d["host"], "1.2.3.4")
        self.assertEqual(d["port"], 2222)
        self.assertEqual(d["os_type"], "zspace")

    def test_from_dict(self):
        d = {"id": "y", "name": "test", "host": "10.0.0.1", "port": 22,
             "user": "root", "os_type": "fnos"}
        p = nas_profile.NASProfile.from_dict(d)
        self.assertEqual(p.id, "y")
        self.assertEqual(p.name, "test")
        self.assertEqual(p.host, "10.0.0.1")

    def test_from_dict_missing_fields(self):
        """缺少字段时用默认值"""
        p = nas_profile.NASProfile.from_dict({})
        self.assertTrue(p.id)  # 自动生成 UUID
        self.assertEqual(p.name, "未命名")
        self.assertEqual(p.port, 22)
        self.assertEqual(p.os_type, "fnos")


class TestProfileManager(unittest.TestCase):
    """ProfileManager CRUD + 持久化测试 (用临时目录)"""

    def setUp(self):
        """每个测试用独立临时目录, 避免污染用户真实配置"""
        self.tmpdir = tempfile.mkdtemp(prefix="nas_test_")
        self.tmp_path = Path(self.tmpdir)
        # 替换全局路径
        self._orig_dir = nas_profile.CONFIG_DIR
        self._orig_file = nas_profile.PROFILES_FILE
        nas_profile.CONFIG_DIR = self.tmp_path
        nas_profile.PROFILES_FILE = self.tmp_path / "profiles.json"

    def tearDown(self):
        nas_profile.CONFIG_DIR = self._orig_dir
        nas_profile.PROFILES_FILE = self._orig_file
        # 清临时目录
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_add_and_get_current(self):
        mgr = nas_profile.ProfileManager()
        self.assertEqual(len(mgr.profiles), 0)
        cur = mgr.get_current()
        self.assertIsNone(cur)

        p1 = nas_profile.NASProfile(id="1", name="NAS1", host="1.1.1.1", user="a")
        mgr.add(p1)
        self.assertEqual(len(mgr.profiles), 1)
        cur = mgr.get_current()
        self.assertIsNotNone(cur)
        self.assertEqual(cur.id, "1")  # 第一个自动设为当前

    def test_multiple_profiles(self):
        mgr = nas_profile.ProfileManager()
        mgr.add(nas_profile.NASProfile(id="1", name="NAS1", host="1.1.1.1", user="a"))
        mgr.add(nas_profile.NASProfile(id="2", name="NAS2", host="2.2.2.2", user="b"))
        mgr.add(nas_profile.NASProfile(id="3", name="NAS3", host="3.3.3.3", user="c"))

        self.assertEqual(len(mgr.profiles), 3)
        cur = mgr.get_current()
        self.assertIsNotNone(cur)
        self.assertEqual(cur.id, "1")  # 第一个加的还是 current

        mgr.set_current("2")
        cur = mgr.get_current()
        self.assertIsNotNone(cur)
        self.assertEqual(cur.id, "2")
        self.assertEqual(cur.name, "NAS2")

    def test_remove(self):
        mgr = nas_profile.ProfileManager()
        p1 = nas_profile.NASProfile(id="1", name="NAS1", host="1.1.1.1", user="a")
        p2 = nas_profile.NASProfile(id="2", name="NAS2", host="2.2.2.2", user="b")
        mgr.add(p1)
        mgr.add(p2)
        mgr.set_current("1")

        mgr.remove("1")
        self.assertEqual(len(mgr.profiles), 1)
        # current 自动切到剩下的
        cur = mgr.get_current()
        self.assertIsNotNone(cur)
        self.assertEqual(cur.id, "2")

    def test_persistence(self):
        """保存后重新加载, 数据应该还在"""
        mgr1 = nas_profile.ProfileManager()
        mgr1.add(nas_profile.NASProfile(id="x", name="持久化测试", host="5.5.5.5",
                                          port=2222, user="u", os_type="zspace"))
        mgr1.set_current("x")

        # 重新创建实例 (模拟重启)
        mgr2 = nas_profile.ProfileManager()
        self.assertEqual(len(mgr2.profiles), 1)
        loaded = mgr2.get_current()
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.name, "持久化测试")
        self.assertEqual(loaded.host, "5.5.5.5")
        self.assertEqual(loaded.port, 2222)
        self.assertEqual(loaded.os_type, "zspace")

    def test_corrupted_config(self):
        """配置文件损坏时不抛异常, 重置为空"""
        self.tmp_path.mkdir(parents=True, exist_ok=True)
        (self.tmp_path / "profiles.json").write_text("{ corrupted json", encoding="utf-8")

        mgr = nas_profile.ProfileManager()  # 应该不抛异常
        self.assertEqual(len(mgr.profiles), 0)

    def test_new_id_unique(self):
        ids = {nas_profile.ProfileManager.new_id() for _ in range(100)}
        self.assertEqual(len(ids), 100)  # UUID 几乎不会重复


class TestKeyring(unittest.TestCase):
    """keyring 集成测试 (用 sys.modules mock 模拟 keyring 包存在)"""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="nas_kr_test_")
        self.tmp_path = Path(self.tmpdir)
        self._orig_dir = nas_profile.CONFIG_DIR
        self._orig_file = nas_profile.PROFILES_FILE
        nas_profile.CONFIG_DIR = self.tmp_path
        nas_profile.PROFILES_FILE = self.tmp_path / "profiles.json"

    def tearDown(self):
        nas_profile.CONFIG_DIR = self._orig_dir
        nas_profile.PROFILES_FILE = self._orig_file
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_keyring_unavailable_fallback(self):
        """keyring 包未安装时, save 返回 False, get 返回 None"""
        # 确保 KEYRING_AVAILABLE 是 False
        orig_available = nas_profile.KEYRING_AVAILABLE
        nas_profile.KEYRING_AVAILABLE = False
        try:
            mgr = nas_profile.ProfileManager()
            self.assertFalse(mgr.save_password("x", "y"))
            self.assertIsNone(mgr.get_password("x"))
            self.assertFalse(mgr.has_password("x"))
            # delete 不抛异常
            mgr.delete_password("x")
        finally:
            nas_profile.KEYRING_AVAILABLE = orig_available

    def test_keyring_available_with_mock(self):
        """keyring 装了时, save/get/has/delete 走 keyring 模块"""
        # 注入 fake keyring 模块到 sys.modules
        from unittest.mock import MagicMock
        fake_kr = MagicMock()
        fake_kr.get_password.return_value = "secret123"
        fake_err = MagicMock()
        fake_err.PasswordDeleteError = type("PDE", (Exception,), {})
        fake_kr.errors = fake_err

        orig_kr = sys.modules.get("keyring")
        orig_kr_err = sys.modules.get("keyring.errors")
        sys.modules["keyring"] = fake_kr
        sys.modules["keyring.errors"] = fake_err

        # 临时覆盖 KEYRING_AVAILABLE + 重新设置 module-level keyring 引用
        orig_available = nas_profile.KEYRING_AVAILABLE
        orig_module_kr = getattr(nas_profile, "keyring", None)
        orig_module_kr_err = getattr(nas_profile, "keyring.errors", None)
        nas_profile.KEYRING_AVAILABLE = True
        nas_profile.keyring = fake_kr
        nas_profile.keyring.errors = fake_err

        try:
            mgr = nas_profile.ProfileManager()

            # save
            ok = mgr.save_password("test_id", "secret123")
            self.assertTrue(ok)
            fake_kr.set_password.assert_called_with("NASDeployer", "test_id", "secret123")

            # get
            pwd = mgr.get_password("test_id")
            self.assertEqual(pwd, "secret123")
            self.assertTrue(mgr.has_password("test_id"))

            # delete
            mgr.delete_password("test_id")
            fake_kr.delete_password.assert_called_with("NASDeployer", "test_id")
        finally:
            # 还原
            nas_profile.KEYRING_AVAILABLE = orig_available
            if orig_module_kr is None:
                if hasattr(nas_profile, "keyring"):
                    delattr(nas_profile, "keyring")
            else:
                nas_profile.keyring = orig_module_kr
            if orig_kr is None:
                sys.modules.pop("keyring", None)
            else:
                sys.modules["keyring"] = orig_kr
            if orig_kr_err is None:
                sys.modules.pop("keyring.errors", None)
            else:
                sys.modules["keyring.errors"] = orig_kr_err


if __name__ == "__main__":
    unittest.main(verbosity=2)
