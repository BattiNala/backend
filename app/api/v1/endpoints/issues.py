"""Issue endpoints."""

import json
import os
import tempfile
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models import Issue
from app.models.user import User
from app.repositories.department_repo import DepartmentRepository
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import (
    AnonymousIssueCreate,
    AnonymousIssueResponse,
    IssueCreate,
    IssueTypesList,
)
from app.services.s3_service import S3Config, S3Service
from app.utils.conversion import department_to_issue_type
from app.utils.issue_utils import generate_issue_label
from app.utils.time import utc_to_timezone
from app.utils.user_agent import get_device_type

issue_router = APIRouter()

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}


def _ensure_required_user_agent(request: Request, required_agent: str) -> None:
    user_agent = request.headers.get("user-agent")
    if not user_agent:
        raise HTTPException(
            status_code=400,
            detail="User-Agent header is required to create anonymous issues.",
        )
    user_agent_check = get_device_type(user_agent)
    if user_agent_check != required_agent:
        raise HTTPException(
            status_code=400,
            detail=f"Only {required_agent} user agents are allowed to create anonymous issues.",
        )


def _validate_photos(photos: list[UploadFile]) -> None:
    if not photos:
        raise HTTPException(
            status_code=400,
            detail="At least one photo is required",
        )
    for photo in photos:
        if photo.content_type not in ALLOWED_IMAGE_TYPES:
            raise HTTPException(
                status_code=400,
                detail="Only JPEG, PNG, and WebP image files are allowed",
            )


def _parse_anonymous_issue_create(issue_create: str) -> AnonymousIssueCreate:
    try:
        issue_create_data = json.loads(issue_create)
        return AnonymousIssueCreate(**issue_create_data)
    except json.JSONDecodeError as e:
        raise HTTPException(
            status_code=400,
            detail="Invalid JSON in issue_create",
        ) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=422,
            detail=e.errors(),
        ) from e


async def _upload_photos_to_s3(
    photos: list[UploadFile],
    s3: S3Service,
) -> tuple[list[str], list[str]]:
    attachment_paths: list[str] = []
    temp_paths: list[str] = []
    for photo in photos:
        fd, temp_path = tempfile.mkstemp(suffix=Path(photo.filename).suffix)
        os.close(fd)
        temp_paths.append(temp_path)

        async with aiofiles.open(temp_path, "wb") as out_file:
            while chunk := await photo.read(1024 * 1024):
                await out_file.write(chunk)

        object_key = await s3.upload_file(Path(temp_path))
        if object_key:
            attachment_paths.append(object_key)
    return attachment_paths, temp_paths


@issue_router.get("/get-issue-types", response_model=IssueTypesList)
async def get_issue_types(db: AsyncSession = Depends(get_db)):
    """Return a list of available issue types."""
    dept_repo = DepartmentRepository(db)
    departments = await dept_repo.list_departments()
    issue_types = [department_to_issue_type(dept) for dept in departments]

    return IssueTypesList(types=issue_types)


@issue_router.get("/")
def list_issues():
    """Return a placeholder issue list response."""
    return {"items": []}


@issue_router.post(
    "/anon-create",
    response_model=AnonymousIssueResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_anonymous_issue(
    request: Request,
    photos: list[UploadFile] = File(...),
    issue_create: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    """Create a new anonymous issue."""
    _ensure_required_user_agent(request, "browser")
    _validate_photos(photos)
    issue_create_obj = _parse_anonymous_issue_create(issue_create)

    attachment_paths: list[str] = []
    temp_paths: list[str] = []

    try:
        async with S3Service(S3Config()) as s3:
            attachment_paths, temp_paths = await _upload_photos_to_s3(photos, s3)

        issue_repo = IssueRepository(db)

        issue_label = generate_issue_label()
        while await issue_repo.check_issue_label_exists(issue_label):
            issue_label = generate_issue_label()

        new_issue: Issue = await issue_repo.create_anon_issue(
            issue_create_obj,
            issue_label,
            attachment_paths,
        )

        await db.commit()

        return AnonymousIssueResponse(
            issue_label=new_issue.issue_label,
            status=new_issue.status,
            created_at=str(utc_to_timezone(new_issue.created_at)),
        )

    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the issue.",
        ) from e
    finally:
        for temp_path in temp_paths:
            try:
                os.remove(temp_path)
            except FileNotFoundError:
                pass


@issue_router.post("/create", status_code=status.HTTP_201_CREATED)
async def create_issue(
    issue_create: IssueCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new issue with user association."""
    issue_repo = IssueRepository(db)
    issue_label = generate_issue_label()
    while await issue_repo.check_issue_label_exists(issue_label):
        issue_label = generate_issue_label()
    new_issue: Issue = await issue_repo.create_issue(issue_create, user.user_id, issue_label)
    return {"message": "Issue created successfully", "issue": new_issue.issue_id}


@issue_router.get("/{issue_id}")
async def get_issue(issue_id: int):
    """Return a placeholder issue detail response."""
    return {"issue_id": issue_id, "details": {}}
