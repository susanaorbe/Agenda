import os
import re
import datetime
from zoneinfo import ZoneInfo
import requests
from bs4 import BeautifulSoup
from telegram import Bot

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
MADRID_TZ = ZoneInfo("Europe/Madrid")

TV_EXCLUSIONS = [
    r"\bfanseat\b",
    r"\bdazn\b",
    r"\blaliga tv bar\b",
    r"\bfiba youtube\b",
    r"\bmovistar\+\s*lite\b",
    r"\bnba league pass\b",
    r"\blaliga\+\s*plus\b",
    r"\bhbo max\b",
    r"\brtve play\b",
]

SPORT_EXCLUSIONS = [
    r"\bgolf\b",
    r"\bpadel\b",
    r"\bpádel\b",
    r"\bbalonmano\b",
    r"\bhockey\b",
    r"\bfútbol sala\b",
    r"\bfutsal\b",
    r"\bsuperbike\b",
    r"\bsbk\b",
    r"\bwsbk\b",
    r"\bmoto2\b",
    r"\bmoto3\b",
    r"\bmotoe\b",
]

EXCLUDE_PATTERNS = [re.compile(pat, re.IGNORECASE) for pat in TV_EXCLUSIONS + SPORT_EXCLUSIONS]

WOMEN_RE = re.compile(
    r"\b(femenino|femenina|fem\.|femenil|women|women's|wta|liga f|liga f moeve)\b",
    re.IGNORECASE
)
REAL_MADRID_RE = re.compile(r"\breal madrid\b", re.IGNORECASE)
PRIMERA_RFEF_RE = re.compile(r"\bprimera rfef\b", re.IGNORECASE)
CASTILLA_RE = re.compile(r"\bcastilla\b", re.IGNORECASE)

FOOTBALL_COMPETITIONS = [
    (re.compile(r"\bchampions league\b", re.IGNORECASE), "UEFA Champions League"),
    (re.compile(r"\beuropa league\b", re.IGNORECASE), "UEFA Europa League"),
    (re.compile(r"\bconference league\b", re.IGNORECASE), "UEFA Conference League"),
    (re.compile(r"\blaliga ea sports\b|\blaliga\b", re.IGNORECASE), "LaLiga EA Sports"),
    (re.compile(r"\blaliga hypermotion\b", re.IGNORECASE), "LaLiga Hypermotion"),
    (re.compile(r"\bcopa del rey\b", re.IGNORECASE), "Copa del Rey"),
    (re.compile(r"\bpremier league\b", re.IGNORECASE), "Premier League"),
    (re.compile(r"\bserie a\b", re.IGNORECASE), "Serie A"),
    (re.compile(r"\bbundesliga\b", re.IGNORECASE), "Bundesliga"),
    (re.compile(r"\bligue 1\b", re.IGNORECASE), "Ligue 1"),
]

BASKET_RE = re.compile(r"\b(baloncesto|basket|liga endesa|acb|euroliga|euroleague|nba|eurocup|baskonia|real madrid baloncesto|barça basquet|unicaja|valencia basket|cb|baskets|bc)\b", re.IGNORECASE)
FOOTBALL_RE = re.compile(r"\b(fútbol|futbol|soccer|liga|champions|copa|derby|football)\b", re.IGNORECASE)
TENNIS_RE = re.compile(r"\b(tenis|tennis|atp|wta|davis cup|fed cup)\b", re.IGNORECASE)
TENNIS_TOURNAMENT_RE = re.compile(r"\b(open|masters 1000|atp 500|atp 250|grand slam|australian open|roland garros|wimbledon|us open|indian wells|miami|monte carlo|madrid|roma|cincinnati|shanghai|paris)\b", re.IGNORECASE)
RUGBY_RE = re.compile(r"\b(rugby|seis naciones|six nations)\b", re.IGNORECASE)
CYCLING_RE = re.compile(r"\b(ciclismo|tour de francia|giro d'italia|vuelta a españa|paris-roubaix|tour de france|giro de italia)\b", re.IGNORECASE)
MOTOR_GENERAL_RE = re.compile(r"\b(fórmula 1|formula 1|f1|fórmula 2|f2|fórmula 3|f3|motogp|moto2|moto3|f1 academy)\b", re.IGNORECASE)

F1_RE = re.compile(r"\b(f1|fórmula 1|formula 1)\b", re.IGNORECASE)
F2_RE = re.compile(r"\b(f2|fórmula 2|formula 2)\b", re.IGNORECASE)
F3_RE = re.compile(r"\b(f3|fórmula 3|formula 3)\b", re.IGNORECASE)
MOTO2_RE = re.compile(r"\bmoto2\b", re.IGNORECASE)
MOTO3_RE = re.compile(r"\bmoto3\b", re.IGNORECASE)

