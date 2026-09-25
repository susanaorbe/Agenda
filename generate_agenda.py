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
        "AppleWebKit/537.36"
    )
}

REQUEST_TIMEOUT = 15


EXCLUDED_CHANNELS = {
    "andalucía tv",
    "antel tv internacional",
    "apple tv",
    "aragón deporte",
    "aragon deporte",
    "aragón deportes",
    "aragon deportes",
    "aragón play",
    "aragón tv",
    "aragon tv",
    "asobal tv",
    "atp tennis tv",
    "baloncesto tv",
    "baloncesto tv ppv",
    "betevé web",
    "cayotv youtube(ver)",
    "cmmplay(castilla-lm)",
    "dazn 1 bar(m148)",
    "dazn 2 bar(m149)",
    "deportes tvcanaria youtube",
    "ehf tv",
    "esport3(cataluña)",
    "esport3 web",
    "etbk(país vasco)",
    "etb1(país vasco)",
    "eurovision sports tv",
    "fanplay tv",
    "fanseat",
    "fc barcelona ppv youtube",
    "fff tv youtube",
    "fiba youtube",
    "flamengo tv youtube",
    "hbo max",
    "laliga tv bar",
    "laliga tv m2",
    "laliga tv m3",
    "laliga tv m4",
    "laliga tv m5",
    "laliga+ plus",
    "la 7(castilla y león)",
    "liga futve",
    "liga futve youtube",
    "ligafutve app",
    "m+ #vamos bar(307)",
    "m+ #vamos bar 2(308)",
    "m+ laliga hdr(m440 o111)",
    "mediaset infinity",
    "motogp videopass",
    "movistar+ lite",
    "nba league pass",
    "onefootball",
    "orange fútbol 1(107)",
    "real sociedad tv youtube",
    "red bull tv",
    "rtve play",
    "sefutbol youtube",
    "siroko tv",
    "streaming / web",
    "tv canaria",
    "tv footballclub(acceder)",
    "tv melilla",
    "tv galicia",
    "tvg(galicia)",
    "tvg2(galicia)",
    "tvg web",
    "tv3(cataluña)",
    "tv5monde",
    "twitch btvesports",
    "uefa tv",
    "ver en directo",
    "ver partido",
    "win sports tv youtube",
    "wta tv",
    "101 tv(málaga)",
    "9tv león",
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

CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|ver partido",
    re.IGNORECASE,
)

PUNCTUATION_RE = re.compile(r"[\|,]+")
SPACES_RE = re.compile(r"\s+")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|"
    r"teledeporte|tv|desport|disney\+?|disney)"
)

