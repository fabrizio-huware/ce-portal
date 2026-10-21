"""I nomi dei tipi dello schema delle API sono quelli che il frontend usa: non devono dividersi."""

from app.core.config import Settings
from app.main import create_app

# Tipi che il frontend importa per nome da frontend/src/api/schema.d.ts.
USED_BY_THE_FRONTEND = ("ContentIn", "HeaderIn", "PhaseIn", "LineIn", "AllocationIn")


def schemas() -> dict:
    return create_app(Settings()).openapi()["components"]["schemas"]


def test_no_schema_is_split_into_input_and_output_variants():
    """Un tipo di ingresso non deve comparire anche in una risposta (vedi IntegrationContent.content)."""
    split = sorted(name for name in schemas() if name.endswith(("-Input", "-Output")))
    assert split == [], (
        f"Tipi divisi in -Input/-Output: {split}. Succede quando un tipo compare sia in ingresso sia in "
        "uscita senza separate_input_output_schemas=False: il frontend non troverebbe più il nome."
    )


def test_the_types_the_frontend_relies_on_keep_their_names():
    names = schemas()
    for name in USED_BY_THE_FRONTEND:
        assert name in names, name
