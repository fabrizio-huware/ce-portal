"""La documentazione non deve contenere collegamenti rotti, comandi inesistenti o percorsi che non ci sono più."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOCS = sorted([ROOT / "README.md", ROOT / "CONTRIBUTING.md", *(ROOT / "docs").glob("*.md")])
LINK = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)\)")
# file locali o generati che le guide nominano ma che non stanno nel repository
LOCAL_ONLY = {
    "backend/.env",
    "frontend/.env.local",
    "frontend/e2e/screens",
    "frontend/dist",
    "frontend/node_modules",
}


def slug(heading: str) -> str:
    """Come GitHub trasforma un titolo in ancora: minuscolo, senza punteggiatura, spazi → trattini."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(path: Path) -> set[str]:
    out, in_code = set(), False
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("```"):
            in_code = not in_code
        m = re.match(r"#{1,6}\s+(.*)", line)
        if m and not in_code:
            out.add(slug(m.group(1)))
    return out


def test_there_is_documentation_to_check():
    assert len(DOCS) >= 12


def test_every_relative_link_and_anchor_resolves():
    broken = []
    for doc in DOCS:
        for target in LINK.findall(doc.read_text(encoding="utf-8")):
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, fragment = target.partition("#")
            dest = doc if not file_part else (doc.parent / file_part).resolve()
            if not dest.exists():
                broken.append(f"{doc.relative_to(ROOT)}: {target} (il file non esiste)")
            elif fragment and dest.suffix == ".md" and fragment not in anchors(dest):
                broken.append(f"{doc.relative_to(ROOT)}: {target} (titolo non trovato)")
    assert not broken, "collegamenti rotti:\n" + "\n".join(broken)


def test_every_doc_is_reachable_from_the_readme():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    missing = [p.name for p in (ROOT / "docs").glob("*.md") if f"docs/{p.name}" not in readme]
    assert not missing, f"pagine non collegate dal README: {missing}"


def test_every_make_command_mentioned_exists():
    targets = set(re.findall(r"^([a-z][a-z-]*):", (ROOT / "Makefile").read_text(), re.M))
    unknown = []
    for doc in DOCS:
        for command in re.findall(r"\bmake ([a-z][a-z-]*)", doc.read_text(encoding="utf-8")):
            if command not in targets:
                unknown.append(f"{doc.relative_to(ROOT)}: make {command}")
    assert not unknown, "comandi make inesistenti:\n" + "\n".join(unknown)


PATH_IN_TEXT = re.compile(
    r"(?<![\w./-])((?:infra|backend|frontend|docs|\.github)/[\w./-]*[\w])(?![\w./<*{…-])"
)


def test_every_repository_path_mentioned_exists():
    """Vale per i percorsi ovunque compaiano (anche dentro un comando più lungo); si saltano quelli con segnaposto."""
    missing = []
    for doc in DOCS:
        for path in PATH_IN_TEXT.findall(doc.read_text(encoding="utf-8")):
            if path in LOCAL_ONLY or any(path.startswith(p + "/") for p in LOCAL_ONLY):
                continue
            if not (ROOT / path).exists():
                missing.append(f"{doc.relative_to(ROOT)}: {path}")
    assert not missing, "percorsi citati che non esistono:\n" + "\n".join(sorted(set(missing)))


def test_the_guides_say_where_the_unverified_things_are():
    deploy = (ROOT / "docs" / "deploy.md").read_text(encoding="utf-8")
    assert "Ancora da verificare" in deploy and "mai eseguito su un vero progetto" not in deploy
