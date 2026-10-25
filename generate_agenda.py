from collections import Counter
from datetime import datetime
import functools
from html import escape
import zoneinfo
import re

import requests
from bs4 import BeautifulSoup


# ============================================================================
# CONFIGURACIÓN Y DICCIONARIO DE CANALES
# ============================================================================

WIDGET_URL = (
    "https://widgets.futbolenlatv.com/partidos/agenda"
    "?color=005df8&culture=es-ES"
)

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15

CHANNEL_DICT = {
    'la 1': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-533.php', 'https://dlive.sx/hub/stream-533.php', 'https://dlive.sx/watch/stream-533.php', 'https://dlive.sx/cast/stream-533.php', 'https://daddylive.pk/'],
    'la 2': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-536.php', 'https://dlive.sx/hub/stream-536.php', 'https://dlive.sx/watch/stream-536.php', 'https://dlive.sx/cast/stream-536.php', 'https://daddylive.pk/'],
    'antena 3': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-531.php', 'https://dlive.sx/hub/stream-531.php', 'https://dlive.sx/watch/stream-531.php', 'https://dlive.sx/cast/stream-531.php', 'https://daddylive.pk/'],
    'cuatro': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-535.php', 'https://dlive.sx/hub/stream-535.php', 'https://dlive.sx/watch/stream-535.php', 'https://dlive.sx/cast/stream-535.php', 'https://daddylive.pk/'],
    'telecinco': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-532.php', 'https://dlive.sx/hub/stream-532.php', 'https://dlive.sx/watch/stream-532.php', 'https://dlive.sx/cast/stream-532.php', 'https://daddylive.pk/'],
    'la sexta': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-534.php', 'https://dlive.sx/hub/stream-534.php', 'https://dlive.sx/watch/stream-534.php', 'https://dlive.sx/cast/stream-534.php', 'https://daddylive.pk/'],
    'movistar plus+': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-437.php', 'https://dlive.sx/hub/stream-437.php', 'https://dlive.sx/watch/stream-437.php', 'https://dlive.sx/cast/stream-437.php', 'https://daddylive.pk/'],
    'm+ vamos': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-521.php', 'https://dlive.sx/hub/stream-521.php', 'https://dlive.sx/watch/stream-521.php', 'https://dlive.sx/cast/stream-521.php', 'https://daddylive.pk/'],
    'dazn laliga': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-538.php', 'https://dlive.sx/hub/stream-538.php', 'https://dlive.sx/watch/stream-538.php', 'https://dlive.sx/cast/stream-538.php', 'https://daddylive.pk/'],
    'm+ laliga': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-84.php', 'https://dlive.sx/hub/stream-84.php', 'https://dlive.sx/watch/stream-84.php', 'https://dlive.sx/cast/stream-84.php', 'https://daddylive.pk/'],
    'm+ liga de campeones': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-435.php', 'https://dlive.sx/hub/stream-435.php', 'https://dlive.sx/watch/stream-435.php', 'https://dlive.sx/cast/stream-435.php', 'https://daddylive.pk/'],
    'dazn': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn 1': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-445.php', 'https://dlive.sx/hub/stream-445.php', 'https://dlive.sx/watch/stream-445.php', 'https://dlive.sx/cast/stream-445.php', 'https://daddylive.pk/'],
    'dazn 2': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-446.php', 'https://dlive.sx/hub/stream-446.php', 'https://dlive.sx/watch/stream-446.php', 'https://dlive.sx/cast/stream-446.php', 'https://daddylive.pk/'],
    'dazn 3': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-447.php', 'https://dlive.sx/hub/stream-447.php', 'https://dlive.sx/watch/stream-447.php', 'https://dlive.sx/cast/stream-447.php', 'https://daddylive.pk/'],
    'dazn 4': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-448.php', 'https://dlive.sx/hub/stream-448.php', 'https://dlive.sx/watch/stream-448.php', 'https://dlive.sx/cast/stream-448.php', 'https://daddylive.pk/'],
    'dazn f1': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-537.php', 'https://dlive.sx/hub/stream-537.php', 'https://dlive.sx/watch/stream-537.php', 'https://dlive.sx/cast/stream-537.php', 'https://daddylive.pk/'],
    'dazn motogp': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'eurosport 1': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-524.php', 'https://dlive.sx/hub/stream-524.php', 'https://dlive.sx/watch/stream-524.php', 'https://dlive.sx/cast/stream-524.php', 'https://daddylive.pk/'],
    'eurosport 2': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-525.php', 'https://dlive.sx/hub/stream-525.php', 'https://dlive.sx/watch/stream-525.php', 'https://dlive.sx/cast/stream-525.php', 'https://daddylive.pk/'],
    'm+ deportes': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-436.php', 'https://dlive.sx/hub/stream-436.php', 'https://dlive.sx/watch/stream-436.php', 'https://dlive.sx/cast/stream-436.php', 'https://daddylive.pk/'],
    'm+ deportes 2': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-438.php', 'https://dlive.sx/hub/stream-438.php', 'https://dlive.sx/watch/stream-438.php', 'https://dlive.sx/cast/stream-438.php', 'https://daddylive.pk/'],
    'm+ deportes 3': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-526.php', 'https://dlive.sx/hub/stream-526.php', 'https://dlive.sx/watch/stream-526.php', 'https://dlive.sx/cast/stream-526.php', 'https://daddylive.pk/'],
    'm+ deportes 4': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-527.php', 'https://dlive.sx/hub/stream-527.php', 'https://dlive.sx/watch/stream-527.php', 'https://dlive.sx/cast/stream-527.php', 'https://daddylive.pk/'],
    'tennis channel - orange tv': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'real madrid tv': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-523.php', 'https://dlive.sx/hub/stream-523.php', 'https://dlive.sx/watch/stream-523.php', 'https://dlive.sx/cast/stream-523.php', 'https://daddylive.pk/'],
    'teledeporte': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-529.php', 'https://dlive.sx/hub/stream-529.php', 'https://dlive.sx/watch/stream-529.php', 'https://dlive.sx/cast/stream-529.php', 'https://daddylive.pk/'],
    'laliga tv hypermotion': ['https://hubu.ru/fctvlink', 'https://dlive.sx/stream/stream-539.php', 'https://dlive.sx/hub/stream-539.php', 'https://dlive.sx/watch/stream-539.php', 'https://dlive.sx/cast/stream-539.php', 'https://daddylive.pk/'],
    'amazon prime video': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
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

    if clean_name in CHANNEL_DICT:
        return CHANNEL_DICT[clean_name]

    for k, v in CHANNEL_DICT.items():
        if normalize_search_text(k) == clean_name or clean_name in normalize_search_text(k):
            return v

    if clean_name in {"#vamos", "m+ #vamos", "#vamos spain", "m+ vamos 8 y 50"}:
        if "m+ vamos" in CHANNEL_DICT:
            return CHANNEL_DICT["m+ vamos"]
    elif clean_name in {"movistar plus", "movistar+"}:
        if "movistar plus+" in CHANNEL_DICT:
            return CHANNEL_DICT["movistar plus+"]
    elif clean_name in {"tennis channel", "tennis channel orange tv"}:
        if "tennis channel - orange tv" in CHANNEL_DICT:
            return CHANNEL_DICT["tennis channel - orange tv"]
    elif clean_name in {"tdp", "teledeporte spain (tdp)"}:
        if "teledeporte" in CHANNEL_DICT:
            return CHANNEL_DICT["teledeporte"]

    return ['https://hubu.ru/fctvlink', 'https://daddylive.pk/']


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
    "orange fútbol 2(108)", "orange fútbol 3(109)", "prosieben maxx(m+ astra)", "rcd deportivo tv youtube",
    "rcdeportivo tv youtube", "rcn nuestra tele", "red bull tv", "rfef tv youtube",
    "rfef.es", "rtve play", "sefutbol youtube", "sevilla fc +",
    "siroko tv", "tv 3", "tv footballclub(acceder)", "tv footballclub", "tv canaria",
    "tv galicia", "tv3(cataluña)", "tvg(galicia)", "tv footballclub ▾",
    "tvg", "tv5monde", "uefa tv", "uefa youtube",
    "win sports tv youtube", "wta tv", "web directo", "zapping internacional",
    "a-leagues youtube", "liga u youtube", "marca youtube", "german football youtube", "l1 max youtube"
}

