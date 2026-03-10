"""Issue endpoints."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
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
from app.utils.conversion import department_to_issue_type
from app.utils.issue_utils import generate_issue_label
from app.utils.time import utc_to_timezone
from app.utils.user_agent import get_device_type

issue_router = APIRouter()


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


# @issue_router.post(
#     "/anon-create", response_model=AnonymousIssueResponse, status_code=status.HTTP_201_CREATED
# )
# async def create_anonymous_issue(
#     request: Request,
#     issue_create: AnonymousIssueCreate,
#     db: AsyncSession = Depends(get_db),
# ):
#     """Create a new anonymous issue."""
#     try:
#         user_agent = request.headers.get("user-agent")
#         user_agent_check = get_device_type(user_agent)
#         if user_agent_check != "browser":
#             return {"message": "Only browser user agents are allowed to create anonymous issues."}

#         issue_repo = IssueRepository(db)
#         issue_label = generate_issue_label()
#         while await issue_repo.check_issue_label_exists(issue_label):
#             issue_label = generate_issue_label()
#         new_issue: Issue = await issue_repo.create_anon_issue(issue_create, issue_label)
#         await issue_repo.add_issue_location(
#             new_issue.issue_id,
#             issue_create.latitude,
#             issue_create.longitude,
#             issue_create.issue_location,
#         )
#         return AnonymousIssueResponse(
#             issue_label=new_issue.issue_label,
#             status=new_issue.status,
#             created_at=str(utc_to_timezone(new_issue.created_at)),
#         )
#     except Exception as e:
#         return {"message": f"An error occurred while creating the issue: {str(e)}"}


@issue_router.post(
    "/anon-create", response_model=AnonymousIssueResponse, status_code=status.HTTP_201_CREATED
)
async def create_anonymous_issue(
    request: Request,
    issue_create: AnonymousIssueCreate,
    db: AsyncSession = Depends(get_db),
):
    """Create a new anonymous issue."""
    try:
        user_agent = request.headers.get("user-agent")
        user_agent_check = get_device_type(user_agent)

        if user_agent_check != "browser":
            raise HTTPException(
                status_code=400,
                detail="Only browser user agents are allowed to create anonymous issues.",
            )

        issue_repo = IssueRepository(db)

        issue_label = generate_issue_label()
        while await issue_repo.check_issue_label_exists(issue_label):
            issue_label = generate_issue_label()

        new_issue: Issue = await issue_repo.create_anon_issue(issue_create, issue_label)

        await db.commit()

        return AnonymousIssueResponse(
            issue_label=new_issue.issue_label,
            status=new_issue.status,
            created_at=str(utc_to_timezone(new_issue.created_at)),
        )

    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"An error occurred while creating the issue: {str(e)}",
        ) from e


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
