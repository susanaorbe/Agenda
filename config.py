from datetime import datetime
import re
import zoneinfo
from zoneinfo import ZoneInfoNotFoundError

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


# ============================================================================
# CONFIGURACIÓN GENERAL Y CONSTANTES
# ============================================================================

WIDGET_URL = "https://www.futbolenlatv.es/deporte"

REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15
TAPLINK_URL = "https://taplink.cc/fctvlink"

SPORT_TV_GUIDE_LOGIN_URL = "https://sport-tv-guide.live/es/user/login"
SPORT_TV_GUIDE_SPORT_URLS = {
    "futbol": ("FÚTBOL", "⚽", "https://sport-tv-guide.live/es/live/futbol"),
    "baloncesto": ("BALONCESTO", "🏀", "https://sport-tv-guide.live/es/live/baloncesto"),
    "tenis": ("TENIS", "🎾", "https://sport-tv-guide.live/es/live/tenis"),
    "motor": ("MOTOR", "🏆", "https://sport-tv-guide.live/es/live/deportes-de-motor"),
}


# ============================================================================
# UTILIDADES DE FECHA, RED Y NORMALIZACIÓN DE TEXTO
# ============================================================================

def get_spain_timezone():
    """Devuelve Europe/Madrid; usa la zona local como último recurso."""
    try:
        return zoneinfo.ZoneInfo("Europe/Madrid")
    except ZoneInfoNotFoundError:
        return datetime.now().astimezone().tzinfo


def create_http_session() -> requests.Session:
    """Sesión HTTP con reintentos limitados ante errores transitorios."""
    session = requests.Session()
    retry_options = {
        "total": 3,
        "connect": 3,
        "read": 2,
        "status": 2,
        "backoff_factor": 0.5,
        "status_forcelist": (429, 500, 502, 503, 504),
        "raise_on_status": False,
    }
    try:
        retry = Retry(**retry_options, allowed_methods=frozenset({"GET"}))
    except TypeError:
        retry = Retry(**retry_options, method_whitelist=frozenset({"GET"}))
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session


def normalize_search_text(text: str) -> str:
    value = str(text or "").lower().replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    value = (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ç", "c")
        .replace("ñ", "n").replace("º", "ª")
    )
    value = re.sub(r"[|,;:/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def contains_previo_or_previa(*texts) -> bool:
    """Devuelve True si algún texto contiene la palabra 'previo' o 'previa'."""
    for txt in texts:
        if not txt:
            continue
        norm = normalize_search_text(str(txt))
        if re.search(r"\bprevi[oa]s?\b", norm):
            return True
    return False


def get_time_slot(time_str: str) -> str:
    try:
        if time_str == "LIVE":
            return "noche"
        parts = time_str.split(":")
        h = int(parts[0])
        m = int(parts[1]) if len(parts) > 1 else 0
        total_mins = h * 60 + m
        if total_mins <= 419:
            return "madrugada"
        elif total_mins <= 779:
            return "manana"
        elif total_mins <= 1229:
            return "tarde"
        else:
            return "noche"
    except Exception:
        return "noche"


def clean_time(time_str: str) -> str:
    if not time_str:
        return ""
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", str(time_str))
    if not match:
        return ""
    hours, minutes = map(int, match.groups())
    if not (0 <= hours <= 23 and 0 <= minutes <= 59):
        return ""
    return f"{hours:02d}:{minutes:02d}"


def clean_channel_display_name(channel_name: str) -> str:
    cleaned = str(channel_name or "").strip()
    cleaned = re.sub(
        r"\s*[-–—]\s*orange\s+tv\s*$",
        "",
        cleaned,
        flags=re.IGNORECASE,
    ).strip()
    if normalize_search_text(cleaned) == "tennis channel":
        return "Tennis Channel"
    return cleaned


def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


# ============================================================================
# EXPRESIONES REGULARES Y DICCIONARIOS DE EXCLUSIÓN / SINÓNIMOS
# ============================================================================

REAL_MADRID_RE = rx(r" real madrid ", r" rm castilla ", r" r\.?\s*madrid ")
CASTILLA_RE = rx(r" real madrid castilla ", r" rm castilla ", r" castilla ")
YOUTH_BASKET_RE = rx(r" sub\s*[-]?\d+ ", r" junior ", r" cadete ", r" infantil ")
SPAIN_SELECTION_RE = rx(r"\bspain\b", r"\bespaña\b", r"\bespana\b")

EXCLUDED_SPORTS_RE = rx(
    r" hockey ", r" patines ", r" nfl ", r" cowboys ", r" packers ",
    r" balonmano ", r" asobal ", r" handball ", r" waterpolo ", r" rugby ", r" rutby ", r" rucby ", r" rubgy ",
    r" ehf ", r" ihf ", r" futsal ", r" futbol sala ", r" golf ", r" beisbol ",
    r" padel ", r" padell ",
    r" badminton ", r" bwf ", r" cricket ", r" t20 ", r" list a ", r" emerging teams ",
    r" snooker ", r" darts ", r" dardos ", r" boxing ", r" ufc ", r" mma "
)

EXCLUDED_COMPETITIONS_RE = rx(
    r" national league ", r" vanarama national league ", r" liga u ",
    r" tercera ", r" 3[ªa]\s*(?:rfef|federacion|division|grupo) ", r" grupo 8 ", r" tercera federacion ",
    r" basketball champions league ", r" futsal champions ",
    r" 2\.?\s*bundesliga ", r" serie a femminile ",
    r" laliga hypermotion ", r" segunda division ", r" hypermotion ",
    r" brasil\s*[-–—]?\s*serie\s+a ",
    r" argentina ", r" torneo clausura ", r" torneo apertura ",
    r" liga profesional ", r" primera division argentina ",
    r" international cup ", r" eurocup ",
    r" hong kong open ", r" international league t20 ", r" emerging teams asia cup "
)

SPANISH_TENNIS_PLAYERS_RE = rx(
    r" carlos alcaraz ", r" alcaraz ", r" alejandro davidovich ", r" davidovich ",
    r" cristina bucsa ", r" bucsa ", r" paula badosa ", r" badosa ",
    r" jaume munar ", r" munar ", r" rafael jodar ", r" jodar ",
    r" dani merida ", r" merida "
)

WTA_RE = re.compile(r" wta ", re.IGNORECASE)
WOMEN_RE = rx(r" femenina ", r" femenino ", r" frauen ", r" women ", r"\(f\) ", r"\(w\) ")
PRIMERA_RFEF_RE = rx(
    r" primera federacion ", r" primera rfef ", r" 1[ªa]\s*federacion ",
    r" spanish primera division rfef ", r" primera division rfef "
)
LALIGA_RE = rx(
    r" liga ea sports ", r" liga ea ", r" espana - la liga ",
    r" laliga(?![\s\-]*(?:hypermotion|smartbank|tv hypermotion|123)) ",
    r" primera division de espana ", r" primera division espana "
)
BASKET_ALLOWED_COMPETITIONS_RE = rx(
    r" liga endesa ", r" acb ", r" euroliga ", r" euroleague ", r" euro league ",
    r" copa acb ", r" supercopa endesa ", r" supercopa de espana ",
    r" nba ", r" national basketball association "
)

WOMEN_FOOTBALL_COMPETITIONS = (
    (rx(r" liga f ", r" primera division femenina "), "Liga F"),
    (rx(r" copa de la reina "), "Copa de la Reina"),
    (rx(r" supercopa de espana femenina ", r" supercopa femenina "), "Supercopa de España Femenina"),
    (rx(r" women'?s champions league ", r" champions league femenina "), "UEFA Women's Champions League"),
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
DATE_RE = re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})")

CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder",
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")
TV_IDENTIFIERS_RE = rx(r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|videopass|prime video|amazon|à punt)")
CHANNEL_LINE_RE = rx(r" tennis channel ", r" orange tv ", r" channel\s*[-–—]\s*orange tv ", r" prime video ", r" à punt mèdia ", r" à punt ")
JUNK_RESIDUES_RE = rx(r"\(\s*(?:cataluña|catalunya|país vasco|pais vasco|galicia|andalucía|andalucia)\s*\)", r"\(\s*(?:ver gratis|ver en directo|acceder|ver)\s*\)", r"\(\s*\d+\s*\)")
EVENT_CLEANUP_TRAIL_RE = re.compile(
    r"\s*-\s*(?:orange\s*f[uú]tbol\s*\d*|movistar[^\-]*|dazn[^\-]*|nba\s+league\s+pass|primera\s+federaci[oó]n(?:\s*\(\s*[mo]\d+(?:\s+[mo]\d+)*\s*\))?|\(\s*\d+(?:\s*y\s*\d+)?\s*\))\s*$",
    re.IGNORECASE
)

TENNIS_EVENT_RE = rx(r" tenis ", r" atp ", r" wta ", r" masters ", r" open ", r" challenger ", r" itf ", r" torneo de ")
GOLF_RE = rx(r" golf ")
NBA_RE = rx(r" nba ", r" national basketball association ")
EUROLIGA_RE = rx(r" euroliga ", r" euroleague ")
BASKET_WOMEN_RE = rx(r"\(f\) ", r"\(w\) ")
COPA_DEL_REY_RE = rx(r" copa del rey ")
BASKET_CONTEXT_RE = rx(r" basket ", r" baloncesto ", r" acb ")
CHAMPIONS_RE = rx(r" champions league ", r" champions ")
CHAMPIONS_NON_FOOTBALL_RE = rx(r" basketball ", r" cl ", r" afc ", r" asia ")
PREMIER_RE = rx(
    r" inglaterra - premier league ",
    r"(?<!saint kitts nevis )(?<!ukrainian )(?<!ukranian )(?<!egyptian )(?<!jamaica )(?<!antigua barbuda )premier league(?!\s+(?:saint kitts|ukrainian|ukranian|egyptian|jamaica|antigua))",
    r"(?<!saint kitts nevis )(?<!ukrainian )(?<!ukranian )(?<!egyptian )(?<!jamaica )(?<!antigua barbuda )premier(?!\s+(?:division|league|saint kitts|ukrainian|ukranian|egyptian|jamaica|antigua))"
)
SERIE_A_RE = rx(r"(?<!ligapro )(?<!brazilian )(?<!brasil )(?<!femminile )serie a(?!\s+(?:ligapro|brazilian|brasil|femminile))")
BUNDESLIGA_RE = rx(r" bundesliga ", r" alemania - bundesliga ")
BUNDESLIGA_2_RE = rx(r"2\.?\s*bundesliga ")
LIGUE1_RE = rx(r" ligue 1 ", r" francia - ligue 1 ")
EREDIVISIE_RE = rx(r" eredivisie ")
LIGA_PORTUGAL_RE = rx(
    r" liga portugal betclic ", r" portugal betclic ", r" betclic ",
    r" liga portugues[ae](?!\s+(?:sub\s*[-]?\d+|u\d+|2|ii|femenina|women)) "
)
WORLD_CUP_RE = rx(
    r" copa mundial(?!\s+sub\s*[-]?\d+|\s+u\d+|\s+femenina|\s+women)",
    r" mundial de la fifa(?!\s+sub\s*[-]?\d+|\s+u\d+|\s+femenina|\s+women)",
    r"(?<!u17\s)(?<!u20\s)(?<!u21\s)(?<!u23\s)(?<!sub17\s)(?<!sub20\s)(?<!sub21\s)(?<!sub23\s)(?<!womens\s)(?<!women\s)(?<!'s\s)world cup(?!\s+u\d+|\s+sub\s*[-]?\d+|\s+women)"
)
EUROCUP_RE = rx(r" eurocup ")
EURO_FINAL_RE = rx(r" eurocopa ", r" euro\s*20\d{2} ", r" euro\s*cup ")
NATIONS_LEAGUE_RE = rx(r" nations league ")

