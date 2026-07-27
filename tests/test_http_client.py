import json
import tempfile
import unittest
from pathlib import Path

from zhihu_scraper.http import (
    AccessDeniedError,
    AuthenticationError,
    CookieFileError,
    InvalidResponseError,
    RateLimitError,
    ServerError,
    TransportError,
    UnsafeZhihuUrlError,
    ZhihuHttpClient,
    diagnose_cookies,
    load_cookies,
)


class FakeResponse:
    def __init__(
        self,
        *,
        status_code: int = 200,
        json_data: object = None,
        text: str = "",
        headers: dict[str, str] | None = None,
    ):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        if isinstance(self._json_data, BaseException):
            raise self._json_data
        return self._json_data


class FakeSession:
    def __init__(self, responses: list[FakeResponse]):
        self._responses = list(responses)
        self.calls: list[tuple[str, dict[str, object]]] = []

    def get(self, url: str, **kwargs):
        self.calls.append((url, kwargs))
        return self._responses.pop(0)


class ExplodingSession:
    def __init__(self, message: str):
        self._message = message

    def get(self, url: str, **kwargs):
        raise RuntimeError(self._message)


class CookieLoadingTests(unittest.TestCase):
    def test_loads_browser_cookie_list_and_reports_missing_core_cookie_names(self):
        secret_value = "secret-z-c0-value"
        exported_cookies = [
            {"name": "z_c0", "value": secret_value, "domain": ".zhihu.com"},
            {"name": "other_cookie", "value": "other-secret"},
        ]

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)
            diagnostic = diagnose_cookies(cookies)

        self.assertEqual(cookies["z_c0"], secret_value)
        self.assertEqual(diagnostic.missing, ("d_c0",))
        self.assertFalse(diagnostic.is_complete)
        self.assertIn("d_c0", diagnostic.message)
        self.assertNotIn(secret_value, diagnostic.message)

    def test_loads_cookie_mapping_and_ignores_empty_non_string_values(self):
        exported_cookies = {
            "z_c0": "z-secret",
            "d_c0": "d-secret",
            "empty": "",
            "not-a-cookie": 123,
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)

        self.assertEqual(cookies, {"z_c0": "z-secret", "d_c0": "d-secret"})
        self.assertTrue(diagnose_cookies(cookies).is_complete)

    def test_malformed_cookie_file_raises_a_sanitized_error(self):
        secret_value = "malformed-secret-value"

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(
                f'{{"z_c0": "{secret_value}", broken',
                encoding="utf-8",
            )

            with self.assertRaises(CookieFileError) as raised:
                load_cookies(cookie_path)

        self.assertIn("cookies.json", str(raised.exception))
        self.assertNotIn(secret_value, str(raised.exception))

    def test_placeholder_cookie_values_are_diagnosed_as_missing(self):
        exported_cookies = {
            "z_c0": "YOUR_Z_C0_HERE",
            "d_c0": "   ",
            "language": " zh-CN ",
        }

        with tempfile.TemporaryDirectory() as temporary_directory:
            cookie_path = Path(temporary_directory) / "cookies.json"
            cookie_path.write_text(json.dumps(exported_cookies), encoding="utf-8")

            cookies = load_cookies(cookie_path)
            diagnostic = diagnose_cookies(cookies)

        self.assertEqual(cookies, {"language": "zh-CN"})
        self.assertEqual(diagnostic.missing, ("z_c0", "d_c0"))


