from collections import Counter
from datetime import datetime, date, timedelta
import functools
from html import escape
import zoneinfo
import re

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURACIÓN DE APPS Y PAQUETES FIRE TV / ANDROID TV
# ============================================================================

WIDGET_URL = "https://www.futbolenlatv.es/deporte"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15

# Intents limpios y estándar compatibles con Android TV / Fire TV
FIRE_TV_PACKAGES = {
    "movistar": "intent://#Intent;package=es.movistarplus.androidtv;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end",
    "dazn": "intent://#Intent;package=com.dazn;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end",
    "prime": "intent://#Intent;package=com.amazon.firebat;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end",
    "fctv33": "intent://#Intent;package=com.fctv77.com;action=android.intent.action.MAIN;category=android.intent.category.LAUNCHER;end"
}

# MAPEO EXACTO DE CANALES A APLICACIONES SEGÚN TUS INSTRUCCIONES
CHANNEL_APP_MAP = {
    # MOVISTAR PLUS+
    'la 1': 'movistar',
    'la 2': 'movistar',
    'antena 3': 'movistar',
    'cuatro': 'movistar',
    'telecinco': 'movistar',
    'la sexta': 'movistar',
    'movistar plus+': 'movistar',
    'm+ vamos': 'movistar',
    'm+ vamos 2': 'movistar',
    'm+ vamos 3': 'movistar',
    'primera federacion': 'movistar',
    'eurosport 1': 'movistar',
    'eurosport 2': 'movistar',
    'real madrid tv': 'movistar',
    'teledeporte': 'movistar',
    'replay': 'movistar',

    # DAZN (DAZN 1, 2 y general con app DAZN; 3, 4, F1, MotoGP y Baloncesto a FCTV33)
    'dazn': 'dazn',
    'dazn laliga': 'dazn',
    'dazn 1': 'dazn',
    'dazn 2': 'dazn',
    'dazn 3': 'fctv33',
    'dazn 4': 'fctv33',
    'dazn f1': 'fctv33',
    'dazn motogp': 'fctv33',
    'dazn baloncesto': 'fctv33',
    'dazn baloncesto 2': 'fctv33',
    'dazn baloncesto 3': 'fctv33',

    # PRIME VIDEO
    'tennis channel': 'prime',
    'tennis channel - orange tv': 'prime',
    'amazon prime video': 'prime'
}


