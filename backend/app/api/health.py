from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health", summary="Check API process health")
def health_check() -> dict[str, str]:
    """Return a lightweight liveness response without touching external services."""
    return {"status": "ok"}
