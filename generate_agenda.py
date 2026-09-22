from datetime import datetime
import re
import requests
from bs4 import BeautifulSoup

# -------------------------------------------------------------------
# CONFIGURACIÓN DEL WIDGET
# -------------------------------------------------------------------
WIDGET_URL = "https://widgets.futbolenlatv.com/partidos/agenda?color=005df8&culture=es-ES"

EXCLUDED_CHANNELS = (
    "andalucía tv", "antel tv internacional", "apple tv", "aragón deporte", 
    "aragon deporte", "aragón deportes", "aragon deportes", "aragón tv", 
    "aragon tv", "asobal tv", "atp tennis tv", 
    "betevé web", 
    "cayotv youtube(ver)", "cmmplay(castilla-lm)",
    "dazn 1 bar(m148)", "dazn 2 bar(m149)", "deportes tvcanaria youtube", 
    "ehf tv", "esport3(cataluña)", "esport3 web", "eurovision sports tv", 
    "fanplay tv", "fanseat", "fc barcelona ppv youtube", "fiba youtube", 
    "flamengo tv youtube", 
    "hbo max", 
    "laliga tv bar", "laliga tv m2", "laliga tv m3", "laliga tv m4", 
    "laliga tv m5", "laliga+ plus", "la 7(castilla y león)", "liga futve", 
    "liga futve youtube", "ligafutve app", 
    "m+ #vamos bar(307)", "m+ #vamos bar 2(308)", "m+ laliga hdr(m440 o111)", "mediaset infinity",
    "motogp videopass", "movistar+ lite", 
    "nba league pass", 
    "onefootball", "orange fútbol 1(107)", 
    "real sociedad tv youtube", "red bull tv", "rtve play", 
    "siroko tv", "streaming / web", 
    "tv canaria", "tv footballclub(acceder)", "tv melilla", "tv galicia",
    "tvg(galicia)", "tvg2(galicia)", "tvg web", "tv3(cataluña)",
    "tv5monde", "twitch btvesports", 
    "uefa tv", 
    "ver en directo", "ver partido",
    "win sports tv youtube", "wta tv",  
    "101 tv(málaga)", "9tv león"
)

EXCLUDED_CHANNELS_SET = set(EXCLUDED_CHANNELS)
EXCLUDED_CHANNELS_RE = re.compile(r'(?:' + r'|'.join(map(re.escape, EXCLUDED_CHANNELS)) + r')', re.IGNORECASE)

def build_re(patterns):
    return re.compile(r'(?:' + r'|'.join(patterns) + r')', re.IGNORECASE)

SPANISH_BIG_THREE = build_re([r"\breal madrid\b", r"\bbarcelona\b", r"\bbarça\b", r"\batletico de madrid\b", r"\batlético de madrid\b"])
TOP3_FOREIGN = build_re([r"\bmanchester city\b", r"\barsenal\b", r"\bliverpool\b", r"\binter de milán\b", r"\binter milan\b", r"\bnapoles\b", r"\bjuventus\b", r"\bbayern de múnich\b", r"\bbayern munich\b", r"\bbayern\b", r"\bborussia dortmund\b", r"\bdortmund\b", r"\brb leipzig\b", r"\bleipzig\b", r"\bparis saint-germain\b", r"\bpsg\b", r"\bolympique de marsella\b", r"\bmarsella\b", r"\brc lens\b", r"\blens\b", r"\bsporting cp\b", r"\bsporting de portugal\b", r"\bbenfica\b", r"\bporto\b"])
TENNIS_PLAYERS = build_re([r"\balcaraz\b", r"\bjódar\b", r"\bdavidovich\b", r"\bmunar\b", r"\bmérida\b", r"\blandaluce\b", r"\bcarreño\b", r"\bbucsa\b", r"\bbouzas\b", r"\bbadosa\b", r"\bquevedo\b", r"\bsinner\b", r"\bzverev\b", r"\bsabalenka\b", r"\brybakina\b", r"\bpegula\b"])