EXCLUDED_CHANNELS = {
    "* sin tv en directo *", "antel tv internacional", "aragón play", "aragón tv",
    "asobal tv", "atp tennis tv", "athletic-club.eus", "baloncesto tv",
    "baloncesto tv ppv", "barclays women's super league youtube", "be mad", "betevé web",
    "beisbolplay", "canal 9 soria youtube", "cayotv youtube", "cmmplay",
    "concacaf youtube", "conmebol libertadores youtube", "dazn 1 bar(m148)", "dazn 1 bar", "dazn 2 bar(m149)",
    "dazn 2 bar", "deportes tvcanaria youtube", "eleventv youtube", "esport3 web",
    "esport3(cataluña)", "esport3", "etb1", "etb1(país vasco)", "f1 academy youtube", "fanatiz", "fanplay",
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
    "tv galicia", "tv3(cataluña)", "tvg(galicia)", "tvg2", "tvg 2", "tvg2(galicia)", "tv footballclub ▾",
    "tvg", "tv5monde", "uefa tv", "uefa youtube",
    "win sports tv youtube", "wta tv", "web directo", "zapping internacional",
    "a-leagues youtube", "liga u youtube", "marca youtube", "german football youtube", "l1 max youtube",
    "the afc hub youtube", "hc eivissa youtube", "vinxtv youtube",
    "valencia cf youtube", "valencia cf app", "à punt", "à punt mèdia",
    "fip - international padel federation youtube", "fip youtube"
}


def channel_exclusion_key(channel: str) -> str:
    base = re.sub(r"\([^)]*\)", "", normalize_search_text(channel))
    return re.sub(r"[^a-z0-9]+", "", base)


EXCLUDED_CHANNEL_KEYS = {channel_exclusion_key(c) for c in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = channel_exclusion_key(channel)
    if not key:
        return True
    return key in EXCLUDED_CHANNEL_KEYS


COMPETITION_TERMS = (
    "liga", "primera", "segunda", "tercera", "federacion", "division", "grupo",
    "torneo", "serie a", "endesa", "bundesliga", "atp", "wta", "masters",
    "copa", "champions", "superbike", "eredivisie", "euroliga", "euroleague",
    "nba", "portugal", "portuguesa",
)

EVENT_SIMILARITY_SYNONYMS = {
    "euroleague": "euroliga",
    "national basketball association": "nba",
    "french ligue 1": "ligue 1",
    "spanish la liga": "laliga ea sports",
    "spanish primera division de la liga de futbol femenino": "liga f",
    "spanish primera division rfef": "espana - primera federacion",
    "uefa women's champions league": "uefa womens champions league",
    "ax olimpia milano": "milano",
    "gales": "wales",
    "northern ireland": "irlanda del norte",
    "olimpia milano": "milano",
    "paris basketball": "paris",
    "republica irlanda": "ireland",
    "rumania": "romania",
    "saski baskonia": "baskonia",
    "winterthur fc barcelona": "barcelona",
}