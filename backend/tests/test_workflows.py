"""I flussi di GitHub Actions non devono dipendere dal permesso di esecuzione degli script.

Passando da uno zip (o da certi sistemi) il permesso si perde, e Git registra il file come semplice testo: lanciarlo
direttamente dà «Permission denied» (codice 126). Lanciandolo con `bash` funziona sempre.
"""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = sorted((ROOT / ".github" / "workflows").glob("*.yml"))
SCRIPT = re.compile(r"infra/scripts/[\w-]+\.sh")


def test_there_are_workflows_to_check():
    assert len(WORKFLOWS) >= 4


def test_scripts_are_always_run_through_bash():
    direct = []
    for wf in WORKFLOWS:
        for number, line in enumerate(wf.read_text().splitlines(), 1):
            for match in SCRIPT.finditer(line):
                if not line[: match.start()].rstrip().endswith("bash") and "shellcheck" not in line:
                    direct.append(f"{wf.name}:{number}: {line.strip()}")
    assert not direct, "script lanciati direttamente (usa `bash infra/scripts/…`):\n" + "\n".join(
        direct
    )


def test_every_script_has_a_bash_shebang_and_strict_mode():
    scripts = sorted((ROOT / "infra" / "scripts").glob("*.sh"))
    assert scripts
    for script in scripts:
        text = script.read_text()
        assert text.startswith("#!/usr/bin/env bash"), script.name
        assert "set -euo pipefail" in text, script.name


def test_scripts_used_by_workflows_exist():
    used = {m.group(0) for wf in WORKFLOWS for m in SCRIPT.finditer(wf.read_text())}
    for path in used:
        assert (ROOT / path).is_file(), f"{path} è usato da un flusso ma non esiste"
