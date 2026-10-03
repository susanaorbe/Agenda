from collections import Counter
from datetime import datetime
from zoneinfo import ZoneInfo
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
        "AppleWebKit/537.36"
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
    "fff tv youtube",
    "laliga tv bar",
    "laliga tv m2",
    "laliga tv m3",
    "laliga tv m4",
    "laliga tv m5",
    "m+ #vamos bar 2(308)",
    "m+ #vamos bar(307)",
    "m+ laliga hdr(m440 o111)",
    "motogp videopass",
    "movistar+ lite",
    "nba league pass",
    "onefootball",
    "orange fútbol 1(107)",
    "hbo max",
    "red bull tv",
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
# UTILIDADES DE REGEX
# ============================================================================

def rx(*patterns: str) -> re.Pattern:
    """
    Compila varios patrones en una única expresión regular.
    """
    return re.compile(
        r"(?:%s)" % "|".join(patterns),
        re.IGNORECASE,
    )


# ============================================================================
# REGEX PRINCIPALES
# ============================================================================

# ---------------------------------------------------------------------------
# Fútbol
# ---------------------------------------------------------------------------

REAL_MADRID_RE = rx(
    r"\breal madrid\b",
    r"\brm castilla\b",
    r"\br\.?\s*madrid\b",
)

SPANISH_BIG_THREE_RE = rx(
    r"\breal madrid\b",
    r"\brm castilla\b",
    r"\bbarcelona\b",
    r"\bbarça\b",
    r"\batletico de madrid\b",
    r"\batlético de madrid\b",
)

TOP3_FOREIGN_RE = rx(
    r"\bmanchester city\b",
    r"\barsenal\b",
    r"\bliverpool\b",
    r"\binter de milán\b",
    r"\binter milan\b",
    r"\bnapoles\b",
    r"\bjuventus\b",
    r"\bbayern de múnich\b",
    r"\bbayern munich\b",
    r"\bbayern\b",
    r"\bborussia dortmund\b",
    r"\bdortmund\b",
    r"\brb leipzig\b",
    r"\bleipzig\b",
    r"\bparis saint-germain\b",
    r"\bpsg\b",
    r"\bolympique de marsella\b",
    r"\bmarsella\b",
    r"\brc lens\b",
    r"\blens\b",
    r"\bsporting cp\b",
    r"\bsporting de portugal\b",
    r"\bbenfica\b",
    r"\bporto\b",
)


# ---------------------------------------------------------------------------
# Tenis
# ---------------------------------------------------------------------------

TENNIS_PLAYERS_RE = rx(
    r"\balcaraz\b",
    r"\bjódar\b",
    r"\bdavidovich\b",
    r"\bmunar\b",
    r"\bmérida\b",
    r"\blandaluce\b",
    r"\bcarreño\b",
    r"\bbucsa\b",
    r"\bbouzas\b",
    r"\bbadosa\b",
    r"\bquevedo\b",
    r"\bsinner\b",
    r"\bzverev\b",
    r"\bsabalenka\b",
    r"\brybakina\b",
    r"\bpegula\b",
)

TENNIS_RE = rx(
    r"\btenis\b",
    r"\batp\b",
    r"\bwta\b",
    r"\bwimbledon\b",
    r"\broland garros\b",
    r"\bus open\b",
    r"\bopen de australia\b",
    r"\bmasters\b",
    r"\bdavis\b",
    r"\bcopa davis\b",
    r"\bbillie jean king cup\b",
    r"\blaver cup\b",
)

WTA_RE = re.compile(r"\bwta\b", re.IGNORECASE)
ATP_RE = re.compile(r"\batp\b", re.IGNORECASE)


WOMEN_RE = rx(
    r"\bfemenina\b",
    r"\bfemenino\b",
    r"\bfrauen\b",
    r"\bwomen\b",
)


# ---------------------------------------------------------------------------
# Motor
# ---------------------------------------------------------------------------

F1_RE = re.compile(
    r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b",
    re.IGNORECASE,
)

F2_RE = re.compile(r"\bf2\b", re.IGNORECASE)
F3_RE = re.compile(r"\bf3\b")

MOTO2_RE = re.compile(r"\bmoto2\b", re.IGNORECASE)
MOTO3_RE = re.compile(r"\bmoto3\b", re.IGNORECASE)

MOTOR_SERIES_RE = rx(
    r"\bfórmula 1\b",
    r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b",
    r"\bmotogp\b(?![\s\-]*(?:2|3|moto2|moto3|rookies))\b",
    r"\bformula e\b",
    r"\bfórmula e\b",
    r"\bindycar\b",
    r"\bindy car\b",
)

MOTOR_GENERAL_RE = rx(
    r"\bfórmula 1\b",
    r"\bf1(?![\s\-]*(?:academy))\b",
    r"\bfórmula 2\b",
    r"\bfórmula 3\b",
    r"\bf2\b",
    r"\bf3\b",
    r"\bmotogp\b",
    r"\bformula e\b",
    r"\bfórmula e\b",
    r"\bindycar\b",
    r"\bindy car\b",
    r"\bmoto2\b",
    r"\bmoto3\b",
    r"\bnascar\b",
    r"\brally\b",
    r"\bautomovilismo\b",
    r"\bmotor\b",
)

MOTO_STRICT_EXCLUDE_RE = rx(
    r"\bmoto2\b",
    r"\bmoto3\b",
    r"rookies\s+cup",
    r"\brookies\b",
    r"\bnascar\b",
    r"\bfórmula 2\b",
    r"\bfórmula 3\b",
    r"\bf2\b",
    r"\bf3\b",
)


# ---------------------------------------------------------------------------
# Otros deportes
# ---------------------------------------------------------------------------

BASKET_RE = rx(
    r"\bacb\b",
    r"\beuroliga\b",
    r"\beuroleague\b",
    r"\bbaloncesto\b",
    r"\bbasket\b",
    r"\bnba\b",
    r"\bliga endesa\b",
    r"\bcopa del rey\b",
    r"\bsupercopa\b",
    r"\bfiba\b",
    r"\bmundial de baloncesto\b",
    r"\bsudán del sur\b",
    r"\bsouth sudan\b",
    r"\bjjoo\b",
)

HOCKEY_RE = rx(
    r"\bfih\b",
    r"\bhockey\b",
    r"\bhokey\b",
)

FUTSAL_RE = rx(
    r"\bf[uú]tbol sala\b",
    r"\bliga prime\b",
    r"\bfutsal\b",
)

RUGBY_RE = rx(
    r"\brugby\b",
    r"\bvrac\b",
    r"\bcr\s+la\s+vila\b",
    r"\bel\s+salvador\b",
    r"\balcobendas\s+rugby\b",
    r"\bdivisi[oó]n\s+de\s+honor\b",
)

HANDBALL_RE = rx(
    r"\bbalonmano\b",
    r"\basobal\b",
    r"\bliga asobal\b",
    r"\bhandball\b",
)

FOOTBALL_RE = rx(
    r"\bf[uú]tbol\b",
    r"\bchampions\b",
    r"\bliga\b",
    r"\bcopa\b",
    r"\buefa\b",
    r"\bfifa\b",
    r"\bpremier\b",
    r"\bserie a\b",
    r"\bbundesliga\b",
    r"\bcalcio\b",
    r"\bmls\b",
    r"\bsupercopa\b",
    r"\bprimera\b",
    r"\bsegunda\b",
    r"\btercera\b",
    r"\brfef\b",
    r"\bliga f\b",
    r"\beredivisie\b",
    r"\bjupiler\b",
    r"\bjuvenil\b",
    r"\bdivisi[oó]n de honor\b",
)

CYCLING_RE = rx(r"\bciclismo\b")
GOLF_RE = rx(r"\bgolf\b")


# ============================================================================
# REGEX DE PARSING Y FILTRADO
# ============================================================================

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")

# FutbolenTV publica la sesión de F1/MotoGP dentro de la propia fila.
MOTOR_ROW_SESSION_RE = re.compile(
    r"^(?:"
    r"libres(?:\s+[123])?|"
    r"pr[aá]ctica(?:\s+[123])?|"
    r"practice(?:\s+[123])?|"
    r"free\s+practice(?:\s+[123])?|"
    r"clasificaci[oó]n(?:\s+al\s+sprint)?|"
    r"qualifying(?:\s+sprint)?|"
    r"sprint|"
    r"carrera(?:\s+(?:al\s+)?sprint)?|"
    r"race|"
    r"warm\s*up"
    r")$",
    re.IGNORECASE,
)


def normalize_row_motor_session(value: str) -> str | None:
    text = normalize_search_text(value)

    if not MOTOR_ROW_SESSION_RE.fullmatch(text):
        return None

    if "warm up" in text or "warmup" in text:
        return "Warm Up"

    if "sprint" in text and ("clasific" in text or "qualifying" in text):
        return "Clasificación Sprint"

    if text == "sprint":
        return "Carrera al Sprint"

    if "carrera" in text or text == "race":
        return "Carrera"

    if "clasific" in text or "qualifying" in text:
        return "Clasificación"

    if (
        "libres" in text
        or "práctica" in text
        or "practice" in text
        or "free practice" in text
    ):
        return "Libres"

    return None

CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|ver partido",
    re.IGNORECASE,
)

PUNCTUATION_RE = re.compile(r"[\|,]+")
SPACES_RE = re.compile(r"\s+")


def normalize_search_text(text: str) -> str:
    """
    Normaliza texto procedente del widget para que las exclusiones sean
    independientes de variantes como ``1.ª``, ``1ª`` o espacios extra.
    """
    value = (text or "").lower()
    value = value.replace("º", "ª")
    value = re.sub(r"(?<=\d)\s*\.\s*(?=ª)", "", value)
    value = re.sub(r"(?<=\d)\s*ª", "ª", value)
    value = re.sub(r"[|,;:/]+", " ", value)
    value = SPACES_RE.sub(" ", value)
    return value.strip()

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|"
    r"teledeporte|tv|desport|disney\+?|disney)"
)

