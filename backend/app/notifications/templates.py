"""Testi delle email (italiano): versione testo e versione grafica semplice.

Regole di riservatezza: le email non contengono mai costi o margini, solo il prezzo.
Ogni testo inserito da un utente (progetto, motivo, nomi) è protetto prima di entrare nell'HTML
e ripulito dagli a-capo prima di entrare nell'oggetto, così non si può iniettare codice né intestazioni.
"""

import html
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Any

TYPES = ("ce_submitted", "ce_approved", "ce_rejected", "ce_new_version", "user_enabled", "test")
ROLE_LABELS = {"admin": "Amministratore", "presale": "Presale", "viewer": "Viewer"}
FOOTER = "Portale Conti Economici · messaggio automatico, non rispondere a questa email."


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    text: str
    html: str


def oneline(value: Any) -> str:
    """Una sola riga, senza a-capo né tabulazioni (sicura per le intestazioni dell'email)."""
    return " ".join(str(value).split())


def money(value: str | None) -> str | None:
    """'47162.50' -> '47.162,50 €'"""
    if value is None:
        return None
    formatted = f"{Decimal(value):,.2f}"
    return formatted.replace(",", "§").replace(".", ",").replace("§", ".") + " €"


def fmt_date(value: str) -> str:
    return date.fromisoformat(value).strftime("%d/%m/%Y")


def _ce_facts(p: dict[str, Any]) -> list[tuple[str, str]]:
    facts = [
        ("Cliente", oneline(p["client_name"])),
        ("Progetto", oneline(p["project_name"])),
        ("Periodo", f"{fmt_date(p['start_date'])} – {fmt_date(p['end_date'])}"),
    ]
    if price := money(p.get("price")):
        facts.append(("Prezzo", price))
    return facts


def _ce_link(base_url: str, p: dict[str, Any]) -> str:
    return f"{base_url}/ce/{p['ce_id']}"


def _compose(
    name: str,
    intro: list[str],
    facts: list[tuple[str, str]],
    button: str,
    url: str,
) -> tuple[str, str]:
    text_lines = [f"Ciao {name},", ""]
    for paragraph in intro:
        text_lines += [paragraph, ""]
    text_lines += [f"{label}: {value}" for label, value in facts]
    if facts:
        text_lines.append("")
    text_lines += [f"{button}: {url}", "", "—", FOOTER]

    esc = html.escape
    rows = "".join(
        f'<tr><td style="padding:4px 16px 4px 0;color:#667085">{esc(label)}</td>'
        f'<td style="padding:4px 0;color:#101828"><strong>{esc(value)}</strong></td></tr>'
        for label, value in facts
    )
    paragraphs = "".join(f'<p style="margin:0 0 14px">{esc(p)}</p>' for p in intro)
    html_body = (
        '<!doctype html><html lang="it"><body style="margin:0;background:#f2f4f7;'
        'font-family:Arial,Helvetica,sans-serif;font-size:15px;line-height:1.5;color:#101828">'
        '<table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr><td align="center" '
        'style="padding:24px 12px"><table role="presentation" width="100%" cellpadding="0" '
        'cellspacing="0" style="max-width:560px;background:#ffffff;border-radius:8px">'
        '<tr><td style="padding:18px 28px;background:#101828;color:#ffffff;border-radius:8px 8px 0 0;'
        'font-weight:bold">Portale Conti Economici</td></tr>'
        f'<tr><td style="padding:28px"><p style="margin:0 0 14px">Ciao {esc(name)},</p>{paragraphs}'
        f'<table role="presentation" cellpadding="0" cellspacing="0" style="margin:0 0 22px">{rows}</table>'
        f'<a href="{esc(url, quote=True)}" style="display:inline-block;background:#1d4ed8;color:#ffffff;'
        f'padding:11px 20px;border-radius:6px;text-decoration:none;font-weight:bold">{esc(button)}</a>'
        f'<p style="margin:22px 0 0;font-size:12px;color:#667085">{esc(FOOTER)}</p></td></tr>'
        "</table></td></tr></table></body></html>"
    )
    return "\n".join(text_lines), html_body


def render(type_: str, payload: dict[str, Any], base_url: str) -> RenderedEmail:
    """Costruisce oggetto, testo e HTML a partire dal contenuto salvato nella coda."""
    p = payload
    name = oneline(p.get("recipient_name") or "")
    actor = oneline(p.get("actor_name") or "Un collega")

    if type_ in ("ce_submitted", "ce_approved", "ce_rejected", "ce_new_version"):
        code, version = oneline(p["code"]), p["version"]
        facts = _ce_facts(p)
        url = _ce_link(base_url, p)
        if type_ == "ce_submitted":
            subject = f"[CE] Da approvare: {code} (v{version}) – {oneline(p['client_name'])}"
            intro = [f"{actor} ha inviato in approvazione il CE {code} (versione {version})."]
            button = "Apri il CE"
        elif type_ == "ce_approved":
            subject = f"[CE] Approvato: {code} (v{version})"
            intro = [
                f"Il tuo CE {code} (versione {version}) è stato approvato da {actor}.",
                "Da ora è visibile ai viewer.",
            ]
            button = "Apri il CE"
        elif type_ == "ce_rejected":
            subject = f"[CE] Rifiutato: {code} (v{version})"
            intro = [
                f"Il tuo CE {code} (versione {version}) è stato rifiutato da {actor}.",
                "Puoi correggerlo e inviarlo di nuovo in approvazione.",
            ]
            facts.append(("Motivo", oneline(p["reason"])))
            button = "Apri il CE"
        else:
            subject = f"[CE] Nuova versione: {code} (v{version})"
            intro = [
                f"{actor} ha creato la versione {version} del CE {code}, "
                f"a partire dalla versione {version - 1} approvata.",
                "La nuova versione è in bozza: i viewer continuano a vedere l'ultima approvata.",
            ]
            button = "Apri il CE"
    elif type_ == "user_enabled":
        subject = "Accesso al portale Conti Economici"
        role = ROLE_LABELS.get(p.get("role", ""), oneline(p.get("role", "")))
        intro = [
            f"{actor} ti ha abilitato al portale Conti Economici con il ruolo {role}.",
            "Accedi con il tuo account Google aziendale.",
        ]
        facts, url, button = [], base_url, "Apri il portale"
    elif type_ == "test":
        subject = "Email di prova – Portale Conti Economici"
        intro = ["Se leggi questo messaggio, l'invio delle email dal portale funziona."]
        facts, url, button = [], base_url, "Apri il portale"
    else:
        raise ValueError(f"Tipo di email sconosciuto: {type_!r}")

    text, html_body = _compose(name, intro, facts, button, url)
    return RenderedEmail(subject=subject, text=text, html=html_body)
