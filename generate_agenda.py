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

# URLs de programación de Fútbol en la TV para Motor[cite: 1]
FUTBOLENLATV_AUTOMOVILISMO_URL = "https://www.futbolenlatv.es/deporte/automovilismo"
FUTBOLENLATV_MOTOCICLISMO_URL = "https://www.futbolenlatv.es/deporte/motociclismo"

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
    "mediaset infinity", "motogp videopass", "movistar+ lite", "nba league pass",
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
    return any(key == excluded or key.startswith(excluded) for excluded in EXCLUDED_CHANNEL_KEYS)


def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder", 
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|primera federaci[oó]n|videopass)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis channel\b", r"\borange tv\b", r"\bchannel\s*[-–—]\s*orange tv\b", r"\bprimera federaci[oó]n\b", r"\bvideopass\b"
)

JUNK_RESIDUES_RE = rx(
    r"\(\s*(?:cataluña|catalunya|país vasco|pais vasco|galicia|andalucía|andalucia)\s*\)",
    r"\(\s*(?:ver gratis|ver en directo|acceder|ver)\s*\)",
    r"\(\s*\d+\s*\)"
)


# ============================================================================
# EXTRACCIÓN DE MOTOR (F1, MotoGP, Fórmula E, Indycar)
# ============================================================================

