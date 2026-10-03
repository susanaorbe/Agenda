from collections import Counter
from datetime import datetime
import re
from typing import Iterable

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURACIÓN
# ============================================================================

WIDGET_URL = (
    "https://widgets.futbolenlatv.com/partidos/agenda"
    "?color=005df8&culture=es-ES"
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15

EXCLUDED_CHANNELS = {
    "* sin tv en directo *",
    "aragón play",
    "aragón tv",
    "asobal tv",
    "atp tennis tv",
    "dazn 1 bar(m148)",
    "dazn 2 bar(m149)",
    "fanplay",
    "fanseat",
    "fff tv youtube",
    "fiba youtube",
    "hbo max",
    "laliga tv bar",
    "laliga tv m2",
    "laliga tv m3",
    "laliga tv m4",
    "laliga tv m5",
    "laliga+ plus",
    "m+ #vamos bar 2(308)",
    "m+ #vamos bar(307)",
    "m+ laliga hdr(m440 o111)",
    "motogp videopass",
    "movistar+ lite",
    "nba league pass",
    "onefootball",
    "orange fútbol 1(107)",
    "orange fútbol 2(108)",
    "rcdeportivo tv youtube",
    "rcd deportivo tv youtube",
    "red bull tv",
    "rtve play",
    "sefutbol youtube",
    "siroko tv",
    "tv footballclub(acceder)",
    "tv canaria",
    "tv3(cataluña)",
    "tvg(galicia)",
    "uefa tv",
    "uefa youtube",
    "wta tv",
}


# ============================================================================
# REGEX
# ============================================================================

def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r"\breal madrid\b", r"\brm castilla\b", r"\br\.?\s*madrid\b")
CASTILLA_RE = rx(r"\breal madrid castilla\b", r"\brm castilla\b", r"\bcastilla\b")

SPANISH_BIG_THREE_RE = rx(
    r"\breal madrid\b", r"\brm castilla\b", r"\bbarcelona\b",
    r"\bbarça\b", r"\batletico de madrid\b", r"\batlético de madrid\b"
)

TOP3_FOREIGN_RE = rx(
    r"\bmanchester city\b", r"\barsenal\b", r"\bliverpool\b", r"\binter de milán\b",
    r"\binter milan\b", r"\bnapoles\b", r"\bjuventus\b", r"\bbayern de múnich\b",
    r"\bbayern munich\b", r"\bbayern\b", r"\bborussia dortmund\b", r"\bdortmund\b",
    r"\brb leipzig\b", r"\bleipzig\b", r"\bparis saint-germain\b", r"\bpsg\b",
    r"\bolympique de marsella\b", r"\bmarsella\b", r"\brc lens\b", r"\blens\b",
    r"\bsporting cp\b", r"\bsporting de portugal\b", r"\bbenfica\b", r"\bporto\b"
)

TENNIS_FAVORITES_RE = rx(
    r"\bsinner\b", r"\bzverev\b", r"\balcaraz\b",
    r"\bsabalenka\b", r"\bswiatek\b", r"\bgauff\b", r"\brybakina\b", r"\bpegula\b",
    r"\bnadal\b", r"\bmunar\b", r"\bjódar\b", r"\bdavidovich\b", r"\bmérida\b",
    r"\blandaluce\b", r"\bcarreño\b", r"\bbucsa\b", r"\bbouzas\b", r"\bbadosa\b",
    r"\bquevedo\b", r"\bselekhmeteva\b", r"\bramos\b", r"\btabener\b", r"\bmachado\b",
    r"\bmasarova\b", r"\bparrizas\b", r"\bosorio\b"
)

TENNIS_RE = rx(
    r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bwimbledon\b", r"\broland garros\b",
    r"\bus open\b", r"\bopen de australia\b", r"\bmasters\b", r"\bdavis\b",
    r"\bcopa davis\b", r"\bbillie jean king cup\b", r"\blaver cup\b",
    r"\bpek[í]n\b", r"\bbeijing\b", r"\bchina open\b", r"\btorneo de pek[í]n\b",
    r"\bhangzhou\b", r"\bchengd[uú]\b", r"\btokio\b", r"\btokyo\b", r"\bjapan open\b",
    r"\btennis\s+channel\b", r"\btennis\s+tv\b"
)

WTA_RE = re.compile(r"\bwta\b", re.IGNORECASE)
ATP_RE = re.compile(r"\batp\b", re.IGNORECASE)
WOMEN_RE = rx(r"\bfemenina\b", r"\bfemenino\b", r"\bfrauen\b", r"\bwomen\b")

