"""Issue endpoints."""

import json
import os
import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Type, TypeVar

import aiofiles
import aiofiles.os
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Request,
    UploadFile,
    status,
)
from pydantic import BaseModel, ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies import (
    get_current_user,
    get_optional_current_user,
    require_department_admin,
    require_staff,
)
from app.api.v1.rbac import authorize_issue_access
from app.core.logger import get_logger
from app.db.session import get_db
from app.models import Issue
from app.models.citizens import Citizen
from app.models.user import User
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.department_repo import DepartmentRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.issue_repo import IssueListFilters, IssueRepository
from app.repositories.user_repo import UserRepository
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
    IssueReportRequest,
    IssueStatus,
    IssueStatusUpdate,
    IssueTypesList,
)
from app.services.s3_service import S3Config, S3Service
from app.tasks.jobs import assign_issue_to_nearest_employee
from app.utils.conversion import department_to_issue_type
from app.utils.issue_utils import generate_issue_label
from app.utils.time import utc_to_timezone
from app.utils.validators import ensure_required_user_agent, validate_photos

issue_router = APIRouter()
logger = get_logger("api.issues")


def _get_s3_service() -> S3Service:
    return S3Service(S3Config())


def _populate_attachment_urls(issue) -> None:
    """Replace attachment paths with full S3 URLs."""
    s3 = _get_s3_service()
    for attachment in issue.attachments:
        attachment.path = s3.build_s3_url(attachment.path)


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


@dataclass(slots=True)
class _IssueEndpointContext:
    """Request-scoped dependencies shared by issue endpoints."""

    db: AsyncSession
    current_user: User


async def _get_issue_endpoint_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> _IssueEndpointContext:
    """Bundle common issue endpoint dependencies into one object."""
    return _IssueEndpointContext(db=db, current_user=current_user)


def _get_issue_list_filters(
    issue_status: IssueStatus | None = None,
    priority: IssuePriority | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> IssueListFilters:
    """Build list filters from query params."""
    return IssueListFilters(
        status=issue_status,
        priority=priority,
        date_from=date_from,
        date_to=date_to,
    )


async def _scope_issue_filters_for_user(
    context: _IssueEndpointContext, filters: IssueListFilters
) -> IssueListFilters:
    """Apply role-based issue visibility filters for the current user."""
    user_repo = UserRepository(context.db)
    role_name = await user_repo.get_user_role_name(context.current_user.user_id)

    if role_name == "superadmin":
        return filters

    if role_name in {"department_admin", "staff"}:
        employee_repo = EmployeeRepository(context.db)
        employee = await employee_repo.get_employee_by_user_id(context.current_user.user_id)
        if not employee:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        if role_name == "department_admin":
            filters.department_id = employee.department_id
        else:
            filters.assignee_id = employee.employee_id
        return filters

    if role_name == "citizen":
        citizen_repo = CitizenRepository(context.db)
        citizen = await citizen_repo.get_citizen_by_user_id(context.current_user.user_id)
        if not citizen:
            raise HTTPException(status_code=403, detail="Access forbidden.")
        filters.reporter_id = citizen.citizen_id
        return filters

    raise HTTPException(status_code=403, detail="Access forbidden.")


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

        try:
            object_key = await s3.upload_file(Path(temp_path))
        except Exception:
            await _delete_uploaded_s3_objects(s3, attachment_paths)
            raise

        if not object_key:
            await _delete_uploaded_s3_objects(s3, attachment_paths)
            raise RuntimeError(f"Failed to upload photo: {photo.filename}")

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


async def _delete_uploaded_s3_objects(s3: S3Service, object_keys: list[str]) -> None:
    """Best-effort delete for uploaded S3 objects."""
    for object_key in object_keys:
        deleted = await s3.delete_file(object_key)
        if not deleted:
            logger.warning("Failed to delete uploaded attachment from storage: key=%s", object_key)


async def delete_uploaded_files(object_keys: list[str]) -> None:
    """Best-effort cleanup for uploaded S3 objects after request failure."""
    if not object_keys:
        return

    try:
        async with _get_s3_service() as s3:
            await _delete_uploaded_s3_objects(s3, object_keys)
    # pylint: disable=broad-exception-caught
    except Exception:
        logger.exception("Failed to clean up uploaded attachments: keys=%s", object_keys)


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


@issue_router.get(
    "/",
    status_code=status.HTTP_200_OK,
    summary="List Issues with Filters",
    description="Retrieve a list of issues with optional filters."
    " department_admin and staff see issues in their department,"
    " citizens see their own issues, superadmins see all issues. "
    " Filters: status, priority, date range.",
)
async def list_issues(
    filters: IssueListFilters = Depends(_get_issue_list_filters),
    context: _IssueEndpointContext = Depends(_get_issue_endpoint_context),
):
    """Filters: status, priority, date range"""
    scoped_filters = await _scope_issue_filters_for_user(context, filters)
    issue_repo = IssueRepository(context.db)
    issues = await issue_repo.list_issues(scoped_filters)
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
    except HTTPException:
        await db.rollback()
        await delete_uploaded_files(attachment_paths)
        raise
    except Exception as e:
        await db.rollback()
        await delete_uploaded_files(attachment_paths)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the issue.",
        ) from e
    finally:
        await delete_temp_files(temp_paths)

    return AnonymousIssueCreateResponse(
        issue_label=new_issue.issue_label,
        status=new_issue.status,
        created_at=str(utc_to_timezone(new_issue.created_at)),
    )


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
    background_tasks: BackgroundTasks,
    photos: list[UploadFile] = File(...),
    issue_create: str = Form(...),
    context: _IssueEndpointContext = Depends(_get_issue_endpoint_context),
):
    """Create a new issue with user association."""
    ensure_required_user_agent(request, "BattinalaApp")
    validate_photos(photos)
    attachment_paths: list[str] = []
    temp_paths: list[str] = []
    try:
        issue_create_obj = _parse_issue_create(issue_create, IssueCreate)
        attachment_paths, temp_paths = await _safe_upload_photos_to_s3(photos)

        issue_repo = IssueRepository(context.db)
        citizen_repo = CitizenRepository(context.db)
        citizen_profile: Citizen = await citizen_repo.get_citizen_by_user_id(
            context.current_user.user_id
        )
        issue_label = generate_issue_label()
        while await issue_repo.check_issue_label_exists(issue_label):
            issue_label = generate_issue_label()
        new_issue: Issue = await issue_repo.create_issue(
            issue_create_obj, citizen_profile.citizen_id, issue_label, attachment_paths
        )
        await context.db.commit()
    except HTTPException:
        await context.db.rollback()
        await delete_uploaded_files(attachment_paths)
        raise
    except Exception as e:
        await context.db.rollback()
        await delete_uploaded_files(attachment_paths)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while creating the issue.",
        ) from e
    finally:
        await delete_temp_files(temp_paths)

    background_tasks.add_task(assign_issue_to_nearest_employee, new_issue.issue_id)
    logger.info(
        "Queued issue auto-assignment task: issue_id=%s issue_label=%s reporter_id=%s",
        new_issue.issue_id,
        new_issue.issue_label,
        citizen_profile.citizen_id,
    )

    return IssueCreateResponse(
        issue_label=new_issue.issue_label,
        status=new_issue.status,
        created_at=str(utc_to_timezone(new_issue.created_at)),
    )


