"""Issue endpoints."""

import json
from typing import List, Type, TypeVar

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
from app.api.v1.openapi_schema_helper import (
    OPENAPI_ANON_ISSUE_SCHEMA,
    OPENAPI_ISSUE_CREATE_SCHEMA,
)

# scoping helper functions
from app.api.v1.rbac import (
    IssueEndpointContext,
    authorize_issue_access,
    get_issue_list_filters,
    scope_issue_filters_for_user,
)
from app.core.logger import get_logger
from app.db.session import get_db
from app.exceptions.auth_expection import (
    ErrorNotFoundException,
    UnauthorizedException,
)

# models
from app.models import Issue
from app.models.citizens import Citizen
from app.models.employee import Employee
from app.models.user import User

# centralized repositories
from app.repositories.citizen_repo import CitizenRepository
from app.repositories.department_repo import DepartmentRepository
from app.repositories.employee_repo import EmployeeRepository
from app.repositories.issue_repo import IssueListFilters, IssueRepository
from app.repositories.user_repo import UserRepository

# schemas
from app.schemas.employee import EmployeeActivityStatus
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
    IssueRejectRequest,
    IssueRejectResponse,
    IssueReportRequest,
    IssueStatus,
    IssueStatusUpdate,
    IssueTypesList,
)
from app.tasks.celery_jobs import assign_issue_to_nearest_employee_task
from app.tasks.jobs import assign_issue_to_nearest_employee
from app.utils.conversion import department_to_issue_type
from app.utils.issue_utils import generate_issue_label
from app.utils.return_wrappers.issues import wrap_issue_detail_response
from app.utils.s3_utils import (
    delete_temp_files,
    delete_uploaded_files,
    populate_attachment_urls,
    safe_upload_photos_to_s3,
)
from app.utils.time import utc_to_timezone
from app.utils.validators import ensure_required_user_agent, validate_photos

issue_router = APIRouter()
logger = get_logger("api.issues")


T = TypeVar("T", bound=BaseModel)


async def _get_issue_endpoint_context(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> IssueEndpointContext:
    """Bundle common issue endpoint dependencies into one object."""
    return IssueEndpointContext(db=db, current_user=current_user)


async def _safe_upload_photos_to_s3(photos: list[UploadFile]) -> tuple[list[str], list[str]]:
    """Endpoint-local wrapper kept for compatibility and testability."""
    return await safe_upload_photos_to_s3(photos)


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


async def _get_current_employee(
    db: AsyncSession,
    user: User,
) -> Employee:
    """wrapper to get current employee profile, with error handling for missing profile"""
    employee_repo = EmployeeRepository(db)
    employee = await employee_repo.get_employee_by_user_id(user.user_id)

    if not employee:
        raise UnauthorizedException(detail="Employee not found")

    return employee


async def generate_unique_issue_label(issue_repo: IssueRepository) -> str:
    """Generate a unique issue label, retrying if a collision occurs."""
    issue_label = generate_issue_label()
    while await issue_repo.check_issue_label_exists(issue_label):
        issue_label = generate_issue_label()
    return issue_label


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
    filters: IssueListFilters = Depends(get_issue_list_filters),
    context: IssueEndpointContext = Depends(_get_issue_endpoint_context),
):
    """Filters: status, priority, date range"""
    scoped_filters = await scope_issue_filters_for_user(
        context,
        filters,
        user_repo_cls=UserRepository,
        employee_repo_cls=EmployeeRepository,
        citizen_repo_cls=CitizenRepository,
    )
    issue_repo = IssueRepository(context.db)
    issues = await issue_repo.list_issues(scoped_filters)
    return {"items": issues, "total": len(issues)}