def normalize_search_text(text: str) -> str:
    value = (text or "").lower()
    value = (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ç", "c")
        .replace("º", "ª")
    )
    value = re.sub(r"[|,;:/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def clean_time(time_str: str) -> str:
    if not time_str:
        return ""
    parts = time_str.split(":")
    if len(parts) == 2:
        hours = parts[0].zfill(2)
        minutes = parts[1]
        return f"{hours}:{minutes}"
    return time_str


def get_channel_urls(channel_name: str) -> list[str]:
    norm = normalize_search_text(channel_name)
    clean_name = re.sub(r"\([^)]*\)", "", norm).strip()
    clean_name = normalize_search_text(clean_name)

    app_key = None

    if clean_name in CHANNEL_APP_MAP:
        app_key = CHANNEL_APP_MAP[clean_name]
    else:
        for k, v in CHANNEL_APP_MAP.items():
            if normalize_search_text(k) == clean_name or clean_name in normalize_search_text(k):
                app_key = v
                break

    if not app_key:
        if clean_name in {"#vamos", "m+ #vamos", "#vamos spain", "m+ vamos 8 y 50"}:
            app_key = "movistar"
        elif clean_name in {"movistar plus", "movistar+"}:
            app_key = "movistar"
        elif "dazn" in clean_name:
            if any(x in clean_name for x in ["3", "4", "f1", "motogp", "baloncesto"]):
                app_key = "fctv33"
            else:
                app_key = "dazn"
        elif "prime" in clean_name or "amazon" in clean_name:
            app_key = "prime"
        else:
            app_key = "fctv33"

    url = FIRE_TV_PACKAGES.get(app_key, FIRE_TV_PACKAGES["fctv33"])
    return [url]


EXCLUDED_CHANNELS = {
    "* sin tv en directo *", "antel tv internacional", "aragón play", "aragón tv",
    "asobal tv", "atp tennis tv", "athletic-club.eus", "baloncesto tv",
    "baloncesto tv ppv", "barclays women's super league youtube", "be mad", "betevé web",
    "beisbolplay", "canal 9 soria youtube", "cayotv youtube", "cmmplay",
    "concacaf youtube", "conmebol libertadores youtube", "dazn 1 bar(m148)", "dazn 1 bar", "dazn 2 bar(m149)",
    "dazn 2 bar", "deportes tvcanaria youtube", "eleventv youtube", "esport3 web",
    "esport3(cataluña)", "esport3", "etb1(país vasco)", "f1 academy youtube", "fanatiz", "fanplay",
    "fanplay tv", "fanseat", "fc barcelona ppv youtube", "fff tv youtube", "fiba youtube",
    "flamengo tv youtube", "hbo max", "j.league international youtube", "la 7", "la 7 tv",
    "la ocho mediterráneo", "la xarxa+", "laliga tv bar", "laliga tv m2",
    "laliga tv m3", "laliga tv m4", "laliga tv m5", "laliga+ plus",
    "liga futve youtube", "ligafutve app", "lleida televisió", "m+ #vamos bar", "m+ #vamos bar 2",
    "m+ #vamos bar 2(308)", "m+ #vamos bar(307)", "m+ laliga hdr", "m+ laliga hdr(m440 o111)",
    "mediaset infinity", "motogp videopass", "movistar+ lite",
    "nwsl+", "onefootball", "onefootball ppv", "orange fútbol 1(107)",
    "orange fútbol 2(108)", "orange fútbol 3(109)", "popular tv murcia", "prosieben maxx(m+ astra)", "rcd deportivo tv youtube",
    "rcdeportivo tv youtube", "rcn nuestra tele", "red bull tv", "rfef tv youtube",
    "rfef.es", "rtve play", "sefutbol youtube", "sevilla fc +",
    "siroko tv", "tv 3", "tv footballclub(acceder)", "tv footballclub", "tv canaria",
    "tv galicia", "tv3(cataluña)", "tvg(galicia)", "tv footballclub ▾",
    "tvg", "tv5monde", "uefa tv", "uefa youtube",
    "win sports tv youtube", "wta tv", "web directo", "zapping internacional",
    "a-leagues youtube", "liga u youtube", "marca youtube", "german football youtube", "l1 max youtube",
    "the afc hub youtube", "hc eivissa youtube", "vinxtv youtube"
}

EXCLUDED_CHANNEL_KEYS = {re.sub(r"[^a-z0-9]+", "", normalize_search_text(c)) for c in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = re.sub(r"[^a-z0-9]+", "", normalize_search_text(channel))
    if not key:
        return True
    return any(key == excluded or key.startswith(excluded) for excluded in EXCLUDED_CHANNEL_KEYS)


def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


# ============================================================================
# REGEX DE PATRONES Y FECHAS
# ============================================================================

def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r"\breal madrid\b", r"\brm castilla\b", r"\br\.?\s*madrid\b")
CASTILLA_RE = rx(r"\breal madrid castilla\b", r"\brm castilla\b", r"\bcastilla\b")
YOUTH_BASKET_RE = rx(r"\bsub\s*[-]?\d+\b", r"\bjunior\b", r"\bcadete\b", r"\binfantil\b")

PSG_RE = rx(r"\bparis saint germain\b", r"\bpsg\b")
ARSENAL_RE = rx(r"\barsenal\b")
BAYERN_RE = rx(r"\bbayern munich\b", r"\bbayern\b")

EXCLUDED_SPORTS_RE = rx(
    r"\bhockey\b", r"\bpatines\b", r"\bnfl\b", r"\bcowboys\b", r"\bpackers\b",
    r"\bbalonmano\b", r"\basobal\b", r"\bhandball\b", r"\bwaterpolo\b", r"\brugby\b", r"\brutby\b", r"\brucby\b", r"\brubgy\b",
    r"\behf\b", r"\bihf\b", r"\bfutsal\b", r"\bfutbol sala\b", r"\bgolf\b", r"\bbeisbol\b"
)

EXCLUDED_COMPETITIONS_RE = rx(
    r"\bnational league\b", r"\bvanarama national league\b", r"\bliga u\b",
    r"\btercera\b", r"\b3ª\b", r"\b3a\b", r"\bgrupo 8\b", r"\btercera federacion\b",
    r"\bbasketball champions league\b", r"\bfutsal champions\b",
    r"\b2\.?\s*bundesliga\b", r"\bserie a fem+inile\b", r"\bserie a femminile\b",
    r"\blaliga hypermotion\b", r"\bsegunda division\b", r"\bhypermotion\b"
)

SPANISH_TENNIS_PLAYERS_RE = rx(
    r"\bcarlos alcaraz\b", r"\balcaraz\b", r"\balejandro davidovich\b", r"\bdavidovich\b",
    r"\bcristina bucsa\b", r"\bbucsa\b", r"\bpaula badosa\b", r"\bbadosa\b",
    r"\bjaume munar\b", r"\bmunar\b", r"\bjessica bouzas\b", r"\bbouzas\b",
    r"\brafael jodar\b", r"\bjodar\b", r"\broberto bautista\b", r"\bbautista\b",
    r"\bpedro martinez\b", r"\brabelo\b", r"\bcarballes\b"
)

WTA_RE = re.compile(r"\bwta\b", re.IGNORECASE)
WOMEN_RE = rx(r"\bfemenina\b", r"\bfemenino\b", r"\bfrauen\b", r"\bwomen\b", r"\(f\)\b", r"\(w\)\b")

PRIMERA_RFEF_RE = rx(
    r"\bprimera federacion\b", r"\bprimera rfef\b", r"\b1[ªa]\s*federacion\b",
)

LALIGA_RE = rx(
    r"\blaliga ea sports\b", r"\blaliga ea\b", r"\bprimera division\b", 
    r"\bespaña - la liga\b", r"\blaliga(?![\s\-]*(?:hypermotion|smartbank|tv hypermotion|123))\b"
)

BASKET_ALLOWED_COMPETITIONS_RE = rx(
    r"\bliga endesa\b", r"\bacb\b", r"\beuroliga\b", r"\beuroleague\b", r"\beuro league\b",
    r"\bcopa acb\b", r"\bsupercopa endesa\b", r"\bsupercopa de espana\b",
    r"\bnba\b"
)

WOMEN_FOOTBALL_COMPETITIONS = (
    (rx(r"\bliga f\b", r"\bprimera division femenina\b"), "Liga F"), (rx(r"\bcopa de la reina\b"), "Copa de la Reina"),
    (rx(r"\bsupercopa de espana femenina\b", r"\bsupercopa femenina\b"), "Supercopa de España Femenina"),
    (rx(r"\bwomen'?s champions league\b", r"\bchampions league femenina\b"), "UEFA Women's Champions League"),
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DATE_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")

CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder", 
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|videopass|prime video|amazon|à punt)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis channel\b", r"\borange tv\b", r"\bchannel\s*[-–—]\s*orange tv\b", r"\bprime video\b", r"\bà punt mèdia\b", r"\bà punt\b"
)

