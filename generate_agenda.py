from collections import Counter
from datetime import datetime
from html import escape
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
        "Chrome/136.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 20


# ============================================================================
# CANALES EXCLUIDOS
# ============================================================================

EXCLUDED_CHANNELS = {
    "aragón play",
    "aragón tv",
    "asobal tv",
    "dazn 1 bar(m148)",
    "fanplay",
    "fff tv youtube",
    "tvg(galicia)",
    "tv footballclub(acceder)",
    "tv3(cataluña)",
    "uefa tv",
    "uefa youtube",
    "wta tv",
}


# ============================================================================
# REGEX
# ============================================================================

def rx(*patterns: str) -> re.Pattern:
    return re.compile(
        "(?:" + "|".join(patterns) + ")",
        re.IGNORECASE,
    )


def normalize(text: str) -> str:
    text = text or ""
    text = text.replace("\xa0", " ")
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def normalize_search(text: str) -> str:
    text = normalize(text).lower()
    text = (
        text.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
    )
    return text


# ============================================================================
# TIEMPOS
# ============================================================================

TIME_RE = re.compile(
    r"\b([01]?\d|2[0-3]):([0-5]\d)\b"
)


# ============================================================================
# IDENTIFICACIÓN DE CANALES
# ============================================================================

TV_IDENTIFIERS_RE = rx(
    r"\bm\+",
    r"\bmovistar\b",
    r"\bdazn\b",
    r"\bchannel\b",
    r"\beurosport\b",
    r"\brtve\b",
    r"\blaliga\b",
    r"\bteledeporte\b",
    r"\btv\b",
    r"\bdesport\b",
    r"\bdisney\+?\b",
    r"\btennis\s+channel\b",
    r"\bwta\s*tv\b",
    r"\batp\s+tennis\s+tv\b",
)


# ============================================================================
# TENIS
# ============================================================================

# Jugadores que sirven para detectar tenis y, cuando corresponda, favoritos.
TENNIS_PLAYERS_RE = rx(
    r"\balcaraz\b",
    r"\bjódar\b",
    r"\bjodar\b",
    r"\bdavidovich\b",
    r"\bmunar\b",
    r"\bmérida\b",
    r"\bmerida\b",
    r"\blandaluce\b",
    r"\bcarreño\b",
    r"\bcarreno\b",
    r"\bbucsa\b",
    r"\bbouzas\b",
    r"\bbadosa\b",
    r"\bquevedo\b",
    r"\bsinner\b",
    r"\bzverev\b",
    r"\bsabalenka\b",
    r"\brybakina\b",
    r"\bpegula\b",
    r"\bsorribes\b",
    r"\bmasarova\b",
    r"\bparrizas\b",
    r"\bbassols\b",
    r"\blázaro\b",
    r"\blazaro\b",
)


# WTA / ATP genérico.
WTA_RE = rx(
    r"\bwta\b",
    r"\bwta\s+\d+\b",
    r"\bwta\s+(?:1000|500|250|125)\b",
    r"\bwta\s+tour\b",
    r"\bwta\s+finals\b",
)

ATP_RE = rx(
    r"\batp\b",
    r"\batp\s+\d+\b",
    r"\batp\s+(?:1000|500|250|challenger)\b",
    r"\batp\s+tour\b",
    r"\batp\s+finals\b",
)


TENNIS_TOURNAMENT_RE = rx(
    # China / Beijing
    r"\bchina\s+open\b",
    r"\bbeijing\b",
    r"\bpekin\b",
    r"\bpekin\b",

    # Tokyo / Japan
    r"\btokyo\b",
    r"\btokio\b",
    r"\bjapan\s+open\b",

    # Grandes torneos
    r"\bwimbledon\b",
    r"\broland\s+garros\b",
    r"\bus\s+open\b",
    r"\bopen\s+de\s+eeuu\b",
    r"\bopen\s+de\s+estados\s+unidos\b",
    r"\bopen\s+de\s+australia\b",
    r"\baustralian\s+open\b",

    # Otros torneos importantes
    r"\bmadrid\s+open\b",
    r"\bmutua\s+madrid\b",
    r"\bmasters\s+de\s+roma\b",
    r"\brome\s+masters\b",
    r"\bindian\s+wells\b",
    r"\bmiami\s+open\b",
    r"\bmontecarlo\b",
    r"\bmonte\s+carlo\b",
    r"\bcincinnati\b",
    r"\bshanghai\b",
    r"\bmontreal\b",
    r"\btoronto\b",
    r"\bguadalajara\b",
    r"\bwuhan\b",
    r"\bdoha\b",
    r"\bdubai\b",

    # Competiciones por equipos
    r"\blaver\s+cup\b",
    r"\bcopa\s+davis\b",
    r"\bdavis\s+cup\b",
    r"\bbillie\s+jean\s+king\s+cup\b",
    r"\bbjk\s+cup\b",
)