EXCLUDED_CHANNEL_KEYS = {re.sub(r"[^a-z0-9]+", "", normalize_search_text(c)) for c in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = re.sub(r"[^a-z0-9]+", "", normalize_search_text(channel))
    if not key:
        return True
    
    # Bloquear explícitamente nombres de competiciones que se cuelan como canales (ej. Primera Federación, España - Primera Federación)
    norm_ch = normalize_search_text(channel)
    if "primera federacion" in norm_ch or "españa -" in norm_ch or "grupo" in norm_ch:
        return True

    return any(key == excluded or key.startswith(excluded) for excluded in EXCLUDED_CHANNEL_KEYS)


def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


# ============================================================================
# REGEX DE PATRONES
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
    r"\behf\b", r"\bihf\b"
)

EXCLUDED_COMPETITIONS_RE = rx(
    r"\bnational league\b", r"\bvanarama national league\b", r"\bliga u\b",
    r"\btercera\b", r"\b3ª\b", r"\b3a\b", r"\bgrupo 8\b", r"\btercera federacion\b"
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
    r"\bcopa del rey\b", r"\bcopa acb\b", r"\bsupercopa endesa\b", r"\bsupercopa de espana\b",
    r"\bnba\b"
)

WOMEN_FOOTBALL_COMPETITIONS = (
    (rx(r"\bliga f\b", r"\bprimera division femenina\b"), "Liga F"), (rx(r"\bcopa de la reina\b"), "Copa de la Reina"),
    (rx(r"\bsupercopa de espana femenina\b", r"\bsupercopa femenina\b"), "Supercopa de España Femenina"),
    (rx(r"\bwomen'?s champions league\b", r"\bchampions league femenina\b"), "UEFA Women's Champions League"),
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder", 
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|primera federaci[oó]n|videopass|prime video|amazon)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis channel\b", r"\borange tv\b", r"\bchannel\s*[-–—]\s*orange tv\b", r"\bprimera federaci[oó]n\b", r"\bprime video\b"
)

