# ==============================================================================
# 测试: _clean_host 函数 (host 字段清洗)
# ==============================================================================

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from host_utils import clean_host, extract_port_from_host  # noqa: E402

# 为兼容旧的测试代码
_clean_host = clean_host


class TestCleanHost(unittest.TestCase):
    """验证 host 字段清洗, 兼容用户粘贴 URL"""

    def test_plain_ip(self):
        self.assertEqual(clean_host("192.168.3.88"), "192.168.3.88")

    def test_strip_whitespace(self):
        self.assertEqual(clean_host("  192.168.3.88  "), "192.168.3.88")

    def test_strip_http_scheme(self):
        """用户的实际 bug: http:// 前缀"""
        self.assertEqual(clean_host("http://192.168.3.88"), "192.168.3.88")

    def test_strip_https_scheme(self):
        self.assertEqual(clean_host("https://192.168.3.88"), "192.168.3.88")

    def test_strip_ssh_scheme(self):
        self.assertEqual(clean_host("ssh://nas.local"), "nas.local")

    def test_strip_trailing_slash(self):
        self.assertEqual(clean_host("nas.local/"), "nas.local")

    def test_strip_path(self):
        """https://nas.local/admin/ -> nas.local"""
        self.assertEqual(clean_host("https://nas.local/admin/"), "nas.local")

    def test_strip_userinfo(self):
        """user@host 形式"""
        self.assertEqual(clean_host("user@192.168.3.88"), "192.168.3.88")

    def test_extract_port_with_scheme(self):
        """用户实际输入: ssh://admin@nas.local:22"""
        host, port = extract_port_from_host("ssh://admin@nas.local:22")
        self.assertEqual(host, "nas.local")
        self.assertEqual(port, 22)

    def test_extract_port_plain(self):
        """192.168.3.88:5666"""
        host, port = extract_port_from_host("192.168.3.88:5666")
        self.assertEqual(host, "192.168.3.88")
        self.assertEqual(port, 5666)

    def test_extract_port_no_port(self):
        """nas.local (没端口)"""
        host, port = extract_port_from_host("nas.local")
        self.assertEqual(host, "nas.local")
        self.assertIsNone(port)

    def test_complex_url(self):
        """完整 URL: scheme + user + host + port + path"""
        host, port = extract_port_from_host("https://admin@nas.example.com:8443/admin/dashboard")
        self.assertEqual(host, "nas.example.com")
        self.assertEqual(port, 8443)

    def test_ipv6_no_crash(self):
        """IPv6 含多个 : 不崩"""
        host, port = extract_port_from_host("2001:db8::1")
        # 多个 : 视为 IPv6, 不剥离
        self.assertIn(":", host)
        self.assertIsNone(port)

    def test_empty_string(self):
        self.assertEqual(clean_host(""), "")
        self.assertEqual(extract_port_from_host(""), ("", None))

    def test_nas_with_dots(self):
        """域名形式"""
        self.assertEqual(clean_host("nas.local.lan"), "nas.local.lan")

    def test_http_uppercase(self):
        """HTTP:// 大写也支持"""
        self.assertEqual(clean_host("HTTP://192.168.3.88"), "192.168.3.88")


if __name__ == "__main__":
    unittest.main(verbosity=2)