TENNIS_RE = rx(
    r"\btenis\b",
    r"\btennis\b",
    r"\batp\b",
    r"\bwta\b",
    r"\bwimbledon\b",
    r"\broland\s+garros\b",
    r"\bus\s+open\b",
    r"\bopen\s+de\s+australia\b",
    r"\baustralian\s+open\b",
    r"\bmasters\b",
    r"\bdavis\s+cup\b",
    r"\bcopa\s+davis\b",
    r"\bbillie\s+jean\s+king\s+cup\b",
    r"\blaver\s+cup\b",
    r"\bchina\s+open\b",
    r"\bbeijing\b",
    r"\bpekin\b",
    r"\btokyo\b",
    r"\btokio\b",
    r"\bjapan\s+open\b",
)


TENNIS_COMPETITIONS = (
    (rx(r"\bchina\s+open\b", r"\bbeijing\b", r"\bpekin\b"), "China Open"),
    (rx(r"\bjapan\s+open\b", r"\btokyo\b", r"\btokio\b"), "Japan Open"),
    (rx(r"\bwimbledon\b"), "Wimbledon"),
    (rx(r"\broland\s+garros\b"), "Roland Garros"),
    (rx(r"\bus\s+open\b"), "US Open"),
    (
        rx(
            r"\bopen\s+de\s+australia\b",
            r"\baustralian\s+open\b",
        ),
        "Open de Australia",
    ),
    (rx(r"\bmadrid\s+open\b", r"\bmutua\s+madrid\b"), "Madrid Open"),
    (
        rx(
            r"\bmasters\s+de\s+roma\b",
            r"\brome\s+masters\b",
        ),
        "Masters de Roma",
    ),
    (rx(r"\blaver\s+cup\b"), "Laver Cup"),
    (
        rx(
            r"\bcopa\s+davis\b",
            r"\bdavis\s+cup\b",
        ),
        "Copa Davis",
    ),
    (
        rx(
            r"\bbillie\s+jean\s+king\s+cup\b",
            r"\bbjk\s+cup\b",
        ),
        "Billie Jean King Cup",
    ),
)


# ============================================================================
# FÚTBOL
# ============================================================================

FOOTBALL_RE = rx(
    r"\bfútbol\b",
    r"\bfutbol\b",
    r"\bla\s*liga\b",
    r"\bliga\s+f\b",
    r"\bprimera\s+división\b",
    r"\bsegunda\s+división\b",
    r"\bsegunda\s+b\b",
    r"\bprimera\s+rfef\b",
    r"\bsegunda\s+rfef\b",
    r"\btercera\s+rfef\b",
    r"\bchampions\b",
    r"\beuropa\s+league\b",
    r"\bconference\s+league\b",
    r"\bpremier\s+league\b",
    r"\bbundesliga\b",
    r"\bserie\s+a\b",
    r"\bligue\s+1\b",
    r"\bcopa\b",
    r"\bmundial\b",
    r"\bnations\s+league\b",
)


# ============================================================================
# BALONCESTO
# ============================================================================

BASKETBALL_RE = rx(
    r"\bbaloncesto\b",
    r"\bbasket\b",
    r"\bacb\b",
    r"\bliga\s+endesa\b",
    r"\bliga\s+femenina\b",
    r"\bnba\b",
    r"\beuroliga\b",
    r"\beuroleague\b",
    r"\beurocup\b",
    r"\bfiba\b",
    r"\bselección\s+española\b",
    r"\bseleccion\s+espanola\b",
)


# ============================================================================
# MOTOR
# ============================================================================

MOTOR_RE = rx(
    r"\bf1\b",
    r"\bformula\s+1\b",
    r"\bfórmula\s+1\b",
    r"\bf2\b",
    r"\bf3\b",
    r"\bmoto\s*gp\b",
    r"\bmoto2\b",
    r"\bmoto3\b",
    r"\bsuperbike\b",
    r"\bwsbk\b",
    r"\bformula\s+e\b",
    r"\bindycar\b",
    r"\bnascar\b",
)


# ============================================================================
# OTROS DEPORTES
# ============================================================================

OTHER_SPORT_RE = rx(
    r"\bciclismo\b",
    r"\bvuelta\b",
    r"\btour\b",
    r"\bvolta\b",
    r"\btenis\s+de\s+mesa\b",
    r"\bping\s+pong\b",
    r"\bvoleibol\b",
    r"\bvoley\b",
    r"\bbalonmano\b",
    r"\brugby\b",
    r"\batletismo\b",
    r"\bnatación\b",
    r"\bnatacion\b",
    r"\bgolf\b",
    r"\bboxeo\b",
    r"\bufc\b",
    r"\bpadel\b",
    r"\bpádel\b",
)