JUNK_RESIDUES_RE = rx(
    r"\(\s*(?:cataluña|catalunya|país vasco|pais vasco|galicia|andalucía|andalucia)\s*\)",
    r"\(\s*(?:ver gratis|ver en directo|acceder|ver)\s*\)",
    r"\(\s*\d+\s*\)"
)

EVENT_CLEANUP_TRAIL_RE = re.compile(
    r"\s*-\s*(?:orange\s*f[uú]tbol\s*\d*|movistar[^\-]*|dazn[^\-]*|\(\s*\d+(?:\s*y\s*\d+)?\s*\))\s*$",
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
# NÚCLEO DE CLASIFICACIÓN (FÚTBOL, BALONCESTO, TENIS)
# ============================================================================

def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str]:
    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob:
        return ("", "", "", False, False, "")

    if EXCLUDED_COMPETITIONS_RE.search(blob):
        return ("", "", "", False, False, "")

    # Tenis
    if contains(rx(r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bmasters\b", r"\bopen\b", r"\bchallenger\b", r"\bitf\b"), blob):
        tour = "WTA" if WTA_RE.search(blob) else "ATP"
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"tenis", "atp", "wta", ""} else f"{tour} Tour"
        is_fav = contains(SPANISH_TENNIS_PLAYERS_RE, blob)
        return ("Tenis", "🎾", comp, is_fav, True, "")

    # Baloncesto
    if BASKET_ALLOWED_COMPETITIONS_RE.search(blob):
        comp_name = "Liga Endesa"
        if contains(rx(r"\beuroliga\b", r"\beuroleague\b"), blob):
            comp_name = "Euroliga"
        elif contains(rx(r"\bcopa del rey\b", r"\bcopa acb\b"), blob):
            comp_name = "Copa del Rey"
        elif contains(rx(r"\bsupercopa\b"), blob):
            comp_name = "Supercopa de España"
        elif contains(rx(r"\bnba\b"), blob):
            comp_name = "NBA"
        
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

    # Primera RFEF
    if PRIMERA_RFEF_RE.search(blob) or "primera federacion" in blob or "primera rfef" in blob:
        if contains(CASTILLA_RE, blob):
            return ("Fútbol", "⚽", "España - Primera Federación", True, True, "")
        return ("", "", "", False, False, "")

    # La Liga
    if LALIGA_RE.search(blob):
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
    if contains(rx(r"\bchampions league\b", r"\bchampions\b"), blob) and not contains(WOMEN_RE, blob) and not contains(rx(r"\bbasketball\b", r"\bbcl\b"), blob):
        is_fav = contains(REAL_MADRID_RE, blob) or contains(ARSENAL_RE, blob)
        return ("Fútbol", "⚽", "UEFA Champions League", is_fav, True, "")

    # Copa del Rey
    if contains(rx(r"\bcopa del rey\b"), blob) and not contains(WOMEN_RE, blob):
        is_fav = contains(REAL_MADRID_RE, blob)
        return ("Fútbol", "⚽", "Copa del Rey", is_fav, True, "")

    # Fútbol general
    if contains(rx(r"\bfutbol\b", r"\bliga ea sports\b", r"\bchampions\b", r"\bcopa del rey\b", r"\bpremier league\b", r"\bserie a\b", r"\bbundesliga\b", r"\bligue 1\b", r"\bsegunda division\b"), blob) and not contains(WOMEN_RE, blob):
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"general", ""} else "Fútbol"
        return ("Fútbol", "⚽", comp, False, False, "")

    return ("", "", "", False, False, "")


