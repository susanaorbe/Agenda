from datetime import date
import re

from config import (
    BASKET_ALLOWED_COMPETITIONS_RE,
    BASKET_CONTEXT_RE,
    BASKET_WOMEN_RE,
    BUNDESLIGA_2_RE,
    BUNDESLIGA_RE,
    CASTILLA_RE,
    CHAMPIONS_NON_FOOTBALL_RE,
    CHAMPIONS_RE,
    CHANNEL_LINE_RE,
    CLEAN_TV_RE,
    COMPETITION_TERMS,
    COPA_DEL_REY_RE,
    EREDIVISIE_RE,
    EUROCUP_RE,
    EUROLIGA_RE,
    EURO_FINAL_RE,
    EVENT_CLEANUP_TRAIL_RE,
    EVENT_SIMILARITY_SYNONYMS,
    EVENT_TEXT_RE,
    EXCLUDED_COMPETITIONS_RE,
    EXCLUDED_SPORTS_RE,
    GOLF_RE,
    JUNK_RESIDUES_RE,
    LALIGA_RE,
    LIGA_PORTUGAL_RE,
    LIGUE1_RE,
    NATIONS_LEAGUE_RE,
    NBA_RE,
    PREMIER_RE,
    PRIMERA_RFEF_RE,
    REAL_MADRID_RE,
    SERIE_A_RE,
    SPAIN_SELECTION_RE,
    SPANISH_TENNIS_PLAYERS_RE,
    TENNIS_EVENT_RE,
    TIME_RE,
    TV_IDENTIFIERS_RE,
    WOMEN_FOOTBALL_COMPETITIONS,
    WOMEN_RE,
    WORLD_CUP_RE,
    WTA_RE,
    DAVIS_CUP_RE,
    YOUTH_BASKET_RE,
    clean_channel_display_name,
    clean_time,
    contains_previo_or_previa,
    is_excluded_channel,
    normalize_search_text,
)


def _strip_parentheses_padded(text: str) -> str:
    """Devuelve texto normalizado y acolchado sin paréntesis para detectar etiquetas como (COPA DE LA REINA)."""
    norm = normalize_search_text(text)
    without_parens = re.sub(r"[()]+", " ", norm)
    collapsed = re.sub(r"\s+", " ", without_parens).strip()
    return f" {collapsed} "


def normalize_competition_label(comp_text: str) -> str:
    """Normaliza nombres largos o variantes de competición a su etiqueta canónica."""
    raw = re.sub(r"\s+", " ", str(comp_text or "")).strip()
    if not raw:
        return ""
    norm = normalize_search_text(raw)
    if norm in {
        "national basketball association",
        "nba basketball",
        "us nba",
        "usa nba",
    } or re.fullmatch(r"nba(?:\s+20\d{2}(?:[/-]\d{2,4})?)?", norm):
        return "NBA"
    if norm in {"euroliga", "euroleague", "euro league", "turkish airlines euroleague"} or re.fullmatch(
        r"(?:euroliga|euroleague|euro league)(?:\s+20\d{2}(?:[/-]\d{2,4})?)?", norm
    ):
        return "EUROLIGA"
    if norm in {"liga endesa acb", "liga endesa", "acb"}:
        return "ACB"
    return raw.upper()


def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)
    padded_motor_blob = f" {blob_lower} "
    if any(
        forbidden in padded_motor_blob
        for forbidden in [
            " academy ", " academie ", " moto2 ", " moto 2 ", " moto3 ", " moto 3 ",
            " motomini ", " moto mini ", " 160cc ", " rookies ", " supercars ",
            " formula 2 ", " fia formula 2 ", " f2 ",
        ]
    ):
        return ("", "", False)
    if any(junk in padded_motor_blob for junk in [" previo ", " post ", " rueda de prensa ", " podio ", " reportaje ", " warm up ", " warmup "]):
        return ("", "", False)
    if re.search(
        r"\b(?:libres|libre|treinos\s+livres|livres|free\s+practice|practice|fp\s*[1-3])\b",
        blob_lower,
    ):
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

    if re.search(
        r"\b(?:libres|libre|treinos\s+livres|livres|free\s+practice|practice|fp\s*[1-3])\b",
        clean_norm,
    ):
        return ("", "", False)

    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
        return (comp_name, event_title, is_fav)

    if comp_name == "MotoGP":
        has_allowed_session = any(k in clean_norm for k in ["carrera", "race", "sprint"])
        is_practice_or_quali = any(
            k in clean_norm
            for k in ["free practice", "practice", "libres", "libre", "treinos libres", "livres", "qualifying", "clasificacion", "fp1", "fp2", "fp3", "q1", "q2"]
        )
        if is_practice_or_quali and not has_allowed_session:
            return ("", "", False)
        return (comp_name, event_title, has_allowed_session)

    is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])
    return (comp_name, event_title, is_fav)