# ============================================================================
# EXCLUSIONES
# ============================================================================

EXCLUDED_SPORTS_RE = rx(
    r"\btorneo\s+betplay\s+dimayor\b",
    r"\bmls\b",
    r"\bnfl\b",
    r"\bncaa\b",
    r"\bufc\b",
    r"\bwnba\b",
)


EXCLUDED_BLOB_RE = rx(
    # Fútbol / competiciones juveniles
    r"\bpreolímpico\s+femenino\b",
    r"\bpreolimpico\s+femenino\b",
    r"\bnfl\s+pretemporada\b",
    r"\bf1\s+academy\b",
    r"\btour\s+del\s+benelux\b",
    r"\bbundesliga\s+femenina\b",
    r"\biaaf\s+diamond\s+league\b",
    r"\bnational\s+league\s+north\b",
    r"\bnational\s+league\s+south\b",
    r"\beredivisie\s+vrouwen\b",
    r"\beuropeo\s+femenino\s+sub\s*16\b",
    r"\bsegunda\s+federación\b",
    r"\bsegunda\s+federacion\b",
    r"\bsegunda\s+rfef\b",
    r"\bsuperliga\s+infantil\b",
    r"\bsupercopa\s+lf\s+femenina\b",
    r"\bfifa\s+asean\s+cup\b",
    r"\btercera\s+federación\b",
    r"\btercera\s+federacion\b",
    r"\bliga\s+nacional\s+juvenil\b",
    r"\bcopa\s+de\s+alemania\s+femenina\b",
    r"\bcopa\s+alemania\s+femenina\b",
    r"\b1[ªa]?\s+autonómica\s+juvenil\b",
    r"\b1[ªa]?\s+autonomica\s+juvenil\b",
    r"\bprimera\s+autonómica\s+juvenil\b",
    r"\bprimera\s+autonomica\s+juvenil\b",

    # Balonmano
    r"\behf\s+euro\s+cup\s+women\b",
    r"\behf\s+european\s+league\b",
    r"\bu20\s+elite\s+league\b",
    r"\bu20\s+elite\s+league\s+women\b",

    # Ciclismo
    r"\btour\s+de\s+croacia\b",

    # Rugby
    r"\bgallagher\s+premiership\b",

    # Tenis
    r"\bplaya\s+del\s+carmen\s+open\b",

    # Fútbol internacional
    r"\bgulf\s+cup\s+of\s+nations\b",

    # Baloncesto
    r"\bprimera\s+feb\b",
    r"\beuroliga\s+femenina\b",
    r"\beuroliga\s+femenino\b",
    r"\beuroleague\s+women\b",
    r"\bwomen'?s\s+euroleague\b",

    # Fútbol americano / otras
    r"\bcopa\s+colombia\b",
    r"\bliga\s+auf\s+uruguaya\b",
    r"\bsegunda\s+uruguay\b",
    r"\bliga\s+vasca\s+cadete\b",

    # Competiciones que no queremos mostrar
    r"\beurocup\b",
    r"\beuro\s+cup\b",
    r"\bcopa\s+rfef\b",
)


LIGAF_RE = rx(
    r"\bliga\s*f\b",
    r"\bliga\s+femenina\s+española\b",
)


PRIMERA_RFEF_RE = rx(
    r"\bprimera\s+rfef\b",
)


CASTILLA_RE = rx(
    r"\bcastilla\b",
)


# ============================================================================
# UTILIDADES
# ============================================================================

def clean_channel(channel: str) -> str:
    channel = normalize(channel)

    channel = re.sub(
        r"\(\s*ver\s+en\s+directo\s*\)",
        "",
        channel,
        flags=re.IGNORECASE,
    )

    channel = re.sub(
        r"\bver\s+partido\b",
        "",
        channel,
        flags=re.IGNORECASE,
    )

    return normalize(channel)


def channel_is_excluded(channel: str) -> bool:
    return normalize_search(channel) in EXCLUDED_CHANNELS


def split_channels(text: str) -> list[str]:
    text = normalize(text)

    if not text:
        return []

    # Separadores habituales.
    parts = re.split(
        r"\s*,\s*|\s*\|\s*|\s*;\s*",
        text,
    )

    result = []

    for part in parts:
        part = clean_channel(part)

        if not part:
            continue

        if channel_is_excluded(part):
            continue

        result.append(part)

    return list(dict.fromkeys(result))


def find_time(text: str) -> str | None:
    match = TIME_RE.search(text)

    if not match:
        return None

    return match.group(0)


