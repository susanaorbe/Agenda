from collections import Counter
from datetime import date, datetime
from html import escape
import json
import os

from config import (
    contains_previo_or_previa,
    get_spain_timezone,
    get_time_slot,
    normalize_search_text,
)
from rules import (
    event_similarity_key,
    is_event_allowed_by_futbolenlatv_rules,
    normalize_competition_label,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE_PATH = os.path.join(BASE_DIR, "templates", "agenda.html")
CSS_PATH = os.path.join(BASE_DIR, "static", "agenda.css")
JS_PATH = os.path.join(BASE_DIR, "static", "agenda.js")


def _read_text_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def generate_html(futbolenlatv_events, sport_tv_guide_events=None):
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")

    unified_events = []
    for ev in (futbolenlatv_events or []):
        if contains_previo_or_previa(ev.get("competicion", ""), ev.get("evento", "")):
            continue
        ev_copy = dict(ev)
        src = str(ev_copy.get("source") or "futbolenlatv").strip().lower()
        if src not in {"futbolenlatv", "fctv33"}:
            src = "futbolenlatv"
        ev_copy["source"] = src
        if src != "futbolenlatv":
            ev_copy["is_filtered"] = False
        unified_events.append(ev_copy)

    for stg in (sport_tv_guide_events or []):
        if contains_previo_or_previa(stg.get("competicion", ""), stg.get("evento", "")):
            continue
        try:
            ev_d = date.fromisoformat(str(stg.get("date_iso", "")))
        except ValueError:
            ev_d = today_date

        allowed, is_fav, final_sport, final_icon, final_comp, final_event, comp_key = is_event_allowed_by_futbolenlatv_rules(
            sport_label=stg.get("deporte", ""),
            competition_label=stg.get("competicion", ""),
            event_title=stg.get("evento", ""),
            raw_lines=[stg.get("evento", ""), stg.get("competicion", "")],
        )
        if not allowed:
            continue

        unified_events.append({
            "date_obj": ev_d,
            "hora": str(stg.get("hora", "")),
            "deporte": final_sport,
            "icono": final_icon,
            "competicion": final_comp,
            "evento": final_event,
            "tv_list": [str(c.get("name", "")) for c in (stg.get("canales") or []) if c.get("name")],
            "stg_channels": stg.get("canales") or [],
            "fctv_url": "",
            "is_filtered": False,
            "is_configured": True,
            "comp_key": comp_key,
            "source": "cdnlive",
        })

    unified_events.sort(key=event_similarity_key)
    futbolenlatv_events = unified_events

    slot_counts = Counter(
        get_time_slot(event["hora"])
        for event in futbolenlatv_events
        if event["date_obj"] == today_date
    )
    total_cnt = sum(1 for event in futbolenlatv_events if event["date_obj"] > today_date)

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not futbolenlatv_events:
        rows_list.append(
            '<div class="empty-state">😴 No hay eventos disponibles en este momento.</div>'
        )
    else:
        for ev in futbolenlatv_events:
            tv_badges_list = []
            if ev.get("source") == "cdnlive":
                for ch_obj in ev.get("stg_channels", []):
                    raw_ch_name = str(ch_obj.get("name", "")).strip()
                    raw_ch_country = str(ch_obj.get("country", "")).strip()
                    if not raw_ch_name:
                        continue
                    safe_ch_name = escape(raw_ch_name, quote=True)
                    safe_ch_country = escape(raw_ch_country, quote=True)
                    tv_badges_list.append(
                        f'<a href="#reproductor" class="channel-action stg-cdn-channel" data-ch-name="{safe_ch_name}" data-ch-country="{safe_ch_country}">▶ {safe_ch_name}</a>'
                    )
            else:
                for channel in ev["tv_list"]:
                    safe_channel = escape(str(channel), quote=True)
                    tv_badges_list.append(
                        f'<span class="tv-badge" title="Canal {safe_channel}">{safe_channel}</span>'
                    )

            if ev.get("fctv_url"):
                fctv_safe_url = escape(ev["fctv_url"], quote=True)
                tv_badges_list.append(
                    f'<a href="{fctv_safe_url}" target="_blank" class="channel-action" title="Ver en FCTV33">▶ FCTV33</a>'
                )

            tv_badges = "".join(tv_badges_list)

            ev_date = ev["date_obj"]
            if ev_date == today_date:
                date_badge_html = '<span class="date-badge today">Hoy</span>'
            else:
                date_badge_html = f'<span class="date-badge">{ev_date.strftime("%d/%m")}</span>'

            slot = get_time_slot(ev["hora"])
            safe_slot = escape(clean_key(slot), quote=True)

            search_text = normalize_search_text(
                " ".join(
                    [str(ev_date), ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
                )
            )
            safe_search = escape(search_text, quote=True)

            if ev["hora"] == "LIVE":
                safe_time = '<span class="time-badge" style="background:#10b981;">LIVE</span>'
                event_timestamp = int(datetime.now(spain_tz).timestamp() * 1000)
            else:
                try:
                    time_obj = datetime.strptime(ev["hora"], "%H:%M").time()
                except ValueError:
                    time_obj = datetime.strptime("00:00", "%H:%M").time()
                event_datetime = datetime.combine(ev_date, time_obj).replace(tzinfo=spain_tz)
                event_timestamp = int(event_datetime.timestamp() * 1000)
                safe_time = f'<span class="time-badge">{escape(str(ev["hora"]))}</span>'

            safe_timestamp = str(event_timestamp)
            safe_date_str = escape(ev_date.isoformat(), quote=True)
            safe_sport_key = escape(clean_key(ev["deporte"]), quote=True)
            safe_source = escape(clean_key(ev.get("source", "futbolenlatv")), quote=True)
            safe_comp_key = escape(str(ev.get("comp_key", "")), quote=True)
            safe_icon = escape(str(ev["icono"]))
            safe_sport = escape(str(ev["deporte"]))
            safe_competition = escape(normalize_competition_label(str(ev["competicion"])))
            safe_event = escape(str(ev["evento"]))

            is_fav_ev = bool(ev["is_filtered"]) and (ev.get("source") == "futbolenlatv")
            is_filtered_str = str(is_fav_ev).lower()
            is_configured_str = str(ev["is_configured"]).lower()

            favorite_pin_html = (
                '<span class="favorite-pin" title="Favorito" aria-label="Favorito">📌</span>'
                if is_fav_ev else ""
            )
            comp_html = (
                f'<span class="comp-meta">({favorite_pin_html}{safe_competition})</span>'
                if safe_competition else ""
            )

            rows_list.append(
                f'<div class="stg-event-card" data-date="{safe_date_str}" data-ts="{safe_timestamp}" data-time="{escape(str(ev["hora"]))}" data-slot="{safe_slot}" data-sport="{safe_sport_key}" data-source="{safe_source}" data-comp-key="{safe_comp_key}" data-filtered="{is_filtered_str}" data-configured="{is_configured_str}" data-search="{safe_search}">'
                f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">'
                f'{date_badge_html}'
                f'{safe_time}'
                f'<span class="sport-tag">{safe_icon} {safe_sport}</span>'
                f'{comp_html}'
                f'<strong class="stg-event-title" style="color: #fff; font-size: 0.9rem;">{safe_event}</strong>'
                f'</div>'
                f'<div class="stg-channels-row">{tv_badges}</div>'
                f'</div>'
            )

    futbolenlatv_rows_html = "".join(rows_list)
    filtered_stg_events = [
        stg for stg in (sport_tv_guide_events or [])
        if not contains_previo_or_previa(stg.get("competicion", ""), stg.get("evento", ""))
    ]
    safe_stg_json = json.dumps(filtered_stg_events, ensure_ascii=False).replace("</", "<\\/")

    embedded_channels = []
    try:
        if os.path.exists("channels.json"):
            with open("channels.json", "r", encoding="utf-8") as f:
                raw_ch = json.load(f)
            if isinstance(raw_ch, list):
                embedded_channels = raw_ch
            elif isinstance(raw_ch, dict):
                embedded_channels = (
                    raw_ch.get("channels")
                    or raw_ch.get("data", {}).get("channels")
                    or raw_ch.get("data")
                    or []
                )
    except Exception:
        embedded_channels = []

    safe_channels_json = json.dumps(embedded_channels, ensure_ascii=False).replace("</", "<\\/")

    html_template = _read_text_file(TEMPLATE_PATH)
    agenda_css = _read_text_file(CSS_PATH)
    agenda_js = _read_text_file(JS_PATH)

    html = html_template.replace("{AGENDA_CSS}", agenda_css)
    html = html.replace("{AGENDA_JS}", agenda_js)
    html = html.replace("{FECHA_ACT}", fecha_act)
    html = html.replace("{MADRUGADA_CNT}", str(slot_counts["madrugada"]))
    html = html.replace("{MANANA_CNT}", str(slot_counts["manana"]))
    html = html.replace("{TARDE_CNT}", str(slot_counts["tarde"]))
    html = html.replace("{NOCHE_CNT}", str(slot_counts["noche"]))
    html = html.replace("{TOTAL_CNT}", str(total_cnt))
    html = html.replace("{TODAY_DATE_STR}", today_date.isoformat())
    html = html.replace("{FUTBOLENLATV_ROWS_HTML}", futbolenlatv_rows_html)
    html = html.replace("{SPORT_TV_GUIDE_EVENTS_JSON}", safe_stg_json)
    html = html.replace("{EMBEDDED_CHANNELS_JSON}", safe_channels_json)
    return html