def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:
    text_full = item.get_text(" | ", strip=True)
    time_match = TIME_RE.search(text_full)
    time_clean = clean_time(time_match.group(0)) if time_match else ""

    raw_parts = [
        part.strip()
        for part in item.get_text("\n", strip=True).split("\n")
        if part.strip()
    ]
    if not 2 <= len(raw_parts) <= 25:
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
                "cmmplay", "etb1", "tvg", "tv3", "esport3", "hbo max", "ehf tv", "videopass", "prime video", "amazon"
            ))
        )
        if looks_like_channel:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            clean_part = JUNK_RESIDUES_RE.sub("", clean_part).strip()
            clean_part = re.sub(r"\(m\d+[^)]*\)", "", clean_part, flags=re.IGNORECASE).strip()
            clean_part = re.sub(r"\s*\([^)]*\)", "", clean_part).strip()

            sub_parts = re.split(r"[,|\n]+", clean_part)
            for channel in sub_parts:
                channel = channel.strip().rstrip(":").strip()
                channel_lower = normalize_search_text(channel)

                if (
                    channel
                    and not is_excluded_channel(channel)
                    and channel not in channels
                    and not re.fullmatch(r"\(?[mo]\+?\d+.*\)?", channel_lower)
                    and channel_lower not in {"acceder", "(acceder)", "ver en directo"}
                ):
                    channels.append(channel)
            continue

        text_lines.append(part)

    if not text_lines:
        return "", "", [], "", []

    tournament_candidates = []
    matchup_candidates = []
    for part in text_lines:
        part_lower = normalize_search_text(part)
        is_competition_line = any(term in part_lower for term in competition_terms)
        has_match_separator = bool(
            re.search(r"\s+-\s+|\s+vs\.?\s+|\s+v\.\s+", part, re.IGNORECASE)
            or re.search(r"\s\(f\)\s*-\s*", part, re.IGNORECASE)
        )
        if is_competition_line and not has_match_separator:
            tournament_candidates.append(part)
        else:
            matchup_candidates.append(part)

    tournament = tournament_candidates[0] if tournament_candidates else text_lines[0]
    remaining_lines = [p for p in text_lines if p != tournament]
    matchup = " - ".join(remaining_lines) if remaining_lines else tournament

    matchup = EVENT_CLEANUP_TRAIL_RE.sub("", matchup).strip()

    return time_clean, matchup, channels, tournament, text_lines