def is_excluded_event(blob: str) -> bool:
    normalized_blob = normalize_search(blob)

    if EXCLUDED_SPORTS_RE.search(normalized_blob):
        return True

    if EXCLUDED_BLOB_RE.search(normalized_blob):
        return True

    return False


def is_tennis_blob(
    blob: str,
    tournament: str = "",
) -> bool:
    combined = normalize_search(
        f"{blob} {tournament}"
    )

    return bool(
        TENNIS_RE.search(combined)
        or TENNIS_PLAYERS_RE.search(combined)
        or TENNIS_TOURNAMENT_RE.search(combined)
        or WTA_RE.search(combined)
        or ATP_RE.search(combined)
    )


def detect_tennis_tour(
    blob: str,
    raw_tournament: str = "",
    tv_blob: str = "",
) -> str:
    combined = normalize_search(
        f"{blob} {raw_tournament} {tv_blob}"
    )

    if WTA_RE.search(combined):
        return "WTA"

    if ATP_RE.search(combined):
        return "ATP"

    return ""


def normalize_tennis_competition(
    tournament: str,
) -> str:
    text = normalize(tournament)

    if not text:
        return ""

    normalized = normalize_search(text)

    if re.search(
        r"\bchina\s+open\b|\bbeijing\b|\bpekin\b",
        normalized,
    ):
        return "China Open"

    if re.search(
        r"\bjapan\s+open\b|\btokyo\b|\btokio\b",
        normalized,
    ):
        return "Japan Open"

    if "wimbledon" in normalized:
        return "Wimbledon"

    if "roland garros" in normalized:
        return "Roland Garros"

    if "us open" in normalized:
        return "US Open"

    if (
        "open de australia" in normalized
        or "australian open" in normalized
    ):
        return "Open de Australia"

    if (
        "madrid open" in normalized
        or "mutua madrid" in normalized
    ):
        return "Madrid Open"

    if (
        "masters de roma" in normalized
        or "rome masters" in normalized
    ):
        return "Masters de Roma"

    if "laver cup" in normalized:
        return "Laver Cup"

    if (
        "copa davis" in normalized
        or "davis cup" in normalized
    ):
        return "Copa Davis"

    if (
        "billie jean king cup" in normalized
        or "bjk cup" in normalized
    ):
        return "Billie Jean King Cup"

    return text


def classify_tennis(
    blob: str,
    raw_tournament: str = "",
    tv_blob: str = "",
) -> str:
    tour = detect_tennis_tour(
        blob,
        raw_tournament,
        tv_blob,
    )

    combined = normalize_search(
        f"{blob} {raw_tournament}"
    )

    competition = ""

    for pattern, name in TENNIS_COMPETITIONS:
        if pattern.search(combined):
            competition = name
            break

    if not competition:
        competition = normalize_tennis_competition(
            raw_tournament
        )

    if competition == "Laver Cup":
        return "ATP Laver Cup"

    if competition in {
        "Copa Davis",
        "Billie Jean King Cup",
    }:
        if tour:
            return f"{tour} {competition}"

        return competition

    if competition:
        if tour:
            return f"{tour} {competition}"

        return competition

    # Si aparece WTA/ATP pero no conocemos el torneo.
    if tour:
        return f"{tour} Tour"

    return "Tenis"


# ============================================================================
# CLASIFICACIÓN GENERAL
# ============================================================================

def classify_sport(
    blob: str,
    tournament: str = "",
) -> str:
    combined = normalize_search(
        f"{blob} {tournament}"
    )

    if is_tennis_blob(
        blob,
        tournament,
    ):
        return "Tenis"

    if MOTOR_RE.search(combined):
        return "Motor"

    if BASKETBALL_RE.search(combined):
        return "Baloncesto"

    if FOOTBALL_RE.search(combined):
        return "Fútbol"

    if OTHER_SPORT_RE.search(combined):
        return "Otros"

    return "Otros"


def classify_event(
    blob: str,
    tournament: str = "",
    tv_blob: str = "",
) -> tuple[str, str]:
    sport = classify_sport(
        blob,
        tournament,
    )

    if sport == "Tenis":
        competition = classify_tennis(
            blob,
            tournament,
            tv_blob,
        )
    else:
        competition = normalize(tournament)

        if not competition:
            competition = sport

    return sport, competition


# ============================================================================
# FAVORITOS
# ============================================================================

def is_favorite_tennis_event(
    event_blob: str,
) -> bool:
    return bool(
        TENNIS_PLAYERS_RE.search(
            normalize_search(event_blob)
        )
    )


def is_spain_event(
    event_blob: str,
) -> bool:
    normalized = normalize_search(event_blob)

    return bool(
        re.search(
            r"\bespaña\b|\bespana\b|\bspain\b",
            normalized,
        )
    )


