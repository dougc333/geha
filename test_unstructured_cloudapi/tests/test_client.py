from pathlib import Path

import pytest
import requests

from unstructured_cloud_test.client import ExtractionError, extract_document
from unstructured_cloud_test.server import ExtractionRequest, _response_payload


class FakeResponse:
    def __init__(self, payload, status_code=200, text=""):
        self._payload = payload
        self.status_code = status_code
        self.text = text

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        return self._payload


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.request = None

    def post(self, url, **kwargs):
        self.request = (url, kwargs)
        return self.response


def test_extract_document_posts_expected_fields(tmp_path: Path):
    document = tmp_path / "claim.pdf"
    document.write_bytes(b"%PDF-test")
    session = FakeSession(FakeResponse([{"type": "Title", "text": "Claim"}]))

    result = extract_document(document, api_key="secret", session=session)

    assert result[0]["type"] == "Title"
    url, request = session.request
    assert url.endswith("/general/v0/general")
    assert request["headers"]["unstructured-api-key"] == "secret"
    assert request["data"]["strategy"] == "hi_res"
    assert request["data"]["infer_table_structure"] == "true"


def test_extract_document_rejects_error_response(tmp_path: Path):
    document = tmp_path / "claim.pdf"
    document.write_bytes(b"%PDF-test")
    session = FakeSession(FakeResponse({}, status_code=401, text="unauthorized"))

    with pytest.raises(ExtractionError, match="HTTP 401"):
        extract_document(document, api_key="bad-key", session=session)


def test_response_payload_summarizes_element_types():
    payload = _response_payload(
        [{"type": "Title"}, {"type": "NarrativeText"}, {"type": "Title"}],
        elapsed_seconds=1.2349,
        cached=False,
        strategy=ExtractionRequest().strategy,
    )

    assert payload["summary"]["element_count"] == 3
    assert payload["summary"]["type_counts"] == {"NarrativeText": 1, "Title": 2}
    assert payload["summary"]["elapsed_seconds"] == 1.235