def fetch_and_parse_agenda() -> list[dict]:
    results = []
    seen_events = set()

    try:
        response = requests.get(WIDGET_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.find_all(("div", "tr", "li")):
            try:
                time_clean, event_str, channels, tournament, text_lines = parse_row_elements(item)
                if not time_clean or not channels: 
                    continue

                tv_blob = " ".join(channels).lower()
                blob = normalize_search_text(f"{' '.join(text_lines)} {tournament} {tv_blob}")

                comp_name, motor_event_title, is_fav = parse_motor_event(blob, tournament, text_lines)
                if comp_name:
                    event_key = (time_clean, comp_name, normalize_search_text(motor_event_title))
                    if event_key in seen_events:
                        continue
                    seen_events.add(event_key)

                    results.append({
                        "hora": time_clean,
                        "deporte": "Motor",
                        "icono": "🏆",
                        "competicion": comp_name,
                        "evento": motor_event_title,
                        "tv_list": channels,
                        "is_filtered": is_fav,
                        "is_configured": True,
                    })
                    continue

                sport, icon, competition, is_favorite, is_configured, custom_event = get_sport_and_competition(
                    blob, tournament, tv_blob, text_lines
                )
                
                if not sport:
                    continue

                final_event = custom_event if custom_event else event_str
                final_event = EVENT_CLEANUP_TRAIL_RE.sub("", final_event).strip()

                if not EVENT_TEXT_RE.search(final_event):
                    continue

                event_key = (time_clean, normalize_search_text(competition), normalize_search_text(final_event))
                if event_key in seen_events: 
                    continue
                seen_events.add(event_key)

                results.append({
                    "hora": time_clean,
                    "deporte": sport,
                    "icono": icon,
                    "competicion": competition,
                    "evento": final_event,
                    "tv_list": channels,
                    "is_filtered": is_favorite,
                    "is_configured": is_configured,
                })
            except Exception:
                continue

    except Exception as e:
        print(f"Error cargando la agenda del widget: {e}")

    results.sort(key=lambda x: x["hora"])
    return results


# ============================================================================
# GENERACIÓN DE HTML COMPLETO
# ============================================================================

def generate_html(events):
    spain_tz = zoneinfo.ZoneInfo("Europe/Madrid")
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")
    
    total_cnt = len(events)
    filtered_cnt = sum(1 for event in events if event["is_filtered"])
    sport_counts = Counter(event["deporte"] for event in events if event["is_configured"])

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
    else:
        for ev in events:
            tv_badges_list = []
            for channel in ev["tv_list"]:
                urls = get_channel_urls(channel)
                safe_channel = escape(str(channel), quote=True)
                
                if urls:
                    if len(urls) > 1:
                        options_html = ""
                        for idx, u in enumerate(urls):
                            lbl = f"Opción {idx + 1}"
                            safe_u = escape(u, quote=True)
                            options_html += f'<a href="{safe_u}" target="_blank" rel="noopener noreferrer">{safe_channel} - {lbl}</a>'
                        
                        tv_badges_list.append(
                            f'<div class="dropdown-tv">'
                            f'<button class="tv-badge tv-dropdown-btn" onclick="toggleDropdown(event)">{safe_channel} ▾</button>'
                            f'<div class="dropdown-content">{options_html}</div>'
                            f'</div>'
                        )
                    else:
                        safe_url = escape(urls[0], quote=True)
                        is_dlive = "dlive.sx" in urls[0]
                        css_cls = "tv-badge alt-link" if is_dlive else "tv-badge"
                        tv_badges_list.append(
                            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
                            f'class="{css_cls}" title="Abrir canal {safe_channel}">'
                            f'{safe_channel} 🔗</a>'
                        )
                else:
                    tv_badges_list.append(
                        f'<span class="tv-badge alt-link" style="cursor:default;" title="Canal sin enlace">'
                        f'{safe_channel}</span>'
                    )

            tv_badges = "".join(tv_badges_list)
            search_text = normalize_search_text(" ".join(
                [ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
            ))
            safe_search = escape(search_text, quote=True)
            safe_sport_key = escape(clean_key(ev["deporte"]), quote=True)
            safe_time = escape(str(ev["hora"]))
            safe_icon = escape(str(ev["icono"]))
            safe_sport = escape(str(ev["deporte"]))
            safe_competition = escape(str(ev["competicion"]))
            safe_event = escape(str(ev["evento"]))

            rows_list.append(
                f"""
                <tr class="event-row" data-sport="{safe_sport_key}" data-filtered="{str(ev['is_filtered']).lower()}" data-configured="{str(ev['is_configured']).lower()}" data-search="{safe_search}">
                    <td class="date-col"><span class="date-badge today">Hoy</span></td>
                    <td class="time-col"><span class="time-badge">{safe_time}</span></td>
                    <td class="sport-col"><span class="sport-tag">{safe_icon} {safe_sport}</span></td>
                    <td class="comp-col"><div class="comp-title">{safe_competition}</div></td>
                    <td class="event-col"><div class="event-title">{safe_event}</div></td>
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
        .header-controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .btn-update {{ background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }}
        .btn-alt {{ background: #6366f1; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; text-decoration: none; transition: all 0.2s; display: inline-flex; align-items: center; }}
        .btn-alt:hover {{ background: #4f46e5; }}
        .last-update {{ font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; text-align: right; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-bottom: 16px; }}
        .stat-card {{ background: var(--card-bg); padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }}
        .stat-card.active-card {{ border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }}
        .stat-card .val {{ font-size: 1.1rem; font-weight: 700; color: var(--accent-blue); }}
        .stat-card .lbl {{ font-size: 0.72rem; color: var(--text-muted); }}
        
        .filter-container {{ display: flex; gap: 10px; margin-bottom: 14px; }}
        .search-input {{ padding: 10px 14px; border-radius: 8px; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); font-size: 0.9rem; outline: none; width: 100%; }}
        .search-input:focus {{ border-color: var(--accent-blue); }}
        
        .table-card {{ background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: visible !important; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); margin-bottom: 80px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }}
        th {{ background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; }}
        tr.event-row:hover {{ background-color: #243146; }}
        
        .sport-col {{ width: 155px !important; min-width: 155px !important; white-space: nowrap; }}
        .time-col, .date-col {{ white-space: nowrap; }}
        .sport-tag {{ font-weight: 600; white-space: nowrap; }}
        .date-badge {{ display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }}
        .date-badge.today {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }}
        .time-badge {{ background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }}
        .comp-title {{ font-weight: 600; color: #38bdf8; font-size: 0.85rem; }}
        .event-title {{ font-weight: 700; color: #ffffff; font-size: 0.9rem; }}
        .tv-container {{ display: flex; flex-direction: column; gap: 4px; }}
        
        .tv-badge {{ display: inline-block; background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; text-decoration: none; transition: all 0.2s ease; cursor: pointer; }}
        .tv-badge:hover {{ background: rgba(99, 102, 241, 0.35); color: #a5b4fc; border-color: #818cf8; transform: translateY(-1px); }}

        .alt-link {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }}
        .alt-link:hover {{ background: rgba(16, 185, 129, 0.35); color: #6ee7b7; border-color: #34d399; }}

        .dropdown-tv {{ position: relative; display: inline-block; }}
        .tv-dropdown-btn {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); text-align: left; width: 100%; white-space: nowrap; }}
        .dropdown-content {{ 
            display: none; 
            position: absolute; 
            background-color: #111827; 
            min-width: 220px; 
            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5); 
            z-index: 1000; 
            border: 1px solid var(--border-color); 
            border-radius: 8px; 
            padding: 4px 0; 
            left: 0; 
            top: 100%; 
        }}
        .dropdown-tv.dropup .dropdown-content {{
            top: auto;
            bottom: 100%;
            margin-bottom: 4px;
        }}
        .dropdown-content a {{ color: #f8fafc; padding: 8px 12px; text-decoration: none; display: block; font-size: 0.78rem; transition: background 0.2s; white-space: nowrap; }}
        .dropdown-content a:hover {{ background-color: #1e293b; color: #60a5fa; }}
        .dropdown-tv.show .dropdown-content {{ display: block; }}

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
            .sport-col {{ order: 2; margin-left: 8px; display: inline-block; font-size: 0.95rem; width: auto !important; min-width: 0 !important; }}
            .comp-col {{ order: 3; margin-top: 4px; }}
            .comp-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }}
            .event-col {{ order: 4; margin: 2px 0 4px 0; }}
            .event-title {{ font-size: 1rem; line-height: 1.35; }}
            .tv-col {{ order: 5; margin-top: 4px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px; }}
            .tv-badge {{ font-size: 0.72rem; padding: 4px 8px; white-space: nowrap; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div><h1>⚡ Agenda Deportiva - Hoy</h1></div>
        <div class="header-controls">
            <a href="https://hubu.ru/fctvlink" target="_blank" class="btn-alt">FCTV33</a>
            <a href="https://daddylive.pk/" target="_blank" class="btn-alt">DLHD</a>
            <button class="btn-update" onclick="location.reload()">🔄 Actualizar</button>
        </div>
        <div class="last-update">Última actualización: <strong>{fecha_act} (España)</strong></div>
    </header>
    <div class="stats-grid">
        <div class="stat-card active-card" id="card-todos" onclick="setFilter('todos')">
            <div><div class="lbl">Todos</div><div class="val">{total_cnt}</div></div><div style="font-size:1.1rem">📺</div>
        </div>
        <div class="stat-card" id="card-favoritos" onclick="setFilter('favoritos')">
            <div><div class="lbl">Favoritos</div><div class="val" style="color:#a78bfa">{filtered_cnt}</div></div><div style="font-size:1.1rem">📌</div>
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
            <div><div class="lbl">Motor</div><div class="val" style="color:#ef4444">{sport_counts['Motor']}</div></div><div style="font-size:1.1rem">🏆</div>
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
                    <th class="sport-col" style="width: 155px;">Deporte</th>
                    <th class="comp-col" style="width: 140px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 250px;">Canal TV</th>
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
    return (str || '').toLowerCase().replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i').replace(/ó/g, 'o').replace(/ú/g, 'u').replace(/ç/g, 'c').trim();
}}

function toggleDropdown(event) {{
    event.stopPropagation();
    const btn = event.currentTarget;
    const dropdown = btn.parentElement;
    
    document.querySelectorAll('.dropdown-tv').forEach(item => {{
        if (item !== dropdown) {{
            item.classList.remove('show', 'dropup');
        }}
    }});

    const rect = btn.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    
    if (spaceBelow < 160) {{
        dropdown.classList.add('dropup');
    }} else {{
        dropdown.classList.remove('dropup');
    }}

    dropdown.classList.toggle('show');
}}

window.onclick = function(event) {{
    if (!event.target.matches('.tv-dropdown-btn')) {{
        document.querySelectorAll('.dropdown-tv').forEach(item => {{
            item.classList.remove('show', 'dropup');
        }});
    }}
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
        const isConfigured = tr.getAttribute('data-configured') === 'true';
        const text = cleanStr(tr.getAttribute('data-search'));

        let matchesFilter = false;
        if (currentFilter === 'todos') {{
            matchesFilter = true;
        }} else if (currentFilter === 'favoritos') {{
            matchesFilter = isFiltered;
        }} else {{
            matchesFilter = (rowSport === currentFilter && isConfigured);
        }}

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
    html_content = generate_html(events)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(f"Archivo index.html generado con éxito. Eventos totales (Fútbol, Baloncesto, Tenis y Motor): {len(events)}")