def matches_strict_criteria(event: dict) -> bool:
    blob = normalize_search(
        " ".join(
            [
                event.get("evento", ""),
                event.get("torneo", ""),
                event.get("competicion", ""),
                " ".join(event.get("canales", [])),
            ]
        )
    )

    # ------------------------------------------------------------
    # Exclusiones globales
    # ------------------------------------------------------------

    if is_excluded_event(blob):
        return False

    # ------------------------------------------------------------
    # Real Madrid
    # ------------------------------------------------------------

    if re.search(
        r"\breal\s+madrid\b",
        blob,
    ):
        return True

    # ------------------------------------------------------------
    # Motor
    # ------------------------------------------------------------

    if event.get("deporte") == "Motor":
        if re.search(
            r"\bf1\s+academy\b",
            blob,
        ):
            return False

        return True

    # ------------------------------------------------------------
    # Futsal
    # ------------------------------------------------------------

    if re.search(
        r"\bfutsal\b|\bfútbol\s+sala\b|\bfutbol\s+sala\b",
        blob,
    ):
        return False

    # ------------------------------------------------------------
    # Competiciones femeninas de fútbol que no queremos
    # ------------------------------------------------------------

    if (
        event.get("deporte") == "Fútbol"
        and re.search(
            r"\bfemenin[ao]\b|\bwomen\b",
            blob,
        )
    ):
        return False

    # ------------------------------------------------------------
    # Baloncesto español
    # ------------------------------------------------------------

    if event.get("deporte") == "Baloncesto":
        if re.search(
            r"\bacb\b"
            r"|\bliga\s+endesa\b"
            r"|\bselección\s+española\b"
            r"|\bseleccion\s+espanola\b",
            blob,
        ):
            return True

    # ------------------------------------------------------------
    # Tenis: jugadores favoritos
    # ------------------------------------------------------------

    if event.get("deporte") == "Tenis":
        if is_favorite_tennis_event(blob):
            return True

    # ------------------------------------------------------------
    # España en Nations League
    # ------------------------------------------------------------

    if (
        is_spain_event(blob)
        and re.search(
            r"\bnations\s+league\b",
            blob,
        )
    ):
        return True

    # ------------------------------------------------------------
    # Davis / Billie Jean King con España
    # ------------------------------------------------------------

    if (
        is_spain_event(blob)
        and re.search(
            r"\bcopa\s+davis\b"
            r"|\bdavis\s+cup\b"
            r"|\bbillie\s+jean\s+king\s+cup\b"
            r"|\bbjk\s+cup\b",
            blob,
        )
    ):
        return True

    return False


# ============================================================================
# PARSEO DE FILAS
# ============================================================================

def parse_row_elements(
    node,
) -> dict:
    full_text = normalize(
        node.get_text(
            " ",
            strip=True,
        )
    )

    hora = find_time(full_text)

    if not hora:
        return {
            "hora": None,
            "evento": "",
            "torneo": "",
            "canales": [],
            "tv_original": "",
            "texto_original": full_text,
        }

    # ------------------------------------------------------------
    # Texto por líneas
    # ------------------------------------------------------------

    raw_parts = [
        normalize(x)
        for x in node.stripped_strings
    ]

    parts = []

    for part in raw_parts:
        if not part:
            continue

        if TIME_RE.fullmatch(part):
            continue

        if normalize_search(part) in {
            "directo",
            "ver partido",
            "ver en directo",
        }:
            continue

        parts.append(part)

    # ------------------------------------------------------------
    # Detectar evento / torneo / TV
    # ------------------------------------------------------------

    event_parts = []
    tournament = ""
    tv_parts = []

    for part in parts:
        normalized_part = normalize_search(part)

        # --------------------------------------------------------
        # Si tiene estructura "Equipo A - Equipo B", es partido.
        # --------------------------------------------------------

        if re.search(
            r"\s+(?:-|–|—|vs\.?|v\.)\s+",
            part,
            flags=re.IGNORECASE,
        ):
            event_parts.append(part)
            continue

        # --------------------------------------------------------
        # TV
        # --------------------------------------------------------

        if TV_IDENTIFIERS_RE.search(part):
            cleaned = re.sub(
                r"\(\s*ver\s+en\s+directo\s*\)",
                "",
                part,
                flags=re.IGNORECASE,
            )

            cleaned = re.sub(
                r"\bver\s+partido\b",
                "",
                cleaned,
                flags=re.IGNORECASE,
            )

            cleaned = normalize(cleaned)

            if cleaned:
                tv_parts.extend(
                    split_channels(cleaned)
                )

            continue

        # --------------------------------------------------------
        # Torneo / competición
        # --------------------------------------------------------

        if (
            not tournament
            and (
                TENNIS_TOURNAMENT_RE.search(
                    normalized_part
                )
                or WTA_RE.search(
                    normalized_part
                )
                or ATP_RE.search(
                    normalized_part
                )
            )
        ):
            tournament = part
            continue

        # --------------------------------------------------------
        # Primer texto corto que no sea TV:
        # puede ser torneo.
        # --------------------------------------------------------

        if (
            not tournament
            and len(part) <= 80
            and not re.search(
                r"\s+(?:-|–|—|vs\.?|v\.)\s+",
                part,
                flags=re.IGNORECASE,
            )
        ):
            tournament = part
            continue

        event_parts.append(part)

    # ------------------------------------------------------------
    # Si no hemos detectado evento explícitamente, intentar
    # recuperar el texto útil.
    # ------------------------------------------------------------

    if not event_parts:
        candidates = []

        for part in parts:
            if part == tournament:
                continue

            if TV_IDENTIFIERS_RE.search(part):
                continue

            candidates.append(part)

        if candidates:
            event_parts = candidates

    evento = normalize(
        " - ".join(
            dict.fromkeys(event_parts)
        )
    )

    tv_original = normalize(
        " | ".join(tv_parts)
    )

    return {
        "hora": hora,
        "evento": evento,
        "torneo": tournament,
        "canales": list(
            dict.fromkeys(tv_parts)
        ),
        "tv_original": tv_original,
        "texto_original": full_text,
    }