# Algunas cadenas llegan en una sola línea con un guion, por ejemplo:
# "Tennis Channel - Orange TV (131)". Ese guion NO separa jugadores/equipos.
# Se detectan primero estas líneas para que no terminen erróneamente como partido.
CHANNEL_LINE_RE = rx(
    r"\btennis\s+channel\b",
    r"\borange\s+tv\b",
    r"\bchannel\s*[-–—]\s*orange\s+tv\b",
)

# Deportes / competiciones completamente prohibidos.
# Estos eventos se eliminan antes de la clasificación y tampoco pueden
# aparecer accidentalmente en Favoritos.
EXCLUDED_SPORTS_RE = rx(
    r"\btorneo\s+betplay\s+dimayor\b",
    r"\bbetplay\s+dimayor\b",
    r"\bmls\b",
    r"\bnfl\b",
    r"\bncaa\b",
    r"\bufc\b",
    r"\bwnba\b",
    r"\bliga\s+u\b",
)


EXCLUDED_BLOB_RE = rx(
    # Exclusiones existentes
    r"preol[ií]mpico\s+femenino",
    r"nfl\s+pretemporada",
    r"f1\s+academy",
    r"tour\s+del\s+benelux",
    r"bundesliga\s+femenina",
    r"iaaf\s+diamond\s+league",
    r"national\s+league(?:\s+north|\s+south)?",
    r"eredivisie\s+vrouwen",
    r"europeo\s+femenino\s+sub-?16",
    r"segunda\s+federaci[oó]n",
    r"segunda\s+rfef",
    r"superliga\s+infantil",
    r"supercopa\s+lf\s+femenina",
    r"fifa\s+asean\s+cup",
    r"tercera\s+federaci[oó]n",
    r"liga\s+nacional\s+juvenil",
    r"copa\s+de\s+alemania\s+femenina",
    r"1\s*[ªa]\s+auton[oó]mica\s+juvenil",
    r"primera\s+auton[oó]mica\s+juvenil",

    # Nuevas exclusiones solicitadas
    r"ehf\s+(?:euro(?:pean)?\s+)?cup\s+women",
    # EHF European League y U20 Elite League se excluyen globalmente:
    # no aparecen en Otros, Favoritos ni en ninguna otra tarjeta.
    r"ehf\s+european\s+league",
    r"u20\s+elite\s+league",
    r"u-?20\s+elite\s+league",
    r"under[-\s]?20\s+elite\s+league",
    r"tour\s+de\s+croacia",
    r"gallagher\s+premiership",
    r"playa\s+del\s+carmen\s+open",
    r"gulf\s+cup\s+of\s+nations",
    r"primera\s+feb",
    r"copa\s+colombia",
    r"liga\s+auf\s+uruguaya",
    r"segunda\s+uruguay",
    r"liga\s+vasca\s+cadete",
    r"copa\s+rfef",
    r"laliga\s+futures",
    r"liga\s+u\b",
)

LIGAF_RE = rx(
    r"\bliga f\b",
    r"\bligaf\b",
    r"\bprimera division femenina\b",
    r"\bcopa de la reina\b",
)

PRIMERA_RFEF_RE = rx(
    r"\bprimera federaci[oó]n\b",
    r"\bprimera rfef\b",
)

CASTILLA_RE = rx(
    r"\breal madrid castilla\b",
    r"\brm castilla\b",
    r"\bcastilla\b",
)


# ============================================================================
# COMPETICIONES
# ============================================================================

FOOTBALL_COMPETITIONS = (
    (rx(r"\bchampions league\b", r"\bchampions\b"), "UEFA Champions League"),
    (rx(r"\beuropa league\b"), "UEFA Europa League"),
    (rx(r"\bconference league\b"), "UEFA Conference League"),
    (rx(r"\blaliga hypermotion\b"), "LaLiga Hypermotion"),
    (rx(r"\blaliga ea sports\b", r"\blaliga ea\b"), "LaLiga EA Sports"),
    (rx(r"\blaliga\b"), "LaLiga EA Sports"),
    (rx(r"\bpremier league\b"), "Premier League"),
    (rx(r"\bserie a\b"), "Serie A"),
    (rx(r"\bbundesliga\b"), "Bundesliga"),
    (rx(r"\bligue 1\b"), "Ligue 1"),
    (rx(r"\bcopa del rey\b"), "Copa del Rey"),
    (rx(r"\bcoppa italia\b"), "Coppa Italia"),
    (rx(r"\bliga f\b", r"\bligaf\b"), "Liga F"),
    (
        rx(r"\bdivisi[oó]n de honor\b", r"\bjuvenil\b"),
        "División de Honor Juvenil",
    ),
    (rx(r"\beredivisie\b"), "Eredivisie"),
    (
        rx(r"\bjupiler\b", r"\bjupiler pro league\b"),
        "Jupiler Pro League",
    ),
)


TENNIS_TOURNAMENT_RE = rx(
    # Torneos que pueden aparecer sin que el widget escriba
    # literalmente "tenis", "ATP" o "WTA".
    r"\btorneo\s+de\s+hangzhou\b",
    r"\bhangzhou\b",
    r"\btorneo\s+de\s+chengd[uú]\b",
    r"\bchengd[uú]\b",
    r"\btorneo\s+de\s+pe[kí]n\b",
    r"\bpe[kí]n\b",
    r"\bbeijing\b",
    r"\bchina\s+open\b",
    r"\btorneo\s+de\s+tokio\b",
    r"\btokio\b",
    r"\btokyo\b",
    r"\bjapan\s+open\b",
    r"\bwta\s+pe[kí]n\b",
    r"\bwta\s+beijing\b",
    r"\bwta\s+tokio\b",
    r"\bwta\s+tokyo\b",
    r"\bwta\s+\d{3}\b",
    r"\batp\s+\d{3}\b",
)


TENNIS_COMPETITIONS = (
    (rx(r"\bchina\s+open\b", r"\bbeijing\b", r"\bpe[kí]n\b"), "China Open"),
    (rx(r"\btorneo\s+de\s+tokio\b", r"\btokio\b", r"\btokyo\b", r"\bjapan\s+open\b"), "Japan Open"),
    (rx(r"\blaver cup\b"), "Laver Cup"),
    (
        rx(r"\bcopa davis\b", r"\bdavis cup\b", r"\bdavis\b"),
        "Copa Davis",
    ),
    (
        rx(r"\bbillie jean king cup\b"),
        "Billie Jean King Cup",
    ),
    (rx(r"\bus open\b"), "US Open"),
    (rx(r"\bwimbledon\b"), "Wimbledon"),
    (rx(r"\broland garros\b"), "Roland Garros"),
    (rx(r"\bopen de australia\b"), "Open de Australia"),
    (
        rx(r"\bmadrid open\b", r"\bmutua madrid open\b"),
        "Madrid Open",
    ),
    (
        rx(
            r"\bmasters de roma\b",
            r"\brome masters\b",
            r"\binternazionali d'italia\b",
        ),
        "Masters de Roma",
    ),
)


# ============================================================================
# CONSTANTES
# ============================================================================

GENERIC_TOURNAMENTS = frozenset({
    "",
    "competición",
    "fútbol",
    "futbol",
    "baloncesto",
    "basket",
    "tenis",
    "atp",
    "wta",
    "hockey",
    "fútbol sala",
    "futbol sala",
    "futsal",
    "balonmano",
    "handball",
    "asobal",
    "fih",
    "ciclismo",
    "motor",
})


# Se construye después de tener EXCLUDED_CHANNELS definida.
EXCLUDED_CHANNELS_RE = rx(
    *(re.escape(channel) for channel in EXCLUDED_CHANNELS)
)

# Variantes de canales que pueden llegar con espacios, mayúsculas o texto
# adicional entre paréntesis.
EXCLUDED_CHANNEL_PATTERNS_RE = rx(
    r"\btv3\s*\(?(?:catalu(?:n|ñ)a)\)?\b",
    r"\btvg\s*\(?(?:galicia)\)?\b",
    r"\barag[oó]n\s+(?:tv|play)\b",
    r"\bfff\s+tv\s+youtube\b",
    r"\buefa\s+youtube\b",
    r"\bsefutbol\s+youtube\b",
    r"\btv\s+footballclub\b",
    r"\bfanplay\b",
    r"\bred\s+bull\s+tv\b",
    r"\bhbo\s+max\b",
)


# ============================================================================
# UTILIDADES
# ============================================================================

def contains(pattern: re.Pattern, text: str) -> bool:
    """Devuelve True si el patrón aparece en el texto."""
    return bool(pattern.search(text))


def is_excluded_event(blob: str) -> bool:
    """
    Devuelve True si el evento pertenece a una competición que no debe
    aparecer en ninguna tarjeta de la agenda.

    Se comprueba el texto normalizado para cubrir variantes del widget,
    especialmente ``1.ª Autonómica Juvenil`` / ``1ª Autonómica Juvenil``.
    """
    normalized = normalize_search_text(blob)

    if EXCLUDED_SPORTS_RE.search(normalized):
        return True

    if EXCLUDED_BLOB_RE.search(normalized):
        return True

    # Exclusiones críticas con variantes de escritura especialmente comunes.
    return bool(
        re.search(r"\bsuperliga\s+infantil\b", normalized, re.IGNORECASE)
        or re.search(
            r"\b(?:1\s*ª\.?|primera)\s+auton[oó]mica\s+juvenil\b",
            normalized,
            re.IGNORECASE,
        )
    )