def _is_non_football_premier_event(padded_blob: str) -> bool:
    """Detecta torneos o eventos de otros deportes con la palabra 'premier' (ej. WBSC Premier 12)."""
    if re.search(r"\bwbsc\s+premier(?:\s+\d+)?\b", padded_blob):
        return True
    if " premier 12 " in padded_blob or re.search(r"\bpremier\s*12\b", padded_blob):
        return True
    non_football_tokens = (
        " beisbol ", " baseball ", " wbsc ", " softball ", " softbol ",
        " snooker ", " darts ", " dardos ", " badminton ", " squash ", " table tennis ", " tenis de mesa "
    )
    return any(tok in padded_blob for tok in non_football_tokens)


def _is_non_english_premier_league(padded_blob: str) -> bool:
    """Evita confundir ligas nacionales o torneos llamados 'premier league' de otros países con la Premier League inglesa."""
    non_english_tokens = (
        " congo ", " congolese ", " brazzaville ", " kinshasa ", " dr congo ", " rdc ",
        " lebanese ", " libano ", " liban ",
        " egyptian ", " egipto ", " egypt ",
        " irish ", " irlandesa ", " ireland ",
        " welsh ", " gales ", " wales ",
        " scottish ", " escocia ", " scotland ",
        " thai ", " tailandia ", " thailand ",
        " indian ", " india ",
        " russian ", " rusia ", " russia ",
        " ukrainian ", " ucrania ", " ukraine ",
        " armenian ", " armenia ",
        " vietnamese ", " vietnam ",
        " malaysian ", " malasia ", " malaysia ",
        " singapore ", " singapur ",
        " ghana ", " kenya ", " uganda ", " tanzania ", " zambia ", " nigeria ", " south africa ",
        " turks and caicos ", " turks caicos ", " turks ", " caicos ",
        " premier 12 ", " wbsc ",
    )
    return any(tok in padded_blob for tok in non_english_tokens)


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:
    padded_blob = f" {normalize_search_text(blob)} "
    unparenthesized_blob = _strip_parentheses_padded(blob)
    padded_tv = f" {normalize_search_text(tv_blob)} "

    if _is_non_football_premier_event(padded_blob):
        return ("", "", "", False, False, "", "")

    is_explicit_basketball = any(
        tok in padded_blob
        for tok in (
            " baloncesto ", " basketball ", " lega basket ",
            " pallacanestro ", " baskets ", " liga femenina de baloncesto "
        )
    )
    is_explicit_volleyball = any(
        tok in padded_blob
        for tok in (" volleyball ", " volley ", " voleibol ")
    )

    if is_explicit_volleyball and not is_explicit_basketball:
        return ("", "", "", False, False, "", "")

    if EXCLUDED_SPORTS_RE.search(padded_blob) or "ehf tv" in padded_tv or "movistar golf" in padded_blob:
        return ("", "", "", False, False, "", "")
    competition_filter_blob = re.sub(r"\b[1-5]\s*[ªaº]?\s*(?:ronda|round)\b", " ", padded_blob, flags=re.IGNORECASE)
    if EXCLUDED_COMPETITIONS_RE.search(competition_filter_blob):
        return ("", "", "", False, False, "", "")

    blob_normalized = normalize_search_text(padded_blob)

    if DAVIS_CUP_RE.search(padded_blob):
        if GOLF_RE.search(padded_tv) or "movistar golf" in padded_blob:
            return ("", "", "", False, False, "", "")
        if not SPAIN_SELECTION_RE