# ============================================================================
# PARSEO DE EVENTO
# ============================================================================

def parse_event(node) -> dict | None:
    raw = parse_row_elements(node)

    hora = raw["hora"]

    if not hora:
        return None

    evento = normalize(raw["evento"])
    torneo = normalize(raw["torneo"])
    canales = raw["canales"]
    original = raw["texto_original"]

    if not evento:
        # Último intento: usar todo el texto salvo la hora.
        fallback = TIME_RE.sub(
            "",
            original,
        )

        fallback = normalize(fallback)

        if fallback:
            evento = fallback

    combined_before_classification = normalize(
        " ".join(
            [
                original,
                evento,
                torneo,
                raw.get("tv_original", ""),
            ]
        )
    )

    # ------------------------------------------------------------
    # Exclusiones antes de clasificar.
    # ------------------------------------------------------------

    if is_excluded_event(
        combined_before_classification
    ):
        return None

    # ------------------------------------------------------------
    # Clasificación.
    # ------------------------------------------------------------

    deporte, competicion = classify_event(
        combined_before_classification,
        torneo,
        raw.get("tv_original", ""),
    )

    # ------------------------------------------------------------
    # IMPORTANTE:
    #
    # Si todos los canales son excluidos (por ejemplo WTA TV),
    # NO eliminamos el partido de tenis.
    #
    # Esto soluciona precisamente el problema de los partidos WTA.
    # ------------------------------------------------------------

    if not canales:
        is_tennis = (
            deporte == "Tenis"
            or is_tennis_blob(
                combined_before_classification,
                torneo,
            )
        )

        if not is_tennis:
            return None

    # ------------------------------------------------------------
    # Evitar basura.
    # ------------------------------------------------------------

    if not evento:
        return None

    return {
        "hora": hora,
        "evento": evento,
        "torneo": torneo,
        "competicion": competicion,
        "deporte": deporte,
        "canales": canales,
        "favorito": False,
    }


# ============================================================================
# OBTENER AGENDA
# ============================================================================

def fetch_and_parse_agenda() -> list[dict]:
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

    events = []
    seen = set()

    # El widget puede utilizar diferentes elementos dependiendo
    # de la versión de la página.
    nodes = soup.find_all(
        ["div", "tr", "li"]
    )

    for node in nodes:
        text = normalize(
            node.get_text(
                " ",
                strip=True,
            )
        )

        if not TIME_RE.search(text):
            continue

        event = parse_event(node)

        if not event:
            continue

        key = (
            event["hora"],
            normalize_search(event["evento"]),
            normalize_search(event["competicion"]),
            tuple(
                normalize_search(c)
                for c in event["canales"]
            ),
        )

        if key in seen:
            continue

        seen.add(key)
        events.append(event)

    # ------------------------------------------------------------
    # Favoritos
    # ------------------------------------------------------------

    for event in events:
        event["favorito"] = matches_strict_criteria(
            event
        )

    return events


# ============================================================================
# HTML
# ============================================================================

