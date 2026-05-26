import unittest
import execjs
from pathlib import Path
from core.signature import get_sign as python_get_sign

REPO_ROOT = Path(__file__).resolve().parent.parent


class SignatureEquivalenceTests(unittest.TestCase):
    def test_python_and_js_signatures_are_identical(self):
        js_path = REPO_ROOT / "static" / "z_core.js"
        if not js_path.exists():
            self.skipTest("z_core.js not found, skipping cross-check")

        js_code = js_path.read_text(encoding="utf-8")
        # Patch JS code to make Math.random() deterministic (always returns 63)
        patched_js = js_code.replace("Math.floor(Math.random() * 127)", "63")

        try:
            js_ctx = execjs.compile(patched_js)
        except Exception as e:
            self.skipTest(f"JS Engine not available for validation: {e}")

        urls = [
            "/api/v4/answers/12345",
            "/api/v4/members/someone/answers?limit=20&offset=0",
            "/api/v4/questions/999/answers?limit=5&offset=20",
        ]
        d_c0s = [
            "ABCDEFG1234567",
            "SEARCH_ME",
            "d_c0_cookie_value",
        ]

        for url in urls:
            for d_c0 in d_c0s:
                js_res = js_ctx.call("get_sign", url, f"d_c0={d_c0}")
                py_res = python_get_sign(url, d_c0, seed_byte=63)

                self.assertEqual(js_res["x-zst-81"], py_res["x-zst-81"])
                self.assertEqual(
                    js_res["x-zse-96"],
                    py_res["x-zse-96"],
                    f"Failed for url={url}, d_c0={d_c0}",
                )


if __name__ == "__main__":
    unittest.main()