@issue_router.get("/my-issues", response_model=IssueListResponse, status_code=status.HTTP_200_OK)
async def get_my_issues(db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    """Return a list of issues reported by the current user."""
    issue_repo = IssueRepository(db)
    citizen_repo = CitizenRepository(db)
    citizen: Citizen = await citizen_repo.get_citizen_by_user_id(user.user_id)
    issues: list[IssueListItem] = await issue_repo.get_issues_by_reporter(citizen.citizen_id)
    return IssueListResponse(issues=issues, total=len(issues))


@issue_router.post(
    "/verify-status",
    status_code=status.HTTP_200_OK,
)
async def verify_issue_status(
    payload: IssueStatusUpdate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Verify an issue (department admin only)."""
    if payload.status not in {IssueStatus.OPEN, IssueStatus.REJECTED}:
        raise HTTPException(
            status_code=400,
            detail="Verification can only set status to OPEN or REJECTED.",
        )

    issue_repo = IssueRepository(db)
    employee_repo = EmployeeRepository(db)
    issue = await issue_repo.get_issue_by_label(payload.issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status != IssueStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=400,
            detail="Only issues pending verification can be verified.",
        )

    employee = await employee_repo.get_employee_by_user_id(current_user.user_id)
    if not employee or issue.issue_type != employee.department_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Wrong department.")

    await issue_repo.update_issue_status(issue, payload.status)
    if payload.status == IssueStatus.OPEN and issue.assignee_id is None:
        background_tasks.add_task(assign_issue_to_nearest_employee, issue.issue_id)
    return {"message": "Issue status updated.", "status": payload.status}


@issue_router.post(
    "/update-status",
    status_code=status.HTTP_200_OK,
)
async def update_issue_status_by_employee(
    payload: IssueStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Update issue status by staff/employee."""
    if payload.status in {IssueStatus.PENDING_VERIFICATION, IssueStatus.REJECTED}:
        raise HTTPException(
            status_code=400,
            detail="Staff cannot set status to PENDING_VERIFICATION or REJECTED.",
        )

    issue_repo = IssueRepository(db)
    employee_repo = EmployeeRepository(db)
    issue = await issue_repo.get_issue_by_label(payload.issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    employee = await employee_repo.get_employee_by_user_id(current_user.user_id)
    if not employee or issue.issue_type != employee.department_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Wrong department.")
    if issue.assignee_id is not None and issue.assignee_id != employee.employee_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Not assignee.")

    await issue_repo.update_issue_status(issue, payload.status)
    return {"message": "Issue status updated.", "status": payload.status}


@issue_router.post(
    "/report-false",
    status_code=status.HTTP_200_OK,
)
async def report_false_issue(
    payload: IssueReportRequest,
    _current_user: User = Depends(require_staff),
):
    """Placeholder for reporting a false issue by staff."""
    return {"message": "False report received (placeholder).", "issue_label": payload.issue_label}


@issue_router.get(
    "/{issue_label}",
    response_model=IssueDetailResponse,
    status_code=status.HTTP_200_OK,
    description="Get detailed information about an issue by its label."
    " Accessible by staff and department admins for their department's issues, "
    "and by citizens for their own issues.",
)
async def get_issue(
    issue_label: str,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Return issue details.

    Anonymous issues can be accessed without authentication.
    Non-anonymous issues require authorization based on user role.
    """
    issue_repo = IssueRepository(db)
    issue = await issue_repo.get_issue_by_label(issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await authorize_issue_access(issue=issue, current_user=current_user, db=db)
    _populate_attachment_urls(issue)

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
