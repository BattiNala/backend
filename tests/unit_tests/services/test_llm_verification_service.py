"""Tests for LLM verification fallback providers."""

# pylint: disable=protected-access,too-few-public-methods,missing-function-docstring,unused-argument

import asyncio
import json
import os

import httpx
import pytest

from app.services import llm_verification_service as llm_module
from app.services.llm_verification_service import (
    GeminiVerificationService,
    GroqVerificationService,
    VerificationResponse,
    VerificationVerdict,
)

os.environ["SMTP_START_TLS"] = "false"


class _FakeAsyncClient:
    """Async client test double for httpx.AsyncClient."""

    response: httpx.Response | None = None
    requests: list[dict] = []

    def __init__(self, *args, **kwargs):
        """Init."""
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context."""
        return None

    async def post(self, url, **kwargs):
        """Record outgoing request and return the configured response."""
        self.__class__.requests.append({"url": url, **kwargs})
        return self.__class__.response


class _ContextClient:
    """Minimal async context manager for build-parts tests."""

    def __init__(self, *args, **kwargs):
        """Init."""
        self.args = args
        self.kwargs = kwargs

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context."""
        return None


class _UploadClient:
    """Client double for Gemini resumable upload flow."""

    def __init__(self):
        """Init."""
        self.calls = []

    async def post(self, url, **kwargs):
        """Return the next upload step response."""
        self.calls.append({"url": url, **kwargs})
        request = httpx.Request("POST", url)

        if url == llm_module.GEMINI_UPLOAD_START_URL:
            return httpx.Response(
                200,
                headers={"x-goog-upload-url": "https://upload.example.com/session-1"},
                request=request,
            )

        return httpx.Response(
            200,
            json={"file": {"uri": "gs://gemini/uploads/image-1"}},
            request=request,
        )


def test_upload_file_to_gemini_uses_resumable_upload(monkeypatch):
    """Test Gemini file uploads use the expected resumable flow."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")
    client = _UploadClient()

    file_uri = asyncio.run(
        GeminiVerificationService._upload_file_to_gemini(
            client=client,
            data=b"image-bytes",
            mime_type="image/png",
            display_name="issue_image_1_photo.png",
        )
    )

    assert file_uri == "gs://gemini/uploads/image-1"
    assert client.calls[0]["url"] == llm_module.GEMINI_UPLOAD_START_URL
    assert client.calls[0]["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert client.calls[0]["headers"]["X-Goog-Upload-Protocol"] == "resumable"
    assert client.calls[0]["json"] == {"file": {"display_name": "issue_image_1_photo.png"}}
    assert client.calls[1]["url"] == "https://upload.example.com/session-1"
    assert client.calls[1]["headers"]["X-Goog-Upload-Command"] == "upload, finalize"
    assert client.calls[1]["content"] == b"image-bytes"


def test_verify_with_gemini_returns_success(monkeypatch):
    """Test Gemini verification parses a valid provider response."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")

    async def _fake_build_parts(prompt, image_urls):
        return [{"text": prompt}, {"file_data": {"file_uri": image_urls[0]}}]

    monkeypatch.setattr(
        GeminiVerificationService,
        "_build_parts",
        staticmethod(_fake_build_parts),
    )
    rationale = "The image clearly shows the reported overflowing garbage."

    response_json = {
        "candidates": [
            {
                "content": {
                    "parts": [
                        {
                            "text": json.dumps(
                                {
                                    "score": 91,
                                    "verdict": "strong_match",
                                    "rationale": rationale,
                                }
                            )
                        }
                    ]
                }
            }
        ]
    }
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response = httpx.Response(
        200,
        json=response_json,
        request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
    )
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        GeminiVerificationService.verify_with_gemini(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["gs://gemini/uploads/image-1"],
        )
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.result is not None
    assert result.result.score == 91
    assert result.result.verdict == VerificationVerdict.STRONG_MATCH
    assert _FakeAsyncClient.requests[0]["url"] == llm_module.gemini_generate_url(
        llm_module.GEMINI_MODEL
    )
    assert _FakeAsyncClient.requests[0]["headers"]["x-goog-api-key"] == "test-gemini-key"
    assert _FakeAsyncClient.requests[0]["json"][
        "generationConfig"
    ] == llm_module.gemini_generation_config(
        llm_module.GEMINI_MODEL,
    )