JUNK_RESIDUES_RE = rx(
    r"\(\s*(?:cataluña|catalunya|país vasco|pais vasco|galicia|andalucía|andalucia)\s*\)",
    r"\(\s*(?:ver gratis|ver en directo|acceder|ver)\s*\)",
    r"\(\s*\d+\s*\)"
)

TECHNICAL_CODE_RE = re.compile(r"\([A-Z0-9\s]{3,}\)", re.IGNORECASE)

EVENT_CLEANUP_TRAIL_RE = re.compile(
    r"\s*-\s*(?:orange\s*f[uú]tbol\s*\d*|movistar[^\-]*|dazn[^\-]*|nba\s+league\s+pass|\(\s*\d+(?:\s*y\s*\d+)?\s*\))\s*$",
    re.IGNORECASE
)


# ============================================================================
# PARSER ROBUSTO DE MOTOR
# ============================================================================

def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)

    if any(forbidden in blob_lower for forbidden in ["academy", "moto2", "moto 2", "moto3", "moto 3", "rookies", "supercars"]):
        return ("", "", False)

    if any(junk in blob_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje"]):
        return ("", "", False)

    comp_name = ""
    if "formula 1" in blob_lower or "f1" in blob_lower:
        comp_name = "Fórmula 1"
    elif "motogp" in blob_lower:
        comp_name = "MotoGP"
    elif "formula e" in blob_lower or "fórmula e" in blob_lower:
        comp_name = "Fórmula E"
    elif "indycar" in blob_lower or "indy car" in blob_lower:
        comp_name = "Indycar"

    if not comp_name:
        return ("", "", False)

    valid_lines = [l for l in text_lines if normalize_search_text(l) not in {normalize_search_text(comp_name), "motor", "automovilismo", "motociclismo"}]
    clean_desc = " - ".join(valid_lines).strip()
    clean_desc = EVENT_CLEANUP_TRAIL_RE.sub("", clean_desc).strip()
    
    if not clean_desc or clean_desc == "-":
        clean_desc = "Carrera"
    
    event_title = f"{comp_name} - {clean_desc}"
    clean_norm = normalize_search_text(event_title)

    is_fav = False
    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
    else:
        is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])

    return (comp_name, event_title, is_fav)


