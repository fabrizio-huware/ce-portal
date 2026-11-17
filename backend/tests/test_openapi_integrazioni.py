"""La documentazione Swagger delle API per le integrazioni è ricavata dal codice e resta allineata."""

import json
from pathlib import Path

from app import openapi_integrazioni as doc
from app.main import app

DIR = Path(__file__).resolve().parents[2] / "docs" / "api-integrazioni"


def test_the_published_files_match_the_code():
    spec = doc.spec_json(app)
    assert (DIR / "openapi.json").read_text(encoding="utf-8") == spec, (
        "esegui 'make api-integrazioni'"
    )
    assert (DIR / "index.html").read_text(encoding="utf-8") == doc.swagger_html(spec), (
        "esegui 'make api-integrazioni'"
    )


def test_only_the_external_routes_are_documented():
    spec = json.loads(doc.spec_json(app))
    assert spec["paths"]
    assert all(
        p.startswith("/api/v1/integrazioni/") or p == "/api/v1/integrazioni" for p in spec["paths"]
    )
    external = {
        (path, method)
        for path, item in app.openapi()["paths"].items()
        if path.startswith(doc.PREFIX)
        for method in item
    }
    assert external == {(p, m) for p, item in spec["paths"].items() for m in item}


def test_internal_data_and_internal_routes_do_not_leak():
    text = doc.spec_json(app)
    for secret in (
        "extra_costs",
        "discounts",
        "markup",
        "/integrations",
        "/api/v1/ce/",
        "/api/v1/users",
        "ExtraCostIn",
    ):
        assert secret not in text, secret


def test_every_reference_resolves_and_the_security_scheme_is_there():
    spec = json.loads(doc.spec_json(app))
    names = set(spec["components"]["schemas"])
    refs: set[str] = set()
    doc._refs(spec, refs)
    assert refs <= names
    assert "TokenAccountDiServizio" in spec["components"]["securitySchemes"]


def test_the_page_embeds_the_spec_and_pins_the_library():
    html = doc.swagger_html(doc.spec_json(app))
    assert f"swagger-ui-dist@{doc.SWAGGER_UI_VERSION}" in html
    assert "Integrazioni" in html and "</script>" in html
    assert (
        "supportedSubmitMethods: []" in html
    )  # solo consultazione: niente «Try it out» verso il portale