def test_build_parts_keeps_single_small_image_inline(monkeypatch):
    """Test a single small image stays inline and skips the Files API."""
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _ContextClient)

    async def _fake_download_image(_client, _image_url):
        return b"small-image", "image/png", "photo.png"

    async def _fail_upload(*args, **kwargs):
        raise AssertionError("Files API should not be used for a single small image")

    monkeypatch.setattr(
        GeminiVerificationService,
        "_download_image",
        staticmethod(_fake_download_image),
    )
    monkeypatch.setattr(
        GeminiVerificationService,
        "_upload_file_to_gemini",
        staticmethod(_fail_upload),
    )

    parts = asyncio.run(
        GeminiVerificationService._build_parts(
            prompt="Check this image",
            image_urls=["https://example.com/photo.png"],
        )
    )

    assert parts[0] == {"text": "Check this image"}
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["inline_data"]["data"] == "c21hbGwtaW1hZ2U="


def test_build_parts_keeps_multiple_small_images_inline(monkeypatch):
    """Test multiple small images stay inline and skip the Files API."""
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _ContextClient)

    async def _fake_download_image(_client, image_url):
        filename = image_url.rsplit("/", maxsplit=1)[-1]
        return filename.encode("utf-8"), "image/png", filename

    async def _fail_upload(*args, **kwargs):
        raise AssertionError("Files API should not be used for small inline images")

    monkeypatch.setattr(
        GeminiVerificationService,
        "_download_image",
        staticmethod(_fake_download_image),
    )
    monkeypatch.setattr(
        GeminiVerificationService,
        "_upload_file_to_gemini",
        staticmethod(_fail_upload),
    )

    parts = asyncio.run(
        GeminiVerificationService._build_parts(
            prompt="Compare these two images",
            image_urls=[
                "https://example.com/one.png",
                "https://example.com/two.png",
            ],
        )
    )

    assert parts[0] == {"text": "Compare these two images"}
    assert parts[1]["inline_data"]["mime_type"] == "image/png"
    assert parts[1]["inline_data"]["data"] == "b25lLnBuZw=="
    assert parts[2]["inline_data"]["mime_type"] == "image/png"
    assert parts[2]["inline_data"]["data"] == "dHdvLnBuZw=="


def test_verify_with_gemini_returns_google_error_details_on_403(monkeypatch):
    """Test Gemini verification surfaces provider permission errors."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")

    async def _fake_build_parts(_prompt, _image_urls):
        return [{"text": "prompt"}, {"file_data": {"file_uri": "gs://gemini/uploads/image-1"}}]

    monkeypatch.setattr(
        GeminiVerificationService,
        "_build_parts",
        staticmethod(_fake_build_parts),
    )

    response_json = {
        "error": {
            "code": 403,
            "message": "Your project has been denied access. Please contact support.",
            "status": "PERMISSION_DENIED",
        }
    }
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response = httpx.Response(
        403,
        json=response_json,
        request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
    )
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        GeminiVerificationService.verify_with_gemini(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["https://example.com/photo.png"],
        )
    )

    assert result.ok is False
    assert result.status == "error"
    assert result.result is None
    assert result.message == (
        "Gemini HTTP error: 403 - Your project has been denied access. Please contact support."
    )


def test_verify_with_gemini_requires_configured_api_key(monkeypatch):
    """Test Gemini verification fails cleanly when the API key is missing."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", None)

    with pytest.raises(llm_module.VerificationError, match="GEMINI_API_KEY is not configured."):
        GeminiVerificationService._headers()