# ============================================================================
# NÚCLEO DE CLASIFICACIÓN
# ============================================================================

def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str]:
    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob or "movistar golf" in tv_blob:
        return ("", "", "", False, False, "")

    if EXCLUDED_COMPETITIONS_RE.search(blob):
        return ("", "", "", False, False, "")

    # Forzar inclusión si el evento se emite en canales específicos de DAZN que quieres capturar
    has_target_dazn = any(ch in tv_blob for ch in ["dazn 3", "dazn 4", "dazn f1", "dazn motogp", "dazn baloncesto"])

    # Tenis
    if contains(rx(r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bmasters\b", r"\bopen\b", r"\bchallenger\b", r"\bitf\b", r"\btorneo de\b"), blob):
        if "golf" in tv_blob or "movistar golf" in blob:
            return ("", "", "", False, False, "")
        tour = "WTA" if WTA_RE.search(blob) else "ATP"
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"tenis", "atp", "wta", ""} else f"{tour} Tour"
        is_fav = contains(SPANISH_TENNIS_PLAYERS_RE, blob)
        return ("Tenis", "🎾", comp, is_fav, True, "")

    # Baloncesto (incluyendo DAZN Baloncesto)
    if BASKET_ALLOWED_COMPETITIONS_RE.search(blob) or "baloncesto" in tv_blob:
        if contains(WOMEN_RE, blob) and not "baloncesto" in tv_blob:
            return ("", "", "", False, False, "")

        comp_name = "Liga Endesa"
        if contains(rx(r"\beuroliga\b", r"\beuroleague\b"), blob):
            comp_name = "Euroliga"
        elif contains(rx(r"\bcopa acb\b"), blob) or (contains(rx(r"\bcopa del rey\b"), blob) and contains(rx(r"\bbasket\b", r"\bbaloncesto\b", r"\bacb\b"), blob)):
            comp_name = "Copa del Rey"
        elif contains(rx(r"\bsupercopa\b"), blob):
            comp_name = "Supercopa de España"
        elif contains(rx(r"\bnba\b"), blob):
            comp_name = "NBA"
        elif "baloncesto" in tv_blob:
            comp_name = raw_tournament if raw_tournament and raw_tournament.lower() not in {"general", ""} else "Baloncesto"
        
        is_fav = contains(REAL_MADRID_RE, blob) and not contains(YOUTH_BASKET_RE, blob)
        return ("Baloncesto", "🏀", comp_name, is_fav, True, "")

    # Fútbol Femenino
    if contains(WOMEN_RE, blob) or any(p.search(blob) for p, _ in WOMEN_FOOTBALL_COMPETITIONS):
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(blob) or ("femenina" in blob and name.lower() in blob):
                comp_match = name
                break
        if comp_match and contains(REAL_MADRID_RE, blob):
            return ("Fútbol", "⚽", comp_match, True, True, "")
        return ("", "", "", False, False, "")

    # Copa del Rey de Fútbol
    if contains(rx(r"\bcopa del rey\b"), blob) and not contains(WOMEN_RE, blob) and not contains(rx(r"\bbasket\b", r"\bbaloncesto\b", r"\bacb\b"), blob):
        is_fav = contains(REAL_MADRID_RE, blob)
        return ("Fútbol", "⚽", "Copa del Rey", is_fav, True, "")

    # Primera RFEF
    if PRIMERA_RFEF_RE.search(blob) or "primera federacion" in blob or "primera rfef" in blob:
        if contains(CASTILLA_RE, blob):
            return ("Fútbol", "⚽", "España - Primera Federación", True, True, "")
        return ("", "", "", False, False, "")

    # La Liga
    if LALIGA_RE.search(blob) or "dazn laliga" in tv_blob:
        is_fav = contains(REAL_MADRID_RE, blob)
        return ("Fútbol", "⚽", "España - La Liga", is_fav, True, "")

    # Ligas Europeas
    if not contains(WOMEN_RE, blob):
        if contains(rx(r"\bligue 1\b", r"\bfrancia - ligue 1\b"), blob) and contains(PSG_RE, blob):
            return ("Fútbol", "⚽", "Francia - Ligue 1", False, True, "")
        
        if contains(rx(r"\bpremier league\b", r"\bpremier\b", r"\binglaterra - premier league\b"), blob) and contains(ARSENAL_RE, blob):
            return ("Fútbol", "⚽", "Inglaterra - Premier League", True, True, "")

        if contains(rx(r"\bbundesliga\b", r"\balemania - bundesliga\b"), blob) and contains(BAYERN_RE, blob):
            return ("Fútbol", "⚽", "Alemania - Bundesliga", False, True, "")

    # Champions League
    if contains(rx(r"\bchampions league\b", r"\bchampions\b"), blob) and not contains(WOMEN_RE, blob) and not contains(rx(r"\bbasketball\b", r"\bcl\b", r"\bafc\b", r"\basia\b"), blob):
        is_fav = contains(REAL_MADRID_RE, blob) or contains(ARSENAL_RE, blob)
        return ("Fútbol", "⚽", "UEFA Champions League", is_fav, True, "")

    # Si es un canal objetivo de DAZN (como DAZN 3, 4, etc.) pero no cayó en los filtros anteriores, lo rescatamos como evento general
    if has_target_dazn:
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"general", ""} else "Deportes"
        return ("Fútbol", "⚽", comp, False, True, "")

    # Fútbol general
    if contains(rx(r"\bfutbol\b", r"\bliga ea sports\b", r"\bchampions\b", r"\bcopa del rey\b", r"\bpremier league\b", r"\bserie a\b", r"\bbundesliga\b", r"\bligue 1\b"), blob) and not contains(WOMEN_RE, blob):
        if contains(rx(r"\bligue\s*1\b"), blob):
            comp = "Francia - Ligue 1"
        elif contains(rx(r"\bbundesliga\b"), blob):
            comp = "Alemania - Bundesliga"
        elif contains(rx(r"\bpremier league\b"), blob):
            comp = "Inglaterra - Premier League"
        elif contains(rx(r"\bserie a\b"), blob):
            comp = "Italia - Serie A"
        else:
            comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"general", ""} else "Fútbol"
        return ("Fútbol", "⚽", comp, False, False, "")

    return ("", "", "", False, False, "")


