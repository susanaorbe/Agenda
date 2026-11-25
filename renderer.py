from __future__ import annotations

import html
import json
import re
from datetime import date, datetime
from typing import Any

from rules import is_copa_de_la_reina_allowed, is_event_allowed_by_futbolenlatv_rules
from scrapers import get_spain_timezone


def _is_event_allowed_defensively(ev: dict[str, Any]) -> bool:
    """Filtro defensivo común en el punto de renderizado para todas las fuentes."""
    comp = str(ev.get("competicion", "") or "")
    evento = str(ev.get("evento", "") or "")
    deporte = str(ev.get("deporte", "") or "")
    url_ref = str(ev.get("fctv_url", "") or ev.get("url", "") or "")
    slug_ref = re.sub(r"[-_/+]+", " ", url_ref)
    tv_txt = " ".join(str(c) for c in (ev.get("tv_list") or []))

    combined_blob = f"{deporte} {comp} {evento} {url_ref} {slug_ref} {tv_txt}"
    if not is_copa_de_la_reina_allowed(combined_blob, evento, comp):
        return False

    dep_up = deporte.strip().upper()
    if dep_up in {"FÚTBOL", "FUTBOL", "BALONCESTO", "TENIS", "MOTOR"}:
        allowed, _, _, _, _, _, _ = is_event_allowed_by_futbolenlatv_rules(
            sport_label=deporte,
            competition_label=comp,
            event_title=evento,
            raw_lines=[evento, comp, url_ref, slug_ref],
        )
        if not allowed:
            return False

    return True


def filter_events_defensively(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [ev for ev in (events or []) if _is_event_allowed_defensively(ev)]


def generate_html(agenda_events: list[dict[str, Any]], stg_events: list[dict[str, Any]] | None = None) -> str:
    """Genera el HTML final aplicando filtro defensivo común a todas las fuentes."""
    safe_agenda = filter_events_defensively(agenda_events)
    safe_stg = filter_events_defensively(stg_events or [])

    now_spain = datetime.now(get_spain_timezone())
    generated_at = now_spain.strftime("%Y-%m-%d %H:%M:%S")

    payload = {
        "generated_at": generated_at,
        "agenda_count": len(safe_agenda),
        "stg_count": len(safe_stg),
        "agenda_events": [
            {
                "fecha": ev.get("date_obj").isoformat() if isinstance(ev.get("date_obj"), date) else str(ev.get("date_obj", "")),
                "hora": str(ev.get("hora", "")),
                "deporte": str(ev.get("deporte", "")),
                "competicion": str(ev.get("competicion", "")),
                "evento": str(ev.get("evento", "")),
                "source": str(ev.get("source", "")),
                "favorito": bool(ev.get("is_favorite", False)),
                "url": str(ev.get("fctv_url", "") or ev.get("url", "")),
                "canales": list(ev.get("tv_list") or []),
            }
            for ev in safe_agenda
        ],
        "stg_events": [
            {
                "fecha": ev.get("date_obj").isoformat() if isinstance(ev.get("date_obj"), date) else str(ev.get("date_obj", "")),
                "hora": str(ev.get("hora", "")),
                "deporte": str(ev.get("deporte", "")),
                "competicion": str(ev.get("competicion", "")),
                "evento": str(ev.get("evento", "")),
                "source": str(ev.get("source", "sport-tv-guide")),
                "favorito": bool(ev.get("is_favorite", True)),
                "url": str(ev.get("url", "") or ev.get("fctv_url", "")),
                "canales": list(ev.get("tv_list") or []),
            }
            for ev in safe_stg
        ],
    }

    rows_html = []
    for ev in [*safe_agenda, *safe_stg]:
        dt_str = ev.get("date_obj").isoformat() if isinstance(ev.get("date_obj"), date) else str(ev.get("date_obj", ""))
        hora_s = html.escape(str(ev.get("hora", "")))
        dep_s = html.escape(str(ev.get("deporte", "")))
        comp_s = html.escape(str(ev.get("competicion", "")))
        ev_s = html.escape(str(ev.get("evento", "")))
        src_s = html.escape(str(ev.get("source", "")))
        rows_html.append(
            f'<div class="ev-row" data-source="{src_s}" data-date="{html.escape(dt_str)}">'
            f'<span class="ev-time">{hora_s}</span> '
            f'<span class="ev-sport">{dep_s}</span> '
            f'<span class="ev-comp">({comp_s})</span> '
            f'<span class="ev-title">{ev_s}</span>'
            f'</div>'
        )

    safe_json = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    body_rows = "\n".join(rows_html) if rows_html else '<div class="ev-empty">Sin eventos</div>'

    return (
        "<!DOCTYPE html>\n"
        '<html lang="es">\n'
        "<head>\n"
        '  <meta charset="utf-8" />\n'
        "  <title>Agenda Deportiva</title>\n"
        "</head>\n"
        "<body>\n"
        f'  <div id="agenda-root" data-generated="{html.escape(generated_at)}">\n'
        f"    {body_rows}\n"
        "  </div>\n"
        f'  <script id="agenda-data" type="application/json">{safe_json}</script>\n'
        "</body>\n"
        "</html>\n"
    )