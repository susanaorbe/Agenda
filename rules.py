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
    YOUTH_BASKET_RE,
    clean_channel_display_name,
    clean_time,
    contains_previo_or_previa,
    is_excluded_channel,
    normalize_search_text,
)


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
    return raw.upper()


def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)
    if any(forbidden in blob_lower for forbidden in ["academy", "academie", "moto2", "moto 2", "moto3", "moto 3", "motomini", "moto mini", "160cc", "rookies", "supercars"]):
        return ("", "", False)
    if any(junk in blob_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje", "warm up", "warmup"]):
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

    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
        return (comp_name, event_title, is_fav)

    if comp_name == "MotoGP":
        has_allowed_session = any(k in clean_norm for k in ["carrera", "race", "sprint"])
        is_practice_or_quali = any(
            k in clean_norm
            for k in ["free practice", "practice", "qualifying", "clasificacion", "fp1", "fp2", "q1", "q2"]
        )
        if is_practice_or_quali and not has_allowed_session:
            return ("", "", False)
        return (comp_name, event_title, has_allowed_session)

    is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])
    return (comp_name, event_title, is_fav)


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:
    padded_blob = f" {normalize_search_text(blob)} "
    padded_tv = f" {normalize_search_text(tv_blob)} "

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

    if TENNIS_EVENT_RE.search(padded_blob):
        if GOLF_RE.search(padded_tv) or "movistar golf" in padded_blob:
            return ("", "", "", False, False, "", "")
        tour = "WTA" if WTA_RE.search(padded_blob) else "ATP"
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"tenis", "atp", "wta", ""} else f"{tour} Tour"
        is_fav = bool(SPANISH_TENNIS_PLAYERS_RE.search(padded_blob))
        return ("Tenis", "🎾", comp, is_fav, True, "", "tenis")

    if is_explicit_basketball or BASKET_ALLOWED_COMPETITIONS_RE.search(padded_blob):
        if (
            " primera feb " in padded_blob
            or " liga femenina endesa " in padded_blob
            or " euroliga femenina " in padded_blob
            or " euroleague women " in padded_blob
            or " korean womens basketball league " in padded_blob
            or " china womens basketball association " in padded_blob
            or " fiba africa basketball league " in padded_blob
            or " womens basketball " in padded_blob
            or " women basketball " in padded_blob
            or WOMEN_RE.search(padded_blob)
            or BASKET_WOMEN_RE.search(padded_blob)
        ):
            return ("", "", "", False, False, "", "")
        if not BASKET_ALLOWED_COMPETITIONS_RE.search(padded_blob) and not any(
            tok in padded_blob
            for tok in (
                " liga femenina de baloncesto ",
                " lega basket ",
                " pallacanestro ",
                " basketball bundesliga ",
                " baskets ",
            )
        ):
            return ("", "", "", False, False, "", "")
        if NBA_RE.search(padded_blob):
            comp_name = "NBA"
            comp_key = "nba"
        elif EUROLIGA_RE.search(padded_blob):
            comp_name = "Euroliga"
            comp_key = "euroliga"
        elif " liga femenina de baloncesto " in padded_blob:
            comp_name = "Liga Femenina de Baloncesto"
            comp_key = "ligaendesa"
        elif " lega basket " in padded_blob or " pallacanestro " in padded_blob:
            comp_name = "Lega Basket Serie A"
            comp_key = "ligaendesa"
        elif " basketball bundesliga " in padded_blob or " baskets " in padded_blob:
            comp_name = "Basketball Bundesliga"
            comp_key = "ligaendesa"
        else:
            comp_name = "Liga Endesa / ACB"
            comp_key = "ligaendesa"
        is_fav = bool(
            REAL_MADRID_RE.search(padded_blob)
            and not YOUTH_BASKET_RE.search(padded_blob)
            and not WOMEN_RE.search(padded_blob)
            and not BASKET_WOMEN_RE.search(padded_blob)
        )
        return ("Baloncesto", "🏀", comp_name, is_fav, True, "", comp_key)

    if WOMEN_RE.search(padded_blob) or any(p.search(padded_blob) for p, _ in WOMEN_FOOTBALL_COMPETITIONS):
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(padded_blob) or ("femenina" in padded_blob and name.lower() in padded_blob):
                comp_match = name
                break
        if comp_match and (REAL_MADRID_RE.search(padded_blob) or SPAIN_SELECTION_RE.search(padded_blob) or "espana" in blob_normalized):
            return ("Fútbol", "⚽", comp_match, True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    if PRIMERA_RFEF_RE.search(padded_blob) or "primera federacion" in padded_blob or "primera rfef" in padded_blob:
        if not CASTILLA_RE.search(padded_blob):
            return ("", "", "", False, False, "", "")
        return ("Fútbol", "⚽", "España - Primera Federación", True, True, "", "other_football")

    if COPA_DEL_REY_RE.search(padded_blob) and not WOMEN_RE.search(padded_blob) and not BASKET_CONTEXT_RE.search(padded_blob):
        is_fav = bool(REAL_MADRID_RE.search(padded_blob) or SPAIN_SELECTION_RE.search(padded_blob))
        return ("Fútbol", "⚽", "Copa del Rey", is_fav, True, "", "copadelrey")

    if CHAMPIONS_RE.search(padded_blob) and not WOMEN_RE.search(padded_blob) and not CHAMPIONS_NON_FOOTBALL_RE.search(padded_blob):
        is_fav = bool(REAL_MADRID_RE.search(padded_blob))
        return ("Fútbol", "⚽", "UEFA Champions League", is_fav, True, "", "champions")

    foreign_primera_markers = (
        "honduras", "bolivia", "bolivian", "paraguay", "paraguayan",
        "costa rica", "colombia", "chile", "peru", "ecuador", "uruguay",
        "mexico", "argentina", "venezuela", "guatemala", "el salvador", "panama",
        "nicaragua", "brazil", "brasil", "portugal", "francia", "france",
        "alemania", "germany", "italia", "italy", "inglaterra", "england"
    )
    has_primera_division_token = (
        " primera division " in padded_blob
        and not any(m in padded_blob for m in foreign_primera_markers)
        and any(sp_m in padded_blob for sp_m in ("espana", "espana -", "real madrid", "barcelona", "atletico", "sevilla", "betis", "valencia", "getafe", "villarreal", "athletic", "real sociedad", "laliga"))
    )
    if LALIGA_RE.search(padded_blob) or has_primera_division_token:
        is_fav = bool(REAL_MADRID_RE.search(padded_blob))
        return ("Fútbol", "⚽", "LaLiga EA Sports", is_fav, True, "", "laliga")

    if PREMIER_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Premier League", False, True, "", "premier")

    brazil_serie_a_markers = (
        " brasil ", " brazil ", " brasileirao ", " campeonato brasileiro ",
        " bragantino ", " rb bragantino ", " vasco ", " vasco da gama ",
        " botafogo ", " flamengo ", " palmeiras ", " corinthians ",
        " sao paulo ", " fluminense ", " gremio ", " internacional ",
        " cruzeiro ", " atletico mineiro ", " bahia ", " fortaleza ",
        " athletico paranaense ", " vitoria ", " juventude ", " cuiba ", " criciuma "
    )
    if SERIE_A_RE.search(padded_blob) and any(m in padded_blob for m in brazil_serie_a_markers):
        return ("", "", "", False, False, "", "")

    if SERIE_A_RE.search(padded_blob) and not ("brasil" in padded_blob or "serie a brasil" in padded_blob):
        return ("Fútbol", "⚽", "Serie A", False, True, "", "seriea")

    if BUNDESLIGA_RE.search(padded_blob) and not BUNDESLIGA_2_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Bundesliga", False, True, "", "bundesliga")

    if LIGUE1_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Ligue 1", False, True, "", "ligue1")

    if EREDIVISIE_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Eredivisie", False, True, "", "eredivisie")

    if LIGA_PORTUGAL_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Liga Portugal Betclic", False, True, "", "ligaportugal")

    if WORLD_CUP_RE.search(padded_blob):
        is_fav = bool(SPAIN_SELECTION_RE.search(padded_blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "Copa Mundial de la FIFA", is_fav, True, "", "mundial")

    if EURO_FINAL_RE.search(padded_blob) and not EUROCUP_RE.search(padded_blob):
        is_fav = bool(SPAIN_SELECTION_RE.search(padded_blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "Eurocopa", is_fav, True, "", "eurocopa")

    if NATIONS_LEAGUE_RE.search(padded_blob):
        is_fav = bool(REAL_MADRID_RE.search(padded_blob) or SPAIN_SELECTION_RE.search(padded_blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "UEFA Nations League", is_fav, True, "", "nationsleague")

    return ("", "", "", False, False, "", "")


def is_event_allowed_by_futbolenlatv_rules(
    sport_label: str,
    competition_label: str,
    event_title: str,
    raw_lines: list[str] | None = None,
) -> tuple[bool, bool, str, str, str, str, str]:
    """
    Evalúa si un evento y su competición son permitidos exactamente con las mismas reglas
    que FUTBOLENLATV para 'FÚTBOL', 'BALONCESTO', 'TENIS' y 'MOTOR'.
    Retorna: (allowed, is_fav, final_sport_label, final_icon, final_comp_label, final_event_title, comp_key)
    """
    lines = [
        re.sub(r"\s+", " ", str(x or "")).strip()
        for x in (raw_lines or [])
        if re.sub(r"\s+", " ", str(x or "")).strip()
    ]
    raw_comp = str(competition_label or "").strip()
    raw_ev = str(event_title or "").strip()

    if raw_ev and raw_ev not in lines:
        lines.insert(0, raw_ev)
    if raw_comp and raw_comp not in lines:
        lines.append(raw_comp)

    blob = normalize_search_text(f"{raw_comp} {raw_ev} {' '.join(lines)}")

    sport_up = str(sport_label or "").strip().upper()
    if sport_up in {"BALONCESTO", "BASKETBALL"} and (
        "femenin" in blob or "women" in blob or " (f) " in f" {blob} " or " (w) " in f" {blob} "
    ):
        return (False, False, "", "", "", "", "")

    is_motor_candidate = sport_up in {"MOTOR", "DEPORTES DE MOTOR"} or any(
        k in blob
        for k in [
            "formula 1", "fórmula 1", "f1", "motogp",
            "formula e", "fórmula e", "indycar", "indy car",
            "automovilismo", "motociclismo", "motor",
        ]
    )

    if is_motor_candidate:
        comp_name, motor_title, is_fav = parse_motor_event(blob, raw_comp, lines or [raw_ev])
        if not comp_name:
            return (False, False, "", "", "", "", "")
        return (
            True,
            bool(is_fav),
            "MOTOR",
            "🏆",
            normalize_competition_label(comp_name),
            motor_title.upper(),
            "motor",
        )

    sport, icon, competition, is_favorite, _, _, comp_key = get_sport_and_competition(
        blob, raw_comp, "", lines or [raw_ev]
    )
    if not sport:
        return (False, False, "", "", "", "", "")

    comp_label = normalize_competition_label(competition or raw_comp)
    norm_comp = normalize_search_text(comp_label)
    if norm_comp == "brasil serie a" or ("brasil" in norm_comp and "serie a" in norm_comp):
        return (False, False, "", "", "", "", "")

    if sport.upper() == "BALONCESTO" and raw_comp:
        norm_raw_comp = normalize_search_text(raw_comp)
        if norm_raw_comp not in {"baloncesto", "basketball", "liga endesa acb", "liga endesa", "acb"}:
            comp_label = normalize_competition_label(raw_comp)

    final_ev = raw_ev
    if comp_label:
        final_ev = re.sub(re.escape(comp_label), "", final_ev, flags=re.IGNORECASE)
    if raw_comp:
        final_ev = re.sub(re.escape(raw_comp), "", final_ev, flags=re.IGNORECASE)
    final_ev = re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", final_ev).strip()
    final_ev = EVENT_CLEANUP_TRAIL_RE.sub("", final_ev).strip()
    if not EVENT_TEXT_RE.search(final_ev):
        return (False, False, "", "", "", "", "")

    return (
        True,
        bool(is_favorite),
        sport.upper(),
        icon,
        comp_label,
        final_ev.upper(),
        comp_key,
    )


def parse_row_elements(item) -> tuple[str, str, list[str], str, list[str]]:
    if item is None or not hasattr(item, "get_text"):
        return "", "", [], "", []

    raw_parts = [part.strip() for part in item.get_text("\n", strip=True).split("\n") if part.strip()]
    if not 3 <= len(raw_parts) <= 30:
        return "", "", [], "", []

    text_full = " | ".join(raw_parts)
    time_match = TIME_RE.search(text_full)
    time_clean = clean_time(time_match.group(0)) if time_match else ""

    if not time_clean:
        return "", "", [], "", []

    channels: list[str] = []
    channel_keys = set()
    text_lines = []

    for part in raw_parts:
        part = JUNK_RESIDUES_RE.sub("", part).strip()
        if not part:
            continue

        part_lower = normalize_search_text(part)
        if TIME_RE.fullmatch(part) or part_lower in {"ver partido", "directo", "(ver en directo)", "ver gratis", "(ver)", "acceder", "(acceder)"}:
            continue
        if re.fullmatch(r"[\s,.|;:/-]*", part):
            continue
        if re.fullmatch(r"\(?[mo]\+?\d+.*\)?", part_lower):
            continue

        is_primera_federacion_channel = part_lower == "primera federacion"
        is_laliga_competition = "laliga" in part_lower and not any(token in part_lower for token in (" tv", "m+", "movistar", "dazn"))
        is_tennis_tv_channel = bool(re.fullmatch(r"(?:atp|wta)\s+tennis\s+tv", part_lower))

        looks_like_channel = (
            is_primera_federacion_channel
            or is_tennis_tv_channel
            or (TV_IDENTIFIERS_RE.search(part) and not is_laliga_competition)
            or CHANNEL_LINE_RE.search(part_lower)
            or any(term in part_lower for term in (
                "m+", "dazn", "youtube", "fanatiz", "onefootball",
                "siroko", "tv footballclub", "aragon tv", "aragon play",
                "cmmplay", "etb1", "tvg", "tv3", "esport3", "hbo max", "ehf tv", "videopass", "prime video", "amazon", "à punt", "rcn", "beisbolplay", "app"
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
                channel = clean_channel_display_name(channel)
                channel_lower = normalize_search_text(channel)

                if (
                    channel
                    and not is_excluded_channel(channel)
                    and normalize_search_text(channel) not in channel_keys
                    and not re.fullmatch(r"\(?[mo]\+?\d+.*\)?", channel_lower)
                    and channel_lower not in {"acceder", "(acceder)", "ver en directo"}
                ):
                    channels.append(channel)
                    channel_keys.add(normalize_search_text(channel))
            continue

        text_lines.append(part)

    if not text_lines or not channels:
        return "", "", [], "", []

    tournament_candidates = []
    matchup_candidates = []
    for part in text_lines:
        part_lower = normalize_search_text(part)
        is_competition_line = any(term in part_lower for term in COMPETITION_TERMS)
        has_match_separator = bool(
            re.search(r"\s+-\s+|\s+vs\.?\s+|\s+v\.\s+", part, re.IGNORECASE)
            or re.search(r"\s\(f\)\s*-\s*", part, re.IGNORECASE)
        )
        is_primera_federacion_group = bool(
            re.search(r"primera\s+federaci[oó]n", part_lower)
            and re.search(r"\bgrupo\s*\d+\b", part_lower)
            and not re.search(r"\bvs\.?\b|\bv\.\b", part_lower)
        )
        if is_primera_federacion_group or (is_competition_line and not has_match_separator):
            tournament_candidates.append(part)
        else:
            matchup_candidates.append(part)

    if tournament_candidates:
        valid_tournaments = [
            t for t in tournament_candidates
            if normalize_search_text(t) not in {
                "fase de grupos", "jornada", "cuartos de final", "semifinales", "final", "ida", "vuelta"
            }
        ]
        tournament = valid_tournaments[0] if valid_tournaments else tournament_candidates[0]
        event_lines = [part for part in matchup_candidates if part != tournament]
    else:
        tournament = text_lines[0]
        event_lines = text_lines[1:]

    matchup = " - ".join(event_lines) if event_lines else tournament
    matchup = EVENT_CLEANUP_TRAIL_RE.sub("", matchup).strip()

    if contains_previo_or_previa(tournament, matchup, *text_lines):
        return "", "", [], "", []

    return time_clean, matchup, channels, tournament, text_lines


def event_similarity_key(x):
    comp_norm = normalize_search_text(x.get("competicion", ""))
    ev_norm = normalize_search_text(x.get("evento", ""))

    for k, v in EVENT_SIMILARITY_SYNONYMS.items():
        comp_norm = comp_norm.replace(k, v)
        ev_norm = ev_norm.replace(k, v)

    for w in [" vs ", " - ", "fc", "bc", "basket", "club", "mts", "red", "star"]:
        ev_norm = ev_norm.replace(w, " ")

    ev_core = " ".join(sorted(set([w for w in ev_norm.split() if len(w) > 2])))
    ev_date = x.get("date_obj") or date.min
    return (ev_date, x.get("hora", ""), comp_norm, ev_core)