def test_verify_with_gemini_normalizes_non_json_with_strict_model(monkeypatch):
    """Test Gemini vision output is normalized through a strict text model when needed."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")

    async def _fake_build_parts(prompt, image_urls):
        return [{"text": prompt}, {"file_data": {"file_uri": image_urls[0]}}]

    monkeypatch.setattr(
        GeminiVerificationService,
        "_build_parts",
        staticmethod(_fake_build_parts),
    )

    class _SequencedAsyncClient:
        """Return one response per post call."""

        responses = []
        requests = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, **kwargs):
            self.__class__.requests.append({"url": url, **kwargs})
            return self.__class__.responses.pop(0)

    rationale = "The image likely matches the reported garbage with some ambiguity."
    _SequencedAsyncClient.requests = []
    _SequencedAsyncClient.responses = [
        httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {"text": "The image likely shows overflowing garbage near a road."}
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
        ),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "score": 83,
                                            "verdict": "moderate_match",
                                            "rationale": rationale,
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request(
                "POST", llm_module.gemini_generate_url(llm_module.GEMINI_STRICT_MODEL)
            ),
        ),
    ]
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _SequencedAsyncClient)

    result = asyncio.run(
        GeminiVerificationService.verify_with_gemini(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["gs://gemini/uploads/image-1"],
        )
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.score == 83
    assert len(_SequencedAsyncClient.requests) == 2
    assert _SequencedAsyncClient.requests[0]["url"] == llm_module.gemini_generate_url(
        llm_module.GEMINI_MODEL
    )
    assert _SequencedAsyncClient.requests[1]["url"] == llm_module.gemini_generate_url(
        llm_module.GEMINI_STRICT_MODEL
    )
    assert _SequencedAsyncClient.requests[1]["json"]["generationConfig"] == (
        llm_module.gemini_generation_config(llm_module.GEMINI_STRICT_MODEL)
    )


def test_verify_with_gemini_retries_transient_503(monkeypatch):
    """Test Gemini retries transient overload responses before succeeding."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")

    async def _fake_sleep(_seconds):
        return None

    monkeypatch.setattr(llm_module.asyncio, "sleep", _fake_sleep)

    async def _fake_build_parts(prompt, image_urls):
        return [{"text": prompt}, {"file_data": {"file_uri": image_urls[0]}}]

    monkeypatch.setattr(
        GeminiVerificationService,
        "_build_parts",
        staticmethod(_fake_build_parts),
    )

    class _RetryClient:
        """Return a transient 503 before a successful response."""

        responses = []
        requests = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, **kwargs):
            self.__class__.requests.append({"url": url, **kwargs})
            return self.__class__.responses.pop(0)

    rationale = "The image clearly matches the reported issue."

    _RetryClient.requests = []
    _RetryClient.responses = [
        httpx.Response(
            503,
            json={
                "error": {
                    "code": 503,
                    "message": "This model is currently experiencing high demand.",
                }
            },
            request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
        ),
        httpx.Response(
            200,
            json={
                "candidates": [
                    {
                        "content": {
                            "parts": [
                                {
                                    "text": json.dumps(
                                        {
                                            "score": 90,
                                            "verdict": "strong_match",
                                            "rationale": rationale,
                                        }
                                    )
                                }
                            ]
                        }
                    }
                ]
            },
            request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
        ),
    ]
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _RetryClient)

    result = asyncio.run(
        GeminiVerificationService.verify_with_gemini(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["gs://gemini/uploads/image-1"],
        )
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.score == 90
    assert len(_RetryClient.requests) == 2


def test_verify_with_gemini_surfaces_finish_reason_when_no_parts(monkeypatch):
    """Test Gemini returns a useful message when no text parts are present."""
    monkeypatch.setattr(llm_module.settings, "GEMINI_API_KEY", "test-gemini-key")

    async def _fake_build_parts(prompt, image_urls):
        return [{"text": prompt}, {"file_data": {"file_uri": image_urls[0]}}]

    monkeypatch.setattr(
        GeminiVerificationService,
        "_build_parts",
        staticmethod(_fake_build_parts),
    )

    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response = httpx.Response(
        200,
        json={
            "candidates": [
                {
                    "content": {"role": "model"},
                    "finishReason": "SAFETY",
                }
            ]
        },
        request=httpx.Request("POST", llm_module.gemini_generate_url(llm_module.GEMINI_MODEL)),
    )
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        GeminiVerificationService.verify_with_gemini(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["gs://gemini/uploads/image-1"],
        )
    )

    assert result.ok is False
    assert result.message == "Gemini returned no text content: finishReason=SAFETY"


def test_normalize_result_unwraps_single_nested_object():
    """Test wrapped provider JSON is normalized before validation."""
    result = llm_module.normalize_result(
        {
            "We": {
                "score": 9,
                "verdict": "irrelevant_or_unusable",
                "rationale": "Image shows a laptop screen, not garbage or roadside issues.",
            }
        }
    )

    assert result.score == 9
    assert result.verdict == VerificationVerdict.IRRELEVANT_OR_UNUSABLE


