import re
import os
import json
import asyncio
import unicodedata
from datetime import datetime, timedelta, date
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

# --- CONFIGURACIÓN DE FILTROS Y REGLAS ---

EXCLUDED_MOTOR_TERMS = (
    "f1 academy",
    "f1 academie",
    "academy",
    "academie",
    "moto2",
    "moto 2",
    "moto3",
    "moto 3",
    "rookies",
    "supercars",
    "padel",
)

EXCLUDED_SPORTS_RE = re.compile(
    r"\b(padel|premier padel|darters|darts|snooker|billiards|esports|e-sports|chess|ajedrez|rugby|hockey|waterpolo|waterpolo|handball|balonmano|volleyball|voleibol|golf|boxing|boxeo|ufc|mma|wrestling|lucha|cycling|ciclismo|athletics|atletismo|swimming|natacion|rowing|remo|sailing|vela|horse racing|hipica|lacrosse|badminton|table tennis|tenis de mesa|futsal|futbol sala|beach soccer|futbol playa)\b",
    re.IGNORECASE,
)

EXCLUDED_COMPETITIONS_RE = re.compile(
    r"\b(concacaf|f1 academy|f1 academie|a-leagues|a leagues|liga u|german football|l1 max|popular tv murcia|hc eivissa|vinxtv|etb1|valencia cf youtube|valencia cf app|a punt|afc champions league|serie a|laliga hypermotion|espana - tercera|espana tercera|liga futve|premier padel|sub-?\d+|u-?\d+|juvenil|cadete|infantil|alevin|benjamin|youth|femenino sub|women u\d+)\b",
    re.IGNORECASE,
)

BASKET_ALLOWED_COMPETITIONS_RE = re.compile(
    r"\b(nba|euroliga|euroleague|liga endesa|acb)\b",
    re.IGNORECASE,
)

YOUTH_BASKET_RE = re.compile(
    r"\b(sub-?\d+|u-?\d+|juvenil|cadete|infantil|alevin|benjamin|youth|liga u)\b",
    re.IGNORECASE,
)

TENNIS_EVENT_RE = re.compile(
    r"\b(atp|wta|grand slam|open de australia|australian open|roland garros|wimbledon|us open|masters 1000|copa davis|davis cup|billie jean king|alcaraz|badosa|bucsa|davidovich|jodar|merida|dani merida)\b",
    re.IGNORECASE,
)

SPANISH_TENNIS_FAVORITES_RE = re.compile(
    r"\b(carlos alcaraz|alcaraz|paula badosa|badosa|cristina bucsa|bucsa|alejandro davidovich|davidovich|rafa jodar|jodar|dani merida|merida)\b",
    re.IGNORECASE,
)

EXCLUDED_TENNIS_PLAYERS_RE = re.compile(
    r"\b(jessica bouzas|bouzas|roberto bautista|bautista agut|pedro martinez|carballes|carballes baena)\b",
    re.IGNORECASE,
)

EVENT_CLEANUP_TRAIL_RE = re.compile(r"[\s\-–—:|/]+$")
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]{2,}")

_EVENT_STOPWORDS = {
    "vs", "v", "fc", "cf", "bc", "club", "cd", "ud", "sd", "rcd", "rc",
    "atletico", "atletic", "real", "deportivo", "sporting", "union",
    "the", "de", "del", "la", "el", "los", "las", "en", "y", "e", "a",
    "carrera", "race", "qualifying", "clasificacion", "sprint", "round", "ronda",
}


def normalize_search_text(text: str) -> str:
    if not text:
        return ""
    s = unicodedata.normalize("NFD", str(text).lower())
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_competition_label(comp: str) -> str:
    if not comp:
        return ""
    s = re.sub(r"\s+", " ", str(comp)).strip()
    low = normalize_search_text(s)
    if "laliga ea sports" in low or low == "laliga":
        return "LaLiga EA Sports"
    if "laliga hypermotion" in low or "segunda division" in low:
        return "LaLiga Hypermotion"
    if "champions league" in low or "liga de campeones" in low:
        return "UEFA Champions League"
    if "europa league" in low or "liga europa" in low:
        return "UEFA Europa League"
    if "conference league" in low:
        return "UEFA Conference League"
    if "liga endesa" in low or "acb" in low:
        return "Liga Endesa"
    if "euroliga" in low or "euroleague" in low:
        return "Euroliga"
    if "nba" in low:
        return "NBA"
    return s


