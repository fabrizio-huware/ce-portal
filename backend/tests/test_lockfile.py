"""Il file delle versioni esatte (usato per costruire l'immagine) deve coprire le dipendenze di pyproject.toml."""

import re
import tomllib
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]


def normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def declared() -> set[str]:
    deps = tomllib.loads((BACKEND / "pyproject.toml").read_text())["project"]["dependencies"]
    return {normalize(re.split(r"[\[<>=!~ ;]", d, maxsplit=1)[0]) for d in deps}


def locked() -> dict[str, str]:
    out = {}
    for line in (BACKEND / "requirements.lock").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, _, version = line.partition("==")
            out[normalize(name)] = version
    return out


def test_every_declared_dependency_is_locked_to_an_exact_version():
    lock = locked()
    missing = declared() - set(lock)
    assert not missing, f"mancano nel file delle versioni (esegui `make lock`): {sorted(missing)}"
    assert all(re.fullmatch(r"\d+(\.\d+)*([a-z]+\d+|\.post\d+)?", v) for v in lock.values()), (
        "versioni non esatte"
    )


def test_development_tools_are_not_in_the_production_image():
    lock = locked()
    for dev_only in ("pytest", "ruff", "pypdf", "httpx"):
        assert dev_only not in lock, f"{dev_only} è solo di sviluppo"


def test_the_lock_file_says_how_it_is_generated():
    assert "make lock" in (BACKEND / "requirements.lock").read_text().splitlines()[0]


def locked_dev() -> dict[str, str]:
    out = {}
    for line in (BACKEND / "requirements-dev.lock").read_text().splitlines():
        if line.strip() and not line.startswith("#"):
            name, _, version = line.partition("==")
            out[normalize(name)] = version
    return out


def test_the_dev_lock_pins_the_same_production_versions_plus_the_test_tools():
    prod, dev = locked(), locked_dev()
    assert {k: v for k, v in dev.items() if k in prod} == prod, (
        "le versioni di produzione devono coincidere nei due file"
    )
    for tool in ("pytest", "ruff", "httpx", "pypdf"):
        assert tool in dev, f"{tool} deve essere fissato nel file di sviluppo"


def test_ci_installs_the_exact_versions_not_the_latest():
    ci = (BACKEND.parent / ".github" / "workflows" / "ci.yml").read_text()
    assert "requirements-dev.lock" in ci
    assert 'pip install -e ".[dev]"' not in ci and "pip install -e backend\n" not in ci, (
        "la CI non deve installare le ultime versioni"
    )
