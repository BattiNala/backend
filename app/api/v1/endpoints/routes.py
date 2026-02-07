from fastapi import APIRouter

router = APIRouter()


@router.post("/generate")
def generate_route():
    return {"route": []}