@issue_router.post(
    "/anon-create",
    response_model=AnonymousIssueCreateResponse,
    status_code=status.HTTP_201_CREATED,
    openapi_extra=OPENAPI_ANON_ISSUE_SCHEMA,
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
        issue_label = await generate_unique_issue_label(issue_repo)
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
    openapi_extra=OPENAPI_ISSUE_CREATE_SCHEMA,
)
async def create_issue(
    request: Request,
    photos: list[UploadFile] = File(...),
    issue_create: str = Form(...),
    context: IssueEndpointContext = Depends(_get_issue_endpoint_context),
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
        issue_label = await generate_unique_issue_label(issue_repo)

        new_issue: Issue = await issue_repo.create_issue(
            issue_create_obj,
            citizen_profile.citizen_id,
            issue_label,
            attachment_paths,
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

    assign_issue_to_nearest_employee_task.delay(new_issue.issue_id)

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


@issue_router.get("/my-issues", status_code=status.HTTP_200_OK)
async def get_my_issues(
    filters: IssueListFilters = Depends(get_issue_list_filters),
    context: IssueEndpointContext = Depends(_get_issue_endpoint_context),
):
    """Return issues visible to the current user within their role scope."""
    scoped_filters = await scope_issue_filters_for_user(
        context,
        filters,
        user_repo_cls=UserRepository,
        employee_repo_cls=EmployeeRepository,
        citizen_repo_cls=CitizenRepository,
    )
    issue_repo = IssueRepository(context.db)
    issues: List[IssueListItem] = await issue_repo.list_issues(scoped_filters)
    return IssueListResponse(items=issues, total=len(issues))


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
    issue = await issue_repo.get_issue_by_label(payload.issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status != IssueStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=400,
            detail="Only issues pending verification can be verified.",
        )

    employee: Employee = await _get_current_employee(db, current_user)

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
async def update_issue_status_by_admin(
    payload: IssueStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Update issue status by department admin."""
    # if payload.status in {IssueStatus.PENDING_VERIFICATION, IssueStatus.REJECTED}:
    #     raise HTTPException(
    #         status_code=400,
    #         detail="Staff cannot set status to PENDING_VERIFICATION or REJECTED.",
    #     )

    issue_repo = IssueRepository(db)
    issue = await issue_repo.get_issue_by_label(payload.issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    employee: Employee = await _get_current_employee(db, current_user)
    if not employee or issue.issue_type != employee.department_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Wrong department.")
    await issue_repo.update_issue_status(issue, payload.status)
    return {"message": "Issue status updated.", "status": payload.status}


@issue_router.post(
    "/resolve",
    status_code=status.HTTP_200_OK,
)
async def resolve_issue_by_staff(
    payload: IssueStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Update issue status by staff/employee."""
    try:
        issue_repo = IssueRepository(db)
        employee_repo = EmployeeRepository(db)
        issue = await issue_repo.get_issue_by_label(payload.issue_label)
        if not issue:
            raise HTTPException(status_code=404, detail="Issue not found")

        employee: Employee = await _get_current_employee(db, current_user)
        if issue.assignee_id is not None and issue.assignee_id != employee.employee_id:
            raise HTTPException(status_code=403, detail="Access forbidden: Not assignee.")

        await issue_repo.update_issue_status(issue, IssueStatus.RESOLVED)
        await employee_repo.update_employee_status(employee, EmployeeActivityStatus.AVAILABLE)
        return {"message": "Issue status updated.", "status": IssueStatus.RESOLVED}
    except Exception as e:
        await db.rollback()
        logger.error("Error resolving issue: %s", str(e), exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="An error occurred while updating the issue status.",
        ) from e


@issue_router.post(
    "/report-false",
    status_code=status.HTTP_200_OK,
)
async def report_false_issue(
    payload: IssueReportRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_staff),
):
    """Report an issue as false (staff only).
    Only the assigned employee can report their issue as false,
    and only if it's currently open or in progress."""
    try:
        issue_repo = IssueRepository(db)
        employee_repo = EmployeeRepository(db)

        issue: Issue = await issue_repo.get_issue_by_label(payload.issue_label)
        if not issue:
            raise ErrorNotFoundException(detail="Issue not found")

        employee: Employee = await employee_repo.get_employee_by_user_id(current_user.user_id)
        if not employee:
            raise UnauthorizedException(detail="Employee not found")

        if issue.status not in (IssueStatus.OPEN, IssueStatus.IN_PROGRESS):
            raise HTTPException(
                status_code=400,
                detail="Only open issues can be reported as false.",
            )

        if employee.employee_id != issue.assignee_id:
            raise UnauthorizedException(
                detail="Only the assigned employee can report this issue as false."
            )

        await issue_repo.report_issue_as_false(
            issue,
            reason=payload.reason,
            reported_by_employee_id=employee.employee_id,
        )

        await db.commit()

        return {"message": "Issue reported as false."}

    except HTTPException:
        await db.rollback()
        raise
    except Exception as e:
        await db.rollback()
        logger.error("Error reporting issue as false: %s", str(e), exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


@issue_router.post(
    "/reject",
    status_code=status.HTTP_200_OK,
    response_model=IssueRejectResponse,
    description="Reject an issue (department admin only). "
    "Only issues pending verification / reported can be rejected.",
)
async def reject_issue(
    payload: IssueRejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_department_admin),
):
    """Reject an issue (department admin only)."""

    issue_repo = IssueRepository(db)
    employee_repo = EmployeeRepository(db)
    issue = await issue_repo.get_issue_by_label(payload.issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    if issue.status != IssueStatus.PENDING_VERIFICATION:
        raise HTTPException(
            status_code=400,
            detail="Only issues pending verification can be rejected.",
        )

    employee = await employee_repo.get_employee_by_user_id(current_user.user_id)
    if not employee or issue.issue_type != employee.department_id:
        raise HTTPException(status_code=403, detail="Access forbidden: Wrong department.")

    await issue_repo.reject_issue(
        issue, reason=payload.reason, rejected_by_employee_id=employee.employee_id
    )
    return IssueRejectResponse(message="Issue rejected.", status=IssueStatus.REJECTED)


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
    issue: Issue = await issue_repo.get_issue_by_label(issue_label)
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")

    await authorize_issue_access(issue=issue, current_user=current_user, db=db)
    populate_attachment_urls(issue)

    return wrap_issue_detail_response(issue)