def fetch_futbolenlatv_motor_events(url: str, target_category: str) -> list[dict]:
    motor_events = []
    try:
        response = requests.get(url, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        items = soup.find_all(["li", "div", "article", "tr"], class_=re.compile("match|item|event|row|partido|guia", re.IGNORECASE))
        if not items:
            items = soup.find_all(True)

        seen_times = set()
        for item in items:
            text_block = item.get_text(" ", strip=True)
            text_lower = text_block.lower()

            if target_category == "Fórmula 1":
                if not ("formula 1" in text_lower or "f1" in text_lower) or "academy" in text_lower:
                    continue
                comp_name = "Fórmula 1"
                default_channels = ["DAZN F1", "DAZN"]
            elif target_category == "MotoGP":
                if "motogp" not in text_lower:
                    continue
                if any(cat in text_lower for cat in ["moto2", "moto 2", "moto3", "moto 3", "rookies"]):
                    continue
                comp_name = "MotoGP"
                default_channels = ["DAZN MotoGP", "DAZN"]
            elif target_category == "Fórmula E":
                if "formula e" not in text_lower and "fórmula e" not in text_lower:
                    continue
                comp_name = "Fórmula E"
                default_channels = ["Eurosport 1", "Eurosport 2", "DAZN"]
            elif target_category == "Indycar":
                if "indycar" not in text_lower and "indy car" not in text_lower:
                    continue
                comp_name = "Indycar"
                default_channels = ["M+ Deportes", "DAZN"]
            else:
                continue

            if any(junk in text_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje"]):
                continue

            time_match = TIME_RE.search(text_block)
            if not time_match:
                continue

            time_clean = clean_time(time_match.group(0))
            if time_clean in seen_times:
                continue

            channels = []
            for ch in default_channels:
                if ch.lower() in text_lower or "dazn" in text_lower or "eurosport" in text_lower or "movistar" in text_lower:
                    channels.append(ch)
            if not channels:
                channels = default_channels

            title = text_block.replace(time_match.group(0), "").strip()
            title = re.sub(r"(?i)en directo|deporte|termina\s*\d{2}:\d{2}|\d{2}:\d{2}|[–\-\:\s]+", " ", title).strip()
            title = re.sub(r"\s+", " ", title)

            clean_norm = normalize_search_text(title)
            is_valid_session = any(k in clean_norm for k in [
                "fp1", "fp2", "fp3", "libres", "practice", "qualifying", "clasificacion",
                "sprint", "carrera", "race", "warm up"
            ])

            if is_valid_session and title and len(title) > 2:
                seen_times.add(time_clean)
                
                # REGLAS DE FAVORITOS SOLICITADAS:
                # - F1: solo clasificaciones (qualifying/clasificacion), sprint y carreras (race/carrera)
                # - MotoGP, Fórmula E, Indycar: solo todas las carreras (race/carrera)
                is_fav = False
                if comp_name == "Fórmula 1":
                    is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
                else:
                    is_fav = any(k in clean_norm for k in ["carrera", "race"])

                motor_events.append({
                    "hora": time_clean,
                    "deporte": "Motor",
                    "icono": "🏆",
                    "competicion": comp_name,
                    "evento": f"{comp_name} - {title}",
                    "tv_list": channels,
                    "is_filtered": is_fav,
                    "is_configured": True,
                })
    except Exception as e:
        print(f"Aviso: No se pudo cargar la parrilla de motor desde {url}: {e}")

    return motor_events


# ============================================================================
# NÚCLEO DE CLASIFICACIÓN (EXCLUYENDO TODO LO QUE NO SEA MOTOR SOLICITADO)
# ============================================================================

def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str]:
    # Como SOLO quieres Motor (F1, MotoGP, Fórmula E, Indycar), descartamos todo lo demás del widget general.
    MOTOR_GENERAL_RE = rx(r"\bformula 1\b", r"\bf1\b", r"\bmotogp\b", r"\bindycar\b", r"\bindy car\b", r"\bformula e\b", r"\bfórmula e\b")
    
    if contains(MOTOR_GENERAL_RE, blob):
        is_f1 = ("formula 1" in blob or "f1" in blob) and "academy" not in blob
        is_motogp = "motogp" in blob and "moto2" not in blob and "moto3" not in blob
        is_indycar = "indycar" in blob or "indy car" in blob
        is_formulae = "formula e" in blob or "fórmula e" in blob

        if not (is_f1 or is_motogp or is_indycar or is_formulae):
            return ("", "", "", False, False, "")

        comp_name = "Motor"
        if is_f1: comp_name = "Fórmula 1"
        elif is_motogp: comp_name = "MotoGP"
        elif is_indycar: comp_name = "Indycar"
        elif is_formulae: comp_name = "Fórmula E"

        event_parts = [p for p in text_lines if normalize_search_text(p) != normalize_search_text(comp_name)]
        event_title = " - ".join(event_parts) if event_parts else comp_name
        clean_norm = normalize_search_text(event_title)

        # Aplicar reglas de favoritos también aquí si procede del widget general
        is_fav = False
        if comp_name == "Fórmula 1":
            is_fav = any(term in clean_norm for term in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
        else:
            is_fav = any(term in clean_norm for term in ["carrera", "race"])

        return ("Motor", "🏆", comp_name, is_fav, True, event_title)

    # Bloquear cualquier otro deporte (Fútbol, Baloncesto, Tenis, etc.)
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

        looks_like_channel = (
            TV_IDENTIFIERS_RE.search(part)
            or CHANNEL_LINE_RE.search(part_lower)
            or any(term in part_lower for term in ("m+", "dazn", "eurosport", "youtube"))
        )
        if looks_like_channel:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            clean_part = JUNK_RESIDUES_RE.sub("", clean_part).strip()
            sub_parts = re.split(r"[,|\n]+", clean_part)
            for channel in sub_parts:
                channel = channel.strip().rstrip(":").strip()
                if channel and not is_excluded_channel(channel) and channel not in channels:
                    channels.append(channel)
            continue

        text_lines.append(part)

    if not text_lines:
        return "", "", [], "", []

    tournament = text_lines[0]
    matchup = " - ".join(text_lines[1:]) if len(text_lines) > 1 else tournament

    return time_clean, matchup, channels, tournament, text_lines


def fetch_and_parse_agenda() -> list[dict]:
    results = []
    seen_events = set()

    # Obtener eventos de las páginas específicas de motor de futbolenlatv.es[cite: 1]
    f1_events = fetch_futbolenlatv_motor_events(FUTBOLENLATV_AUTOMOVILISMO_URL, "Fórmula 1")
    motogp_events = fetch_futbolenlatv_motor_events(FUTBOLENLATV_MOTOCICLISMO_URL, "MotoGP")
    fe_events = fetch_futbolenlatv_motor_events(FUTBOLENLATV_AUTOMOVILISMO_URL, "Fórmula E")
    indy_events = fetch_futbolenlatv_motor_events(FUTBOLENLATV_AUTOMOVILISMO_URL, "Indycar")

    for ev in f1_events + motogp_events + fe_events + indy_events:
        event_key = (ev["hora"], normalize_search_text(ev["competicion"]), normalize_search_text(ev["evento"]))
        if event_key not in seen_events:
            seen_events.add(event_key)
            results.append(ev)

    # También explorar el widget general por si incluye Indycar o Fórmula E de forma directa
    try:
        response = requests.get(WIDGET_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")

        for item in soup.find_all(("div", "tr", "li")):
            try:
                time_clean, event_str, channels, tournament, text_lines = parse_row_elements(item)
                if not time_clean or not text_lines or not channels: 
                    continue

                tv_blob = " ".join(channels).lower()
                blob = normalize_search_text(f"{' '.join(text_lines)} {tournament} {tv_blob}")

                sport, icon, competition, is_favorite, is_configured, custom_event = get_sport_and_competition(
                    blob, tournament, tv_blob, text_lines
                )
                
                if not sport:
                    continue

                final_event = custom_event if custom_event else event_str
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
        print(f"Error cargando el widget general: {e}")

    results.sort(key=lambda x: x["hora"])
    return results


# ============================================================================
# GENERACIÓN DE HTML (Adaptado solo a Motor)
# ============================================================================

def generate_html(events):
    spain_tz = zoneinfo.ZoneInfo("Europe/Madrid")
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")
    
    total_cnt = len(events)
    filtered_cnt = sum(1 for event in events if event["is_filtered"])

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos de motor disponibles en este momento.</td></tr>')
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
                        tv_badges_list.append(
                            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" class="tv-badge" title="Abrir canal {safe_channel}">{safe_channel} 🔗</a>'
                        )
                else:
                    tv_badges_list.append(f'<span class="tv-badge" style="cursor:default;">{safe_channel}</span>')

            tv_badges = "".join(tv_badges_list)
            search_text = normalize_search_text(" ".join([ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]))
            
            rows_list.append(
                f"""
                <tr class="event-row" data-filtered="{str(ev['is_filtered']).lower()}" data-search="{escape(search_text, quote=True)}">
                    <td class="date-col"><span class="date-badge today">Hoy</span></td>
                    <td class="time-col"><span class="time-badge">{escape(str(ev['hora']))}</span></td>
                    <td class="sport-col"><span class="sport-tag">{escape(str(ev['icono']))} {escape(str(ev['competicion']))}</span></td>
                    <td class="comp-col"><div class="comp-title">{escape(str(ev['competicion']))}</div></td>
                    <td class="event-col"><div class="event-title">{escape(str(ev['evento']))}</div></td>
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
    <title>Agenda Motor - Hoy</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg-color: #0f172a; --card-bg: #1e293b; --border-color: #334155; --text-main: #f8fafc; --text-muted: #94a3b8; --accent-blue: #3b82f6; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 16px 12px; display: flex; justify-content: center; }}
        .container {{ width: 100%; max-width: 1150px; }}
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 8px; }}
        h1 {{ font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #ef4444, #f59e0b); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header-controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .btn-update {{ background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; }}
        .btn-alt {{ background: #6366f1; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; text-decoration: none; display: inline-flex; align-items: center; }}
        .last-update {{ font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; text-align: right; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 16px; }}
        .stat-card {{ background: var(--card-bg); padding: 10px 14px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }}
        .stat-card.active-card {{ border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }}
        .stat-card .val {{ font-size: 1.2rem; font-weight: 700; color: var(--accent-blue); }}
        .stat-card .lbl {{ font-size: 0.8rem; color: var(--text-muted); }}
        
        .filter-container {{ display: flex; gap: 10px; margin-bottom: 14px; }}
        .search-input {{ padding: 10px 14px; border-radius: 8px; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); font-size: 0.9rem; outline: none; width: 100%; }}
        
        .table-card {{ background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: visible !important; margin-bottom: 80px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }}
        th {{ background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; }}
        tr.event-row:hover {{ background-color: #243146; }}
        
        .sport-col {{ width: 155px !important; white-space: nowrap; }}
        .time-col, .date-col {{ white-space: nowrap; }}
        .date-badge {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; }}
        .time-badge {{ background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; }}
        .comp-title {{ font-weight: 600; color: #38bdf8; font-size: 0.85rem; }}
        .event-title {{ font-weight: 700; color: #ffffff; font-size: 0.9rem; }}
        .tv-container {{ display: flex; flex-direction: column; gap: 4px; }}
        .tv-badge {{ display: inline-block; background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; text-decoration: none; }}
        
        .dropdown-tv {{ position: relative; display: inline-block; }}
        .tv-dropdown-btn {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); text-align: left; width: 100%; }}
        .dropdown-content {{ display: none; position: absolute; background-color: #111827; min-width: 220px; z-index: 1000; border: 1px solid var(--border-color); border-radius: 8px; padding: 4px 0; left: 0; top: 100%; }}
        .dropdown-tv.show .dropdown-content {{ display: block; }}
        .dropdown-content a {{ color: #f8fafc; padding: 8px 12px; text-decoration: none; display: block; font-size: 0.78rem; }}
        .empty-state {{ text-align: center; padding: 30px; color: var(--text-muted); }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div><h1>🏁 Agenda Motor - F1, MotoGP, FE, Indycar</h1></div>
        <div class="header-controls">
            <a href="https://hubu.ru/fctvlink" target="_blank" class="btn-alt">FCTV33</a>
            <a href="https://daddylive.pk/" target="_blank" class="btn-alt">DLHD</a>
            <button class="btn-update" onclick="location.reload()">🔄 Actualizar</button>
        </div>
        <div class="last-update">Última actualización: <strong>{fecha_act} (España)</strong></div>
    </header>
    <div class="stats-grid">
        <div class="stat-card active-card" id="card-todos" onclick="setFilter('todos')">
            <div><div class="lbl">Todos los Eventos</div><div class="val">{total_cnt}</div></div><div style="font-size:1.1rem">📺</div>
        </div>
        <div class="stat-card" id="card-favoritos" onclick="setFilter('favoritos')">
            <div><div class="lbl">Favoritos (Clasics. & Carreras)</div><div class="val" style="color:#a78bfa">{filtered_cnt}</div></div><div style="font-size:1.1rem">📌</div>
        </div>
    </div>
    <div class="filter-container">
        <input type="text" id="searchInput" class="search-input" onkeyup="filterTable()" placeholder="🔍 Filtrar sesión, campeonato o canal TV...">
    </div>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th class="date-col" style="width: 70px;">Fecha</th>
                    <th class="time-col" style="width: 70px;">Hora</th>
                    <th class="sport-col" style="width: 155px;">Categoría</th>
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
    document.querySelectorAll('.dropdown-tv').forEach(item => {{ if (item !== dropdown) item.classList.remove('show'); }});
    dropdown.classList.toggle('show');
}}

window.onclick = function(event) {{
    if (!event.target.matches('.tv-dropdown-btn')) {{
        document.querySelectorAll('.dropdown-tv').forEach(item => item.classList.remove('show'));
    }}
}}

let currentFilter = 'todos';

function setFilter(filterType) {{
    currentFilter = cleanStr(filterType);
    document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active-card'));
    document.getElementById('card-' + currentFilter).classList.add('active-card');
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

        const isFiltered = tr.getAttribute('data-filtered') === 'true';
        const text = cleanStr(tr.getAttribute('data-search'));

        let matchesFilter = (currentFilter === 'todos') || (currentFilter === 'favoritos' && isFiltered);
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
    print(f"Archivo index.html generado con éxito. Total eventos de Motor: {len(events)}")