class ZhihuHttpClientTests(unittest.TestCase):
    def test_invalid_json_is_wrapped_without_copying_response_details(self):
        session = FakeSession([FakeResponse(json_data=ValueError("secret response body"))])

        with self.assertRaises(InvalidResponseError) as raised:
            ZhihuHttpClient(session=session).get_json("/api/v4/me")

        self.assertIn("not valid JSON", str(raised.exception))
        self.assertNotIn("secret response body", str(raised.exception))

    def test_get_json_uses_the_zhihu_origin_and_authenticated_session(self):
        cookies = {"z_c0": "z-secret", "d_c0": "d-secret"}
        session = FakeSession([FakeResponse(json_data={"id": "member-id", "name": "归档用户"})])
        client = ZhihuHttpClient(cookies=cookies, session=session)

        payload = client.get_json("/api/v4/me")

        self.assertEqual(payload, {"id": "member-id", "name": "归档用户"})
        requested_url, request_options = session.calls[0]
        self.assertEqual(requested_url, "https://www.zhihu.com/api/v4/me")
        self.assertEqual(request_options["cookies"], cookies)

    def test_get_html_preserves_absolute_url_and_applies_optional_proxy(self):
        source_url = "https://zhuanlan.zhihu.com/p/357892158"
        proxy = "http://127.0.0.1:7890"
        session = FakeSession([FakeResponse(text="<article>正文</article>")])
        client = ZhihuHttpClient(proxy=proxy, session=session)

        html = client.get_html(source_url)

        self.assertEqual(html, "<article>正文</article>")
        requested_url, request_options = session.calls[0]
        self.assertEqual(requested_url, source_url)
        self.assertEqual(request_options["proxy"], proxy)

    def test_unauthorized_error_does_not_disclose_cookie_or_proxy_values(self):
        cookie_secret = "never-print-this-cookie"
        proxy_secret = "never-print-this-proxy-password"
        session = FakeSession(
            [
                FakeResponse(
                    status_code=401,
                    text=f"server echoed {cookie_secret}",
                )
            ]
        )
        client = ZhihuHttpClient(
            cookies={"z_c0": cookie_secret},
            proxy=f"http://user:{proxy_secret}@proxy.example",
            session=session,
        )

        with self.assertRaises(AuthenticationError) as raised:
            client.get_json("/api/v4/me")

        message = str(raised.exception)
        self.assertIn("HTTP 401", message)
        self.assertIn("z_c0", message)
        self.assertIn("d_c0", message)
        self.assertNotIn(cookie_secret, message)
        self.assertNotIn(proxy_secret, message)
        self.assertEqual(len(session.calls), 1)

    def test_forbidden_response_has_a_distinct_non_retryable_error(self):
        session = FakeSession([FakeResponse(status_code=403)])
        client = ZhihuHttpClient(session=session)

        with self.assertRaises(AccessDeniedError) as raised:
            client.get_html("https://zhuanlan.zhihu.com/p/1")

        self.assertIn("HTTP 403", str(raised.exception))
        self.assertEqual(raised.exception.status_code, 403)
        self.assertEqual(len(session.calls), 1)

    def test_rate_limit_waits_then_returns_the_successful_retry(self):
        session = FakeSession(
            [
                FakeResponse(status_code=429, headers={"Retry-After": "0.25"}),
                FakeResponse(json_data={"items": [1, 2, 3]}),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=2,
            sleep=delays.append,
        )

        payload = client.get_json("/api/v4/items")

        self.assertEqual(payload, {"items": [1, 2, 3]})
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(delays, [0.25])

    def test_rate_limit_stops_after_the_configured_retry_budget(self):
        session = FakeSession(
            [
                FakeResponse(status_code=429),
                FakeResponse(status_code=429),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=1,
            sleep=delays.append,
        )

        with self.assertRaises(RateLimitError) as raised:
            client.get_json("/api/v4/items")

        self.assertEqual(raised.exception.status_code, 429)
        self.assertEqual(len(session.calls), 2)
        self.assertEqual(delays, [1.0])

    def test_server_error_retries_then_raises_a_distinct_error(self):
        session = FakeSession(
            [
                FakeResponse(status_code=503),
                FakeResponse(status_code=503),
                FakeResponse(status_code=503),
            ]
        )
        delays: list[float] = []
        client = ZhihuHttpClient(
            session=session,
            max_retries=2,
            sleep=delays.append,
        )

        with self.assertRaises(ServerError) as raised:
            client.get_html("https://zhuanlan.zhihu.com/p/1")

        self.assertEqual(raised.exception.status_code, 503)
        self.assertIn("HTTP 503", str(raised.exception))
        self.assertEqual(len(session.calls), 3)
        self.assertEqual(delays, [1.0, 2.0])

    def test_login_check_returns_authenticated_member_identity(self):
        session = FakeSession(
            [
                FakeResponse(
                    json_data={
                        "id": "member-id",
                        "name": "归档用户",
                        "url_token": "archive-user",
                    }
                )
            ]
        )
        client = ZhihuHttpClient(session=session)

        status = client.check_login()

        self.assertTrue(status.authenticated)
        self.assertEqual(status.member_id, "member-id")
        self.assertEqual(status.name, "归档用户")
        self.assertEqual(session.calls[0][0], "https://www.zhihu.com/api/v4/me")

    def test_login_check_turns_rejected_session_into_an_unauthenticated_status(self):
        session = FakeSession([FakeResponse(status_code=401)])
        client = ZhihuHttpClient(session=session)

        status = client.check_login()

        self.assertFalse(status.authenticated)
        self.assertEqual(status.reason, "authentication_rejected")
        self.assertIsNone(status.member_id)

    def test_transport_failure_is_wrapped_without_disclosing_cookie_values(self):
        secret_value = "transport-secret-cookie"
        client = ZhihuHttpClient(
            cookies={"z_c0": secret_value},
            session=ExplodingSession(f"network failed with {secret_value}"),
            max_retries=0,
        )

        with self.assertRaises(TransportError) as raised:
            client.get_json("/api/v4/me")

        self.assertIn("request failed", str(raised.exception))
        self.assertNotIn(secret_value, str(raised.exception))

    def test_refuses_to_send_zhihu_cookies_to_an_external_host(self):
        secret_value = "host-safety-secret"
        session = FakeSession([])
        client = ZhihuHttpClient(
            cookies={"z_c0": secret_value},
            session=session,
        )

        with self.assertRaises(UnsafeZhihuUrlError) as raised:
            client.get_html("https://attacker.example/collect")

        self.assertEqual(session.calls, [])
        self.assertNotIn(secret_value, str(raised.exception))


if __name__ == "__main__":
    unittest.main()
