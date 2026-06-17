import unittest
from main import mask_proxy_host, mask_token, mask_url

class TestMainUtilities(unittest.TestCase):
    def test_mask_token(self):
        self.assertEqual(mask_token("1234567890:ABCDEF"), "1234...CDEF")
        self.assertEqual(mask_token("short"), "***")
        self.assertEqual(mask_token(""), "***")

    def test_mask_url(self):
        self.assertEqual(mask_url("socks5://user:pass@127.0.0.1:1080"), "socks5://user:***@127.0.0.1:1080")
        self.assertEqual(mask_url("http://127.0.0.1:8080"), "http://127.0.0.1:8080")
        self.assertEqual(mask_url(""), "")

    def test_mask_proxy_host(self):
        self.assertEqual(mask_proxy_host("socks5://user:pass@127.0.0.1:1080"), "socks5://127.0.0.1:1080")
        self.assertEqual(mask_proxy_host("http://proxy.example.com:8080"), "http://proxy.example.com:8080")

if __name__ == '__main__':
    unittest.main()
