from fastapi import APIRouter

router = APIRouter(tags=["system"])


@router.get("/health", summary="Verifica che il servizio sia attivo")
def health() -> dict[str, str]:
    return {"status": "ok"}