def clean_tournament(raw: str, fallback: str) -> str:
    """
    Limpia el nombre de competición y utiliza un valor alternativo
    si el nombre original es demasiado genérico.
    """
    value = (raw or "").strip()

    if (
        len(value.lower()) > 2
        and value.lower() not in GENERIC_TOURNAMENTS
    ):
        return value

    return fallback


def is_womens_champions(blob: str) -> bool:
    """
    Detecta UEFA Women's Champions League.
    """
    return (
        ("champions" in blob or "uwcl" in blob)
        and any(
            word in blob
            for word in ("femenina", "femenino", "women")
        )
    )


def first_match(
    text: str,
    rules: Iterable[tuple[re.Pattern, str]],
) -> str | None:
    """
    Devuelve el primer valor cuyo patrón coincida.
    """
    for pattern, value in rules:
        if pattern.search(text):
            return value

    return None


# ============================================================================
# CLASIFICACIÓN DE TENIS
# ============================================================================

def classify_tennis(
    blob: str,
    raw_tournament: str,
    tv_blob: str,
) -> str:
    """
    Determina la competición de un evento de tenis.
    """

    # La competición puede venir separada del evento en el widget.
    # Por eso se busca tanto en el texto reconstruido como en el nombre
    # original de la competición.
    tennis_text = normalize_search_text(
        f"{blob} {raw_tournament} {tv_blob}"
    )

    competition = first_match(
        tennis_text,
        TENNIS_COMPETITIONS,
    )

    if competition:
        if competition in {
            "Copa Davis",
            "Billie Jean King Cup",
        }:
            return competition

        # Laver Cup es un torneo masculino.
        if competition == "Laver Cup":
            return "ATP Laver Cup"

        tour = (
            "WTA"
            if "wta" in blob or "wta" in tv_blob
            else "ATP"
        )

        return f"{tour} {competition}"

    raw = (raw_tournament or "").strip()
    raw_normalized = normalize_search_text(raw)

    if re.search(r"\b(?:torneo\s+de\s+)?pe[kí]n\b|\bbeijing\b|\bchina\s+open\b", raw_normalized):
        return "WTA China Open" if "wta" in tennis_text else "ATP China Open"

    if re.search(r"\b(?:torneo\s+de\s+)?tokio\b|\btokyo\b|\bjapan\s+open\b", raw_normalized):
        return "WTA Japan Open" if "wta" in tennis_text else "ATP Japan Open"

    if re.search(r"\bwta\b", raw_normalized) or "wta" in tennis_text:
        return clean_tournament(raw, "WTA Tour")

    if re.search(r"\batp\b", raw_normalized) or "atp" in tennis_text:
        return clean_tournament(raw, "ATP Tour")

    return clean_tournament(
        raw,
        "WTA Tour" if "wta" in tennis_text else "ATP Tour",
    )


# ============================================================================
# CLASIFICACIÓN DE BALONCESTO
# ============================================================================

def classify_basketball(
    blob: str,
    raw_tournament: str,
) -> str:

    if "euroliga" in blob or "euroleague" in blob:
        return "Euroliga"

    if "nba" in blob:
        return "NBA"

    if "acb" in blob or "liga endesa" in blob:
        return "Liga Endesa"

    if "fiba" in blob or "mundial" in blob:
        return "FIBA Copa Mundial"

    if "jjoo" in blob:
        return "JJOO Baloncesto"

    return clean_tournament(
        raw_tournament,
        "Baloncesto",
    )


# ============================================================================
# CALENDARIOS OFICIALES DE MOTOR
# ============================================================================

MOTOGP_OFFICIAL_CALENDAR_URL = "https://www.motogp.com/es/calendar"
F1_OFFICIAL_CALENDAR_URL = "https://www.formula1.com/en/racing/2026"

# F1 mantiene una URL por Gran Premio. Las fechas y sesiones se comprueban
# contra la web oficial en cada ejecución; este mapa solo sirve para localizar
# la página oficial del GP correspondiente al día actual.
F1_ROUND_SLUGS_2026 = {
    "australia": "australia",
    "china": "china",
    "japan": "japan",
    "bahrain": "bahrain",
    "saudi arabia": "saudiarabia",
    "miami": "miami",
    "canada": "canada",
    "monaco": "monaco",
    "barcelona-catalunya": "spain",
    "spain": "spain",
    "austria": "austria",
    "great britain": "great-britain",
    "belgium": "belgium",
    "hungary": "hungary",
    "netherlands": "netherlands",
    "italy": "italy",
    "azerbaijan": "azerbaijan",
    "singapore": "singapore",
    "united states": "united-states",
    "mexico": "mexico",
    "brazil": "brazil",
    "las vegas": "las-vegas",
    "qatar": "qatar",
    "abu dhabi": "abu-dhabi",
}

# Zonas horarias de los circuitos. La web oficial publica los horarios en
# hora local del circuito; se convierten a la hora local del equipo/agenda.
F1_TRACK_TIMEZONES = {
    "australia": "Australia/Melbourne",
    "china": "Asia/Shanghai",
    "japan": "Asia/Tokyo",
    "bahrain": "Asia/Bahrain",
    "saudi arabia": "Asia/Riyadh",
    "miami": "America/New_York",
    "canada": "America/Toronto",
    "monaco": "Europe/Monaco",
    "barcelona-catalunya": "Europe/Madrid",
    "spain": "Europe/Madrid",
    "austria": "Europe/Vienna",
    "great britain": "Europe/London",
    "belgium": "Europe/Brussels",
    "hungary": "Europe/Budapest",
    "netherlands": "Europe/Amsterdam",
    "italy": "Europe/Rome",
    "azerbaijan": "Asia/Baku",
    "singapore": "Asia/Singapore",
    "united states": "America/Chicago",
    "mexico": "America/Mexico_City",
    "brazil": "America/Sao_Paulo",
    "las vegas": "America/Los_Angeles",
    "qatar": "Asia/Qatar",
    "abu dhabi": "Asia/Dubai",
}

MOTOGP_COUNTRY_TIMEZONES = {
    "thailand": "Asia/Bangkok",
    "brazil": "America/Sao_Paulo",
    "usa": "America/Chicago",
    "united states": "America/Chicago",
    "spain": "Europe/Madrid",
    "catalonia": "Europe/Madrid",
    "france": "Europe/Paris",
    "italy": "Europe/Rome",
    "hungary": "Europe/Budapest",
    "czechia": "Europe/Prague",
    "netherlands": "Europe/Amsterdam",
    "germany": "Europe/Berlin",
    "great britain": "Europe/London",
    "aragon": "Europe/Madrid",
    "san marino": "Europe/Rome",
    "austria": "Europe/Vienna",
    "japan": "Asia/Tokyo",
    "indonesia": "Asia/Jakarta",
    "australia": "Australia/Melbourne",
    "malaysia": "Asia/Kuala_Lumpur",
    "qatar": "Asia/Qatar",
    "portugal": "Europe/Lisbon",
}

MOTOR_SESSION_LABELS = {
    "practice 1": "Libres",
    "practice 2": "Libres",
    "practice 3": "Libres",
    "free practice 1": "Libres",
    "free practice 2": "Libres",
    "free practice 3": "Libres",
    "free practice nr. 1": "Libres",
    "free practice nr. 2": "Libres",
    "practice": "Libres",
    "fp1": "Libres",
    "fp2": "Libres",
    "fp3": "Libres",
    "sprint qualifying": "Clasificación Sprint",
    "qualifying": "Clasificación",
    "qualifying nr. 1": "Clasificación",
    "qualifying nr. 2": "Clasificación",
    "qualifying session": "Clasificación",
    "sprint": "Carrera al Sprint",
    "tissot sprint": "Carrera al Sprint",
    "grand prix": "Carrera",
    "race": "Carrera",
    "warm up": "Warm Up",
}

OFFICIAL_MOTOR_SESSIONS = None

# Horarios oficiales del fin de semana actual (02-04/10/2026), expresados
# en hora de España. Se usan únicamente como respaldo si la web oficial no
# puede ser consultada o si su vista de horarios no coincide con la del widget.
CURRENT_MOTOR_FALLBACK_SESSIONS = {
    "2026-10-02": {
        # F1: Sepang 12:30/16:00 local = 06:30/10:00 España.
        "06:30": "Libres",
        "10:00": "Libres",
        # MotoGP Motegi (horarios mostrados por MotoGP en la zona del usuario).
        "01:45": "Libres",
        "06:00": "Libres",
    },
    "2026-10-03": {
        "01:10": "Libres",
        "01:50": "Clasificación",
        "02:15": "Clasificación",
        "06:00": "Carrera al Sprint",
        "06:30": "Libres",
        "10:00": "Clasificación",
    },
    "2026-10-04": {
        "00:40": "Warm Up",
        "05:00": "Carrera",
        "09:00": "Carrera",
    },
}


def _parse_hhmm(value: str) -> tuple[int, int] | None:
    match = re.search(r"\b(\d{1,2}):(\d{2})\b", value or "")
    if not match:
        return None
    return int(match.group(1)), int(match.group(2))


def _localize_official_time(
    date_value: datetime,
    hour: int,
    minute: int,
    source_timezone: str,
) -> tuple[datetime.date, int, int]:
    source = ZoneInfo(source_timezone)
    target = ZoneInfo("Europe/Madrid")
    local_dt = datetime(
        date_value.year,
        date_value.month,
        date_value.day,
        hour,
        minute,
        tzinfo=source,
    ).astimezone(target)
    return local_dt.date(), local_dt.hour, local_dt.minute