EXCLUDED_BLOB_RE = rx(
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


TENNIS_COMPETITIONS = (
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


# ============================================================================
# UTILIDADES
# ============================================================================

def contains(pattern: re.Pattern, text: str) -> bool:
    """Devuelve True si el patrón aparece en el texto."""
    return bool(pattern.search(text))


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

    competition = first_match(
        blob,
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

    return clean_tournament(
        raw,
        "WTA Tour" if "wta" in blob else "ATP Tour",
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

    tournament = raw_tournament or ""

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
) -> bool:
    """
    Determina si el evento debe aparecer como filtrado/favorito.
    """

    # ------------------------------------------------------------------------
    # Real Madrid: prioridad absoluta.
    # ------------------------------------------------------------------------

    if contains(REAL_MADRID_RE, blob):
        return True

    # ------------------------------------------------------------------------
    # Canales excluidos.
    # ------------------------------------------------------------------------

    if any(
        EXCLUDED_CHANNELS_RE.search(channel)
        for channel in channels
    ):
        return False

    # ------------------------------------------------------------------------
    # Categorías de motor excluidas de favoritos.
    # ------------------------------------------------------------------------

    if contains(MOTO_STRICT_EXCLUDE_RE, blob):
        return False

    # ------------------------------------------------------------------------
    # Competiciones excluidas.
    # ------------------------------------------------------------------------

    if contains(EXCLUDED_BLOB_RE, blob):
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
) -> tuple[str, str, list[str], str]:
    """
    Extrae:

        hora
        evento
        canales
        competición

    de un nodo HTML.

    Devuelve cadenas/listas vacías si la estructura no es válida.
    """

    text_full = item.get_text(
        " | ",
        strip=True,
    )

    # ------------------------------------------------------------------------
    # Hora
    # ------------------------------------------------------------------------

    time_match = TIME_RE.search(text_full)
    time_clean = (
        time_match.group(0)
        if time_match
        else ""
    )

    # ------------------------------------------------------------------------
    # Partes del nodo
    # ------------------------------------------------------------------------

    raw_parts = [
        part.strip()
        for part in item.get_text(
            "\n",
            strip=True,
        ).split("\n")
        if part.strip()
    ]

    if not 2 <= len(raw_parts) <= 15:
        return "", "", [], ""

    matchup = ""
    channels: list[str] = []
    tournament = ""

    # ------------------------------------------------------------------------
    # Clasificación de cada parte
    # ------------------------------------------------------------------------

    for part in raw_parts:
        part_lower = part.lower()

        # Elementos que no necesitamos.
        if (
            TIME_RE.match(part)
            or part_lower in {
                "ver partido",
                "directo",
                "(ver en directo)",
            }
        ):
            continue

        has_tv_identifier = bool(
            TV_IDENTIFIERS_RE.search(part)
        )

        # --------------------------------------------------------------------
        # Partido / evento
        # --------------------------------------------------------------------

        if (
            " - " in part
            and not has_tv_identifier
        ):
            if len(part) > 3 and not matchup:
                matchup = part

            continue

        # --------------------------------------------------------------------
        # Canales
        # --------------------------------------------------------------------

        if has_tv_identifier:
            clean_part = CLEAN_TV_RE.sub(
                "",
                part,
            ).strip()

            for channel in clean_part.split(","):
                channel = (
                    channel
                    .strip()
                    .rstrip(":")
                    .strip()
                )

                channel_lower = channel.lower()

                if (
                    channel
                    and channel_lower not in EXCLUDED_CHANNELS
                    and channel not in channels
                ):
                    channels.append(channel)

            continue

        # --------------------------------------------------------------------
        # Competición
        # --------------------------------------------------------------------

        if (
            len(part) < 35
            and not tournament
        ):
            tournament = part

    # ------------------------------------------------------------------------
    # Fallback para eventos sin matchup detectado.
    # ------------------------------------------------------------------------

    if not matchup:
        clean_desc = text_full

        for channel in channels:
            clean_desc = clean_desc.replace(
                channel,
                "",
            )

        clean_desc = TIME_RE.sub(
            "",
            clean_desc,
        )

        clean_desc = PUNCTUATION_RE.sub(
            " ",
            clean_desc,
        )

        clean_desc = SPACES_RE.sub(
            " ",
            clean_desc,
        ).strip()

        matchup = (
            clean_desc
            if len(clean_desc) > 3
            else "Evento Deportivo"
        )

    return (
        time_clean,
        matchup,
        channels,
        tournament,
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
        return False

    if (
        contains(GOLF_RE, blob)
        or "movistar golf" in tv_blob
    ):
        return True

    if contains(EXCLUDED_BLOB_RE, blob):
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
    (
        time_clean,
        event_str,
        channels,
        tournament,
    ) = parse_row_elements(item)

    if (
        not time_clean
        or not channels
        or event_str in {
            "",
            "Evento Deportivo",
        }
    ):
        return None

    text_block = (
        f"{event_str} {tournament}"
    )

    tv_blob = " ".join(channels).lower()

    blob = (
        f"{text_block.lower()} {tv_blob}"
    )

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

                # ----------------------------------------------------------------
                # Resultado final.
                # ----------------------------------------------------------------

                results.append({
                    "hora": parsed["hora"],
                    "deporte": sport,
                    "icono": icon,
                    "competicion": competition,
                    "evento": parsed["evento"],
                    "tv_list": parsed["tv_list"],
                    "is_filtered": matches_strict_criteria(
                        parsed["blob"],
                        parsed["tv_list"],
                    ),
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
                    <th>Evento / Partido</th>
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
