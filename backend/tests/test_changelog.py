"""Il registro delle modifiche (docs/changelog.md) deve restare ordinato, completo e collegato."""

import re
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHANGELOG = ROOT / "docs" / "changelog.md"

TYPES = {"Funzione", "Ritocco", "Correzione", "Infrastruttura", "Documentazione", "Strumenti"}
STATES = ("In corso", "Consegnata", "Pubblicata sul test", "In produzione", "Annullata")
REQUIRED = ("Richiesta", "Tipo", "Cosa è cambiato", "Verifica", "Stato")
HEADER = re.compile(r"^### (CL-(\d{3,})) · (\d{4}-\d{2}-\d{2}) · (.+)$")


def entries() -> list[dict]:
    """Voci del registro (fuori dai blocchi di codice), nell'ordine del file."""
    out, current, fence = [], None, False
    for line in CHANGELOG.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        if fence:
            continue
        m = HEADER.match(line)
        if m:
            current = {
                "id": m.group(1),
                "number": int(m.group(2)),
                "date": m.group(3),
                "title": m.group(4),
                "fields": {},
                "raw": line,
            }
            out.append(current)
        elif line.startswith("### "):
            out.append(
                {"id": None, "raw": line, "fields": {}}
            )  # titolo che non rispetta il formato
            current = out[-1]
        elif current is not None:
            f = re.match(r"^- \*\*([^*]+)\*\*: (.*)$", line)
            if f:
                current["fields"][f.group(1)] = f.group(2)
    return out


def test_the_changelog_exists_and_has_entries():
    assert CHANGELOG.exists(), "manca docs/changelog.md"
    assert len(entries()) >= 30


def test_every_heading_follows_the_format():
    bad = [e["raw"] for e in entries() if e["id"] is None]
    assert not bad, (
        "titoli di voce non nel formato «### CL-NNN · AAAA-MM-GG · Titolo»:\n" + "\n".join(bad)
    )


def test_ids_are_unique_and_run_down_without_gaps_from_newest_to_oldest():
    numbers = [e["number"] for e in entries()]
    assert numbers == list(range(numbers[0], numbers[0] - len(numbers), -1)), (
        f"ID non consecutivi o non decrescenti: {numbers}"
    )
    assert numbers[-1] == 1, "la voce più vecchia deve essere CL-001 (non si cancellano voci)"


def test_dates_are_valid_and_newest_first():
    dates = []
    for e in entries():
        try:
            dates.append(date.fromisoformat(e["date"]))
        except ValueError:
            raise AssertionError(f"{e['id']}: data non valida {e['date']}") from None
    assert dates == sorted(dates, reverse=True), (
        "le voci devono essere dalla più recente alla più vecchia"
    )


def test_every_entry_has_the_required_fields_filled_in():
    problems = []
    for e in entries():
        for label in REQUIRED:
            if not e["fields"].get(label, "").strip():
                problems.append(f"{e['id']}: manca «{label}»")
    assert not problems, "\n".join(problems)


def test_type_and_state_use_the_allowed_values():
    problems = []
    for e in entries():
        if e["fields"].get("Tipo") not in TYPES:
            problems.append(
                f"{e['id']}: Tipo «{e['fields'].get('Tipo')}» non ammesso ({sorted(TYPES)})"
            )
        if not e["fields"].get("Stato", "").startswith(STATES):
            problems.append(f"{e['id']}: Stato «{e['fields'].get('Stato')}» non ammesso ({STATES})")
    assert not problems, "\n".join(problems)


def test_commit_references_are_hashes_or_this_commit():
    problems = []
    for e in entries():
        commit = e["fields"].get("Commit")
        if (
            commit is not None
            and commit != "questo commit"
            and not re.fullmatch(r"[0-9a-f]{7,12}(, [0-9a-f]{7,12})*", commit)
        ):
            problems.append(f"{e['id']}: riferimento ai commit non valido: {commit!r}")
    assert not problems, "\n".join(problems)


def test_the_changelog_is_linked_and_the_rule_is_written_down():
    assert "docs/changelog.md" in (ROOT / "README.md").read_text(encoding="utf-8")
    contributing = (ROOT / "CONTRIBUTING.md").read_text(encoding="utf-8")
    assert "docs/changelog.md" in contributing and "Refs: CL-" in contributing