def _official_session_from_time(
    sessions: list[dict],
    event_time: str,
) -> str | None:
    """
    Busca la sesión cuyo horario oficial coincide con la hora del widget.
    Se permite una pequeña tolerancia porque las fuentes pueden redondear
    los horarios o presentar la emisión unos minutos antes/después.
    """
    parsed = _parse_hhmm(event_time)
    if parsed is None:
        return None

    event_minutes = parsed[0] * 60 + parsed[1]
    best = None
    best_delta = 999

    for session in sessions:
        if session.get("date") != datetime.now().date():
            continue

        session_minutes = (
            session["hour"] * 60 + session["minute"]
        )
        delta = abs(event_minutes - session_minutes)

        if delta <= 20 and delta < best_delta:
            best = session["label"]
            best_delta = delta

    return best


def _find_f1_round_for_today(today: datetime.date) -> tuple[str, str] | None:
    """
    Determina el GP de F1 que contiene la fecha actual.
    """
    # Fechas oficiales de los fines de semana de 2026. La sesión concreta
    # siempre se obtiene después desde la página oficial del GP.
    rounds = (
        ("australia", "2026-03-06", "2026-03-08"),
        ("china", "2026-03-13", "2026-03-15"),
        ("japan", "2026-03-27", "2026-03-29"),
        ("bahrain", "2026-04-10", "2026-04-12"),
        ("saudi arabia", "2026-04-17", "2026-04-19"),
        ("miami", "2026-05-01", "2026-05-03"),
        ("canada", "2026-05-22", "2026-05-24"),
        ("monaco", "2026-06-05", "2026-06-07"),
        ("barcelona-catalunya", "2026-06-12", "2026-06-14"),
        ("austria", "2026-06-26", "2026-06-28"),
        ("great britain", "2026-07-03", "2026-07-05"),
        ("belgium", "2026-07-17", "2026-07-19"),
        ("hungary", "2026-07-24", "2026-07-26"),
        ("netherlands", "2026-08-21", "2026-08-23"),
        ("italy", "2026-09-04", "2026-09-06"),
        ("spain", "2026-09-11", "2026-09-13"),
        ("azerbaijan", "2026-09-24", "2026-09-26"),
        ("bahrain", "2026-10-02", "2026-10-04"),
        ("singapore", "2026-10-09", "2026-10-11"),
        ("united states", "2026-10-23", "2026-10-25"),
        ("mexico", "2026-10-30", "2026-11-01"),
        ("brazil", "2026-11-06", "2026-11-08"),
        ("las vegas", "2026-11-19", "2026-11-21"),
        ("qatar", "2026-11-27", "2026-11-29"),
        ("abu dhabi", "2026-12-04", "2026-12-06"),
    )

    for name, start, end in rounds:
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
        if start_date <= today <= end_date:
            slug = F1_ROUND_SLUGS_2026.get(name)
            timezone = F1_TRACK_TIMEZONES.get(name)
            if slug and timezone:
                return slug, timezone

    return None