HOCKEY_RE = re.compile(r"\bhockey\b", re.IGNORECASE)
FUTSAL_RE = re.compile(r"\b(fútbol sala|futsal)\b", re.IGNORECASE)
HANDBALL_RE = re.compile(r"\bbalonmano\b", re.IGNORECASE)


def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def clean_tournament(raw: str, default: str) -> str:
    cleaned = raw.strip()
    return cleaned if cleaned else default


def is_excluded_event(blob: str) -> bool:
    return any(pat.search(blob) for pat in EXCLUDE_PATTERNS)


def classify_tennis(blob: str, raw_tournament: str, tv_blob: str) -> str:
    blob_low = blob.lower()
    raw_low = raw_tournament.lower()

    if "atp" in blob_low or "atp" in raw_low:
        return clean_tournament(raw_tournament, "ATP")
    if "davis" in blob_low or "davis" in raw_low:
        return "Copa Davis"
    if "roland garros" in blob_low or "roland garros" in raw_low:
        return "Roland Garros"
    if "wimbledon" in blob_low or "wimbledon" in raw_low:
        return "Wimbledon"
    if "australian open" in blob_low or "australian open" in raw_low:
        return "Open de Australia"
    if "us open" in blob_low or "us open" in raw_low:
        return "US Open"

    return clean_tournament(raw_tournament, "Tenis")


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str) -> tuple[str, str, str]:
    if is_excluded_event(blob):
        return ("__EXCLUDED__", "", "")

    if contains(WOMEN_RE, blob) and not contains(TENNIS_RE, blob):
        if not contains(REAL_MADRID_RE, blob):
            return ("__EXCLUDED__", "", "")

    if contains(PRIMERA_RFEF_RE, blob) and not contains(CASTILLA_RE, blob):
        return ("__EXCLUDED__", "", "")

    if contains(TENNIS_RE, blob) or contains(TENNIS_TOURNAMENT_RE, blob) or contains(TENNIS_TOURNAMENT_RE, raw_tournament):
        return ("Tenis", "🎾", classify_tennis(blob, raw_tournament, tv_blob))

    if contains(RUGBY_RE, blob):
        return ("__EXCLUDED__", "", "")

    # 1. Baloncesto (se evalúa PRIMERO para evitar que la Champions League de Baloncesto caiga en Fútbol)
    if contains(BASKET_RE, blob):
        comp = clean_tournament(raw_tournament, "Baloncesto")
        if "eurocup" in comp.lower() or "eurocup" in blob:
            comp = "Eurocup"
        elif "champions" in comp.lower() or "champions" in blob:
            comp = "Liga de Campeones de Baloncesto"
        return ("Baloncesto", "🏀", comp)

    # 2. Competiciones de Fútbol explícitas
    for pattern, comp_name in FOOTBALL_COMPETITIONS:
        if pattern.search(blob):
            return ("Fútbol", "⚽", comp_name)

    if contains(HOCKEY_RE, blob):
        return ("Otros", "🎯", clean_tournament(raw_tournament, "Hockey"))

    if contains(FUTSAL_RE, blob):
        return ("Otros", "🎯", clean_tournament(raw_tournament, "Fútbol Sala"))

    if contains(HANDBALL_RE, blob):
        return ("Otros", "🎯", clean_tournament(raw_tournament, "Balonmano"))

    if contains(FOOTBALL_RE, blob):
        return ("Fútbol", "⚽", clean_tournament(raw_tournament, "Fútbol"))

    if contains(CYCLING_RE, blob):
        return ("Ciclismo", "🚴‍♂️", clean_tournament(raw_tournament, "Ciclismo"))

    if contains(MOTOR_GENERAL_RE, blob):
        is_f1 = ("fórmula 1" in blob or F1_RE.search(blob)) and "academy" not in blob
        is_motogp = "motogp" in blob and not MOTO2_RE.search(blob) and not MOTO3_RE.search(blob) and "rookies" not in blob
        is_f2 = "fórmula 2" in blob or F2_RE.search(blob)
        is_f3 = "fórmula 3" in blob or F3_RE.search(blob)

        if is_f1:
            comp = "Fórmula 1"
        elif is_motogp:
            comp = "MotoGP"
        elif is_f2:
            comp = "Fórmula 2"
        elif is_f3:
            comp = "Fórmula 3"
        else:
            comp = clean_tournament(raw_tournament, "Motor")

        return ("Motor", "🏎️", comp)

    return ("Otros", "🎯", clean_tournament(raw_tournament, "Evento Deportivo"))