MOTOR_SERIES = build_re([r"\bfórmula 1\b", r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b", r"\bmotogp\b(?![\s\-]*(?:2|3|moto2|moto3|rookies))\b", r"\bformula e\b", r"\bfórmula e\b", r"\bindycar\b", r"\bindy car\b"])
MOTOR_GEN = build_re([r"\bfórmula 1\b", r"\bf1(?![\s\-]*(?:academy))\b", r"\bfórmula 2\b", r"\bfórmula 3\b", r"\bf2\b", r"\bf3\b", r"\bmotogp\b", r"\bformula e\b", r"\bfórmula e\b", r"\bindycar\b", r"\bindy car\b", r"\bmoto2\b", r"\bmoto3\b", r"\bnascar\b", r"\brally\b", r"\bautomovilismo\b", r"\bmotor\b"])

BASKET_COMPS = build_re([r"\bacb\b", r"\beuroliga\b", r"\beuroleague\b", r"\bbaloncesto\b", r"\bbasket\b", r"\bnba\b", r"\bliga endesa\b", r"\bcopa del rey\b", r"\bsupercopa\b", r"\bfiba\b", r"\bmundial de baloncesto\b"])
BASKET_GENERAL = build_re([r"\bbaloncesto\b", r"\bbasket\b", r"\bacb\b", r"\beuroliga\b", r"\beuroleague\b", r"\bnba\b", r"\bliga endesa\b", r"\bfiba\b", r"\bsudán del sur\b", r"\bsouth sudan\b", r"\bjjoo\b", r"\bmundial de baloncesto\b"])

HOCKEY_RE = build_re([r"\bfih\b", r"\bhockey\b", r"\bhokey\b"])
FUTSAL_RE = build_re([r"\bf[uú]tbol sala\b", r"\bliga prime\b", r"\bfutsal\b"])
HANDBALL_RE = build_re([r"\bbalonmano\b", r"\basobal\b", r"\bliga asobal\b", r"\bhandball\b"])
TENNIS_INDICATORS = build_re([r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bwimbledon\b", r"\broland garros\b", r"\bus open\b", r"\bopen de australia\b", r"\bmasters\b", r"\bdavis\b", r"\bcopa davis\b"])
DAVIS_RE = re.compile(r"\bcopa davis\b|\bdavis cup\b|\bdavis\b", re.IGNORECASE)
SPAIN_RE = re.compile(r"\bespaña\b", re.IGNORECASE)

WOMEN_MATCH = build_re([r"\bfemenina\b", r"\bfemenino\b", r"\bfrauen\b", r"\bwomen\b"])
REAL_MADRID = re.compile(r"\breal madrid\b", re.IGNORECASE)

FOOTBALL_INDICATORS = build_re([r"\bf[uú]tbol\b", r"\bchampions\b", r"\bliga\b", r"\bcopa\b", r"\buefa\b", r"\bfifa\b", r"\bpremier\b", r"\bserie a\b", r"\bbundesliga\b", r"\bcalcio\b", r"\bmls\b", r"\bsupercopa\b", r"\bprimera\b", r"\bsegunda\b", r"\btercera\b", r"\brfef\b", r"\bliga f\b", r"\beredivisie\b", r"\bjupiler\b"])

TIME_RE = re.compile(r'\b\d{1,2}:\d{2}\b')
CLEAN_TV_RE = re.compile(r'\(ver en directo\)|ver partido', re.IGNORECASE)
PUNCTUATION_RE = re.compile(r'[\|,]+')
SPACES_RE = re.compile(r'\s+')
TV_IDENTIFIERS_RE = re.compile(r'(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport)', re.IGNORECASE)

FOOTBALL_MAP = [
    (re.compile(r"\bchampions league\b|\bchampions\b", re.IGNORECASE), "UEFA Champions League"), 
    (re.compile(r"\beuropa league\b", re.IGNORECASE), "UEFA Europa League"), 
    (re.compile(r"\bconference league\b", re.IGNORECASE), "UEFA Conference League"), 
    (re.compile(r"\blaliga hypermotion\b", re.IGNORECASE), "LaLiga Hypermotion"), 
    (re.compile(r"\blaliga ea sports\b|\blaliga ea\b", re.IGNORECASE), "LaLiga EA Sports"), 
    (re.compile(r"\blaliga\b", re.IGNORECASE), "LaLiga EA Sports"), 
    (re.compile(r"\bpremier league\b", re.IGNORECASE), "Premier League"), 
    (re.compile(r"\bserie a\b", re.IGNORECASE), "Serie A"), 
    (re.compile(r"\bbundesliga\b", re.IGNORECASE), "Bundesliga"), 
    (re.compile(r"\bligue 1\b", re.IGNORECASE), "Ligue 1"), 
    (re.compile(r"\bcopa del rey\b", re.IGNORECASE), "Copa del Rey"), 
    (re.compile(r"\bcoppa italia\b", re.IGNORECASE), "Coppa Italia"), 
    (re.compile(r"\bliga f\b|\bligaf\b", re.IGNORECASE), "Liga F"),
    (re.compile(r"\beredivisie\b", re.IGNORECASE), "Eredivisie"),
    (re.compile(r"\bjupiler\b|\bjupiler pro league\b", re.IGNORECASE), "Jupiler Pro League")
]

TENNIS_MAP = [
    (re.compile(r"\bcopa davis\b|\bdavis cup\b|\bdavis\b", re.IGNORECASE), "Copa Davis"),
    (re.compile(r"\bus open\b", re.IGNORECASE), "US Open"),
    (re.compile(r"\bwimbledon\b", re.IGNORECASE), "Wimbledon"),
    (re.compile(r"\broland garros\b", re.IGNORECASE), "Roland Garros"),
    (re.compile(r"\bopen de australia\b", re.IGNORECASE), "Open de Australia"),
    (re.compile(r"\bmadrid\b", re.IGNORECASE), "Madrid Open"),
    (re.compile(r"\broma\b", re.IGNORECASE), "Masters de Roma")
]

CYCLING_RE = re.compile(r"\bciclismo\b", re.IGNORECASE)
GOLF_RE = re.compile(r"\bgolf\b", re.IGNORECASE)
EXCLUDED_BLOB_RE = re.compile(r"preol[ií]mpico\s+femenino|nfl\s+pretemporada|f1\s+academy|tour\s+del\s+benelux|bundesliga\s+femenina|iaaf\s+diamond\s+league|national\s+league(?:\s+north|\s+south)?|eredivisie\s+vrouwen|europeo\s+femenino\s+sub-?16|segunda\s+federaci[oó]n|segunda\s+rfef", re.IGNORECASE)
MOTO_STRICT_EXCLUDE_RE = re.compile(r"\bmoto2\b|\bmoto3\b|rookies\s+cup|rookies|\bnascar\b|\bfórmula 2\b|\bfórmula 3\b|\bf2\b|\bf3\b", re.IGNORECASE)
LIGAF_RE = re.compile(r"\bliga f\b|\bligaf\b|\bprimera division femenina\b|\bcopa de la reina\b", re.IGNORECASE)
PRIMERA_RFEF_RE = re.compile(r"\bprimera federaci[oó]n\b|\bprimera rfef\b", re.IGNORECASE)
CASTILLA_RE = re.compile(r"\breal madrid castilla\b|\bcastilla\b", re.IGNORECASE)

F1_RE = re.compile(r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b", re.IGNORECASE)
F2_RE = re.compile(r"\bf2\b", re.IGNORECASE)
F3_RE = re.compile(r"\bf3\b", re.IGNORECASE)
MOTO2_RE = re.compile(r"moto2", re.IGNORECASE)
MOTO3_RE = re.compile(r"moto3", re.IGNORECASE)

def get_general_sport_and_comp(blob, raw_tournament, tv_blob):
    rt_lower = raw_tournament.lower() if raw_tournament else ""

    if BASKET_GENERAL.search(blob):
        if "euroliga" in blob or "euroleague" in blob: comp = "Euroliga"
        elif "nba" in blob: comp = "NBA"
        elif "acb" in blob or "liga endesa" in blob: comp = "Liga Endesa"
        elif "fiba" in blob or "mundial" in blob: comp = "FIBA Copa Mundial"
        elif "jjoo" in blob: comp = "JJOO Baloncesto"
        else: comp = raw_tournament if rt_lower not in ["baloncesto", "basket", "competición", ""] else "Baloncesto"
        return "Baloncesto", "🏀", comp

    if HOCKEY_RE.search(blob):
        return "Otros", "🎯", raw_tournament if rt_lower not in ["fih", "hockey", "competición", ""] else "Hockey (FIH)"

    if FUTSAL_RE.search(blob):
        comp = "Liga Prime" if "prime" in blob else (raw_tournament if rt_lower not in ["fútbol sala", "futbol sala", "futsal", "competición", ""] else "Fútbol Sala")
        return "Otros", "🎯", comp

    if HANDBALL_RE.search(blob):
        comp = "Liga ASOBAL" if "asobal" in blob else (raw_tournament if rt_lower not in ["balonmano", "handball", "competición", ""] else "Balonmano")
        return "Otros", "🎯", comp

    if TENNIS_INDICATORS.search(blob) or TENNIS_PLAYERS.search(blob):
        for pat, name in TENNIS_MAP:
            if pat.search(blob):
                prefix = "" if name == "Copa Davis" else ("WTA " if 'wta' in blob or 'wta' in tv_blob else "ATP ")
                return "Tenis", "🎾", f"{prefix}{name}".strip()
        return "Tenis", "🎾", raw_tournament if len(rt_lower) > 2 and rt_lower not in ["tenis", "atp", "wta"] else ("WTA Tour" if 'wta' in blob else "ATP Tour")

    for pat, name in FOOTBALL_MAP:
        if pat.search(blob):
            return "Fútbol", "⚽", name

    if FOOTBALL_INDICATORS.search(blob):
        return "Fútbol", "⚽", raw_tournament if len(rt_lower) > 2 and rt_lower not in ["fútbol", "futbol", "competición"] else "Fútbol"

    if WOMEN_MATCH.search(blob) and not REAL_MADRID.search(blob):
        return "Otros", "🎯", raw_tournament if len(rt_lower) > 2 and rt_lower != "competición" else "Fútbol Femenino"

    if CYCLING_RE.search(blob):
        return "Ciclismo", "🚴‍♂️", raw_tournament if rt_lower not in ["ciclismo", "competición", ""] else "Ciclismo"

    if MOTOR_GEN.search(blob):
        if ("fórmula 1" in blob or F1_RE.search(blob)) and "academy" not in blob:
            comp = "Fórmula 1"
        elif "fórmula 2" in blob or F2_RE.search(blob):
            comp = "Fórmula 2"
        elif "fórmula 3" in blob or F3_RE.search(blob):
            comp = "Fórmula 3"
        elif "motogp" in blob and not (MOTO2_RE.search(blob) or MOTO3_RE.search(blob) or "rookies" in blob):
            comp = "MotoGP"
        elif MOTO2_RE.search(blob):
            comp = "Moto2"
        elif MOTO3_RE.search(blob):
            comp = "Moto3"
        elif "formula e" in blob or "fórmula e" in blob:
            comp = "Fórmula E"
        elif "indycar" in blob or "indy car" in blob:
            comp = "IndyCar"
        elif "nascar" in blob:
            comp = "NASCAR"
        else:
            comp = raw_tournament if rt_lower not in ["motor", "competición", ""] else "Motor"
        return "Motor", "🏎️", comp

    return "Otros", "🎯", raw_tournament if len(rt_lower) > 2 and rt_lower != "competición" else "Evento Deportivo"

def matches_strict_criteria(blob, tv_channels_list):
    if WOMEN_MATCH.search(blob) and REAL_MADRID.search(blob):
    return True
    
    for ch in tv_channels_list:
        if EXCLUDED_CHANNELS_RE.search(ch):
            return False

    if MOTO_STRICT_EXCLUDE_RE.search(blob):
        return False

    if EXCLUDED_BLOB_RE.search(blob):
        return False

    if WOMEN_MATCH.search(blob):
        if not REAL_MADRID.search(blob):
            return False

    if MOTOR_SERIES.search(blob):
        return True

    if BASKET_COMPS.search(blob):
        return bool(REAL_MADRID.search(blob))

    if TENNIS_INDICATORS.search(blob) or TENNIS_PLAYERS.search(blob):
        if DAVIS_RE.search(blob) and SPAIN_RE.search(blob):
            return True
        return bool(TENNIS_PLAYERS.search(blob))

    if LIGAF_RE.search(blob):
        return bool(REAL_MADRID.search(blob))

    if PRIMERA_RFEF_RE.search(blob):
        return bool(CASTILLA_RE.search(blob))

    if SPANISH_BIG_THREE.search(blob) or TOP3_FOREIGN.search(blob):
        return True

    return False

def parse_row_elements(item):
    text_full = item.get_text(" | ", strip=True)
    time_match = TIME_RE.search(text_full)
    time_clean = time_match.group(0) if time_match else ""

    raw_parts = [p.strip() for p in item.get_text("\n", strip=True).split("\n") if p.strip()]
    if len(raw_parts) > 15 or len(raw_parts) < 2:
        return "", "", [], ""

    matchup, channels, tournament = "", [], ""

    for part in raw_parts:
        part_lower = part.lower()
        if TIME_RE.match(part) or part_lower in ("ver partido", "directo", "(ver en directo)"):
            continue
        
        has_tv_id = TV_IDENTIFIERS_RE.search(part)
        
        if " - " in part and not has_tv_id:
            if len(part) > 3 and not matchup: matchup = part
            continue

        if has_tv_id:
            clean_part = CLEAN_TV_RE.sub('', part).strip()
            for sc in (x.strip() for x in clean_part.split(',') if x.strip()):
                sc_clean = sc.rstrip(':').strip()
                if sc_clean and sc_clean.lower() not in EXCLUDED_CHANNELS_SET and sc_clean not in channels:
                    channels.append(sc_clean)
        else:
            if len(part) < 35 and not tournament:
                tournament = part

    if not matchup:
        clean_desc = text_full
        for ch in channels: clean_desc = clean_desc.replace(ch, "")
        clean_desc = TIME_RE.sub('', clean_desc)
        clean_desc = SPACES_RE.sub(' ', PUNCTUATION_RE.sub(' ', clean_desc)).strip()
        matchup = clean_desc if len(clean_desc) > 3 else "Evento Deportivo"

    return time_clean, matchup, channels, tournament

def fetch_and_parse_agenda():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    results, seen_events = [], set()

    try:
        response = requests.get(WIDGET_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            for item in soup.find_all(['div', 'tr', 'li']):
                try:
                    time_clean, event_str, allowed_tv_list, tournament = parse_row_elements(item)
                    if not time_clean or not allowed_tv_list or event_str in ("", "Evento Deportivo"):
                        continue

                    text_block = f"{event_str} {tournament}"
                    tv_blob = " ".join(allowed_tv_list).lower()
                    blob = f"{text_block.lower()} {tv_blob}"

                    if GOLF_RE.search(blob) or "movistar golf" in tv_blob:
                        continue
                    if EXCLUDED_BLOB_RE.search(blob):
                        continue
                        
                    if PRIMERA_RFEF_RE.search(blob) and not CASTILLA_RE.search(blob):
                        continue
                        
                    if LIGAF_RE.search(blob) and not REAL_MADRID.search(blob):
                        continue

                    event_key = (time_clean, event_str.lower())
                    if event_key in seen_events: continue
                    seen_events.add(event_key)

                    sport_type, icon, comp_clean = get_general_sport_and_comp(blob, tournament, tv_blob)
                    is_strict_filtered = matches_strict_criteria(blob, allowed_tv_list)

                    results.append({
                        "hora": time_clean, "deporte": sport_type, "icono": icon,
                        "competicion": comp_clean, "evento": event_str,
                        "tv_list": allowed_tv_list, "is_filtered": is_strict_filtered
                    })
                except Exception:
                    continue
    except Exception as e:
        print(f"Error procesando eventos: {e}")

    return results

def generate_html(events):
    fecha_act = datetime.now().strftime("%d/%m/%Y - %H:%M")
    
    total_cnt = len(events)
    filtered_cnt = sum(1 for e in events if e['is_filtered'])
    futbol_cnt = sum(1 for e in events if e['deporte'] == 'Fútbol')
    baloncesto_cnt = sum(1 for e in events if e['deporte'] == 'Baloncesto')
    tenis_cnt = sum(1 for e in events if e['deporte'] == 'Tenis')
    motor_cnt = sum(1 for e in events if e['deporte'] == 'Motor')
    otros_cnt = sum(1 for e in events if e['deporte'] == 'Otros')

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
    else:
        for ev in events:
            tv_badges = "".join([f'<span class="tv-badge">{channel}</span>' for channel in ev['tv_list']])
            rows_list.append(f"""
            <tr data-sport="{ev['deporte'].lower()}" data-filtered="{str(ev['is_filtered']).lower()}">
                <td class="date-col"><span class="date-badge today">Hoy</span></td>
                <td class="time-col"><span class="time-badge">{ev['hora']}</span></td>
                <td class="sport-col"><span class="sport-tag">{ev['icono']} {ev['deporte']}</span></td>
                <td class="comp-col"><div class="comp-title">{ev['competicion']}</div></td>
                <td class="event-col"><div class="event-title">{ev['evento']}</div></td>
                <td class="tv-col"><div class="tv-container">{tv_badges}</div></td>
            </tr>
            """)

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
        body {{ font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 20px 12px; display: flex; justify-content: center; }}
        .container {{ width: 100%; max-width: 1150px; }}
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; padding-bottom: 12px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 10px; }}
        h1 {{ font-size: 1.6rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header-controls {{ display: flex; gap: 10px; align-items: center; }}
        .btn-update {{ background: #10b981; color: white; border: none; padding: 8px 16px; border-radius: 10px; font-weight: 600; cursor: pointer; font-size: 0.9rem; transition: all 0.2s; display: flex; align-items: center; gap: 6px; }}
        .btn-update:hover {{ background: #059669; }}
        .last-update {{ font-size: 0.8rem; color: var(--text-muted); background: var(--card-bg); padding: 6px 12px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; text-align: right; }}
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 10px; margin-bottom: 20px; }}
        .stat-card {{ background: var(--card-bg); padding: 10px 12px; border-radius: 12px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }}
        .stat-card:hover {{ border-color: var(--accent-blue); transform: translateY(-2px); }}
        .stat-card.active-card {{ border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 15px rgba(59, 130, 246, 0.2); }}
        .stat-card .val {{ font-size: 1.2rem; font-weight: 700; color: var(--accent-blue); }}
        .stat-card .lbl {{ font-size: 0.72rem; color: var(--text-muted); }}
        .filter-container {{ display: flex; gap: 15px; margin-bottom: 15px; }}
        .search-input {{ padding: 12px 16px; border-radius: 10px; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); font-size: 0.95rem; outline: none; width: 100%; }}
        .search-input:focus {{ border-color: var(--accent-blue); }}
        .table-card {{ background: var(--card-bg); border-radius: 16px; border: 1px solid var(--border-color); overflow: hidden; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }}
        th {{ background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; padding: 16px; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 14px 16px; border-bottom: 1px solid #283548; font-size: 0.95rem; word-break: break-word; }}
        tr:last-child td {{ border-bottom: none; }}
        tr:hover {{ background-color: #243146; }}
        .date-badge {{ display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 5px 10px; border-radius: 8px; font-size: 0.82rem; white-space: nowrap; border: 1px solid #475569; }}
        .date-badge.today {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }}
        .time-badge {{ background: #0284c7; color: white; font-weight: 700; padding: 6px 10px; border-radius: 8px; font-size: 0.9rem; white-space: nowrap; display: inline-block; }}
        .sport-tag {{ font-weight: 600; }}
        .comp-title {{ font-weight: 600; color: #38bdf8; }}
        .event-title {{ font-weight: 700; color: #ffffff; }}
        .tv-container {{ display: flex; flex-wrap: wrap; gap: 6px; }}
        .tv-badge {{ display: inline-block; background: rgba(16, 185, 129, 0.15); color: #34d399; border: 1px solid rgba(16, 185, 129, 0.3); padding: 3px 8px; border-radius: 6px; font-size: 0.78rem; font-weight: 600; }}
        .empty-state {{ text-align: center; padding: 40px; color: var(--text-muted); font-size: 1.1rem; }}

        /* --- VISTA ADAPTADA A MÓVILES --- */
        @media (max-width: 768px) {{
            body {{ padding: 12px 8px; }}
            .table-card {{ background: transparent; border: none; box-shadow: none; overflow: visible; }}
            table, thead, tbody, th, td, tr {{ display: block; width: 100%; }}
            thead {{ display: none; }}
            tr {{
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 14px;
                margin-bottom: 12px;
                padding: 14px;
                box-shadow: 0 4px 12px rgba(0, 0, 0, 0.2);
            }}
            td {{
                padding: 3px 0;
                border: none;
            }}
            .date-col {{ display: none; }}
            .time-col {{ display: inline-block; width: auto; margin-right: 8px; }}
            .sport-col {{ display: inline-block; width: auto; float: right; }}
            .comp-col {{ clear: both; margin-top: 8px; }}
            .comp-title {{ font-size: 0.82rem; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.9; }}
            .event-col {{ margin: 6px 0 10px 0; }}
            .event-title {{ font-size: 1.05rem; line-height: 1.35; }}
            .tv-col {{ border-top: 1px solid rgba(255, 255, 255, 0.08); padding-top: 8px; margin-top: 6px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div><h1>⚡ Agenda Deportiva - Hoy</h1></div>
        <div class="header-controls"><button class="btn-update" onclick="location.reload()">🔄 Actualizar</button></div>
        <div class="last-update">Última actualización: <strong>{fecha_act} (UTC)</strong></div>
    </header>
    <div class="stats-grid">
        <div class="stat-card active-card" id="card-todos" onclick="setFilter('todos')">
            <div><div class="lbl">Todos</div><div class="val">{total_cnt}</div></div><div style="font-size:1.3rem">📌</div>
        </div>
        <div class="stat-card" id="card-filtrados" onclick="setFilter('filtrados')">
            <div><div class="lbl">Filtrados</div><div class="val" style="color:#a78bfa">{filtered_cnt}</div></div><div style="font-size:1.3rem">⭐</div>
        </div>
        <div class="stat-card" id="card-fútbol" onclick="setFilter('fútbol')">
            <div><div class="lbl">Fútbol</div><div class="val" style="color:#10b981">{futbol_cnt}</div></div><div style="font-size:1.3rem">⚽</div>
        </div>
        <div class="stat-card" id="card-baloncesto" onclick="setFilter('baloncesto')">
            <div><div class="lbl">Baloncesto</div><div class="val" style="color:#f97316">{baloncesto_cnt}</div></div><div style="font-size:1.3rem">🏀</div>
        </div>
        <div class="stat-card" id="card-tenis" onclick="setFilter('tenis')">
            <div><div class="lbl">Tenis</div><div class="val" style="color:#f59e0b">{tenis_cnt}</div></div><div style="font-size:1.3rem">🎾</div>
        </div>
        <div class="stat-card" id="card-motor" onclick="setFilter('motor')">
            <div><div class="lbl">Motor</div><div class="val" style="color:#ef4444">{motor_cnt}</div></div><div style="font-size:1.3rem">🏎️</div>
        </div>
        <div class="stat-card" id="card-otros" onclick="setFilter('otros')">
            <div><div class="lbl">Otros</div><div class="val" style="color:#a8a29e">{otros_cnt}</div></div><div style="font-size:1.3rem">🎯</div>
        </div>
    </div>
    <div class="filter-container">
        <input type="text" id="searchInput" class="search-input" onkeyup="filterTable()" placeholder="🔍 Filtrar por partido, equipo, tenista o canal TV...">
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
    document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active-card'));
    const activeCard = document.getElementById('card-' + filterType);
    if (activeCard) activeCard.classList.add('active-card');
    applyFilters();
}}
function filterTable() {{ applyFilters(); }}
function applyFilters() {{
    const searchFilter = document.getElementById('searchInput').value.toLowerCase();
    const table = document.getElementById('agendaTable');
    const trs = table.getElementsByTagName('tr');
    let visibleCount = 0;
    for (let i = 0; i < trs.length; i++) {{
        const tr = trs[i];
        if (tr.id === 'dynamicEmptyState') continue;
        const rowSport = (tr.getAttribute('data-sport') || '').toLowerCase();
        const isFiltered = tr.getAttribute('data-filtered') === 'true';
        const text = tr.textContent.toLowerCase();
        let matchesFilter = currentFilter === 'todos' ? true : (currentFilter === 'filtrados' ? isFiltered : rowSport === currentFilter);
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
    
    # Validación de seguridad: solo sobrescribir si la lista no está vacía
    if len(events) > 0:
        html_content = generate_html(events)
        with open("index.html", "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"Archivo index.html generado con éxito. Eventos encontrados: {len(events)}")
    else:
        print("Atención: No se obtuvieron eventos de la fuente. Se conserva la agenda previa sin modificar index.html.")
        