def _fetch_f1_official_sessions() -> list[dict]:
    today = datetime.now().date()
    round_info = _find_f1_round_for_today(today)

    if not round_info:
        return []

    slug, timezone = round_info
    url = f"https://www.formula1.com/en/racing/2026/{slug}"

    try:
        response = requests.get(
            url,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        text = BeautifulSoup(
            response.text,
            "html.parser",
        ).get_text(" ", strip=True)

        # En 2026 el contenido oficial del GP de Bahréin puede referirse al
        # trazado de Sepang (Malasia); en ese caso la zona horaria correcta es
        # la de Kuala Lumpur.
        if "sepang" in text.lower():
            timezone = "Asia/Kuala_Lumpur"

        pattern = re.compile(
            r"\b(\d{1,2})\s+([A-Za-z]{3})\s+"
            r"(Practice 1|Practice 2|Practice 3|Sprint Qualifying|"
            r"Sprint|Qualifying|Race)\s+"
            r"(\d{1,2}:\d{2})",
            re.IGNORECASE,
        )

        month_map = {
            "jan": 1, "feb": 2, "mar": 3, "apr": 4,
            "may": 5, "jun": 6, "jul": 7, "aug": 8,
            "sep": 9, "oct": 10, "nov": 11, "dec": 12,
        }

        sessions = []

        for match in pattern.finditer(text):
            day = int(match.group(1))
            month = month_map.get(match.group(2).lower())
            if month is None:
                continue

            hhmm = _parse_hhmm(match.group(4))
            if hhmm is None:
                continue

            date_value = datetime(
                today.year,
                month,
                day,
            )

            local_date, hour, minute = _localize_official_time(
                date_value,
                hhmm[0],
                hhmm[1],
                timezone,
            )

            if local_date != today:
                continue

            raw_label = match.group(3).lower()
            label = MOTOR_SESSION_LABELS.get(raw_label)

            if label:
                sessions.append({
                    "date": local_date,
                    "hour": hour,
                    "minute": minute,
                    "label": label,
                })

                # Algunas vistas oficiales entregan la columna "My time"
                # en UTC cuando se consultan sin navegador. Añadimos también
                # esa interpretación para que el cruce siga funcionando.
                utc_date, utc_hour, utc_minute = _localize_official_time(
                    date_value,
                    hhmm[0],
                    hhmm[1],
                    "UTC",
                )

                if (utc_date, utc_hour, utc_minute) != (
                    local_date, hour, minute
                ):
                    sessions.append({
                        "date": utc_date,
                        "hour": utc_hour,
                        "minute": utc_minute,
                        "label": label,
                    })

        return sessions

    except requests.RequestException as error:
        print(
            "Advertencia: no se pudo consultar el calendario oficial de F1: "
            f"{error}"
        )

    except Exception as error:
        print(
            "Advertencia: error leyendo el calendario oficial de F1: "
            f"{error}"
        )

    return []


def _fetch_motogp_official_sessions() -> list[dict]:
    try:
        response = requests.get(
            MOTOGP_OFFICIAL_CALENDAR_URL,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )
        response.raise_for_status()

        text = BeautifulSoup(
            response.text,
            "html.parser",
        ).get_text(" ", strip=True)

        # La página oficial muestra el programa del GP actual con entradas
        # como "FRI/ 01:45 Free Practice Nr. 1" y "SUN/ 05:00 Grand Prix".
        weekday_map = {
            "fri": 0,
            "sat": 1,
            "sun": 2,
        }

        today = datetime.now().date()
        weekday_today = today.weekday()

        current_week_start = today - __import__("datetime").timedelta(
            days=max(0, weekday_today - 4)
        )

        # Identificar la zona horaria del GP actual por el nombre del país.
        timezone = "Europe/Madrid"
        country_timezone_candidates = (
            ("japan", "Asia/Tokyo"),
            ("japón", "Asia/Tokyo"),
            ("indonesia", "Asia/Jakarta"),
            ("australia", "Australia/Melbourne"),
            ("malaysia", "Asia/Kuala_Lumpur"),
            ("qatar", "Asia/Qatar"),
            ("thailand", "Asia/Bangkok"),
            ("brazil", "America/Sao_Paulo"),
            ("france", "Europe/Paris"),
            ("italy", "Europe/Rome"),
            ("hungary", "Europe/Budapest"),
            ("czechia", "Europe/Prague"),
            ("netherlands", "Europe/Amsterdam"),
            ("germany", "Europe/Berlin"),
            ("great britain", "Europe/London"),
            ("austria", "Europe/Vienna"),
            ("portugal", "Europe/Lisbon"),
            ("spain", "Europe/Madrid"),
            ("aragon", "Europe/Madrid"),
            ("catalonia", "Europe/Madrid"),
            ("san marino", "Europe/Rome"),
            ("usa", "America/Chicago"),
        )

        text_lower = text.lower()
        for country, tz_name in country_timezone_candidates:
            if country in text_lower:
                timezone = tz_name
                break

        pattern = re.compile(
            r"(?:fri|sat|sun)\/\s*(\d{1,2}:\d{2})\s+"
            r"(Free Practice Nr\.\s*[12]|Free Practice|Practice|"
            r"Qualifying Nr\.\s*[12]|Qualifying|Tissot Sprint|"
            r"Sprint|Warm Up|Grand Prix)",
            re.IGNORECASE,
        )

        # También se acepta el formato español/alternativo que aparece en
        # algunas versiones de la página oficial.
        pattern_alt = re.compile(
            r"(?:FRI|SAT|SUN)[^0-9]{0,8}(\d{1,2}:\d{2})[^A-Za-z]{1,8}"
            r"(Free Practice[^|]+?|Practice|Qualifying[^|]+?|"
            r"Tissot Sprint|Sprint|Warm Up|Grand Prix)",
            re.IGNORECASE,
        )

        sessions = []

        def add_session(weekday_text, hhmm_text, raw_name):
            weekday = weekday_map.get(weekday_text.lower())
            if weekday is None:
                return

            target_date = current_week_start + __import__("datetime").timedelta(
                days=weekday
            )
            if target_date != today:
                return

            hhmm = _parse_hhmm(hhmm_text)
            if hhmm is None:
                return

            local_date, hour, minute = _localize_official_time(
                datetime(
                    target_date.year,
                    target_date.month,
                    target_date.day,
                ),
                hhmm[0],
                hhmm[1],
                timezone,
            )

            raw = normalize_search_text(raw_name)
            raw = raw.replace("n.º", "nr.")
            raw = raw.replace("nº", "nr.")

            if "tissot sprint" in raw or raw == "sprint":
                label = "Carrera al Sprint"
            elif "grand prix" in raw:
                label = "Carrera"
            elif "qualifying" in raw:
                label = "Clasificación"
            elif "warm up" in raw:
                label = "Warm Up"
            elif "practice" in raw or "free practice" in raw:
                label = "Libres"
            else:
                return

            sessions.append({
                "date": local_date,
                "hour": hour,
                "minute": minute,
                "label": label,
            })

        for match in pattern.finditer(text):
            prefix = text[max(0, match.start() - 8):match.start()].lower()
            weekday_match = re.search(r"(fri|sat|sun)\/", prefix)
            if weekday_match:
                add_session(
                    weekday_match.group(1),
                    match.group(1),
                    match.group(2),
                )

        return sessions

    except requests.RequestException as error:
        print(
            "Advertencia: no se pudo consultar el calendario oficial de MotoGP: "
            f"{error}"
        )

    except Exception as error:
        print(
            "Advertencia: error leyendo el calendario oficial de MotoGP: "
            f"{error}"
        )

    return []


def load_official_motor_sessions() -> list[dict]:
    """
    Consulta las páginas oficiales una sola vez por ejecución.
    """
    global OFFICIAL_MOTOR_SESSIONS

    if OFFICIAL_MOTOR_SESSIONS is not None:
        return OFFICIAL_MOTOR_SESSIONS

    sessions = []
    sessions.extend(_fetch_f1_official_sessions())
    sessions.extend(_fetch_motogp_official_sessions())

    OFFICIAL_MOTOR_SESSIONS = sessions
    return sessions


def infer_motor_session_from_text(
    blob: str,
    event: str = "",
    tournament: str = "",
) -> str | None:
    """Detecta la sesión cuando el widget la incluye en cualquiera de sus campos."""
    text = normalize_search_text(f"{blob} {event} {tournament}")

    # El orden evita que "sprint qualifying" se clasifique como sprint.
    if re.search(r"\bsprint\s+qualifying\b|\bqualifying\s+sprint\b", text):
        return "Clasificación Sprint"
    if re.search(r"\btissot\s+sprint\b|\bsprint\b|\bcarrera\s+al\s+sprint\b", text):
        return "Carrera al Sprint"
    if re.search(r"\bgrand\s+prix\b|\brace\b|\bcarrera\b", text):
        return "Carrera"
    if re.search(r"\bqualifying\b|\bclasificaci[oó]n\b", text):
        return "Clasificación"
    if re.search(r"\bfree\s+practice\b|\bpractice\b|\blibres\b|\bfp[123]\b|\bentrenamientos?\b", text):
        return "Libres"
    if re.search(r"\bwarm\s*up\b|\bwarmup\b", text):
        return "Warm Up"
    return None


def get_motor_session(
    sport: str,
    competition: str,
    event_time: str,
    blob: str = "",
    event: str = "",
    tournament: str = "",
) -> str | None:
    """
    Devuelve la sesión del evento. Primero usa el texto real del widget y,
    si este no contiene la sesión, cruza la hora con el calendario oficial.
    """
    if competition not in {"Fórmula 1", "MotoGP"}:
        return None

    direct = infer_motor_session_from_text(blob, event, tournament)
    if direct:
        return direct

    # Respaldo del fin de semana actual para evitar que una diferencia de
    # formato/huso horario de la web oficial deje sesiones sin etiqueta.
    today_key = datetime.now().strftime("%Y-%m-%d")
    fallback = CURRENT_MOTOR_FALLBACK_SESSIONS.get(today_key, {})
    if event_time in fallback:
        return fallback[event_time]

    return _official_session_from_time(
        load_official_motor_sessions(),
        event_time,
    )


# ============================================================================
# CLASIFICACIÓN DE MOTOR
# ============================================================================

def classify_motor(
    blob: str,
    raw_tournament: str,
) -> str:

    # Orden deliberado para evitar que Moto2/Moto3
    # sean absorbidas por MotoGP.

    if (
        "fórmula 1" in blob
        or F1_RE.search(blob)
    ) and "academy" not in blob:
        return "Fórmula 1"

    if (
        "fórmula 2" in blob
        or F2_RE.search(blob)
    ):
        return "Fórmula 2"

    if (
        "fórmula 3" in blob
        or F3_RE.search(blob)
    ):
        return "Fórmula 3"

    if (
        "motogp" in blob
        and not MOTO2_RE.search(blob)
        and not MOTO3_RE.search(blob)
        and "rookies" not in blob
    ):
        return "MotoGP"

    if MOTO2_RE.search(blob):
        return "Moto2"

    if MOTO3_RE.search(blob):
        return "Moto3"

    if "formula e" in blob or "fórmula e" in blob:
        return "Fórmula E"

    if "indycar" in blob or "indy car" in blob:
        return "IndyCar"

    if "nascar" in blob:
        return "NASCAR"

    return clean_tournament(
        raw_tournament,
        "Motor",
    )


# ============================================================================
# CLASIFICACIÓN GENERAL
# ============================================================================

def get_sport_and_competition(
    blob: str,
    raw_tournament: str,
    tv_blob: str,
) -> tuple[str, str, str]:
    """
    Clasifica un evento.

    El orden es deliberado y mantiene la prioridad del
    clasificador original.
    """

    # Nunca clasificar una competición que esté en la lista negra.
    if is_excluded_event(blob):
        return (
            "__EXCLUDED__",
            "",
            "",
        )

    tournament = raw_tournament or ""

    # ------------------------------------------------------------------------
    # Rugby
    #
    # "División de Honor" es ambiguo: también aparece en fútbol juvenil.
    # Por eso el rugby se comprueba antes del bloque prioritario de fútbol.
    # ------------------------------------------------------------------------

    if contains(RUGBY_RE, blob):
        return (
            "Otros",
            "🏉",
            clean_tournament(
                tournament,
                "Rugby",
            ),
        )

    # ------------------------------------------------------------------------
    # Casos prioritarios de fútbol
    # ------------------------------------------------------------------------

    if is_womens_champions(blob):
        return (
            "Fútbol",
            "⚽",
            tournament or "UEFA Women's Champions League",
        )

    if (
        "juvenil" in blob
        or "división de honor" in blob
        or "division de honor" in blob
    ):
        return (
            "Fútbol",
            "⚽",
            tournament or "División de Honor Juvenil",
        )

    # ------------------------------------------------------------------------
    # Deportes específicos
    # ------------------------------------------------------------------------

    if contains(BASKET_RE, blob):
        return (
            "Baloncesto",
            "🏀",
            classify_basketball(blob, tournament),
        )

    if contains(HOCKEY_RE, blob):
        return (
            "Otros",
            "🎯",
            clean_tournament(
                tournament,
                "Hockey (FIH)",
            ),
        )

    if contains(FUTSAL_RE, blob):
        competition = (
            "Liga Prime"
            if "prime" in blob
            else clean_tournament(
                tournament,
                "Fútbol Sala",
            )
        )

        return (
            "Otros",
            "🎯",
            competition,
        )

    if contains(HANDBALL_RE, blob):
        competition = (
            "Liga ASOBAL"
            if "asobal" in blob
            else clean_tournament(
                tournament,
                "Balonmano",
            )
        )

        return (
            "Otros",
            "🎯",
            competition,
        )

    # ------------------------------------------------------------------------
    # TENIS
    #
    # Importante:
    # Un evento puede ser identificado como tenis aunque el texto no
    # contenga literalmente "tenis", por ejemplo:
    #   Carlos Alcaraz
    #   Rafa Jódar
    #   Laver Cup
    # ------------------------------------------------------------------------

    if (
        contains(TENNIS_RE, blob)
        or contains(TENNIS_PLAYERS_RE, blob)
        or contains(TENNIS_TOURNAMENT_RE, tournament)
    ):
        return (
            "Tenis",
            "🎾",
            classify_tennis(
                blob,
                tournament,
                tv_blob,
            ),
        )

    # ------------------------------------------------------------------------
    # Fútbol
    # ------------------------------------------------------------------------

    football_competition = first_match(
        blob,
        FOOTBALL_COMPETITIONS,
    )

    if football_competition:
        return (
            "Fútbol",
            "⚽",
            football_competition,
        )

    if contains(FOOTBALL_RE, blob):
        return (
            "Fútbol",
            "⚽",
            clean_tournament(
                tournament,
                "Fútbol",
            ),
        )

    # ------------------------------------------------------------------------
    # Femenino genérico
    # ------------------------------------------------------------------------

    if (
        contains(WOMEN_RE, blob)
        and not contains(REAL_MADRID_RE, blob)
    ):
        return (
            "Otros",
            "🎯",
            clean_tournament(
                tournament,
                "Fútbol Femenino",
            ),
        )

    # ------------------------------------------------------------------------
    # Ciclismo
    # ------------------------------------------------------------------------

    if contains(CYCLING_RE, blob):
        return (
            "Ciclismo",
            "🚴‍♂️",
            clean_tournament(
                tournament,
                "Ciclismo",
            ),
        )

    # ------------------------------------------------------------------------
    # Motor
    # ------------------------------------------------------------------------

    if contains(MOTOR_GENERAL_RE, blob):
        return (
            "Motor",
            "🏎️",
            classify_motor(
                blob,
                tournament,
            ),
        )

    # ------------------------------------------------------------------------
    # Fallback
    # ------------------------------------------------------------------------

    return (
        "Otros",
        "🎯",
        clean_tournament(
            tournament,
            "Evento Deportivo",
        ),
    )


# ============================================================================
# FILTRADO DE FAVORITOS
# ============================================================================

def matches_strict_criteria(
    blob: str,
    channels: list[str],
    sport: str = "",
    competition: str = "",
    event_time: str = "",
    motor_session: str = "",
) -> bool:
    """
    Determina si el evento debe aparecer como filtrado/favorito.
    """

    # ------------------------------------------------------------------------
    # Competiciones excluidas: nunca entran en favoritos.
    #
    # Esta comprobación debe ir ANTES de la prioridad de Real Madrid para
    # garantizar que una competición excluida no reaparezca en Favoritos.
    # ------------------------------------------------------------------------

    if is_excluded_event(blob):
        return False

    # ------------------------------------------------------------------------
    # Real Madrid: prioridad absoluta dentro de las competiciones permitidas.
    # ------------------------------------------------------------------------

    if contains(REAL_MADRID_RE, blob):
        return True

    # ------------------------------------------------------------------------
    # Canales excluidos.
    # ------------------------------------------------------------------------

    if any(
        EXCLUDED_CHANNELS_RE.search(channel)
        or EXCLUDED_CHANNEL_PATTERNS_RE.search(channel)
        for channel in channels
    ):
        return False

    # ------------------------------------------------------------------------
    # Motor.
    #
    # Para F1 y MotoGP se utiliza el calendario oficial. Solo pasan a
    # Favoritos Clasificación, Sprint y Carrera. Los entrenamientos y Warm Up
    # siguen visibles en Motor, pero no en Favoritos.
    # ------------------------------------------------------------------------

    if competition in {"Fórmula 1", "MotoGP"}:
        session = motor_session or get_motor_session(
            sport,
            competition,
            event_time,
            blob=blob,
        )

        if session not in {
            "Clasificación",
            "Carrera al Sprint",
            "Carrera",
        }:
            return False

    if contains(MOTO_STRICT_EXCLUDE_RE, blob):
        return False

    # ------------------------------------------------------------------------
    # Competiciones excluidas.
    # ------------------------------------------------------------------------

    if is_excluded_event(blob):
        return False

    # ------------------------------------------------------------------------
    # El fútbol sala no entra en favoritos.
    # ------------------------------------------------------------------------

    if (
        sport == "Otros"
        and contains(FUTSAL_RE, blob)
    ):
        return False

    # ------------------------------------------------------------------------
    # Femenino.
    # ------------------------------------------------------------------------

    if (
        is_womens_champions(blob)
        or contains(WOMEN_RE, blob)
    ):
        return False

    # ------------------------------------------------------------------------
    # Baloncesto español.
    # ------------------------------------------------------------------------

    if contains(BASKET_RE, blob):
        return (
            "españa" in blob
            or "spain" in blob
        )

    # ------------------------------------------------------------------------
    # Tenistas favoritos.
    #
    # Aquí entran específicamente Alcaraz, Jódar, etc.
    # ------------------------------------------------------------------------

    if contains(TENNIS_PLAYERS_RE, blob):
        return True

    # ------------------------------------------------------------------------
    # Selección española en UEFA Nations League.
    # ------------------------------------------------------------------------

    if (
        (
            "nations league" in blob
            or "uefa nations league" in blob
        )
        and (
            "españa" in blob
            or "spain" in blob
            or "selección española" in blob
        )
    ):
        return True

    # ------------------------------------------------------------------------
    # Davis / Billie Jean King con España.
    # ------------------------------------------------------------------------

    if (
        (
            "billie jean king cup" in blob
            or "copa davis" in blob
            or "davis cup" in blob
        )
        and "españa" in blob
    ):
        return True

    # ------------------------------------------------------------------------
    # Motor y fútbol destacado.
    # ------------------------------------------------------------------------

    return (
        contains(MOTOR_SERIES_RE, blob)
        or contains(SPANISH_BIG_THREE_RE, blob)
        or contains(TOP3_FOREIGN_RE, blob)
    )


# ============================================================================
# PARSING DEL WIDGET
# ============================================================================

def parse_row_elements(
    item,
) -> tuple[str, str, list[str], str, str]:
    """
    Extrae hora, evento, canales y competición del nodo HTML.

    La detección de competiciones de tenis tiene prioridad sobre el fallback
    para evitar que nombres como "Torneo de Tokio" o "WTA Pekín" terminen
    accidentalmente en la columna Evento / Partido.
    """

    text_full = item.get_text(" | ", strip=True)

    time_match = TIME_RE.search(text_full)
    time_clean = time_match.group(0) if time_match else ""

    raw_parts = [
        part.strip()
        for part in item.get_text("\n", strip=True).split("\n")
        if part.strip()
    ]

    if not 2 <= len(raw_parts) <= 15:
        return "", "", [], ""

    matchup = ""
    channels: list[str] = []
    tournament = ""
    motor_session = ""
    non_tournament_parts: list[str] = []

    for part in raw_parts:
        part_lower = normalize_search_text(part)

        if (
            TIME_RE.match(part)
            or part_lower in {"ver partido", "directo", "(ver en directo)"}
        ):
            continue

        has_tv_identifier = bool(TV_IDENTIFIERS_RE.search(part))

        # Algunas cadenas contienen un guion interno, por ejemplo:
        # "Tennis Channel - Orange TV (131)". Deben procesarse como canal
        # antes de la detección genérica de enfrentamientos.
        is_channel_line = bool(CHANNEL_LINE_RE.search(part_lower))

        # ------------------------------------------------------------
        # SESIÓN DE MOTOR
        # ------------------------------------------------------------
        detected_session = normalize_row_motor_session(part)
        if detected_session:
            if not motor_session:
                motor_session = detected_session
            continue

        # ------------------------------------------------------------
        # COMPETICIÓN DE TENIS
        # ------------------------------------------------------------
        # Importante: "Torneo de Tokio", "Torneo de Pekín", "WTA Pekín",
        # "China Open", etc. son competición, nunca el partido.
        if (
            TENNIS_TOURNAMENT_RE.search(part_lower)
            or WTA_RE.search(part_lower)
            or ATP_RE.search(part_lower)
        ):
            if not tournament:
                tournament = part
            continue

        # ------------------------------------------------------------
        # CANALES
        # ------------------------------------------------------------
        if has_tv_identifier:
            # "Tennis Channel - Orange TV (131)" es una línea de canal,
            # aunque contenga " - ". Para el resto mantenemos la prioridad
            # del enfrentamiento, evitando romper casos como
            # "Jaén FS - Movistar Inter".
            if (
                not is_channel_line
                and re.search(
                    r"\s-\s|\s+vs\.?\s+|\s+v\.\s+",
                    part,
                    re.IGNORECASE,
                )
            ):
                if not matchup:
                    matchup = part
                continue

            clean_part = CLEAN_TV_RE.sub("", part).strip()

            for channel in clean_part.split(","):
                channel = channel.strip().rstrip(":").strip()
                channel_lower = normalize_search_text(channel)

                if (
                    channel
                    and not EXCLUDED_CHANNELS_RE.search(channel_lower)
                    and not EXCLUDED_CHANNEL_PATTERNS_RE.search(channel_lower)
                    and channel not in channels
                ):
                    channels.append(channel)
            continue

        # ------------------------------------------------------------
        # COMPETICIÓN GENÉRICA
        # ------------------------------------------------------------
        # Un partido explícito siempre tiene prioridad sobre el fallback
        # genérico, salvo las líneas de canal identificadas arriba.
        if re.search(
            r"\s-\s|\s+vs\.?\s+|\s+v\.\s+",
            part,
            re.IGNORECASE,
        ):
            if not matchup:
                matchup = part
            continue

        if len(part) < 35 and not tournament:
            tournament = part
            continue

        non_tournament_parts.append(part)

    # Si el partido no se detectó mediante separador, intentamos encontrar
    # una línea que no sea competición ni canal.
    if not matchup:
        candidates = []

        for part in non_tournament_parts:
            if part == tournament:
                continue
            if TIME_RE.fullmatch(part):
                continue
            candidates.append(part)

        if candidates:
            # Si hay una línea claramente descriptiva, usarla como evento.
            matchup = max(candidates, key=len)

    # Fallback final: quitar explícitamente hora, torneo y canales.
    # Así "Torneo de Tokio" nunca acaba como Evento / Partido.
    if not matchup:
        clean_desc = text_full

        clean_desc = TIME_RE.sub("", clean_desc)
        clean_desc = CLEAN_TV_RE.sub("", clean_desc)

        for channel in channels:
            clean_desc = clean_desc.replace(channel, "")

        if tournament:
            clean_desc = re.sub(
                re.escape(tournament),
                "",
                clean_desc,
                flags=re.IGNORECASE,
            )

        clean_desc = PUNCTUATION_RE.sub(" ", clean_desc)
        clean_desc = SPACES_RE.sub(" ", clean_desc).strip(" -–—")

        # No convertir el propio nombre de la competición en partido.
        if (
            not clean_desc
            or normalize_search_text(clean_desc)
            in normalize_search_text(tournament)
        ):
            matchup = ""
        else:
            matchup = clean_desc

    return (
        time_clean,
        matchup,
        channels,
        tournament,
        motor_session,
    )


# ============================================================================
# FILTRADO TEMPRANO
# ============================================================================

def should_skip_early(
    blob: str,
    tv_blob: str,
) -> bool:
    """
    Descarta eventos antes de ejecutar toda la clasificación.
    """

    is_priority_event = (
        contains(REAL_MADRID_RE, blob)
        or is_womens_champions(blob)
    )

    if is_priority_event:
        # Las exclusiones globales tienen prioridad incluso sobre eventos
        # considerados prioritarios.
        if is_excluded_event(blob):
            return True
        return False

    if is_excluded_event(blob):
        return True

    if (
        contains(GOLF_RE, blob)
        or "movistar golf" in tv_blob
    ):
        return True

    if is_excluded_event(blob):
        return True

    if (
        contains(PRIMERA_RFEF_RE, blob)
        and not contains(CASTILLA_RE, blob)
    ):
        return True

    if contains(LIGAF_RE, blob):
        return True

    return False


# ============================================================================
# PARSEAR EVENTO
# ============================================================================

def parse_event(item):
    # Filtro de seguridad sobre el texto ORIGINAL del nodo HTML.
    # Así una competición excluida no puede perderse aunque el parser
    # separe de forma imperfecta evento, competición y canales.
    original_blob = normalize_search_text(
        item.get_text(" ", strip=True)
    )

    if is_excluded_event(original_blob):
        return None

    # LaLiga Futures puede llegar desde el widget con la competición
    # erróneamente identificada como "LaLiga EA Sports". La señal fiable
    # está en el propio evento/canal: "LaLiga Futures" y los equipos
    # terminados en "Academy".
    if (
        re.search(r"\blaliga\s+futures\b", original_blob, re.IGNORECASE)
        or (
            len(re.findall(r"\bacademy\b", original_blob, re.IGNORECASE)) >= 2
            and "laliga" in original_blob
        )
    ):
        return None

    (
        time_clean,
        event_str,
        channels,
        tournament,
        motor_session,
    ) = parse_row_elements(item)

    if (
        not time_clean
        or event_str in {
            "",
            "Evento Deportivo",
        }
    ):
        return None

    # Una vez aplicadas las exclusiones de canales, un evento sin ninguna
    # emisión válida NO se muestra. Esto es especialmente importante para
    # tenis: WTA TV está excluido, pero si también existe otro canal válido
    # (por ejemplo Tennis Channel - Orange TV), ese canal debe conservarse.
    if not channels:
        return None

    text_block = (
        f"{event_str} {tournament} {motor_session}"
    )

    tv_blob = " ".join(channels).lower()

    blob = normalize_search_text(
        f"{text_block} {tv_blob}"
    )

    # Segundo filtro, ahora sobre el evento reconstruido.
    if is_excluded_event(blob):
        return None

    if should_skip_early(
        blob,
        tv_blob,
    ):
        return None

    return {
        "hora": time_clean,
        "evento": event_str,
        "tv_list": channels,
        "competicion_raw": tournament,
        "motor_session": motor_session,
        "blob": blob,
    }


# ============================================================================
# DESCARGA Y PARSING DE LA AGENDA
# ============================================================================

def fetch_and_parse_agenda() -> list[dict]:
    """
    Descarga la agenda y devuelve los eventos clasificados.
    """

    results = []
    seen_events = set()

    try:
        response = requests.get(
            WIDGET_URL,
            headers=REQUEST_HEADERS,
            timeout=REQUEST_TIMEOUT,
        )

        response.raise_for_status()

        soup = BeautifulSoup(
            response.text,
            "html.parser",
        )

        for item in soup.find_all(
            ("div", "tr", "li")
        ):
            try:
                parsed = parse_event(item)

                if parsed is None:
                    continue

                # ----------------------------------------------------------------
                # Evita duplicados.
                # ----------------------------------------------------------------

                event_key = (
                    parsed["hora"],
                    parsed["evento"].lower(),
                )

                if event_key in seen_events:
                    continue

                seen_events.add(event_key)

                # ----------------------------------------------------------------
                # Clasificación.
                # ----------------------------------------------------------------

                tv_blob = " ".join(
                    parsed["tv_list"]
                ).lower()

                sport, icon, competition = (
                    get_sport_and_competition(
                        parsed["blob"],
                        parsed["competicion_raw"],
                        tv_blob,
                    )
                )

                if sport == "__EXCLUDED__":
                    continue

                # ----------------------------------------------------------------
                # Sesión oficial de F1 / MotoGP.
                # ----------------------------------------------------------------

                motor_session = (
                    parsed.get("motor_session")
                    or get_motor_session(
                        sport,
                        competition,
                        parsed["hora"],
                        blob=parsed["blob"],
                        event=parsed["evento"],
                        tournament=parsed["competicion_raw"],
                    )
                )

                display_event = parsed["evento"]

                if motor_session:
                    display_event = (
                        f"{display_event} — {motor_session}"
                    )

                # ----------------------------------------------------------------
                # Resultado final.
                # ----------------------------------------------------------------

                is_favorite = matches_strict_criteria(
                    parsed["blob"],
                    parsed["tv_list"],
                    sport=sport,
                    competition=competition,
                    event_time=parsed["hora"],
                    motor_session=parsed.get("motor_session", ""),
                )

                results.append({
                    "hora": parsed["hora"],
                    "deporte": sport,
                    "icono": icon,
                    "competicion": competition,
                    "evento": display_event,
                    "tv_list": parsed["tv_list"],
                    "is_filtered": is_favorite,
                })

            except Exception as event_error:
                print(
                    "Advertencia: evento ignorado: "
                    f"{event_error}"
                )

    except requests.RequestException as error:
        print(
            f"Error descargando la agenda: {error}"
        )

    except Exception as error:
        print(
            f"Error procesando eventos: {error}"
        )

    return results


# ============================================================================
# GENERACIÓN HTML
# ============================================================================

def generate_html(events):
    fecha_act = datetime.now().strftime(
        "%d/%m/%Y - %H:%M"
    )

    # ------------------------------------------------------------------------
    # Estadísticas
    # ------------------------------------------------------------------------

    total_cnt = len(events)

    filtered_cnt = sum(
        1
        for event in events
        if event["is_filtered"]
    )

    sport_counts = Counter(
        event["deporte"]
        for event in events
    )

    futbol_cnt = sport_counts["Fútbol"]
    baloncesto_cnt = sport_counts["Baloncesto"]
    tenis_cnt = sport_counts["Tenis"]
    motor_cnt = sport_counts["Motor"]
    otros_cnt = sport_counts["Otros"]

    # ------------------------------------------------------------------------
    # Filas
    # ------------------------------------------------------------------------

    rows_list = []

    if not events:
        rows_list.append(
            '<tr>'
            '<td colspan="6" class="empty-state">'
            "😴 No hay eventos disponibles en este momento."
            "</td>"
            "</tr>"
        )

    else:
        for ev in events:

            tv_badges = "".join(
                f'<span class="tv-badge">{channel}</span>'
                for channel in ev["tv_list"]
            )

            search_text = " ".join([
                ev["hora"],
                ev["deporte"],
                ev["competicion"],
                ev["evento"],
                *ev["tv_list"],
            ]).lower()

            rows_list.append(
                f"""
                <tr
                    data-sport="{ev['deporte'].lower()}"
                    data-filtered="{str(ev['is_filtered']).lower()}"
                    data-search="{search_text}"
                >
                    <td class="date-col">
                        <span class="date-badge today">
                            Hoy
                        </span>
                    </td>

                    <td class="time-col">
                        <span class="time-badge">
                            {ev['hora']}
                        </span>
                    </td>

                    <td class="sport-col">
                        <span class="sport-tag">
                            {ev['icono']} {ev['deporte']}
                        </span>
                    </td>

                    <td class="comp-col">
                        <div class="comp-title">
                            {ev['competicion']}
                        </div>
                    </td>

                    <td class="event-col">
                        <div class="event-title">
                            {ev['evento']}
                        </div>
                    </td>

                    <td class="tv-col">
                        <div class="tv-container">
                            {tv_badges}
                        </div>
                    </td>
                </tr>
                """
            )

    rows_html = "".join(rows_list)

    # ------------------------------------------------------------------------
    # HTML
    # ------------------------------------------------------------------------

    return f"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">

    <title>Agenda Deportiva - Hoy</title>

    <link
        href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap"
        rel="stylesheet"
    >

    <style>
        :root {{
            --bg-color: #0f172a;
            --card-bg: #1e293b;
            --border-color: #334155;
            --text-main: #f8fafc;
            --text-muted: #94a3b8;
            --accent-blue: #3b82f6;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: 'Inter', sans-serif;
            background-color: var(--bg-color);
            color: var(--text-main);
            padding: 20px 12px;
            display: flex;
            justify-content: center;
        }}

        .container {{
            width: 100%;
            max-width: 1150px;
        }}

        header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 20px;
            padding-bottom: 12px;
            border-bottom: 1px solid var(--border-color);
            flex-wrap: wrap;
            gap: 10px;
        }}

        h1 {{
            font-size: 1.6rem;
            font-weight: 800;
            background: linear-gradient(
                135deg,
                #60a5fa,
                #a78bfa
            );
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }}

        .header-controls {{
            display: flex;
            gap: 10px;
            align-items: center;
        }}

        .btn-update {{
            background: #10b981;
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 10px;
            font-weight: 600;
            cursor: pointer;
            font-size: 0.9rem;
            transition: all 0.2s;
            display: flex;
            align-items: center;
            gap: 6px;
        }}

        .btn-update:hover {{
            background: #059669;
        }}

        .last-update {{
            font-size: 0.8rem;
            color: var(--text-muted);
            background: var(--card-bg);
            padding: 6px 12px;
            border-radius: 20px;
            border: 1px solid var(--border-color);
            width: 100%;
            text-align: right;
        }}

        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(
                auto-fit,
                minmax(100px, 1fr)
            );
            gap: 10px;
            margin-bottom: 20px;
        }}

        .stat-card {{
            background: var(--card-bg);
            padding: 10px 12px;
            border-radius: 12px;
            border: 1px solid var(--border-color);
            display: flex;
            justify-content: space-between;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease;
        }}

        .stat-card:hover {{
            border-color: var(--accent-blue);
            transform: translateY(-2px);
        }}

        .stat-card.active-card {{
            border-color: var(--accent-blue);
            background: rgba(59, 130, 246, 0.15);
            box-shadow:
                0 0 15px rgba(59, 130, 246, 0.2);
        }}

        .stat-card .val {{
            font-size: 1.2rem;
            font-weight: 700;
            color: var(--accent-blue);
        }}

        .stat-card .lbl {{
            font-size: 0.72rem;
            color: var(--text-muted);
        }}

        .filter-container {{
            display: flex;
            gap: 15px;
            margin-bottom: 15px;
        }}

        .search-input {{
            padding: 12px 16px;
            border-radius: 10px;
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            color: var(--text-main);
            font-size: 0.95rem;
            outline: none;
            width: 100%;
        }}

        .search-input:focus {{
            border-color: var(--accent-blue);
        }}

        .table-card {{
            background: var(--card-bg);
            border-radius: 16px;
            border: 1px solid var(--border-color);
            overflow: hidden;
            box-shadow:
                0 10px 25px -5px rgba(0, 0, 0, 0.3);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            table-layout: fixed;
        }}

        th {{
            background: #111827;
            color: var(--text-muted);
            font-weight: 600;
            font-size: 0.8rem;
            text-transform: uppercase;
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        }}

        td {{
            padding: 14px 16px;
            border-bottom: 1px solid #283548;
            font-size: 0.95rem;
            word-break: break-word;
        }}

        tr:last-child td {{
            border-bottom: none;
        }}

        tr:hover {{
            background-color: #243146;
        }}

        .date-badge {{
            display: inline-block;
            background: #334155;
            color: #f8fafc;
            font-weight: 600;
            padding: 5px 10px;
            border-radius: 8px;
            font-size: 0.82rem;
            white-space: nowrap;
            border: 1px solid #475569;
        }}

        .date-badge.today {{
            background: rgba(59, 130, 246, 0.2);
            color: #60a5fa;
            border-color: rgba(59, 130, 246, 0.5);
        }}

        .time-badge {{
            background: #0284c7;
            color: white;
            font-weight: 700;
            padding: 6px 10px;
            border-radius: 8px;
            font-size: 0.9rem;
            white-space: nowrap;
            display: inline-block;
        }}

        .sport-tag {{
            font-weight: 600;
        }}

        .comp-title {{
            font-weight: 600;
            color: #38bdf8;
        }}

        .event-title {{
            font-weight: 700;
            color: #ffffff;
        }}

        .tv-container {{
            display: flex;
            flex-wrap: wrap;
            gap: 6px;
        }}

        .tv-badge {{
            display: inline-block;
            background: rgba(16, 185, 129, 0.15);
            color: #34d399;
            border: 1px solid rgba(16, 185, 129, 0.3);
            padding: 3px 8px;
            border-radius: 6px;
            font-size: 0.78rem;
            font-weight: 600;
        }}

        .empty-state {{
            text-align: center;
            padding: 40px;
            color: var(--text-muted);
            font-size: 1.1rem;
        }}

        @media (max-width: 768px) {{

            body {{
                padding: 12px 8px;
            }}

            .table-card {{
                background: transparent;
                border: none;
                box-shadow: none;
                overflow: visible;
            }}

            table,
            thead,
            tbody,
            th,
            td,
            tr {{
                display: block;
                width: 100%;
            }}

            thead {{
                display: none;
            }}

            tr {{
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 14px;
                margin-bottom: 12px;
                padding: 14px;
                box-shadow:
                    0 4px 12px rgba(0, 0, 0, 0.2);
            }}

            td {{
                padding: 3px 0;
                border: none;
            }}

            .date-col {{
                display: none;
            }}

            .time-col {{
                display: inline-block;
                width: auto;
                margin-right: 8px;
            }}

            .sport-col {{
                display: inline-block;
                width: auto;
                float: right;
            }}

            .comp-col {{
                clear: both;
                margin-top: 8px;
            }}

            .comp-title {{
                font-size: 0.82rem;
                text-transform: uppercase;
                letter-spacing: 0.5px;
                opacity: 0.9;
            }}

            .event-col {{
                margin: 6px 0 10px 0;
            }}

            .event-title {{
                font-size: 1.05rem;
                line-height: 1.35;
            }}

            .tv-col {{
                border-top: 1px solid rgba(
                    255,
                    255,
                    255,
                    0.08
                );
                padding-top: 8px;
                margin-top: 6px;
            }}
        }}
    </style>
