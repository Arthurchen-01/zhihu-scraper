import io
import tempfile
import unittest
from pathlib import Path
from urllib.request import Request

from zhihu_scraper.media import (
    MediaCandidate,
    download_media,
    select_highest_resolution,
)


class FakeHttpResponse:
    def __init__(self, *, status: int, body: bytes, headers: dict[str, str]):
        self.status = status
        self.headers = headers
        self._body = io.BytesIO(body)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._body.close()

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)


class InterruptingHttpResponse(FakeHttpResponse):
    def __init__(self, *, first_chunk: bytes, expected_total: int):
        super().__init__(
            status=200,
            body=first_chunk,
            headers={"Content-Length": str(expected_total)},
        )
        self._read_count = 0

    def read(self, size: int = -1) -> bytes:
        self._read_count += 1
        if self._read_count == 1:
            return super().read(size)
        raise ConnectionError("connection interrupted")


class RecordingTransport:
    def __init__(self, response: FakeHttpResponse):
        self.response = response
        self.requests: list[Request] = []

    def __call__(self, request: Request):
        self.requests.append(request)
        return self.response


class MediaQualitySelectionTests(unittest.TestCase):
    def test_selects_highest_resolution_and_keeps_the_first_exact_tie(self):
        first_full_hd = MediaCandidate(
            source_url="https://media.example/first-1080p.mp4",
            width=1920,
            height=1080,
        )
        candidates = (
            MediaCandidate(
                source_url="https://media.example/720p.mp4",
                width=1280,
                height=720,
            ),
            first_full_hd,
            MediaCandidate(
                source_url="https://media.example/second-1080p.mp4",
                width=1920,
                height=1080,
            ),
        )

        self.assertIs(select_highest_resolution(candidates), first_full_hd)


class ResumableMediaDownloadTests(unittest.TestCase):
    def test_resumes_an_existing_partial_file_with_a_range_request(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            FakeHttpResponse(
                status=206,
                body=b" world",
                headers={
                    "Content-Range": "bytes 5-10/11",
                    "Content-Length": "6",
                },
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            partial_path = destination.with_name(f"{destination.name}.part")
            partial_path.write_bytes(b"hello")

            receipt = download_media(source_url, destination, transport=transport)

            self.assertEqual(destination.read_bytes(), b"hello world")
            self.assertFalse(partial_path.exists())
            self.assertEqual(transport.requests[0].get_header("Range"), "bytes=5-")
            self.assertEqual(receipt.source_url, source_url)
            self.assertEqual(receipt.destination, destination)
            self.assertEqual(receipt.resumed_from, 5)
            self.assertEqual(receipt.bytes_total, 11)

    def test_restarts_safely_when_a_server_ignores_the_range_header(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            FakeHttpResponse(
                status=200,
                body=b"complete replacement",
                headers={"Content-Length": "20"},
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            partial_path = destination.with_name(f"{destination.name}.part")
            partial_path.write_bytes(b"stale")

            receipt = download_media(source_url, destination, transport=transport)

            self.assertEqual(transport.requests[0].get_header("Range"), "bytes=5-")
            self.assertEqual(destination.read_bytes(), b"complete replacement")
            self.assertEqual(receipt.resumed_from, 0)
            self.assertEqual(receipt.bytes_total, 20)

    def test_interruption_keeps_only_a_resumable_partial_file(self):
        source_url = "https://media.example/video.mp4"
        transport = RecordingTransport(
            InterruptingHttpResponse(first_chunk=b"first chunk", expected_total=20)
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            destination = Path(temporary_directory) / "video.mp4"
            partial_path = destination.with_name(f"{destination.name}.part")

            with self.assertRaisesRegex(ConnectionError, "connection interrupted"):
                download_media(source_url, destination, transport=transport)

            self.assertFalse(destination.exists())
            self.assertEqual(partial_path.read_bytes(), b"first chunk")


if __name__ == "__main__":
    unittest.main()