def event_to_html(event: dict) -> str:
    hora = escape(event.get("hora", ""))
    evento = escape(event.get("evento", ""))
    competicion = escape(
        event.get("competicion", "")
    )

    canales = event.get("canales", [])

    channels_html = ""

    if canales:
        channels_html = (
            "<div class='channels'>"
            + " · ".join(
                escape(channel)
                for channel in canales
            )
            + "</div>"
        )
    else:
        channels_html = (
            "<div class='channels muted'>"
            "Emisión no indicada"
            "</div>"
        )

    favorite_class = (
        " favorite"
        if event.get("favorito")
        else ""
    )

    favorite_mark = (
        " ⭐"
        if event.get("favorito")
        else ""
    )

    return f"""
    <div class="event{favorite_class}"
         data-search="{escape(
             normalize_search(
                 f"{evento} {competicion} "
                 f"{' '.join(canales)}"
             )
         )}">
        <div class="event-time">{hora}</div>

        <div class="event-info">
            <div class="event-name">
                {evento}{favorite_mark}
            </div>

            <div class="event-competition">
                {competicion}
            </div>

            {channels_html}
        </div>
    </div>
    """


def group_events(
    events: Iterable[dict],
) -> dict[str, list[dict]]:
    groups = {
        "Todos": [],
        "Favoritos": [],
        "Fútbol": [],
        "Baloncesto": [],
        "Tenis": [],
        "Motor": [],
        "Otros": [],
    }

    for event in events:
        groups["Todos"].append(event)

        if event.get("favorito"):
            groups["Favoritos"].append(event)

        deporte = event.get("deporte")

        if deporte in groups:
            groups[deporte].append(event)
        else:
            groups["Otros"].append(event)

    return groups


def render_card(
    title: str,
    events: list[dict],
) -> str:
    content = ""

    if events:
        content = "".join(
            event_to_html(event)
            for event in events
        )
    else:
        content = (
            "<div class='empty'>"
            "No hay eventos."
            "</div>"
        )

    return f"""
    <section class="card">
        <div class="card-header">
            <h2>{escape(title)}</h2>
            <span class="counter">{len(events)}</span>
        </div>

        <div class="events">
            {content}
        </div>
    </section>
    """


# ============================================================================
# HTML COMPLETO
# ============================================================================

