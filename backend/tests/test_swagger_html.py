"""La pagina Swagger autonoma: lo schema deve restare JSON valido e nessun testo può chiudere in anticipo i tag."""

import importlib.util
import json
import re
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "build_swagger_html.py"


def load_module():
    spec = importlib.util.spec_from_file_location("build_swagger_html", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


SPEC = {
    "openapi": "3.1.0",
    "info": {"title": "Prova", "version": "1", "description": "Testo con </script> e <!-- dentro"},
    "paths": {"/a": {"get": {"summary": "x </script><b>y</b>"}}},
}


def test_page_embeds_the_schema_as_valid_json_and_never_closes_a_tag_early():
    html = load_module().build_html(
        SPEC, "body{}/* </style> */", "console.log('</script><!--')", "abc1234, 15/10/2026"
    )
    assert (
        html.count("<script") == html.count("</script>") == 3
    )  # schema, libreria, avvio: nessuna chiusura anticipata
    assert html.count("<style") == html.count("</style>") == 2
    embedded = re.search(
        r'<script type="application/json" id="spec">(.*?)</script>', html, re.S
    ).group(1)
    parsed = json.loads(embedded)  # JSON valido anche con «<» e «</script>» nei testi
    assert (
        parsed["paths"]["/a"]["get"]["summary"] == "x </script><b>y</b>"
    )  # il contenuto arriva intatto
    assert (
        "Come si accede" in parsed["info"]["description"]
        and "POST /api/v1/auth/google" in parsed["info"]["description"]
    )
    assert parsed["servers"][0]["url"] == "https://INDIRIZZO-DEL-PORTALE"
    assert "abc1234, 15/10/2026" in html


def test_page_is_read_only_and_needs_no_network():
    html = load_module().build_html(SPEC, "", "", "x")
    assert (
        "supportedSubmitMethods: []" in html
    )  # «Try it out» spento: dal file il browser bloccherebbe le chiamate
    assert not re.search(
        r"""(?:src|href)=["']https?://""", html
    )  # nessuna risorsa esterna: si apre anche offline
    assert (
        SPEC["info"]["description"] == "Testo con </script> e <!-- dentro"
    )  # lo schema in ingresso non viene modificato


def test_the_committed_schema_is_what_the_page_is_built_from():
    module = load_module()
    assert (
        module.SPEC == Path(__file__).resolve().parents[2] / "frontend" / "openapi.json"
        and module.SPEC.exists()
    )
    assert json.loads(module.SPEC.read_text(encoding="utf-8"))["paths"]