def parse_date(date_str: str) -> datetime.date | None:
    parts = date_str.strip().split()
    if len(parts) < 4:
        return None

    try:
        day = int(parts[1])
        month_str = parts[3].lower()

        months = {
            "enero": 1, "febrero": 2, "marzo": 3, "abril": 4,
            "mayo": 5, "junio": 6, "julio": 7, "agosto": 8,
            "septiembre": 9, "octubre": 10, "noviembre": 11, "diciembre": 12
        }

        month = months.get(month_str)
        if not month:
            return None

        today = datetime.datetime.now(MADRID_TZ).date()
        year = today.year

        dt = datetime.date(year, month, day)
        if dt < today - datetime.timedelta(days=180):
            dt = datetime.date(year + 1, month, day)

        return dt
    except Exception as e:
        print(f"Error parseando fecha '{date_str}': {e}")
        return None


def fetch_and_parse() -> list[dict]:
    url = "https://www.satcesc.com/deportes/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    resp = requests.get(url, headers=headers, timeout=15)
    resp.encoding = "utf-8"
    soup = BeautifulSoup(resp.text, "html.parser")

    events = []
    current_date = None

    container = soup.find("div", class_="entry-content") or soup.find("body")
    if not container:
        return events

    for elem in container.find_all(["h3", "p"]):
        text = elem.get_text(" ", strip=True)
        if not text:
            continue

        if elem.name == "h3":
            parsed_d = parse_date(text)
            if parsed_d:
                current_date = parsed_d
            continue

        if elem.name == "p" and current_date:
            time_match = re.match(r"^(\d{2}:\d{2})\s+(.*)$", text)
            if not time_match:
                continue

            time_str = time_match.group(1)
            rest = time_match.group(2)

            tv_channels = []
            tv_spans = elem.find_all("span", class_="tv")
            for span in tv_spans:
                tv_channels.append(span.get_text(strip=True))

            tv_str = ", ".join(tv_channels) if tv_channels else "TV no especificada"

            for span in tv_spans:
                span.decompose()

            raw_event_text = elem.get_text(" ", strip=True)
            raw_event_text = re.sub(r"^\d{2}:\d{2}\s*", "", raw_event_text).strip()

            tournament = ""
            match_title = raw_event_text

            if ":" in raw_event_text:
                parts = raw_event_text.split(":", 1)
                tournament = parts[0].strip()
                match_title = parts[1].strip()

            search_blob = f"{tournament} {match_title} {tv_str}"
            sport, icon, competition = get_sport_and_competition(search_blob, tournament, tv_str)

            if sport == "__EXCLUDED__":
                continue

            events.append({
                "date": current_date,
                "time": time_str,
                "sport": sport,
                "icon": icon,
                "competition": competition,
                "match": match_title,
                "tv": tv_str
            })

    return events


def format_message(events: list[dict]) -> str:
    if not events:
        return "📅 **Agenda Deportiva**\n\nNo hay eventos programados para los próximos días según tus filtros."

    events_by_date = {}
    for ev in events:
        d = ev["date"]
        events_by_date.setdefault(d, []).append(ev)

    days_es = ["Lunes", "Martes", "Miércoles", "Jueves", "Viernes", "Sábado", "Domingo"]
    months_es = ["", "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio", "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre"]

    msg = "📅 **Agenda Deportiva**\n\n"

    for d in sorted(events_by_date.keys()):
        day_name = days_es[d.weekday()]
        date_formatted = f"{day_name} {d.day} de {months_es[d.month]}"

        msg += f"🗓 **{date_formatted}**\n"
        msg += "─" * 20 + "\n"

        for ev in events_by_date[d]:
            msg += f"{ev['icon']} **{ev['time']}** - {ev['competition']}\n"
            msg += f"   ⚽ {ev['match']}\n" if ev['icon'] != '⚽' else f"   {ev['match']}\n"
            msg += f"   📺 *{ev['tv']}*\n\n"

        msg += "\n"

    return msg.strip()


def send_telegram_message(text: str):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("Error: Faltan TELEGRAM_TOKEN o TELEGRAM_CHAT_ID en las variables de entorno.")
        return

    bot = Bot(token=TELEGRAM_TOKEN)
    
    if len(text) <= 4000:
        bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=text, parse_mode="Markdown")
    else:
        chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
        for chunk in chunks:
            bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=chunk, parse_mode="Markdown")


def main():
    print("Obteniendo eventos deportivos...")
    events = fetch_and_parse()
    print(f"Se han encontrado {len(events)} eventos tras aplicar los filtros.")

    message = format_message(events)
    print("\n--- Mensaje Generado ---")
    print(message)
    print("------------------------\n")

    send_telegram_message(message)
    print("Mensaje enviado a Telegram con éxito.")


if __name__ == "__main__":
    main()
