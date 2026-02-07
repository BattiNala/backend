from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def list_issues():
    return {"items": []}


@router.post("/")
def create_issue():
    return {"created": True}