F1_RE = re.compile(r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b", re.IGNORECASE)
F2_RE = re.compile(r"\bf2\b", re.IGNORECASE)
F3_RE = re.compile(r"\bf3\b")
MOTO2_RE = re.compile(r"\bmoto2\b", re.IGNORECASE)
MOTO3_RE = re.compile(r"\bmoto3\b", re.IGNORECASE)

MOTOR_SERIES_RE = rx(
    r"\bfórmula 1\b", r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b",
    r"\bmotogp\b(?![\s\-]*(?:2|3|moto2|moto3|rookies))\b",
    r"\bformula e\b", r"\bfórmula e\b", r"\bindycar\b", r"\bindy car\b"
)

MOTOR_GENERAL_RE = rx(
    r"\bfórmula 1\b", r"\bf1(?![\s\-]*(?:academy))\b", r"\bfórmula 2\b", r"\bfórmula 3\b",
    r"\bf2\b", r"\bf3\b", r"\bmotogp\b", r"\bformula e\b", r"\bfórmula e\b", r"\bindycar\b",
    r"\bindy car\b", r"\bmoto2\b", r"\bmoto3\b", r"\bnascar\b", r"\brally\b", r"\bautomovilismo\b", r"\bmotor\b"
)

MOTO_STRICT_EXCLUDE_RE = rx(
    r"\bmoto2\b", r"\bmoto3\b", r"rookies\s+cup", r"\brookies\b", r"\bnascar\b",
    r"\bfórmula 2\b", r"\bfórmula 3\b", r"\bf2\b", r"\bf3\b"
)

BASKET_RE = rx(
    r"\bacb\b", r"\beuroliga\b", r"\beuroleague\b", r"\bbaloncesto\b", r"\bbasket\b",
    r"\bnba\b", r"\bliga endesa\b", r"\bcopa del rey\b", r"\bsupercopa\b", r"\bfiba\b"
)

HOCKEY_RE = rx(r"\bfih\b", r"\bhockey\b", r"\bhokey\b")
FUTSAL_RE = rx(r"\bf[uú]tbol sala\b", r"\bliga prime\b", r"\bfutsal\b")
RUGBY_RE = rx(r"\brugby\b", r"\bdivisi[oó]n\s+de\s+honor\b")
HANDBALL_RE = rx(r"\bbalonmano\b", r"\basobal\b", r"\bliga asobal\b", r"\bhandball\b")
CYCLING_RE = rx(r"\bciclismo\b")
GOLF_RE = rx(r"\bgolf\b")

FOOTBALL_RE = rx(
    r"\bf[uú]tbol\b", r"\bchampions\b", r"\bliga\b", r"\bcopa\b", r"\buefa\b", r"\bfifa\b",
    r"\bpremier\b", r"\bserie a\b", r"\bbundesliga\b", r"\bcalcio\b", r"\bmls\b", r"\bsupercopa\b"
)

PRIMERA_RFEF_RE = rx(
    r"\bprimera federaci[oó]n\b",
    r"\bprimera rfef\b",
    r"\b1[ªa]\s*federaci[oó]n\b",
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
CLEAN_TV_RE = re.compile(r"\(ver en directo\)|ver partido", re.IGNORECASE)
SPACES_RE = re.compile(r"\s+")


def normalize_search_text(text: str) -> str:
    value = (text or "").lower()
    value = value.replace("º", "ª")
    value = re.sub(r"[|,;:/]+", " ", value)
    return SPACES_RE.sub(" ", value).strip()


TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis\s+channel\b", r"\borange\s+tv\b", r"\bchannel\s*[-–—]\s*orange\s+tv\b"
)

EXCLUDED_SPORTS_RE = rx(
    r"\btorneo\s+betplay\s+dimayor\b",
    r"\bbetplay\s+dimayor\b",
    r"\bmls\b",
    r"\bnfl\b",
    r"\bwnba\b",
    r"\bprimera\s+feb\b",
    r"\bliga\s*u\b"
)

EXCLUDED_BLOB_RE = rx(
    r"preol[ií]mpico\s+femenino",
    r"nfl\s+pretemporada",
    r"f1\s+academy",
    r"segunda\s+federaci[oó]n",
    r"segunda\s+rfef",
    r"tercera\s+federaci[oó]n",
    r"liga\s+nacional\s+juvenil",
    r"fifa\s+asean\s+cup",
    r"laliga\s+futures",
    r"academy\b",
    r"\breplay\b",
    r"\bprimera\s+feb\b",
    r"\bliga\s*u\b",
    r"\bncaa\b",
    r"\bnational\s+league\b",
    r"\bprimera\s+catalana\b",
    r"\bu20\s+elite\s+league\b",
    r"segunda\s+uruguay",
    r"\bwrc\b",
    r"primera\s+divisi[oó]n\s+argentina",
    r"liga\s+auf\s+uruguaya",
    r"\bvelada\b",
    r"rotterdam\s+open",
    r"giro\s+dell['\s]*emilia",
    r"\btop\s+14\b"
)

FOOTBALL_COMPETITIONS = (
    (rx(r"\bchampions league\b", r"\bchampions\b"), "UEFA Champions League"),
    (rx(r"\beuropa league\b"), "UEFA Europa League"),
    (rx(r"\bconference league\b"), "UEFA Conference League"),
    (rx(r"\blaliga hypermotion\b"), "LaLiga Hypermotion"),
    (rx(r"\blaliga ea sports\b", r"\blaliga ea\b"), "LaLiga EA Sports"),
    (PRIMERA_RFEF_RE, "Primera Federación"),
    (rx(r"\bpremier league\b"), "Premier League"),
    (rx(r"\bserie a\b"), "Serie A"),
    (rx(r"\bbundesliga\b"), "Bundesliga"),
    (rx(r"\bcopa del rey\b"), "Copa del Rey"),
)

TENNIS_TOURNAMENT_RE = rx(
    r"\btorneo\s+de\s+hangzhou\b", r"\bhangzhou\b", r"\btorneo\s+de\s+chengd[uú]\b",
    r"\btorneo\s+de\s+pe[kí]n\b", r"\bpe[kí]n\b", r"\bbeijing\b", r"\bchina\s+open\b",
    r"\btorneo\s+de\s+tokio\b", r"\btokio\b", r"\btokyo\b", r"\bjapan\s+open\b",
    r"\bwta\s+pe[kí]n\b", r"\bwta\s+beijing\b", r"\bwta\s+tokio\b", r"\bwta\s+tokyo\b",
    r"\bwta\b", r"\batp\b"
)

TENNIS_COMPETITIONS = (
    (rx(r"\bchina\s+open\b", r"\bbeijing\b", r"\bpe[kí]n\b", r"\btorneo\s+de\s+pe[kí]n\b"), "China Open"),
    (rx(r"\btorneo\s+de\s+tokio\b", r"\btokio\b", r"\btokyo\b", r"\bjapan\s+open\b"), "Japan Open"),
    (rx(r"\blaver cup\b"), "Laver Cup"),
    (rx(r"\bcopa davis\b", r"\bdavis cup\b", r"\bdavis\b"), "Copa Davis"),
    (rx(r"\bbillie jean king cup\b"), "Billie Jean King Cup"),
    (rx(r"\bus open\b"), "US Open"),
    (rx(r"\bwimbledon\b"), "Wimbledon"),
    (rx(r"\broland garros\b"), "Roland Garros"),
    (rx(r"\bopen de australia\b"), "Open de Australia"),
)

GENERIC_TOURNAMENTS = frozenset({
    "", "competición", "fútbol", "futbol", "baloncesto", "basket", "tenis",
    "atp", "wta", "ciclismo", "motor",
})

EXCLUDED_CHANNELS_RE = rx(*(re.escape(channel) for channel in EXCLUDED_CHANNELS))


def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def is_excluded_event(blob: str) -> bool:
    normalized = normalize_search_text(blob)
    return bool(EXCLUDED_SPORTS_RE.search(normalized) or EXCLUDED_BLOB_RE.search(normalized))


def clean_tournament(raw: str, fallback: str) -> str:
    value = (raw or "").strip()
    if len(value.lower()) > 2 and value.lower() not in GENERIC_TOURNAMENTS:
        return value
    return fallback


def classify_tennis(blob: str, raw_tournament: str, tv_blob: str) -> str:
    tennis_text = normalize_search_text(f"{blob} {raw_tournament} {tv_blob}")
    tour = "WTA" if "wta" in tennis_text else "ATP"

    for pattern, comp_name in TENNIS_COMPETITIONS:
        if pattern.search(tennis_text):
            return f"{tour} {comp_name}"

    return clean_tournament(raw_tournament, f"{tour} Tour")


def time_to_minutes(time_str: str) -> int:
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except Exception:
        return 0


def classify_motor_sessions(events_list: list[dict]):
    """
    Agrupa los eventos de motor, asigna sus sesiones de forma cronológica 
    y ajusta estrictamente los favoritos según las reglas de MotoGP y F1.
    """
    groups = {}
    for ev in events_list:
        if ev["deporte"] != "Motor":
            continue
        base_comp = ev["competicion"]
        for key_prefix in ["Fórmula 1", "MotoGP", "Moto2", "Moto3", "Fórmula 2", "Fórmula 3"]:
            if base_comp.startswith(key_prefix):
                base_comp = key_prefix
                break
        
        clean_gp_name = re.sub(r"(libres|fp\d|práctica|entrenamientos|clasificación|warm up|sprint|shootout|q\d).*$", "", ev["evento"], flags=re.IGNORECASE).strip()
        if not clean_gp_name:
            clean_gp_name = ev["evento"]

        key = (base_comp, clean_gp_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(ev)

    for key, group in groups.items():
        comp_base, _ = key
        group.sort(key=lambda x: time_to_minutes(x["hora"]))
        total_sessions = len(group)
        current_weekday = datetime.now().weekday()  # 0: Lunes ... 5: Sábado, 6: Domingo

        for idx, ev in enumerate(group):
            session_name = ""
            
            if comp_base == "MotoGP":
                if current_weekday == 4:  # Viernes
                    if idx == 0: session_name = "Libres 1 (FP1)"
                    elif idx == 1: session_name = "Práctica"
                    else: session_name = f"Sesión {idx + 1}"
                elif current_weekday == 5:  # Sábado
                    if idx == 0: session_name = "Libres 2 (FP2)"
                    elif idx == 1: session_name = "Clasificación (Q1 y Q2)"
                    elif idx == 2: session_name = "Carrera Sprint"
                    else: session_name = f"Sesión {idx + 1}"
                elif current_weekday == 6:  # Domingo
                    if idx == 0: session_name = "Warm Up"
                    elif idx == 1: session_name = "Carrera Principal"
                    else: session_name = f"Sesión {idx + 1}"
                else:
                    if total_sessions == 2:
                        session_name = "Warm Up" if idx == 0 else "Carrera Principal"
                    elif total_sessions == 3:
                        if idx == 0: session_name = "Libres 1 (FP1)"
                        elif idx == 1: session_name = "Práctica"
                        else: session_name = "Clasificación / Sprint"
            
            elif comp_base == "Fórmula 1":
                if current_weekday == 4:  # Viernes
                    if idx == 0: session_name = "Libres 1 (FP1)"
                    elif idx == 1: session_name = "Libres 2 (FP2)"
                    else: session_name = f"Sesión {idx + 1}"
                elif current_weekday == 5:  # Sábado
                    if idx == 0: session_name = "Libres 3 (FP3)"
                    elif idx == 1: session_name = "Clasificación"
                    else: session_name = f"Sesión {idx + 1}"
                elif current_weekday == 6:  # Domingo
                    if idx == 0: session_name = "Carrera Principal"
                    else: session_name = f"Sesión {idx + 1}"
                else:
                    if total_sessions == 1:
                        session_name = "Carrera Principal"
                    elif total_sessions == 2:
                        session_name = "Libres / Shootout" if idx == 0 else "Clasificación / Sprint"
                    elif total_sessions == 3:
                        if idx == 0: session_name = "Libres 1 (FP1)"
                        elif idx == 1: session_name = "Libres 2 / Shootout"
                        else: session_name = "Libres 3 / Clasificación"
            else:
                if total_sessions == 1:
                    session_name = "Carrera"
                elif idx == 0: session_name = "Entrenamientos / Práctica"
                elif idx == 1: session_name = "Clasificación"
                else: session_name = "Carrera"

            ev["competicion"] = comp_base
            
            if session_name:
                clean_base_event = re.sub(r"\s*[-–—]\s*(libres|fp\d|práctica|entrenamientos|clasificación|warm up|sprint|shootout|q\d).*$", "", ev["evento"], flags=re.IGNORECASE).strip()
                ev["evento"] = f"{clean_base_event} - {session_name}"

            # REGLAS ESTRICTAS DE FAVORITOS PARA MOTOR:
            ev_lower = ev["evento"].lower()
            if comp_base == "MotoGP":
                # MotoGP: Solo Carreras Sprint y Carreras Principales
                ev["is_filtered"] = any(term in ev_lower for term in ["sprint", "carrera principal", "carrera"])
            elif comp_base == "Fórmula 1":
                # F1: Carreras Sprint, Carreras Principales y Clasificaciones (incluyendo shootout)
                ev["is_filtered"] = any(term in ev_lower for term in ["sprint", "carrera principal", "carrera", "clasificación", "shootout"])


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str) -> tuple[str, str, str]:
    if is_excluded_event(blob): return ("__EXCLUDED__", "", "")

    if contains(WOMEN_RE, blob) and not contains(TENNIS_RE, blob):
        if not contains(REAL_MADRID_RE, blob):
            return ("__EXCLUDED__", "", "")

    if contains(PRIMERA_RFEF_RE, blob) and not contains(CASTILLA_RE, blob):
        return ("__EXCLUDED__", "", "")

    if contains(TENNIS_RE, blob) or contains(TENNIS_TOURNAMENT_RE, blob) or contains(TENNIS_TOURNAMENT_RE, raw_tournament):
        return ("Tenis", "🎾", classify_tennis(blob, raw_tournament, tv_blob))

    if contains(RUGBY_RE, blob): return ("Otros", "🏉", clean_tournament(raw_tournament, "Rugby"))
    if contains(BASKET_RE, blob): return ("Baloncesto", "🏀", clean_tournament(raw_tournament, "Baloncesto"))
    if contains(HOCKEY_RE, blob): return ("Otros", "🎯", clean_tournament(raw_tournament, "Hockey"))
    if contains(FUTSAL_RE, blob): return ("Otros", "🎯", clean_tournament(raw_tournament, "Fútbol Sala"))
    if contains(HANDBALL_RE, blob): return ("Otros", "🎯", clean_tournament(raw_tournament, "Balonmano"))

    for pattern, comp_name in FOOTBALL_COMPETITIONS:
        if pattern.search(blob): return ("Fútbol", "⚽", comp_name)
    if contains(FOOTBALL_RE, blob): return ("Fútbol", "⚽", clean_tournament(raw_tournament, "Fútbol"))

    if contains(CYCLING_RE, blob): return ("Ciclismo", "🚴‍♂️", clean_tournament(raw_tournament, "Ciclismo"))
    
    if contains(MOTOR_GENERAL_RE, blob):
        is_f1 = ("fórmula 1" in blob or F1_RE.search(blob)) and "academy" not in blob
        is_motogp = "motogp" in blob and not MOTO2_RE.search(blob) and not MOTO3_RE.search(blob) and "rookies" not in blob
        is_f2 = "fórmula 2" in blob or F2_RE.search(blob)
        is_f3 = "fórmula 3" in blob or F3_RE.search(blob)
        is_moto2 = MOTO2_RE.search(blob)
        is_moto3 = MOTO3_RE.search(blob)

        if is_f1: comp = "Fórmula 1"
        elif is_motogp: comp = "MotoGP"
        elif is_f2: comp = "Fórmula 2"
        elif is_f3: comp = "Fórmula 3"
        elif is_moto2: comp = "Moto2"
        elif is_moto3: comp = "Moto3"
        else: comp = clean_tournament(raw_tournament, "Motor")

        return ("Motor", "🏎️", comp)

    return ("Otros", "🎯", clean_tournament(raw_tournament, "Evento Deportivo"))


def matches_strict_criteria(blob: str, channels: list[str], sport: str = "", competition: str = "", event_time: str = "") -> bool:
    if is_excluded_event(blob): return False

    if any(EXCLUDED_CHANNELS_RE.search(ch) for ch in channels):
        return False

    # El motor se filtra con precisión milimétrica después en 'classify_motor_sessions'
    if competition in {"Fórmula 1", "MotoGP"}:
        return False

    if contains(REAL_MADRID_RE, blob): return True
    if contains(MOTO_STRICT_EXCLUDE_RE, blob): return False

    if contains(BASKET_RE, blob):
        return "españa" in blob or "spain" in blob or contains(REAL_MADRID_RE, blob)

    if sport == "Tenis":
        return contains(TENNIS_FAVORITES_RE, blob) or ("españa" in blob)

    return contains(MOTOR_SERIES_RE, blob) or contains(SPANISH_BIG_THREE_RE, blob) or contains(TOP3_FOREIGN_RE, blob)


# ============================================================================
# PARSER
# ============================================================================

def parse_row_elements(item) -> tuple[str, str, list[str], str]:
    text_full = item.get_text(" | ", strip=True)
    time_match = TIME_RE.search(text_full)
    time_clean = time_match.group(0) if time_match else ""

    raw_parts = [part.strip() for part in item.get_text("\n", strip=True).split("\n") if part.strip()]
    if not 2 <= len(raw_parts) <= 15:
        return "", "", [], ""

    matchup = ""
    channels: list[str] = []
    tournament = ""

    for part in raw_parts:
        part_lower = normalize_search_text(part)

        if TIME_RE.match(part) or part_lower in {"ver partido", "directo", "(ver en directo)"}:
            continue

        if re.match(r"^[\s,.|;:/-]*$", part):
            continue

        if TV_IDENTIFIERS_RE.search(part) or CHANNEL_LINE_RE.search(part_lower) or "m+" in part_lower or "dazn" in part_lower:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            for channel in clean_part.split(","):
                channel = channel.strip().rstrip(":").strip()
                channel_lower = normalize_search_text(channel)
                if channel and not EXCLUDED_CHANNELS_RE.search(channel_lower) and channel not in channels:
                    channels.append(channel)
            continue

        if TENNIS_TOURNAMENT_RE.search(part_lower) or WTA_RE.search(part_lower) or ATP_RE.search(part_lower) or PRIMERA_RFEF_RE.search(part_lower):
            if not tournament:
                tournament = part
            continue

        if re.search(r"\s+-\s+|\s+vs\.?\s+|\s+v\.\s+", part, re.IGNORECASE):
            if not matchup:
                matchup = part
            continue

        if not tournament and len(part) < 35:
            tournament = part
        elif not matchup:
            matchup = part

    if not matchup and tournament:
        matchup = tournament

    return time_clean, matchup, channels, tournament


def fetch_and_parse_agenda() -> list[dict]:
    results = []
    seen_events = set()

    try:
        response = requests.get(WIDGET_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.find_all(("div", "tr", "li")):
            try:
                original_blob = normalize_search_text(item.get_text(" ", strip=True))
                if is_excluded_event(original_blob): continue

                time_clean, event_str, channels, tournament = parse_row_elements(item)
                if not time_clean or not event_str: continue

                if not re.search(r"[a-zA-Z0-9áéíóúÁÉÍÓÚñÑ]", event_str):
                    continue

                if not channels:
                    continue

                tv_blob = " ".join(channels).lower()
                blob = normalize_search_text(f"{event_str} {tournament} {tv_blob}")

                if is_excluded_event(blob): continue
                if contains(GOLF_RE, blob): continue

                if contains(WOMEN_RE, blob) and not contains(TENNIS_RE, blob) and not contains(REAL_MADRID_RE, blob):
                    continue

                if contains(PRIMERA_RFEF_RE, blob) and not contains(CASTILLA_RE, blob):
                    continue

                event_key = (time_clean, tournament.lower() if tournament else event_str.lower(), event_str.lower())
                if event_key in seen_events: continue
                seen_events.add(event_key)

                sport, icon, competition = get_sport_and_competition(blob, tournament, tv_blob)
                if sport == "__EXCLUDED__": continue

                is_favorite = matches_strict_criteria(blob, channels, sport=sport, competition=competition, event_time=time_clean)

                results.append({
                    "hora": time_clean,
                    "deporte": sport,
                    "icono": icon,
                    "competicion": competition,
                    "evento": event_str,
                    "tv_list": channels,
                    "is_filtered": is_favorite,
                })
            except Exception:
                continue
        
        classify_motor_sessions(results)

    except Exception as e:
        print(f"Error cargando la agenda: {e}")

    return results


# ============================================================================
# GENERACIÓN DE HTML
# ============================================================================

def generate_html(events):
    fecha_act = datetime.now().strftime("%d/%m/%Y - %H:%M")
    total_cnt = len(events)
    filtered_cnt = sum(1 for event in events if event["is_filtered"])
    sport_counts = Counter(event["deporte"] for event in events)

    def clean_key(s):
        return s.lower().replace("ú", "u").replace("ó", "o").replace("á", "a").replace("é", "e").replace("í", "i")

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
    else:
        for ev in events:
            tv_badges = "".join(f'<span class="tv-badge">{channel}</span>' for channel in ev["tv_list"])
            search_text = " ".join([ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]).lower()

            rows_list.append(
                f"""
                <tr class="event-row" data-sport="{clean_key(ev['deporte'])}" data-filtered="{str(ev['is_filtered']).lower()}" data-search="{search_text}">
                    <td class="date-col"><span class="date-badge today">Hoy</span></td>
                    <td class="time-col"><span class="time-badge">{ev['hora']}</span></td>
                    <td class="sport-col"><span class="sport-tag">{ev['icono']} {ev['deporte']}</span></td>
                    <td class="comp-col"><div class="comp-title">{ev['competicion']}</div></td>
                    <td class="event-col"><div class="event-title">{ev['evento']}</div></td>
                    <td class="tv-col"><div class="tv-container">{tv_badges}</div></td>
                </tr>
                """
            )

    rows_html = "".join(rows_list)

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agenda Deportiva - Hoy</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg-color: #0f172a; --card-bg: #1e293b; --border-color: #334155; --text-main: #f8fafc; --text-muted: #94a3b8; --accent-blue: #3b82f6; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 16px 12px; display: flex; justify-content: center; }}
        .container {{ width: 100%; max-width: 1150px; }}
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 8px; }}
        h1 {{ font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header-controls {{ display: flex; gap: 10px; align-items: center; }}
        .btn-update {{ background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }}
        .last-update {{ font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; text-align: right; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-bottom: 16px; }}
        .stat-card {{ background: var(--card-bg); padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }}
        .stat-card.active-card {{ border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }}
        .stat-card .val {{ font-size: 1.1rem; font-weight: 700; color: var(--accent-blue); }}
        .stat-card .lbl {{ font-size: 0.72rem; color: var(--text-muted); }}
        
        .filter-container {{ display: flex; gap: 10px; margin-bottom: 14px; }}
        .search-input {{ padding: 10px 14px; border-radius: 8px; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); font-size: 0.9rem; outline: none; width: 100%; }}
        .search-input:focus {{ border-color: var(--accent-blue); }}
        
        .table-card {{ background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }}
        th {{ background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; }}
        tr.event-row:hover {{ background-color: #243146; }}
        
        .sport-col, .time-col, .date-col {{ white-space: nowrap; }}
        .sport-tag {{ font-weight: 600; white-space: nowrap; }}
        .date-badge {{ display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }}
        .date-badge.today {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }}
        .time-badge {{ background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }}
        .comp-title {{ font-weight: 600; color: #38bdf8; font-size: 0.85rem; }}
        .event-title {{ font-weight: 700; color: #ffffff; font-size: 0.9rem; }}
        .tv-container {{ display: flex; flex-direction: column; gap: 4px; }}
        .tv-badge {{ display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; word-break: break-word; white-space: normal; }}
        .empty-state {{ text-align: center; padding: 30px; color: var(--text-muted); font-size: 1rem; }}

        @media screen and (max-width: 768px) and (orientation: portrait) and (pointer: coarse) {{
            body {{ padding: 8px 6px; }}
            h1 {{ font-size: 1.25rem; }}
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); gap: 6px; }}
            .stat-card {{ padding: 6px 8px; }}
            
            thead {{ display: none; }}
            table, tbody {{ display: block; width: 100%; }}
            .table-card {{ background: transparent; border: none; box-shadow: none; }}
            
            tr.event-row {{
                display: flex;
                flex-direction: column;
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 10px;
                gap: 6px;
            }}
            
            td {{ padding: 0; border: none; width: auto !important; white-space: normal; }}
            .date-col {{ display: none; }}
            .time-col {{ order: 1; display: inline-block; }}
            .sport-col {{ order: 2; margin-left: 8px; display: inline-block; font-size: 0.95rem; }}
            .comp-col {{ order: 3; margin-top: 4px; }}
            .comp-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }}
            .event-col {{ order: 4; margin: 2px 0 4px 0; }}
            .event-title {{ font-size: 1rem; line-height: 1.35; }}
            .tv-col {{ order: 5; margin-top: 4px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px; }}
            .tv-badge {{ font-size: 0.72rem; padding: 4px 8px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div><h1>⚡ Agenda Deportiva - Hoy</h1></div>
        <div class="header-controls"><button class="btn-update" onclick="location.reload()">🔄 Actualizar</button></div>
        <div class="last-update">Última actualización: <strong>{fecha_act} (UTC)</strong></div>
    </header>
    <div class="stats-grid">
        <div class="stat-card active-card" id="card-todos" onclick="setFilter('todos')">
            <div><div class="lbl">Todos</div><div class="val">{total_cnt}</div></div><div style="font-size:1.1rem">📌</div>
        </div>
        <div class="stat-card" id="card-filtrados" onclick="setFilter('filtrados')">
            <div><div class="lbl">Filtrados</div><div class="val" style="color:#a78bfa">{filtered_cnt}</div></div><div style="font-size:1.1rem">⭐</div>
        </div>
        <div class="stat-card" id="card-futbol" onclick="setFilter('futbol')">
            <div><div class="lbl">Fútbol</div><div class="val" style="color:#10b981">{sport_counts['Fútbol']}</div></div><div style="font-size:1.1rem">⚽</div>
        </div>
        <div class="stat-card" id="card-baloncesto" onclick="setFilter('baloncesto')">
            <div><div class="lbl">Baloncesto</div><div class="val" style="color:#f97316">{sport_counts['Baloncesto']}</div></div><div style="font-size:1.1rem">🏀</div>
        </div>
        <div class="stat-card" id="card-tenis" onclick="setFilter('tenis')">
            <div><div class="lbl">Tenis</div><div class="val" style="color:#f59e0b">{sport_counts['Tenis']}</div></div><div style="font-size:1.1rem">🎾</div>
        </div>
        <div class="stat-card" id="card-motor" onclick="setFilter('motor')">
            <div><div class="lbl">Motor</div><div class="val" style="color:#ef4444">{sport_counts['Motor']}</div></div><div style="font-size:1.1rem">🏎️️</div>
        </div>
        <div class="stat-card" id="card-otros" onclick="setFilter('otros')">
            <div><div class="lbl">Otros</div><div class="val" style="color:#a8a29e">{sport_counts['Otros']}</div></div><div style="font-size:1.1rem">🎯</div>
        </div>
    </div>
    <div class="filter-container">
        <input type="text" id="searchInput" class="search-input" onkeyup="filterTable()" placeholder="🔍 Filtrar partido, equipo, tenista o canal TV...">
    </div>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th class="date-col" style="width: 70px;">Fecha</th>
                    <th class="time-col" style="width: 70px;">Hora</th>
                    <th class="sport-col" style="width: 100px;">Deporte</th>
                    <th class="comp-col" style="width: 140px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 210px;">Canal TV</th>
                </tr>
            </thead>
            <tbody id="agendaTable">
                {rows_html}
            </tbody>
        </table>
    </div>
</div>
<script>
function cleanStr(str) {{
    return (str || '').toLowerCase().replace(/ú/g, 'u').replace(/ó/g, 'o').replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i').trim();
}}

let currentFilter = 'todos';

function setFilter(filterType) {{
    currentFilter = cleanStr(filterType);
    document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active-card'));
    const activeCard = document.getElementById('card-' + currentFilter);
    if (activeCard) activeCard.classList.add('active-card');
    applyFilters();
}}

function filterTable() {{ applyFilters(); }}

function applyFilters() {{
    const searchFilter = cleanStr(document.getElementById('searchInput').value);
    const table = document.getElementById('agendaTable');
    const trs = table.getElementsByClassName('event-row');
    let visibleCount = 0;

    for (let i = 0; i < trs.length; i++) {{
        const tr = trs[i];
        if (tr.id === 'dynamicEmptyState') continue;

        const rowSport = cleanStr(tr.getAttribute('data-sport'));
        const isFiltered = tr.getAttribute('data-filtered') === 'true';
        const text = cleanStr(tr.getAttribute('data-search'));

        const matchesFilter = (currentFilter === 'todos') ? true : 
                              (currentFilter === 'filtrados' ? isFiltered : rowSport === currentFilter);
        const matchesSearch = text.includes(searchFilter);

        if (matchesFilter && matchesSearch) {{
            tr.style.display = '';
            visibleCount++;
        }} else {{
            tr.style.display = 'none';
        }}
    }}

    let emptyRow = document.getElementById('dynamicEmptyState');
    if (visibleCount === 0) {{
        if (!emptyRow) {{
            emptyRow = document.createElement('tr');
            emptyRow.id = 'dynamicEmptyState';
            emptyRow.innerHTML = '<td colspan="6" class="empty-state">😴 No hay eventos que coincidan con la selección y búsqueda.</td>';
            table.appendChild(emptyRow);
        }} else {{ emptyRow.style.display = ''; }}
    }} else {{ if (emptyRow) emptyRow.style.display = 'none'; }}
}}
</script>
</body>
</html>"""


if __name__ == "__main__":
    events = fetch_and_parse_agenda()
    if events:
        html_content = generate_html(events)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Archivo index.html generado con éxito. Eventos encontrados: {len(events)}")
    else:
        print("Atención: No se obtuvieron eventos de la fuente. Se conserva la agenda previa.")
