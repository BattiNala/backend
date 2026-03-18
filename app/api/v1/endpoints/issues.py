"""Issue endpoints."""

import json
import os
import tempfile
from pathlib import Path
from typing import Type, TypeVar

import aiofiles
import aiofiles.os
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import get_current_user
from app.db.session import get_db
from app.models import Issue
from app.models.citizens import Citizen
from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.department_repo import DepartmentRepository
from app.repositories.issue_repo import IssueRepository
from app.schemas.issue import (
    AnonymousIssueCreate,
    AnonymousIssueCreateResponse,
    IssueCreate,
    IssueCreateResponse,
    IssueDetailResponse,
    IssueListItem,
    IssueListResponse,
    IssuePriority,
    IssuePriorityOptionsResponse,
    IssueTypesList,
)
from app.services.s3_service import S3Config, S3Service
from app.utils.conversion import department_to_issue_type
from app.utils.issue_utils import generate_issue_label
from app.utils.time import utc_to_timezone
from app.utils.validators import ensure_required_user_agent, validate_photos

issue_router = APIRouter()


def _get_s3_service() -> S3Service:
    return S3Service(S3Config())


async def _safe_upload_photos_to_s3(photos: list[UploadFile]) -> tuple[list[str], list[str]]:
    try:
        async with _get_s3_service() as s3:
            return await _upload_photos_to_s3(photos, s3)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail="An error occurred while uploading photos.",
        ) from e


T = TypeVar("T", bound=BaseModel)


def _parse_issue_create(issue_create: str, schema_cls: Type[T]) -> T:
    try:
        issue_create_data = json.loads(issue_create)
        return schema_cls(**issue_create_data)
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


async def delete_temp_files(temp_paths):
    """Delete temporary files used for photo uploads."""
    for tmp in temp_paths:
        try:
            await aiofiles.os.remove(tmp)
        except FileNotFoundError:
            # If the file was already removed, we can ignore this error
            pass


@issue_router.get(
    "/issue-priority-options",
    response_model=IssuePriorityOptionsResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Issue Priority Options",
    description="Retrieve a list of available issue priorities.",
)
async def get_issue_priority_options():
    """Return a list of available issue priorities."""
    return IssuePriorityOptionsResponse(priorities=[priority.value for priority in IssuePriority])


@issue_router.get("/get-issue-types", response_model=IssueTypesList)
async def get_issue_types(db: AsyncSession = Depends(get_db)):
    """Return a list of available issue types."""
    dept_repo = DepartmentRepository(db)
    departments = await dept_repo.list_departments()
    issue_types = [department_to_issue_type(dept) for dept in departments]

    return IssueTypesList(types=issue_types)


@issue_router.get("/")
async def list_issues(db: AsyncSession = Depends(get_db)):
    """Return a placeholder issue list response."""
    issue_repo = IssueRepository(db)
    issues = await issue_repo.list_issues()
    return {"items": issues, "total": len(issues)}


@issue_router.post(
    "/anon-create",
    response_model=AnonymousIssueCreateResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "photos": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                                "description": "List of photo files to upload.",
                            },
                            "issue_create": {
                                "type": "string",
                                "description": "JSON string for anonymous issue creation."
                                " Should match the AnonymousIssueCreate schema.",
                                "example": json.dumps(
                                    AnonymousIssueCreate.model_config["json_schema_extra"][
                                        "example"
                                    ]
                                ),
                            },
                        },
                        "required": ["photos", "issue_create"],
                    }
                }
            }
        }
    },
)
async def create_anonymous_issue(
    request: Request,
    photos: list[UploadFile] = File(...),
    issue_create: str = Form(
        ...,
        description="JSON string for anonymous issue creation. "
        "Should match the AnonymousIssueCreate schema.",
    ),
    db: AsyncSession = Depends(get_db),
):
    """Create a new anonymous issue."""
    ensure_required_user_agent(request, "browser")
    validate_photos(photos)
    issue_create_obj = _parse_issue_create(issue_create, AnonymousIssueCreate)

    attachment_paths: list[str] = []
    temp_paths: list[str] = []
    try:
        attachment_paths, temp_paths = await _safe_upload_photos_to_s3(photos)

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

        return AnonymousIssueCreateResponse(
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
        await delete_temp_files(temp_paths)


@issue_router.post(
    "/create",
    status_code=status.HTTP_201_CREATED,
    response_model=IssueCreateResponse,
    openapi_extra={
        "requestBody": {
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "photos": {
                                "type": "array",
                                "items": {"type": "string", "format": "binary"},
                                "description": "List of photo files to upload.",
                            },
                            "issue_create": {
                                "type": "string",
                                "description": (
                                    "JSON string for issue creation. "
                                    "Should match the IssueCreate schema."
                                ),
                                "example": json.dumps(
                                    IssueCreate.model_config["json_schema_extra"]["example"]
                                ),
                            },
                        },
                        "required": ["photos", "issue_create"],
                    }
                }
            }
        }
    },
)
async def create_issue(
    request: Request,
    photos: list[UploadFile] = File(...),
    issue_create: str = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new issue with user association."""
    ensure_required_user_agent(request, "BattinalaApp")
    validate_photos(photos)
    attachment_paths: list[str] = []
    temp_paths: list[str] = []
    try:
        issue_create_obj = _parse_issue_create(issue_create, IssueCreate)
        attachment_paths, temp_paths = await _safe_upload_photos_to_s3(photos)

        issue_repo = IssueRepository(db)
        citizen_repo = CitizenRepository(db)
        citizen_profile: Citizen = await citizen_repo.get_citizen_by_user_id(user.user_id)
        issue_label = generate_issue_label()
        while await issue_repo.check_issue_label_exists(issue_label):
            issue_label = generate_issue_label()
        new_issue: Issue = await issue_repo.create_issue(
            issue_create_obj, citizen_profile.citizen_id, issue_label, attachment_paths
        )
        await db.commit()
        return IssueCreateResponse(
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
        await delete_temp_files(temp_paths)


@issue_router.get("/my-issues", response_model=IssueListResponse, status_code=status.HTTP_200_OK)
async def get_my_issues(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Return a list of issues reported by the current user."""
    issue_repo = IssueRepository(db)
    citizen_repo = CitizenRepository(db)
    citizen: Citizen = await citizen_repo.get_citizen_by_user_id(user.user_id)
    issues: list[IssueListItem] = await issue_repo.get_issues_by_reporter(citizen.citizen_id)
    return IssueListResponse(issues=issues, total=len(issues))


@issue_router.get(
    "/{issue_label}", response_model=IssueDetailResponse, status_code=status.HTTP_200_OK
)
async def get_issue(issue_label: str, db: AsyncSession = Depends(get_db)):
    """Return a placeholder issue detail response."""
    issue_repo = IssueRepository(db)
    issue = await issue_repo.get_issue_by_label(issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    s3 = _get_s3_service()
    for attachment in issue.attachments:
        attachment.path = s3.build_s3_url(attachment.path)
    return IssueDetailResponse(
        issue_label=issue.issue_label,
        issue_type=issue.department.department_name if issue.department else "Unknown",
        description=issue.description,
        status=issue.status,
        issue_priority=issue.issue_priority,
        assigned_to=issue.assignee.name if issue.assignee else None,
        created_at=str(utc_to_timezone(issue.created_at)),
        attachments=[attachment.path for attachment in issue.attachments],
        issue_location=issue.issue_location.address if issue.issue_location else None,
        latitude=issue.issue_location.latitude if issue.issue_location else None,
        longitude=issue.issue_location.longitude if issue.issue_location else None,
    )
