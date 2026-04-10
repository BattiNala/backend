"""Tests for attachment embedding background jobs."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.tasks import embedding_jobs


class _FakeSession:
    """Async session test double for embedding jobs."""

    def __init__(self):
        self.committed = False
        self.rolled_back = False

    async def __aenter__(self):
        """Enter async context."""
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Exit async context."""
        return None

    async def commit(self):
        """Track commit calls."""
        self.committed = True

    async def rollback(self):
        """Track rollback calls."""
        self.rolled_back = True


def test_embed_issue_attachments_downloads_s3_and_persists_embedding(monkeypatch, tmp_path):
    """Attachment embeddings should resolve storage paths and persist the result."""
    downloaded = tmp_path / "issue.png"
    downloaded.write_bytes(b"image-bytes")

    attachment = SimpleNamespace(
        attachment_id=11,
        path="images/issue.png",
        embedding=None,
        embedding_model=None,
    )
    issue = SimpleNamespace(issue_id=7, issue_label="ISS-7", attachments=[attachment])

    cleanup = AsyncMock()
    generate = AsyncMock(return_value=[0.1, 0.2, 0.3])

    monkeypatch.setattr(
        embedding_jobs,
        "_materialize_attachment_paths",
        AsyncMock(return_value=({id(attachment): str(downloaded)}, [str(downloaded)])),
    )
    monkeypatch.setattr(embedding_jobs, "delete_temp_files", cleanup)
    monkeypatch.setattr(
        embedding_jobs.GeminiEmbeddingService,
        "generate_image_embedding",
        generate,
    )
    monkeypatch.setattr(
        embedding_jobs.settings,
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-2-preview",
    )

    embedded_count = asyncio.run(embedding_jobs.embed_issue_attachments(issue))

    assert embedded_count == 1
    assert attachment.embedding == [0.1, 0.2, 0.3]
    assert attachment.embedding_model == "gemini-embedding-2-preview"
    generate.assert_awaited_once_with(str(downloaded))
    cleanup.assert_awaited_once_with([str(downloaded)])


def test_embed_issue_attachments_skips_current_model_embeddings(monkeypatch, tmp_path):
    """Already-embedded attachments for the current model should be skipped."""
    local_image = tmp_path / "issue.png"
    local_image.write_bytes(b"image-bytes")

    attachment = SimpleNamespace(
        attachment_id=12,
        path=str(local_image),
        embedding=[0.9, 0.8],
        embedding_model="gemini-embedding-2-preview",
    )
    issue = SimpleNamespace(issue_id=8, issue_label="ISS-8", attachments=[attachment])

    cleanup = AsyncMock()
    generate = AsyncMock()

    monkeypatch.setattr(
        embedding_jobs,
        "_materialize_attachment_paths",
        AsyncMock(return_value=({id(attachment): str(local_image)}, [])),
    )
    monkeypatch.setattr(embedding_jobs, "delete_temp_files", cleanup)
    monkeypatch.setattr(
        embedding_jobs.GeminiEmbeddingService,
        "generate_image_embedding",
        generate,
    )
    monkeypatch.setattr(
        embedding_jobs.settings,
        "GEMINI_EMBEDDING_MODEL",
        "gemini-embedding-2-preview",
    )

    embedded_count = asyncio.run(embedding_jobs.embed_issue_attachments(issue))

    assert embedded_count == 0
    generate.assert_not_awaited()
    cleanup.assert_awaited_once_with([])


def test_generate_issue_embeddings_commits_on_success(monkeypatch):
    """The embedding job should commit after persisting attachment vectors."""
    session = _FakeSession()
    issue = SimpleNamespace(issue_id=9, issue_label="ISS-9", attachments=[])
    repo = SimpleNamespace(get_issue_by_id=AsyncMock(return_value=issue))
    embed = AsyncMock(return_value=2)

    monkeypatch.setattr(embedding_jobs, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(embedding_jobs, "IssueRepository", lambda _db: repo)
    monkeypatch.setattr(embedding_jobs, "embed_issue_attachments", embed)

    asyncio.run(embedding_jobs.generate_issue_embeddings(issue.issue_id))

    repo.get_issue_by_id.assert_awaited_once_with(issue.issue_id)
    embed.assert_awaited_once_with(issue)
    assert session.committed is True
    assert session.rolled_back is False


def test_generate_issue_embeddings_rolls_back_on_failure(monkeypatch):
    """The embedding job should roll back when vector generation fails."""
    session = _FakeSession()
    issue = SimpleNamespace(issue_id=10, issue_label="ISS-10", attachments=[])
    repo = SimpleNamespace(get_issue_by_id=AsyncMock(return_value=issue))
    embed = AsyncMock(side_effect=RuntimeError("provider failed"))

    monkeypatch.setattr(embedding_jobs, "AsyncSessionLocal", lambda: session)
    monkeypatch.setattr(embedding_jobs, "IssueRepository", lambda _db: repo)
    monkeypatch.setattr(embedding_jobs, "embed_issue_attachments", embed)

    try:
        asyncio.run(embedding_jobs.generate_issue_embeddings(issue.issue_id))
        raise AssertionError("Expected generate_issue_embeddings to raise")
    except RuntimeError as exc:
        assert str(exc) == "provider failed"

    assert session.committed is False
    assert session.rolled_back is True