def is_excluded_motor_event(competicion: str, evento: str, extra: str = "") -> bool:
    blob = normalize_search_text(f"{competicion} {evento} {extra}")
    return any(term in blob for term in EXCLUDED_MOTOR_TERMS)


def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)
    full_extra = " ".join(text_lines or [])
    if is_excluded_motor_event(raw_tournament, blob_lower, full_extra):
        return ("", "", False)
    if any(junk in blob_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje", "practica", "libre"]):
        return ("", "", False)

    is_f1 = bool(re.search(r"\b(f1|formula 1|formula uno)\b", blob_lower))
    is_motogp = bool(re.search(r"\b(motogp|moto gp)\b", blob_lower))
    is_indycar = bool(re.search(r"\bindycar|indy 500\b", blob_lower))
    is_formula_e = bool(re.search(r"\b(formula e|formula-e)\b", blob_lower))

    if not (is_f1 or is_motogp or is_indycar or is_formula_e):
        return ("", "", False)

    is_sprint = "sprint" in blob_lower
    is_quali = bool(re.search(r"\b(clasificacion|qualifying|quali|pole)\b", blob_lower))
    is_race = bool(re.search(r"\b(carrera|race|gran premio|gp)\b", blob_lower)) and not is_quali

    is_fav = False
    if is_f1 and (is_sprint or is_quali or is_race):
        is_fav = True
    elif is_motogp and (is_sprint or is_race):
        is_fav = True
    elif (is_indycar or is_formula_e) and is_race:
        is_fav = True

    comp_label = raw_tournament.strip() or ("Fórmula 1" if is_f1 else "MotoGP" if is_motogp else "IndyCar" if is_indycar else "Fórmula E")
    title = " ".join(line.strip() for line in (text_lines or []) if line.strip()) or comp_label
    return (comp_label, title, is_fav)


def get_sport_and_competition(
    blob: str,
    raw_tournament: str,
    channels_lower: str,
    text_lines: list[str],
) -> tuple[str, str, str, bool, bool, str, str]:
    norm_blob = normalize_search_text(blob)
    norm_comp = normalize_search_text(raw_tournament)
    joined_lines = " ".join(text_lines or [])
    norm_lines = normalize_search_text(joined_lines)

    if EXCLUDED_SPORTS_RE.search(f" {norm_blob} "):
        return ("", "", "", False, False, "", "")

    if EXCLUDED_COMPETITIONS_RE.search(f" {norm_comp} ") or EXCLUDED_COMPETITIONS_RE.search(f" {norm_lines} "):
        return ("", "", "", False, False, "", "")

    if is_excluded_motor_event(raw_tournament, norm_lines, norm_blob):
        return ("", "", "", False, False, "", "")

    # Detección de Baloncesto
    is_basket = bool(
        re.search(r"\b(baloncesto|basket|basketball|nba|euroliga|euroleague|liga endesa|acb)\b", f" {norm_blob} ")
    )
    if is_basket:
        if YOUTH_BASKET_RE.search(f" {norm_blob} "):
            return ("", "", "", False, False, "", "")
        if not BASKET_ALLOWED_COMPETITIONS_RE.search(f" {norm_comp} ") and not BASKET_ALLOWED_COMPETITIONS_RE.search(f" {norm_blob} "):
            return ("", "", "", False, False, "", "")
        comp_clean = normalize_competition_label(raw_tournament or "Baloncesto")
        is_fav = bool(re.search(r"\breal madrid\b", norm_blob)) and not YOUTH_BASKET_RE.search(f" {norm_blob} ")
        return ("BALONCESTO", "🏀", comp_clean, is_fav, True, "", "basket")

    # Detección de Tenis
    is_tennis = bool(re.search(r"\b(tenis|tennis)\b", f" {norm_blob} ") or TENNIS_EVENT_RE.search(f" {norm_blob} "))
    if is_tennis:
        if EXCLUDED_TENNIS_PLAYERS_RE.search(f" {norm_blob} "):
            return ("", "", "", False, False, "", "")
        comp_clean = normalize_competition_label(raw_tournament or "Tenis")
        is_fav = bool(SPANISH_TENNIS_FAVORITES_RE.search(f" {norm_blob} "))
        return ("TENIS", "🎾", comp_clean, is_fav, True, "", "tennis")

    # Detección de Fútbol (por defecto si pasa filtros de deporte/competición)
    comp_clean = normalize_competition_label(raw_tournament or "Fútbol")
    is_fav = bool(
        re.search(
            r"\b(real madrid|real madrid femenino|real madrid castilla|seleccion espanola|espana|spain)\b",
            f" {norm_blob} ",
        )
    )
    return ("FÚTBOL", "⚽", comp_clean, is_fav, True, "", "football")


# --- COINCIDENCIA Y VALIDACIÓN DE FUENTES EXTERNAS (FCTV33 Y SPORT TV GUIDE) ---

def _extract_event_tokens(evento_text: str) -> set[str]:
    norm = normalize_search_text(evento_text)
    norm = re.sub(r"\bvs\.?\b|\bv\.?\b", " ", norm)
    tokens: set[str] = set()
    for raw_tok in re.findall(r"[a-z0-9]+", norm):
        if len(raw_tok) >= 2 and raw_tok not in _EVENT_STOPWORDS:
            tokens.add(raw_tok)
    return tokens


def _events_match(ext_event: str, fl_event: str) -> bool:
    s_norm = normalize_search_text(ext_event)
    f_norm = normalize_search_text(fl_event)
    if not s_norm or not f_norm:
        return False
    if s_norm == f_norm or s_norm in f_norm or f_norm in s_norm:
        return True

    s_tokens = _extract_event_tokens(ext_event)
    f_tokens = _extract_event_tokens(fl_event)
    if not s_tokens or not f_tokens:
        return False

    common = s_tokens & f_tokens
    if not common:
        return False

    min_len = min(len(s_tokens), len(f_tokens))
    if min_len == 1:
        return len(common) >= 1
    return len(common) >= min(2, min_len)


def _build_futbolenlatv_candidates(futbolenlatv_events: list[dict]) -> dict[tuple[date, str, str], list[str]]:
    candidates: dict[tuple[date, str, str], list[str]] = {}
    for ev in (futbolenlatv_events or []):
        if ev.get("source") != "futbolenlatv":
            continue
        ev_d = ev["date_obj"]
        sport_norm = normalize_search_text(ev.get("deporte", ""))
        comp_norm = normalize_search_text(normalize_competition_label(ev.get("competicion", "")))
        ev_str = str(ev.get("evento", "")).strip()
        if not sport_norm or not comp_norm or not ev_str:
            continue
        candidates.setdefault((ev_d, sport_norm, comp_norm), []).append(ev_str)
    return candidates


def _evaluate_external_event_against_rules(
    sport_up: str,
    comp_raw: str,
    evento_raw: str,
    channel_names: list[str] | None = None,
) -> tuple[bool, dict]:
    sport_norm_up = str(sport_up or "").upper().strip()
    comp_str = str(comp_raw or "").strip()
    ev_str = str(evento_raw or "").strip()
    ch_names = [str(c or "").strip() for c in (channel_names or []) if str(c or "").strip()]

    blob = normalize_search_text(f"{sport_norm_up} {comp_str} {ev_str} {' '.join(ch_names)}")
    text_lines = [line for line in (comp_str, ev_str) if line]

    if sport_norm_up == "MOTOR":
        comp_name, motor_title, is_fav = parse_motor_event(blob, comp_str, text_lines or [ev_str])
        if not comp_name:
            return False, {}
        return True, {
            "deporte": "MOTOR",
            "icono": "🏆",
            "competicion": normalize_competition_label(comp_name),
            "evento": motor_title.upper(),
            "is_filtered": is_fav,
            "is_configured": True,
            "comp_key": "motor",
        }

    sport, icon, competition, is_favorite, is_configured, custom_event, comp_key = get_sport_and_competition(
        blob, comp_str, " ".join(ch_names).lower(), text_lines or [ev_str]
    )
    if not sport:
        return False, {}

    sport_expected = sport.upper()
    if sport_norm_up and sport_norm_up != sport_expected:
        return False, {}

    comp_label = normalize_competition_label(competition or comp_str)
    final_event = (custom_event or ev_str).upper()

    if comp_label:
        final_event = re.sub(re.escape(comp_label), "", final_event, flags=re.IGNORECASE)
    final_event = re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", final_event).strip()
    final_event = EVENT_CLEANUP_TRAIL_RE.sub("", final_event).strip()

    if not EVENT_TEXT_RE.search(final_event):
        return False, {}

    comp_norm = normalize_search_text(comp_label)
    if sport_expected == "BALONCESTO":
        if (
            not BASKET_ALLOWED_COMPETITIONS_RE.search(f" {comp_norm} ")
            or YOUTH_BASKET_RE.search(f" {normalize_search_text(final_event)} ")
        ):
            return False, {}
    elif sport_expected == "TENIS":
        if not TENNIS_EVENT_RE.search(f" {blob} "):
            return False, {}

    return True, {
        "deporte": sport_expected,
        "icono": icon,
        "competicion": comp_label,
        "evento": final_event,
        "is_filtered": is_favorite,
        "is_configured": is_configured,
        "comp_key": comp_key,
    }


def _filter_external_source_event(
    ev_d: date,
    sport_up: str,
    comp_raw: str,
    evento_raw: str,
    channel_names: list[str] | None,
    futbolenlatv_candidates: dict[tuple[date, str, str], list[str]],
) -> tuple[bool, dict]:
    allowed, normalized_meta = _evaluate_external_event_against_rules(
        sport_up,
        comp_raw,
        evento_raw,
        channel_names,
    )
    if not allowed:
        return False, {}

    sport_norm = normalize_search_text(normalized_meta["deporte"])
    comp_norm = normalize_search_text(normalized_meta["competicion"])
    candidate_events = futbolenlatv_candidates.get((ev_d, sport_norm, comp_norm), [])

    matched_in_futbolenlatv = any(
        _events_match(normalized_meta["evento"], fl_ev) or _events_match(str(evento_raw or ""), fl_ev)
        for fl_ev in candidate_events
    )
    if not matched_in_futbolenlatv:
        return False, {}

    return True, normalized_meta


def generate_html(futbolenlatv_events: list[dict], sport_tv_guide_events: list[dict] | None = None) -> str:
    today_date = datetime.now().date()
    futbolenlatv_candidates = _build_futbolenlatv_candidates(futbolenlatv_events)
    unified_events: list[dict] = []

    # 1. Eventos de futbolenlatv.es y validación estricta de FCTV33 contra futbolenlatv.es
    for ev in (futbolenlatv_events or []):
        if ev.get("source") == "fctv33":
            ev_d = ev["date_obj"]
            allowed, normalized_meta = _filter_external_source_event(
                ev_d=ev_d,
                sport_up=ev.get("deporte", ""),
                comp_raw=ev.get("competicion", ""),
                evento_raw=ev.get("evento", ""),
                channel_names=ev.get("tv_list") or [],
                futbolenlatv_candidates=futbolenlatv_candidates,
            )
            if not allowed:
                continue

            ev_filtered = dict(ev)
            ev_filtered.update(normalized_meta)
            unified_events.append(ev_filtered)
        else:
            unified_events.append(ev)

    # 2. Validación estricta de Sport TV Guide contra futbolenlatv.es y filtros varios
    for stg in (sport_tv_guide_events or []):
        try:
            ev_d = date.fromisoformat(str(stg.get("date_iso", "")))
        except ValueError:
            ev_d = today_date

        stg_channels = [str(c.get("name", "")) for c in (stg.get("canales") or []) if c.get("name")]
        allowed, normalized_meta = _filter_external_source_event(
            ev_d=ev_d,
            sport_up=stg.get("deporte", ""),
            comp_raw=stg.get("competicion", ""),
            evento_raw=stg.get("evento", ""),
            channel_names=stg_channels,
            futbolenlatv_candidates=futbolenlatv_candidates,
        )
        if not allowed:
            continue

        unified_events.append({
            "date_obj": ev_d,
            "hora": str(stg.get("hora", "")),
            "deporte": normalized_meta["deporte"],
            "icono": normalized_meta["icono"],
            "competicion": normalized_meta["competicion"],
            "evento": normalized_meta["evento"],
            "tv_list": stg_channels,
            "stg_channels": stg.get("canales") or [],
            "fctv_url": "",
            "is_filtered": normalized_meta["is_filtered"],
            "is_configured": normalized_meta["is_configured"],
            "comp_key": normalized_meta["comp_key"],
            "source": "cdnlive",
        })

    events_payload = []
    for item in unified_events:
        d_obj = item.get("date_obj", today_date)
        events_payload.append({
            "date_iso": d_obj.isoformat() if isinstance(d_obj, date) else str(d_obj),
            "hora": str(item.get("hora", "")),
            "deporte": str(item.get("deporte", "")),
            "icono": str(item.get("icono", "")),
            "competicion": str(item.get("competicion", "")),
            "evento": str(item.get("evento", "")),
            "tv_list": item.get("tv_list") or [],
            "stg_channels": item.get("stg_channels") or [],
            "fctv_url": str(item.get("fctv_url", "")),
            "is_filtered": bool(item.get("is_filtered", False)),
            "is_configured": bool(item.get("is_configured", False)),
            "comp_key": str(item.get("comp_key", "")),
            "source": str(item.get("source", "futbolenlatv")),
        })

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>Agenda Deportiva</title>
<script>
const AGENDA_EVENTS = {json.dumps(events_payload, ensure_ascii=False)};
</script>
</head>
<body>
<div id="app">Agenda Deportiva actualizada</div>
</body>
</html>
"""


if __name__ == "__main__":
    sample_fl = [
        {
            "date_obj": date.today(),
            "hora": "21:00",
            "deporte": "FÚTBOL",
            "icono": "⚽",
            "competicion": "LaLiga EA Sports",
            "evento": "REAL MADRID VS BARCELONA",
            "tv_list": ["DAZN"],
            "is_filtered": True,
            "is_configured": True,
            "comp_key": "football",
            "source": "futbolenlatv",
        },
        {
            "date_obj": date.today(),
            "hora": "21:00",
            "deporte": "FÚTBOL",
            "icono": "⚽",
            "competicion": "LaLiga EA Sports",
            "evento": "Real Madrid - Barcelona",
            "tv_list": ["Canal 1"],
            "is_filtered": True,
            "is_configured": True,
            "comp_key": "football",
            "source": "fctv33",
        },
        {
            "date_obj": date.today(),
            "hora": "21:00",
            "deporte": "FÚTBOL",
            "icono": "⚽",
            "competicion": "Serie A",
            "evento": "Inter vs Milan",
            "tv_list": ["Canal 2"],
            "is_filtered": False,
            "is_configured": False,
            "comp_key": "football",
            "source": "fctv33",
        },
    ]
    sample_stg = [
        {
            "date_iso": date.today().isoformat(),
            "hora": "21:00",
            "deporte": "FÚTBOL",
            "competicion": "LaLiga EA Sports",
            "evento": "Real Madrid vs Barcelona",
            "canales": [{"name": "Canal STG"}],
        },
        {
            "date_iso": date.today().isoformat(),
            "hora": "00:00",
            "deporte": "MOTOR",
            "competicion": "F1 Académie",
            "evento": "Las Vegas",
            "canales": [{"name": "RDS CA"}],
        },
    ]
    html = generate_html(sample_fl, sample_stg)
    assert "REAL MADRID VS BARCELONA" in html
    assert "Serie A" not in html
    assert "ACAD" not in html
    print("Archivo generate_agenda.py generado y validado correctamente.")