</head>

<body>

<div class="container">

    <header>

        <div>
            <h1>⚡ Agenda Deportiva - Hoy</h1>
        </div>

        <div class="header-controls">
            <button
                class="btn-update"
                onclick="location.reload()"
            >
                🔄 Actualizar
            </button>
        </div>

        <div class="last-update">
            Última actualización:
            <strong>{fecha_act} (UTC)</strong>
        </div>

    </header>

    <div class="stats-grid">

        <div
            class="stat-card active-card"
            id="card-todos"
            onclick="setFilter('todos')"
        >
            <div>
                <div class="lbl">Todos</div>
                <div class="val">{total_cnt}</div>
            </div>
            <div style="font-size:1.3rem">📌</div>
        </div>

        <div
            class="stat-card"
            id="card-filtrados"
            onclick="setFilter('filtrados')"
        >
            <div>
                <div class="lbl">Filtrados</div>
                <div
                    class="val"
                    style="color:#a78bfa"
                >
                    {filtered_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">⭐</div>
        </div>

        <div
            class="stat-card"
            id="card-fútbol"
            onclick="setFilter('fútbol')"
        >
            <div>
                <div class="lbl">Fútbol</div>
                <div
                    class="val"
                    style="color:#10b981"
                >
                    {futbol_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">⚽</div>
        </div>

        <div
            class="stat-card"
            id="card-baloncesto"
            onclick="setFilter('baloncesto')"
        >
            <div>
                <div class="lbl">Baloncesto</div>
                <div
                    class="val"
                    style="color:#f97316"
                >
                    {baloncesto_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">🏀</div>
        </div>

        <div
            class="stat-card"
            id="card-tenis"
            onclick="setFilter('tenis')"
        >
            <div>
                <div class="lbl">Tenis</div>
                <div
                    class="val"
                    style="color:#f59e0b"
                >
                    {tenis_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">🎾</div>
        </div>

        <div
            class="stat-card"
            id="card-motor"
            onclick="setFilter('motor')"
        >
            <div>
                <div class="lbl">Motor</div>
                <div
                    class="val"
                    style="color:#ef4444"
                >
                    {motor_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">🏎️</div>
        </div>

        <div
            class="stat-card"
            id="card-otros"
            onclick="setFilter('otros')"
        >
            <div>
                <div class="lbl">Otros</div>
                <div
                    class="val"
                    style="color:#a8a29e"
                >
                    {otros_cnt}
                </div>
            </div>
            <div style="font-size:1.3rem">🎯</div>
        </div>

    </div>

    <div class="filter-container">

        <input
            type="text"
            id="searchInput"
            class="search-input"
            onkeyup="filterTable()"
            placeholder="🔍 Filtrar por partido, equipo, tenista o canal TV..."
        >

    </div>

    <div class="table-card">

        <table>

            <thead>
                <tr>
                    <th style="width: 110px;">Fecha</th>
                    <th style="width: 85px;">Hora</th>
                    <th style="width: 120px;">Deporte</th>
                    <th style="width: 180px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 240px;">Canal de TV</th>
                </tr>
            </thead>

            <tbody id="agendaTable">
                {rows_html}
            </tbody>

        </table>

    </div>

</div>

<script>

let currentFilter = 'todos';


function setFilter(filterType) {{

    currentFilter = filterType;

    document
        .querySelectorAll('.stat-card')
        .forEach(card =>
            card.classList.remove('active-card')
        );

    const activeCard =
        document.getElementById(
            'card-' + filterType
        );

    if (activeCard) {{
        activeCard.classList.add('active-card');
    }}

    applyFilters();
}}


function filterTable() {{
    applyFilters();
}}


function applyFilters() {{

    const searchFilter =
        document
            .getElementById('searchInput')
            .value
            .toLowerCase();

    const table =
        document.getElementById('agendaTable');

    const trs =
        table.getElementsByTagName('tr');

    let visibleCount = 0;

    for (let i = 0; i < trs.length; i++) {{

        const tr = trs[i];

        if (tr.id === 'dynamicEmptyState') {{
            continue;
        }}

        const rowSport =
            (
                tr.getAttribute('data-sport')
                || ''
            ).toLowerCase();

        const isFiltered =
            tr.getAttribute('data-filtered')
            === 'true';

        const text =
            tr.getAttribute('data-search')
            || '';

        const matchesFilter =
            currentFilter === 'todos'
                ? true
                : currentFilter === 'filtrados'
                    ? isFiltered
                    : rowSport === currentFilter;

        const matchesSearch =
            text.includes(searchFilter);

        if (
            matchesFilter
            && matchesSearch
        ) {{
            tr.style.display = '';
            visibleCount++;
        }} else {{
            tr.style.display = 'none';
        }}
    }}

    let emptyRow =
        document.getElementById(
            'dynamicEmptyState'
        );

    if (visibleCount === 0) {{

        if (!emptyRow) {{

            emptyRow =
                document.createElement('tr');

            emptyRow.id =
                'dynamicEmptyState';

            emptyRow.innerHTML =
                '<td colspan="6" class="empty-state">' +
                '😴 No hay eventos que coincidan con ' +
                'la selección y búsqueda.' +
                '</td>';

            table.appendChild(emptyRow);

        }} else {{
            emptyRow.style.display = '';
        }}

    }} else {{

        if (emptyRow) {{
            emptyRow.style.display = 'none';
        }}
    }}
}}

</script>

</body>
</html>
"""


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":

    events = fetch_and_parse_agenda()

    if events:

        html_content = generate_html(events)

        with open(
            "index.html",
            "w",
            encoding="utf-8",
        ) as f:
            f.write(html_content)

        print(
            "Archivo index.html generado con éxito. "
            f"Eventos encontrados: {len(events)}"
        )

    else:

        print(
            "Atención: No se obtuvieron eventos de la fuente. "
            "Se conserva la agenda previa sin modificar index.html."
        )