def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:
    raw_parts = [
        part.strip()
        for part in item.get_text("\n", strip=True).split("\n")
        if part.strip()
    ]
    if not 3 <= len(raw_parts) <= 25:
        return "", "", [], "", []

    text_full = " | ".join(raw_parts)
    time_match = TIME_RE.search(text_full)
    time_clean = clean_time(time_match.group(0)) if time_match else ""

    if not time_clean:
        return "", "", [], "", []

    channels: list[str] = []
    text_lines = []

    competition_terms = (
        "liga", "primera", "segunda", "tercera", "federacion", "division", "grupo", "torneo", "serie a", "premier",
        "endesa", "bundesliga", "atp", "wta", "masters", "copa", "champions", "superbike", "eredivisie", "euroliga", "euroleague", "nba"
    )

    for part in raw_parts:
        part = JUNK_RESIDUES_RE.sub("", part).strip()
        if not part:
            continue

        if TECHNICAL_CODE_RE.search(part):
            continue

        part_lower = normalize_search_text(part)
        if TIME_RE.fullmatch(part) or part_lower in {
            "ver partido", "directo", "(ver en directo)", "ver gratis",
            "(ver)", "acceder", "(acceder)"
        }:
            continue
        if re.fullmatch(r"[\s,.|;:/-]*", part):
            continue
        if re.fullmatch(r"\(?[mo]\+?\d+.*\)?", part_lower):
            continue

        looks_like_channel = (
            TV_IDENTIFIERS_RE.search(part)
            or CHANNEL_LINE_RE.search(part_lower)
            or any(term in part_lower for term in (
                "m+", "dazn", "youtube", "fanatiz", "onefootball",
                "siroko", "tv footballclub", "aragon tv", "aragon play",
                "cmmplay", "etb1",