def test_verify_with_groq_returns_success(monkeypatch):
    """Test Groq verification parses a valid provider response."""
    monkeypatch.setattr(llm_module.settings, "GROQ_API_KEY", "test-groq-key")
    rationale = "The image likely matches the reported pothole with some ambiguity."

    response_json = {
        "choices": [
            {
                "message": {
                    "content": json.dumps(
                        {
                            "score": 88,
                            "verdict": "moderate_match",
                            "rationale": rationale,
                        }
                    )
                }
            }
        ]
    }
    _FakeAsyncClient.requests = []
    _FakeAsyncClient.response = httpx.Response(
        200,
        json=response_json,
        request=httpx.Request("POST", llm_module.GROQ_API_URL),
    )
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _FakeAsyncClient)

    result = asyncio.run(
        GroqVerificationService.verify_with_groq(
            issue_type="Road damage",
            issue_description="Pothole in the middle of the street",
            image_urls=["https://example.com/photo.png"],
        )
    )

    assert result.ok is True
    assert result.status == "success"
    assert result.result is not None
    assert result.result.score == 88
    assert result.result.verdict == VerificationVerdict.MODERATE_MATCH
    assert _FakeAsyncClient.requests[0]["url"] == llm_module.GROQ_API_URL
    assert _FakeAsyncClient.requests[0]["headers"]["Authorization"] == "Bearer test-groq-key"
    assert _FakeAsyncClient.requests[0]["json"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "image_verification_result",
            "strict": False,
            "schema": llm_module.image_verification_response_schema(),
        },
    }
    assert _FakeAsyncClient.requests[0]["json"]["messages"][1]["content"][1] == {
        "type": "image_url",
        "image_url": {"url": "https://example.com/photo.png"},
    }


def test_verify_with_groq_normalizes_non_json_with_strict_model(monkeypatch):
    """Test Groq vision output is normalized through a strict text model when needed."""
    monkeypatch.setattr(llm_module.settings, "GROQ_API_KEY", "test-groq-key")

    class _SequencedAsyncClient:
        """Return one response per post call."""

        responses = []
        requests = []

        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def post(self, url, **kwargs):
            self.__class__.requests.append({"url": url, **kwargs})
            return self.__class__.responses.pop(0)

    rationale = "The image likely matches the reported pothole with some ambiguity."
    _SequencedAsyncClient.requests = []
    _SequencedAsyncClient.responses = [
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "The image likely shows a pothole in the middle of the road."
                        }
                    }
                ]
            },
            request=httpx.Request("POST", llm_module.GROQ_API_URL),
        ),
        httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "score": 84,
                                    "verdict": "moderate_match",
                                    "rationale": rationale,
                                }
                            )
                        }
                    }
                ]
            },
            request=httpx.Request("POST", llm_module.GROQ_API_URL),
        ),
    ]
    monkeypatch.setattr(llm_module.httpx, "AsyncClient", _SequencedAsyncClient)

    result = asyncio.run(
        GroqVerificationService.verify_with_groq(
            issue_type="Road damage",
            issue_description="Pothole in the middle of the street",
            image_urls=["https://example.com/photo.png"],
        )
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.score == 84
    assert len(_SequencedAsyncClient.requests) == 2
    assert _SequencedAsyncClient.requests[0]["json"]["model"] == llm_module.GROQ_MODEL
    assert _SequencedAsyncClient.requests[1]["json"]["model"] == llm_module.GROQ_STRICT_MODEL
    assert _SequencedAsyncClient.requests[1]["json"]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "image_verification_result",
            "strict": True,
            "schema": llm_module.image_verification_response_schema(),
        },
    }


def test_verify_images_falls_back_to_groq_when_gemini_fails(monkeypatch):
    """Test the service uses Groq when Mistral and Gemini both fail."""

    async def _mistral_failure(*args, **kwargs):
        return VerificationResponse(ok=False, status="error", message="mistral down", result=None)

    async def _gemini_failure(*args, **kwargs):
        return VerificationResponse(ok=False, status="error", message="gemini denied", result=None)

    async def _groq_success(*args, **kwargs):
        return VerificationResponse(
            ok=True,
            status="success",
            message=None,
            result=llm_module.ImageVerificationResult(
                score=86,
                verdict=VerificationVerdict.STRONG_MATCH,
                rationale="The image clearly shows the reported problem.",
            ),
        )

    monkeypatch.setattr(llm_module.LLMVerificationService, "verify_with_mistral", _mistral_failure)
    monkeypatch.setattr(GeminiVerificationService, "verify_with_gemini", _gemini_failure)
    monkeypatch.setattr(GroqVerificationService, "verify_with_groq", _groq_success)

    result = asyncio.run(
        llm_module.LLMVerificationService.verify_images(
            issue_type="Garbage",
            issue_description="Overflowing garbage near the roadside",
            image_urls=["https://example.com/photo.png"],
        )
    )

    assert result.ok is True
    assert result.result is not None
    assert result.result.score == 86
    assert result.result.verdict == VerificationVerdict.STRONG_MATCH


def test_verify_with_groq_requires_configured_api_key(monkeypatch):
    """Test Groq verification fails cleanly when the API key is missing."""
    monkeypatch.setattr(llm_module.settings, "GROQ_API_KEY", None)

    with pytest.raises(llm_module.VerificationError, match="GROQ_API_KEY is not configured."):
        GroqVerificationService._headers()