def generate_html(
    events: list[dict],
) -> str:
    groups = group_events(events)

    cards = []

    # Orden de tarjetas.
    for title in [
        "Todos",
        "Favoritos",
        "Fútbol",
        "Baloncesto",
        "Tenis",
        "Motor",
        "Otros",
    ]:
        cards.append(
            render_card(
                title,
                groups[title],
            )
        )

    cards_html = "\n".join(cards)

    total = len(events)
    favorites = sum(
        1
        for event in events
        if event.get("favorito")
    )

    tennis = sum(
        1
        for event in events
        if event.get("deporte") == "Tenis"
    )

    football = sum(
        1
        for event in events
        if event.get("deporte") == "Fútbol"
    )

    basketball = sum(
        1
        for event in events
        if event.get("deporte") == "Baloncesto"
    )

    motor = sum(
        1
        for event in events
        if event.get("deporte") == "Motor"
    )

    other = sum(
        1
        for event in events
        if event.get("deporte") == "Otros"
    )

    now = datetime.now().strftime(
        "%d/%m/%Y %H:%M"
    )

    return f"""<!DOCTYPE html>
<html lang="es">

<head>
<meta charset="UTF-8">

<meta
    name="viewport"
    content="width=device-width, initial-scale=1.0"
>

<title>Agenda deportiva</title>

<style>

:root {{
    --bg: #f4f6f8;
    --card: #ffffff;
    --text: #17202a;
    --muted: #6b7280;
    --border: #e5e7eb;
    --accent: #005df8;
}}

* {{
    box-sizing: border-box;
}}

body {{
    margin: 0;
    padding: 24px;
    background: var(--bg);
    color: var(--text);
    font-family:
        Arial,
        Helvetica,
        sans-serif;
}}

.container {{
    max-width: 1500px;
    margin: auto;
}}

h1 {{
    margin: 0 0 6px 0;
}}

.subtitle {{
    color: var(--muted);
    margin-bottom: 20px;
}}

.stats {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(130px, 1fr));
    gap: 12px;
    margin-bottom: 20px;
}}

.stat {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px;
}}

.stat-number {{
    font-size: 28px;
    font-weight: 700;
}}

.stat-label {{
    color: var(--muted);
    font-size: 13px;
}}

.search {{
    width: 100%;
    padding: 13px 15px;
    border: 1px solid var(--border);
    border-radius: 12px;
    font-size: 15px;
    margin-bottom: 20px;
}}

.grid {{
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(360px, 1fr));
    gap: 18px;
}}

.card {{
    background: var(--card);
    border: 1px solid var(--border);
    border-radius: 16px;
    overflow: hidden;
    box-shadow:
        0 2px 8px rgba(0, 0, 0, 0.04);
}}

.card-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 15px 17px;
    border-bottom: 1px solid var(--border);
}}

.card-header h2 {{
    margin: 0;
    font-size: 18px;
}}

.counter {{
    min-width: 28px;
    height: 28px;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    border-radius: 50%;
    background: var(--accent);
    color: white;
    font-size: 13px;
    font-weight: 700;
}}

.events {{
    padding: 6px;
}}

.event {{
    display: flex;
    gap: 12px;
    padding: 12px;
    border-radius: 10px;
    border-bottom: 1px solid var(--border);
}}

.event:last-child {{
    border-bottom: 0;
}}

.event.favorite {{
    background: rgba(255, 193, 7, 0.08);
}}

.event-time {{
    min-width: 48px;
    font-weight: 700;
    font-size: 15px;
}}

.event-info {{
    min-width: 0;
    flex: 1;
}}

.event-name {{
    font-weight: 700;
    line-height: 1.35;
}}

.event-competition {{
    margin-top: 3px;
    color: var(--muted);
    font-size: 13px;
}}

.channels {{
    margin-top: 6px;
    color: #374151;
    font-size: 12px;
}}

.channels.muted {{
    color: #9ca3af;
    font-style: italic;
}}

.empty {{
    padding: 20px;
    color: var(--muted);
    text-align: center;
}}

.hidden {{
    display: none !important;
}}

.footer {{
    margin-top: 25px;
    text-align: center;
    color: var(--muted);
    font-size: 12px;
}}

@media (max-width: 600px) {{
    body {{
        padding: 12px;
    }}

    .grid {{
        grid-template-columns: 1fr;
    }}

    .event {{
        padding: 10px;
    }}
}}

</style>
</head>

<body>

<div class="container">

    <h1>Agenda deportiva</h1>

    <div class="subtitle">
        Última actualización: {escape(now)}
    </div>

    <div class="stats">

        <div class="stat">
            <div class="stat-number">{total}</div>
            <div class="stat-label">Eventos</div>
        </div>

        <div class="stat">
            <div class="stat-number">{favorites}</div>
            <div class="stat-label">Favoritos</div>
        </div>

        <div class="stat">
            <div class="stat-number">{football}</div>
            <div class="stat-label">Fútbol</div>
        </div>

        <div class="stat">
            <div class="stat-number">{basketball}</div>
            <div class="stat-label">Baloncesto</div>
        </div>

        <div class="stat">
            <div class="stat-number">{tennis}</div>
            <div class="stat-label">Tenis</div>
        </div>

        <div class="stat">
            <div class="stat-number">{motor}</div>
            <div class="stat-label">Motor</div>
        </div>

        <div class="stat">
            <div class="stat-number">{other}</div>
            <div class="stat-label">Otros</div>
        </div>

    </div>

    <input
        id="search"
        class="search"
        type="search"
        placeholder="Buscar evento, torneo o canal..."
    >

    <div class="grid" id="cards">

        {cards_html}

    </div>

    <div class="footer">
        Agenda generada automáticamente.
    </div>

</div>


<script>

const search = document.getElementById("search");

search.addEventListener("input", function() {{

    const query = this.value
        .trim()
        .toLowerCase();

    document
        .querySelectorAll(".event")
        .forEach(function(event) {{

            const text =
                event.dataset.search || "";

            if (!query || text.includes(query)) {{
                event.classList.remove("hidden");
            }} else {{
                event.classList.add("hidden");
            }}

        }});

}});

</script>

</body>
</html>
"""


# ============================================================================
# MAIN
# ============================================================================

def main() -> None:
    try:
        events = fetch_and_parse_agenda()

    except requests.RequestException as exc:
        print(
            f"Error descargando la agenda: {exc}"
        )
        return

    except Exception as exc:
        print(
            f"Error procesando la agenda: {exc}"
        )
        return

    if not events:
        print(
            "No se han encontrado eventos."
        )
        return

    # Orden cronológico.
    events.sort(
        key=lambda event: (
            event.get("hora", "99:99"),
            normalize_search(
                event.get("evento", "")
            ),
        )
    )

    html = generate_html(events)

    with open(
        "index.html",
        "w",
        encoding="utf-8",
    ) as file:
        file.write(html)

    counts = Counter(
        event.get("deporte", "Otros")
        for event in events
    )

    print(
        f"Eventos encontrados: {len(events)}"
    )

    print(
        " | ".join(
            f"{sport}: {count}"
            for sport, count in counts.items()
        )
    )

    tennis_events = [
        event
        for event in events
        if event.get("deporte") == "Tenis"
    ]

    if tennis_events:
        print("\nTENIS DETECTADO:")

        for event in tennis_events:
            print(
                f"  {event['hora']} | "
                f"{event['evento']} | "
                f"{event['competicion']} | "
                f"{', '.join(event['canales']) or 'sin canal visible'}"
            )


if __name__ == "__main__":
    main()
