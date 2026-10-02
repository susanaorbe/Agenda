#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Agenda Deportiva Personalizada - "Agenda Deportiva"
Extracción, filtrado y generación de agenda desde futbolenlatv.com
"""

from collections import Counter
from datetime import datetime
import os
import re
import sys
from typing import Iterable, List, Dict, Tuple, Optional

import requests
from bs4 import BeautifulSoup

# ============================================================================
# 1. CONFIGURACIÓN GLOBAL Y PARÁMETROS
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
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "es-ES,es;q=0.9,en;q=0.8",
}

REQUEST_TIMEOUT = 15

# Canales y plataformas a excluir por completo según tus preferencias
EXCLUDED_CHANNELS = {
    "* sin tv en directo *",
    "fanseat",
    "dazn",
    "dazn 1",
    "dazn 2",
    "dazn 3",
    "dazn 4",
    "dazn f1",
    "dazn 1 bar(m148)",
    "dazn 2 bar(m149)",
    "laliga tv bar",
    "fiba youtube",
    "movistar+ lite",
    "nba league pass",
    "laliga+ plus",
    "hbo max",
    "rtve play",
    "aragón play",
    "aragón tv",
    "asobal tv",
    "fanplay",
    "fff tv youtube",
    "laliga tv m2",
    "laliga tv m3",
    "laliga tv m4",
    "laliga tv m5",
    "m+ #vamos bar 2(308)",
    "m+ #vamos bar(307)",
    "m+ laliga hdr(m440 o111)",
    "motogp videopass",
    "onefootball",
    "orange fútbol 1(107)",
    "red bull tv",
    "sefutbol youtube",
    "siroko tv",
    "tv footballclub(acceder)",
    "tv canaria",
    "tv3(cataluña)",
    "tvg(galicia)",
    "uefa tv",
    "uefa youtube",
}

def rx(*patterns: str) -> re.Pattern:
    """Compila múltiples patrones en una sola Expresión Regular (Case Insensitive)."""
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)

# ============================================================================
# 2. PATRONES REGEX DE BÚSQUEDA Y RECONOCIMIENTO
# ============================================================================

# Equipos y Protagonistas
REAL_MADRID_RE = rx(r"\breal madrid\b", r"\brm castilla\b", r"\br\.?\s*madrid\b")

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

# Tenistas clave / Favoritos
TENNIS_FAVORITES_RE = rx(
    r"\bsinner\b", r"\bzverev\b", r"\balcaraz\b", r"\bdjokovic\b", r"\bnadal\b",
    r"\bsabalenka\b", r"\bswiatek\b", r"\bgauff\b", r"\brybakina\b", r"\bpegula\b",
    r"\bmunar\b", r"\bjódar\b", r"\bdavidovich\b", r"\bmérida\b", r"\blandaluce\b",
    r"\bcarreño\b", r"\bbucsa\b", r"\bbouzas\b", r"\bbadosa\b", r"\bquevedo\b",
    r"\bselekhmeteva\b", r"\bramos\b", r"\btabener\b", r"\bmachado\b",
    r"\bmasarova\b", r"\bparrizas\b", r"\bosorio\b", r"\bfaria\b", r"\btsitsipas\b",
    r"\bkhachanov\b", r"\bandreeva\b", r"\bvacherot\b", r"\byuan\b", r"\brmolcan\b", r"\bnoskova\b"
)

# Identificadores de Tenis
TENNIS_RE = rx(
    r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bwimbledon\b", r"\broland garros\b",
    r"\bus open\b", r"\bopen de australia\b", r"\bmasters\b", r"\bdavis\b",
    r"\bcopa davis\b", r"\bbillie jean king cup\b", r"\blaver cup\b",
    r"\bpek[í]n\b", r"\bbeijing\b", r"\bchina open\b", r"\btorneo de pek[í]n\b",
    r"\bhangzhou\b", r"\bchengd[uú]\b", r"\btokio\b", r"\btokyo\b", r"\bjapan open\b",
    r"\btennis\s+channel\b", r"\btennis\s+tv\b", r"\bwta\s+tv\b"
)

WTA_RE = re.compile(r"\bwta\b", re.IGNORECASE)
ATP_RE = re.compile(r"\batp\b", re.IGNORECASE)
WOMEN_RE = rx(r"\bfemenina\b", r"\bfemenino\b", r"\bfrauen\b", r"\bwomen\b")

# Deportes de Motor
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

# Baloncesto
BASKET_RE = rx(
    r"\bacb\b", r"\beuroliga\b", r"\beuroleague\b", r"\bbaloncesto\b", r"\bbasket\b",
    r"\bnba\b", r"\bliga endesa\b", r"\bcopa del rey\b", r"\bsupercopa\b", r"\bfiba\b"
)

# Otros Deportes
HOCKEY_RE = rx(r"\bfih\b", r"\bhockey\b", r"\bhokey\b")
FUTSAL_RE = rx(r"\bf[uú]tbol sala\b", r"\bliga prime\b", r"\bfutsal\b")
RUGBY_RE = rx(r"\brugby\b", r"\bdivisi[oó]n\s+de\s+honor\b")
HANDBALL_RE = rx(r"\bbalonmano\b", r"\basobal\b", r"\bliga asobal\b", r"\bhandball\b")
CYCLING_RE = rx(r"\bciclismo\b", r"\btour\b", r"\bvuelta\b", r"\bgiro\b")
GOLF_RE = rx(r"\bgolf\b")

# Fútbol
FOOTBALL_RE = rx(
    r"\bf[uú]tbol\b", r"\bchampions\b", r"\bliga\b", r"\bcopa\b", r"\buefa\b", r"\bfifa\b",
    r"\bpremier\b", r"\bserie a\b", r"\bbundesliga\b", r"\bcalcio\b", r"\bmls\b", r"\bsupercopa\b"
)

# Expresiones de Tiempo y Limpieza de Canales
TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
CLEAN_TV_RE = re.compile(r"\(ver en directo\)|ver partido", re.IGNORECASE)
SPACES_RE = re.compile(r"\s+")

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?|atp\s+tennis|wta\s+tv)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis\s+channel\b", r"\borange\s+tv\b", r"\bchannel\s*[-–—]\s*orange\s+tv\b",
    r"\batp\s+tennis\s+tv\b", r"\bwta\s+tv\b"
)

# Exclusiones de Deportes Secundarios o Feeds no deseados
EXCLUDED_SPORTS_RE = rx(r"\btorneo\s+betplay\s+dimayor\b", r"\bbetplay\s+dimayor\b", r"\bmls\b", r"\bnfl\b")
EXCLUDED_BLOB_RE = rx(
    r"preol[ií]mpico\s+femenino", r"nfl\s+pretemporada", r"f1\s+academy", r"segunda\s+federaci[oó]n",
    r"segunda\s+rfef", r"tercera\s+federaci[oó]n", r"liga\s+nacional\s+juvenil"
)

FOOTBALL_COMPETITIONS = (
    (rx(r"\bchampions league\b", r"\bchampions\b"), "UEFA Champions League"),
    (rx(r"\beuropa league\b"), "UEFA Europa League"),
    (rx(r"\bconference league\b"), "UEFA Conference League"),
    (rx(r"\blaliga hypermotion\b"), "LaLiga Hypermotion"),
    (rx(r"\blaliga ea sports\b", r"\blaliga ea\b"), "LaLiga EA Sports"),
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

GENERIC_TOURNAMENTS = frozenset({
    "", "competición", "fútbol", "futbol", "baloncesto", "basket", "tenis",
    "atp", "wta", "ciclismo", "motor",
})

EXCLUDED_CHANNELS_RE = rx(*(re.escape(channel) for channel in EXCLUDED_CHANNELS))

# ============================================================================
# 3. FUNCIONES AUXILIARES Y NORMALIZACIÓN
# ============================================================================

def normalize_search_text(text: str) -> str:
    """Normaliza texto eliminando caracteres especiales, tildes y espacios dobles."""
    value = (text or "").lower()
    value = value.replace("º", "ª")
    value = re.sub(r"[|,;:/]+", " ", value)
    return SPACES_RE.sub(" ", value).strip()

def contains(pattern: re.Pattern, text: str) -> bool:
    """Devuelve True si el patrón regex coincide con el texto."""
    return bool(pattern.search(text))

def is_excluded_event(blob: str) -> bool:
    """Comprueba si un evento completo coincide con patrones de exclusión global."""
    normalized = normalize_search_text(blob)
    return bool(EXCLUDED_SPORTS_RE.search(normalized) or EXCLUDED_BLOB_RE.search(normalized))

def clean_tournament(raw: str, fallback: str) -> str:
    """Devuelve el nombre limpio del torneo o un nombre por defecto si es genérico."""
    value = (raw or "").strip()
    if len(value.lower()) > 2 and value.lower() not in GENERIC_TOURNAMENTS:
        return value
    return fallback

# ============================================================================
# 4. LÓGICA DE CLASIFICACIÓN DE DEPORTES Y FILTRADO ESTRUCTURADO
# ============================================================================

def classify_tennis(blob: str, raw_tournament: str, tv_blob: str) -> str:
    """Clasifica los torneos de tenis según ATP/WTA y ubicación."""
    tennis_text = normalize_search_text(f"{blob} {raw_tournament} {tv_blob}")
    tour = "WTA" if "wta" in tennis_text else "ATP"

    if re.search(r"\bpe[kí]n\b|\bbeijing\b|\bchina\s+open\b", tennis_text):
        return f"{tour} Pekín"
    if re.search(r"\btokio\b|\btokyo\b|\bjapan\s+open\b", tennis_text):
        return f"{tour} Tokio"

    return clean_tournament(raw_tournament, f"{tour} Tour")

def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str) -> tuple[str, str, str]:
    """Asigna el deporte, icono y competición correspondiente a cada fila."""
    if is_excluded_event(blob): 
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

    if contains(CYCLING_RE, blob): return ("Ciclismo", "🚴‍♂", clean_tournament(raw_tournament, "Ciclismo"))
    if contains(MOTOR_GENERAL_RE, blob): return ("Motor", "🏎", clean_tournament(raw_tournament, "Motor"))

    return ("Otros", "🎯", clean_tournament(raw_tournament, "Evento Deportivo"))

def matches_strict_criteria(blob: str, channels: list[str], sport: str = "", competition: str = "", event_time: str = "") -> bool:
    """Determina si un evento cumple con los criterios de la Agenda Personalizada."""
    if is_excluded_event(blob): 
        return False

    # Filtro estricto por lista de canales excluidos
    if any(EXCLUDED_CHANNELS_RE.search(ch) for ch in channels):
        return False

    if contains(REAL_MADRID_RE, blob): return True
    if contains(MOTO_STRICT_EXCLUDE_RE, blob): return False

    if sport == "Tenis":
        return contains(TENNIS_FAVORITES_RE, blob) or ("españa" in blob)

    return contains(MOTOR_SERIES_RE, blob) or contains(SPANISH_BIG_THREE_RE, blob) or contains(TOP3_FOREIGN_RE, blob)

# ============================================================================
# 5. PARSER DE FILAS Y EXTRACCIÓN HTML
# ============================================================================

def parse_row_elements(item) -> tuple[str, str, list[str], str]:
    """Extrae la hora, enfrentamiento, canales de transmisión y torneo del HTML."""
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

        # Identificación e inclusión de canales permitidos (incluyendo M+, ATP/WTA Tennis TV)
        if TV_IDENTIFIERS_RE.search(part) or CHANNEL_LINE_RE.search(part_lower) or "m+" in part_lower or "dazn" in part_lower or "tennis" in part_lower:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            for channel in clean_part.split(","):
                channel = channel.strip().rstrip(":").strip()
                channel_lower = normalize_search_text(channel)
                if channel and not EXCLUDED_CHANNELS_RE.search(channel_lower) and channel not in channels:
                    channels.append(channel)
            continue

        # Identificación de torneo de tenis
        if TENNIS_TOURNAMENT_RE.search(part_lower) or WTA_RE.search(part_lower) or ATP_RE.search(part_lower):
            if not tournament:
                tournament = part
            continue

        # Identificación de enfrentamiento (Jugador A - Jugador B o Equipo A vs Equipo B)
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
    """Descarga el widget HTML de la web y genera la lista estructurada de eventos."""
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

                # Descartar si no hay canales válidos permitidos tras aplicar exclusiones
                if not channels:
                    continue

                tv_blob = " ".join(channels).lower()
                blob = normalize_search_text(f"{event_str} {tournament} {tv_blob}")

                if is_excluded_event(blob): continue
                if contains(GOLF_RE, blob): continue

                event_key = (time_clean, event_str.lower())
                if event_key in seen_events: continue
                seen_events.add(event_key)

                sport, icon, competition = get_sport_and_competition(blob, tournament, tv_blob)
                if sport == "__EXCLUDED__": continue

                is_favorite = matches_strict_criteria(blob, channels, sport=sport, competition=competition, event_time=time_clean)

                if is_favorite:
                    results.append({
                        "hora": time_clean,
                        "deporte": sport,
                        "icono": icon,
                        "competicion": competition,
                        "evento": event_str,
                        "tv_list": channels,
                    })
            except Exception:
                continue
    except Exception as e:
        print(f"Error cargando la agenda deportiva: {e}", file=sys.stderr)

    # Ordenar estrictamente por hora
    results.sort(key=lambda x: datetime.strptime(x["hora"], "%H:%M"))
    return results

# ============================================================================
# 6. FORMATEO Y SALIDA DE AGENDA DEPORTIVA
# ============================================================================

def generate_markdown_agenda() -> str:
    """Genera la tabla final en formato Markdown para la Agenda Deportiva."""
    events = fetch_and_parse_agenda()
    
    if not events:
        return "No hay eventos programados en la Agenda Deportiva según los criterios seleccionados."

    lines = ["| Hora | Deporte | Competición | Evento | Canal |"]
    lines.append("| --- | --- | --- | --- | --- |")

    for item in events:
        tv_str = ", ".join(item["tv_list"])
        lines.append(
            f"| {item['hora']} | {item['icono']} {item['deporte']} | "
            f"{item['competicion']} | {item['evento']} | {tv_str} |"
        )

    return "\n".join(lines)

# ============================================================================
# 7. BLOQUE PRINCIPAL DE EJECUCIÓN
# ============================================================================

if __name__ == "__main__":
    markdown_output = generate_markdown_agenda()
    print(markdown_output)
