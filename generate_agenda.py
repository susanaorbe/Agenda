from collections import Counter
from datetime import datetime, date, timedelta
from html import escape
from playwright.sync_api import sync_playwright
import zoneinfo
import re
import json

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from zoneinfo import ZoneInfoNotFoundError
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin


# ============================================================================
# CONFIGURACIÓN Y DICCIONARIO DE CANALES Y APLICACIONES
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


def update_channels_json_from_api():
    """Consulta la API oficial de CDN Live TV y actualiza channels.json correctamente."""
    api_url = "https://api.cdnlivetv.tv/api/v1/channels/?user=cdnlivetv&plan=free"
    try:
        with create_http_session() as session:
            response = session.get(api_url, headers=REQUEST_HEADERS, timeout=10)
            if response.status_code == 200:
                data = response.json()
                with open("channels.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, ensure_ascii=False, indent=2)
                print("Catálogo de canales actualizado desde la API correctamente.")
    except Exception as e:
        print(f"Aviso: No se pudo actualizar channels.json desde la API ({e}). Usando versión local.")


def get_dynamic_domain() -> str | None:
    """Devuelve el dominio activo de FCTV33 leyendo el botón LINK de Taplink."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/122.0.0.0 Safari/537.36"
                ),
                timezone_id="Europe/Madrid"
            )
            page = context.new_page()
            link_href = None
            try:
                page.goto(TAPLINK_URL, timeout=35000, wait_until="domcontentloaded")
                page.wait_for_selector("a[href]", timeout=20000)
                page.wait_for_timeout(1500)

                anchors = page.locator("a[href]").all()
                for a in anchors:
                    txt = (a.inner_text() or "").strip().upper()
                    if txt == "LINK":
                        link_href = a.get_attribute("href")
                        break
            finally:
                context.close()
                browser.close()

        if not link_href:
            print("Aviso: No se encontró el botón LINK en Taplink. FCTV33 se omitirá.")
            return None

        parsed = urlparse(urljoin(TAPLINK_URL, link_href))
        domain = (parsed.netloc or "").split("@")[-1].split(":")[0].lower()

        if parsed.scheme not in ("http", "https") or not re.fullmatch(r"[a-z0-9.-]+\.[a-z]{2,}", domain):
            print(f"Aviso: El botón LINK de Taplink apunta a un destino inválido ({link_href}). FCTV33 se omitirá.")
            return None
        if "taplink.cc" in domain or "taplink.at" in domain:
            print("Aviso: El botón LINK de Taplink sigue apuntando a Taplink. FCTV33 se omitirá.")
            return None

        with create_http_session() as session:
            resp = session.get(
                f"https://{domain}/es?ptst=1",
                headers=REQUEST_HEADERS,
                timeout=10,
                allow_redirects=True,
            )
            if resp.status_code >= 500:
                print(f"Aviso: El dominio activo {domain} no responde (HTTP {resp.status_code}). FCTV33 se omitirá.")
                return None

        print(f"   -> Dominio FCTV activo validado desde Taplink: {domain}")
        return domain
    except Exception as e:
        print(f"Aviso: No se pudo obtener el dominio activo desde Taplink ({e}). FCTV33 se omitirá.")
        return None


def is_fctv_event_allowed(parsed_url_path: str, sport_key: str) -> bool:
    """Filtra estrictamente los eventos de FCTV33 validando directamente la ruta URL."""
    allowed_sports = {"football", "basketball", "tennis", "motorsport"}
    if sport_key not in allowed_sports:
        return False

    path_lower = parsed_url_path.lower()
    excluded_url_patterns = [
        "/american-football/", "/aussie-rules/", "/badminton/", "/cycling/", "/fighting/", "/handball/", "/others/",
        "3x3basketball", "admiralbet-aba-league", "afc-u17-asian-cup", "alms-cup", "argentina-supercopa", 
        "argentine-reserve-league", "argentine-womens-league", "argentine-liga-nacional-de-bosquetbol", "asian-le-mans-cup-2026-27", 
        "asian-le-mans-series", "atp-challenger-orleans", "aus-champ", "australia-w-league", 
        "austrian-basketball-superliga", "auto-racing", "bahrain-premier-league", "basketball-bundesliga", 
        "basketball-champions-league", "basketball-super-league-1", "basketbol-super-ligi", "b1-league", "b2-league", 
        "belgian-womens-super-league", "benin-ligue-1", "bolivian-copa-lfpb", "brazilian-campeonato-paulista-youth", "brazilian-serie-b", "burundi-premier-league",
        "british-basketball-league", "caf-africa-cup-of-nations", "caf-wc", "categoria-primera-a", "chile-liga-nacional-basketball", 
        "china-taipei-professional-basketball-league", "cfa-team-china-international-tournament", "cfa-womens-super-league", 
        "china-hong-kong-basketball-league","china-womens-basketball-association", "chinese-football-assorciation-u-20-league", 
        "college-soccer", "colombian-copa-betplay-dimayor", "colombian-torneo-betplay-dimayor", "concacaf-nations-league", "czech-cup",  
        "east-asia-super-league", "egyptian-scores-cup", "el-salvador-reserves-league", "elite-league-u20", 
        "english-fa-womens-super-league", "english-football-league-one", "english-football-league-trophy", "english-football-league-two", "english-national-league", 
        "epa-one-u18", "eurocup-basketball", "europe-womens-basketball-championship-qualifier", "fa-womens-league-cup", "fiba-3x3-basketball-world-tour", 
        "fiba-africa-basketball-league", "fiba-europe-cup", "fiba-u16-womens-americup-2027-south-american-qualifiers", 
        "french-division-1-feminine", "ftbol-sala-primera-divisin", "futsal-tl-2026-play-off", "german-frauen-bundesliga", 
        "hunan-football-league", "indian-bangalore-super-division", "indian-league-division-1", "indo-d4", "indonesian-womens-liga-1", 
        "international-friendly", "italian-serie-c", "italian-womens-serie-a", "j-league-yamazaki-biscuit-levain-cup", 
        "jamaica-premier-league", "japan-womens-basketball-league", "japanese-j2-league", "japanese-j3-league", 
        "korean-basketball-league", "korean-wk-league", "korean-womens-basketball-league", "liberia-first-division", 
        "liberian-second-division", "liga-espanola-de-baloncesto-oro", "liga-nacional-de-baloncesto-profesional", 
        "liga-nova-kbm", "liga-u", "liga-prime-futsal", "ligue-nationale-de-basket-pro-a", "lithuania-cup", 
        "mali-premiere-division", "mexico-ascenso-mx", "mexico-liga-mx-femenil", "mongolia-premier-league", 
        "national-basketball-association-g-league", "national-basketball-league", "national-collegiate-athletic-association", 
        "new-zealand-basketball-league-womens", "new-zealand-football-championship", "new-zealand-womens-premier-division", "niger-premier-league",
        "oman-tamkeen-league", "panda-cup", "philippine-basketball-governors-cup", "philippines-mpbl", 
        "philippines-university-athletic-association", "portugal-liga-de-basquetebol", "poland-liga-2", "portuguese-u23-league", 
        "premier-padel", "rmc-grand-finals", "romanian-liga-ii", "rotax-grand-finals", "saff-championship", "scottish-womens-premier-league",
        "sierra-leone-premier-league", "slovenia-basketball-cup", "slovenia-2-liga", "spanish-segunda-division", 
        "spanish-segunda-division-rfef", "superettan-basket", "svenska-basketligan", "thai-kings-cup", "thai-league-3", 
        "turkey-basketball-league-2", "united-states-womens-premier-league", "uefa-el-w", "uefa-european-u17-football-championship", 
        "uefa-european-u17-womens-championship", "uefa-european-u19-football-championship", "uefa-european-u21-championship-qualification", 
        "uim-e1-world-championship-presented-by-pif", "ukrainian-basketball-super-league", "ukrainian-first-league", 
        "ukrainian-second-league", "uruguay-cup", "uzbekistan-super-league", "venezuela-primera-division", "venezuela-segunda-division", 
        "vtb-united-league", "women-empowerment-league"
    ]
    for pat in excluded_url_patterns:
        if pat in path_lower:
            return False
    return True


def fetch_fctv_events(domain: str, today_date: date) -> dict:
    fctv_events_by_sport = {
        "football": [],
        "basketball": [],
        "tennis": [],
        "motorsport": []
    }
    base_url = f"https://{domain}"
    target_url = f"{base_url}/es?ptst=1"

    time_re = re.compile(r"\b(\d{1,2}):(\d{2})\b")

    def is_event_detail_url(href: str) -> bool:
        parsed = urlparse(href)
        path = (parsed.path or href.split("?", 1)[0]).lower()
        forbidden_filenames = {
            "football.html", "basketball.html", "tennis.html", "motorsport.html",
            "motor.html", "motorsports.html", "futbol.html", "baloncesto.html",
            "tenis.html", "live.html", "others.html", "index.html", ""
        }
        filename = path.split("/")[-1]
        if filename in forbidden_filenames or path in {"/", "/es", "/es/"}:
            return False
        if "-match-" not in path:
            return False
        return True

    spain_tz = get_spain_timezone()
    now_spain = datetime.now(spain_tz)
    now_minutes = now_spain.hour * 60 + now_spain.minute

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            timezone_id="Europe/Madrid"
        )
        page = context.new_page()

        try:
            page.goto(target_url, timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(2000)

            category_links = page.evaluate("""() => {
                const links = [];
                for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.getAttribute('href');
                    if (href && !links.includes(href)) {
                        links.push(href);
                    }
                }
                return links;
            }""")

            valid_categories = set()
            for link in category_links:
                if link.startswith("mailto:") or "javascript:" in link or "taplink" in link:
                    continue
                parsed_l = urlparse(link)
                path_l = parsed_l.path.strip("/")
                if path_l and "." in path_l and not path_l.endswith(".html"):
                    continue
                if path_l and path_l not in valid_categories:
                    valid_categories.add(path_l)

            global_seen_urls = set()
            
            for cat in valid_categories:
                cat_url = urljoin(base_url, f"/{cat}")
                if "?" not in cat_url:
                    cat_url += "?ptst=1"
                
                try:
                    page.goto(cat_url, timeout=25000, wait_until="domcontentloaded")
                    page.wait_for_timeout(1000)

                    for _ in range(3):
                        page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                        page.wait_for_timeout(300)
                    page.evaluate("window.scrollTo(0, 0)")

                    candidate_cards = page.evaluate("""() => {
                        const out = [];
                        const seen = new Set();
                        const timePattern = /\\b\\d{1,2}:\\d{2}\\b/;
                        for (const a of document.querySelectorAll('a[href]')) {
                            const href = a.getAttribute('href') || '';
                            if (!href) continue;
                            const absolute = a.href;
                            if (seen.has(absolute)) continue;
                            seen.add(absolute);
                            let node = a;
                            let cardText = a.innerText || a.textContent || '';
                            for (let level = 0; level < 9 && node; level++, node = node.parentElement) {
                                const candidate = (node.innerText || node.textContent || '').trim();
                                if (timePattern.test(candidate)) {
                                    cardText = candidate;
                                    break;
                                }
                            }
                            out.push({href: absolute, cardText});
                        }
                        return out;
                    }""")

                    valid_candidates = [
                        item for item in candidate_cards
                        if is_event_detail_url(item.get("href", ""))
                    ]

                    # Lógica precisa de fechas para FCTV33:
                    # Comienza en hoy. Si detectamos un salto hacia atrás en las horas (ej. de la noche a la madrugada)
                    # o si encontramos eventos matutinos al inicio anteriores a la hora actual, se asignan a mañana.
                    current_event_date = today_date
                    last_time_mins = -1
                    has_seen_future_or_current = False

                    for item in valid_candidates:
                        href = item.get("href", "")
                        if not href:
                            continue
                        
                        full_url = urljoin(base_url, href)
                        parsed_url = urlparse(full_url)
                        canonical_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                        if canonical_url in global_seen_urls:
                            continue
                        global_seen_urls.add(canonical_url)

                        path_lower = parsed_url.path.lower()
                        detected_sport_key = "football"
                        detected_sport_label = "FÚTBOL"
                        detected_icon = "⚽"
                        detected_comp_key = "futbol"

                        if any(k in path_lower for k in ["/tennis/", "/es/tennis/", "/tenis/", "/es/tenis/"]):
                            detected_sport_key = "tennis"
                            detected_sport_label = "TENIS"
                            detected_icon = "🎾"
                            detected_comp_key = "tenis"
                        elif any(k in path_lower for k in ["/basketball/", "/es/basketball/", "/baloncesto/", "/es/baloncesto/"]):
                            detected_sport_key = "basketball"
                            detected_sport_label = "BALONCESTO"
                            detected_icon = "🏀"
                            detected_comp_key = "baloncesto"
                        elif any(k in path_lower for k in ["/motorsport/", "/es/motorsport/", "/motor/", "/es/motor/"]):
                            detected_sport_key = "motorsport"
                            detected_sport_label = "MOTOR"
                            detected_icon = "🏆"
                            detected_comp_key = "motor"
                        elif any(k in path_lower for k in ["/rugby/", "/hockey/", "/cricket/", "/baseball/", "/volleyball/"]):
                            detected_sport_key = "other"

                        card_text = item.get("cardText", "").strip()
                        extracted_time = "LIVE"
                        time_match = time_re.search(card_text)
                        if time_match:
                            h, m = time_match.groups()
                            extracted_time = f"{int(h):02d}:{m}"

                        if extracted_time == "LIVE":
                            continue

                        # Calcular minutos del evento
                        ev_h, ev_m = map(int, extracted_time.split(":"))
                        ev_mins = ev_h * 60 + ev_m

                        # Regla de fecha para FCTV33:
                        # 1. Si el evento ocurre antes de la hora actual y aún no hemos visto un evento futuro/actual,
                        #    pertenece al día siguiente (mañana), ya que los partidos de hoy a esa hora ya pasaron.
                        # 2. Si el tiempo desciende respecto al evento anterior (ej. 23:00 -> 13:00), significa que la lista
                        #    ha pasado al día siguiente.
                        if current_event_date == today_date:
                            if not has_seen_future_or_current and ev_mins < now_minutes:
                                current_event_date = today_date + timedelta(days=1)
                            elif last_time_mins != -1 and ev_mins < last_time_mins - 120:
                                current_event_date = today_date + timedelta(days=1)

                        if current_event_date == today_date and ev_mins >= now_minutes:
                            has_seen_future_or_current = True

                        last_time_mins = ev_mins

                        path_parts = [part for part in parsed_url.path.split("/") if part]
                        comp_str = detected_sport_label
                        event_str = "EVENTO FCTV33"
                        try:
                            match_idx = next((i for i, part in enumerate(path_parts) if "-match-" in part), -1)
                            if match_idx >= 0:
                                comp_segment = path_parts[match_idx]
                                raw_comp_slug = comp_segment.split("-match-", 1)[0]
                                filename = path_parts[match_idx + 1] if match_idx + 1 < len(path_parts) else ""
                            else:
                                filename = path_parts[-1] if path_parts else ""
                                comp_segment = path_parts[-2] if len(path_parts) >= 2 else ""
                                raw_comp_slug = re.sub(r"-\d{4,}$", "", comp_segment)

                            comp_str = re.sub(r"-\d{4,}$", "", raw_comp_slug).replace("-", " ").upper().strip()
                            filename = re.sub(r"\.html?$", "", filename, flags=re.IGNORECASE)
                            clean_slug = re.sub(r"-\d{1,2}-\d{4}$", "", filename)
                            clean_slug = re.sub(r"-vs-", " @VS_SEP@ ", clean_slug, flags=re.IGNORECASE)
                            event_str = clean_slug.replace("-", " ").replace("@VS_SEP@", "-").upper()
                            event_str = re.sub(r"\s+", " ", event_str).strip()
                        except Exception:
                            pass

                        if not event_str or event_str == "EVENTO FCTV33":
                            continue
                        if normalize_search_text(comp_str) == normalize_search_text(event_str):
                            comp_str = detected_sport_label

                        if not is_fctv_event_allowed(parsed_url.path, detected_sport_key):
                            continue

                        query = parsed_url.query
                        if "icg=" not in query:
                            query = f"{query}&" if query else ""
                            query += "icg=RVM&ilang=es"
                        elif "ilang=" not in query:
                            query += "&ilang=es"
                        normalized_url = f"{parsed_url.scheme or 'https'}://{parsed_url.netloc}{parsed_url.path}?{query}"

                        fctv_events_by_sport[detected_sport_key].append({
                            "date_obj": current_event_date,
                            "hora": extracted_time,
                            "deporte": detected_sport_label,
                            "icono": detected_icon,
                            "competicion": comp_str,
                            "evento": event_str,
                            "tv_list": [],
                            "fctv_url": normalized_url,
                            "is_filtered": False,
                            "is_configured": True,
                            "comp_key": detected_comp_key,
                            "source": "fctv33"
                        })
                except Exception as e:
                    print(f"   Aviso escaneando categoría {cat}: {e}")

        except Exception as e:
            print(f"Error general en exploración FCTV: {e}")
        finally:
            browser.close()

    return fctv_events_by_sport


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


def normalize_search_text(text: str) -> str:
    value = (text or "").lower()
    value = (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ç", "c")
        .replace("ñ", "n").replace("º", "ª")
    )
    value = re.sub(r"[|,;:/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


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
    "tv galicia", "tv3(cataluña)", "tvg(galicia)", "tv footballclub ▾",
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


def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r" real madrid ", r" rm castilla ", r" r\.?\s*madrid ")
CASTILLA_RE = rx(r" real madrid castilla ", r" rm castilla ", r" castilla ")
YOUTH_BASKET_RE = rx(r" sub\s*[-]?\d+ ", r" junior ", r" cadete ", r" infantil ")
SPAIN_SELECTION_RE = rx(r"\bspain\b", r"\bespaña\b", r"\bespana\b")

EXCLUDED_SPORTS_RE = rx(
    r" hockey ", r" patines ", r" nfl ", r" cowboys ", r" packers ",
    r" balonmano ", r" asobal ", r" handball ", r" waterpolo ", r" rugby ", r" rutby ", r" rucby ", r" rubgy ",
    r" ehf ", r" ihf ", r" futsal ", r" futbol sala ", r" golf ", r" beisbol ",
    r" padel ", r" padell "
)

EXCLUDED_COMPETITIONS_RE = rx(
    r" national league ", r" vanarama national league ", r" liga u ",
    r" tercera ", r" 3[ªa]\s*(?:rfef|federacion|division|grupo) ", r" grupo 8 ", r" tercera federacion ",
    r" basketball champions league ", r" futsal champions ",
    r" 2\.?\s*bundesliga ", r" serie a fem+inile ", r" serie a femminile ",
    r" laliga hypermotion ", r" segunda division ", r" hypermotion ",
    r" brasil\s*[-–—]?\s*serie\s+a ",
    r" argentina ", r" torneo clausura ", r" torneo apertura ",
    r" liga profesional ", r" primera division argentina ",
    r" international cup ", r" eurocup "
)

SPANISH_TENNIS_PLAYERS_RE = rx(
    r" carlos alcaraz ", r" alcaraz ", r" alejandro davidovich ", r" davidovich ",
    r" cristina bucsa ", r" bucsa ", r" paula badosa ", r" badosa ",
    r" jaume munar ", r" munar ", r" rafael jodar ", r" jodar ",
    r" dani merida ", r" merida "
)

WTA_RE = re.compile(r" wta ", re.IGNORECASE)
WOMEN_RE = rx(r" femenina ", r" femenino ", r" frauen ", r" women ", r"\(f\) ", r"\(w\) ")
PRIMERA_RFEF_RE = rx(r" primera federacion ", r" primera rfef ", r" 1[ªa]\s*federacion ")
LALIGA_RE = rx(r" liga ea sports ", r" liga ea ", r" primera division ", r" españa - la liga ", r" laliga(?![\s\-]*(?:hypermotion|smartbank|tv hypermotion|123)) ")
BASKET_ALLOWED_COMPETITIONS_RE = rx(r" liga endesa ", r" acb ", r" euroliga ", r" euroleague ", r" euro league ", r" copa acb ", r" supercopa endesa ", r" supercopa de espana ", r" nba ")

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
EVENT_CLEANUP_TRAIL_RE = re.compile(r"\s*-\s*(?:orange\s*f[uú]tbol\s*\d*|movistar[^\-]*|dazn[^\-]*|nba\s+league\s+pass|primera\s+federaci[oó]n(?:\s*\(\s*[mo]\d+(?:\s+[mo]\d+)*\s*\))?|\(\s*\d+(?:\s*y\s*\d+)?\s*\))\s*$", re.IGNORECASE)

TENNIS_EVENT_RE = rx(r" tenis ", r" atp ", r" wta ", r" masters ", r" open ", r" challenger ", r" itf ", r" torneo de ")
GOLF_RE = rx(r" golf ")
NBA_RE = rx(r" nba ")
EUROLIGA_RE = rx(r" euroliga ", r" euroleague ")
BASKET_WOMEN_RE = rx(r"\(f\) ", r"\(w\) ")
COPA_DEL_REY_RE = rx(r" copa del rey ")
BASKET_CONTEXT_RE = rx(r" basket ", r" baloncesto ", r" acb ")
CHAMPIONS_RE = rx(r" champions league ", r" champions ")
CHAMPIONS_NON_FOOTBALL_RE = rx(r" basketball ", r" cl ", r" afc ", r" asia ")
PREMIER_RE = rx(r" premier league ", r" premier ", r" inglaterra - premier league ")
SERIE_A_RE = rx(r" serie a ")
BUNDESLIGA_RE = rx(r" bundesliga ", r" alemania - bundesliga ")
BUNDESLIGA_2_RE = rx(r"2\.?\s*bundesliga ")
LIGUE1_RE = rx(r" ligue 1 ", r" francia - ligue 1 ")
EREDIVISIE_RE = rx(r" eredivisie ")
LIGA_PORTUGAL_RE = rx(r" liga portugues[ae] ", r" portugues[ae] ", r" betclic ")
WORLD_CUP_RE = rx(r" copa mundial ", r" mundial de la fifa ", r" world cup ")
EUROCUP_RE = rx(r" eurocup ")
EURO_FINAL_RE = rx(r" eurocopa ", r" euro\s*20\d{2} ", r" euro\s*cup ")
NATIONS_LEAGUE_RE = rx(r" nations league ")


def parse_motor_event(blob: str, raw_tournament: str, text_lines: list[str]) -> tuple[str, str, bool]:
    blob_lower = normalize_search_text(blob)
    if any(forbidden in blob_lower for forbidden in ["academy", "moto2", "moto 2", "moto3", "moto 3", "rookies", "supercars"]):
        return ("", "", False)
    if any(junk in blob_lower for junk in ["previo", "post", "rueda de prensa", "podio", "reportaje"]):
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

    is_fav = False
    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
    else:
        is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])

    return (comp_name, event_title, is_fav)


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:
    if EXCLUDED_SPORTS_RE.search(blob) or "ehf tv" in tv_blob or "movistar golf" in blob:
        return ("", "", "", False, False, "", "")
    competition_filter_blob = re.sub(r"\b[1-5]\s*[ªaº]?\s*(?:ronda|round)\b", " ", blob, flags=re.IGNORECASE)
    if EXCLUDED_COMPETITIONS_RE.search(competition_filter_blob):
        return ("", "", "", False, False, "", "")

    blob_normalized = normalize_search_text(blob)

    if TENNIS_EVENT_RE.search(blob):
        if GOLF_RE.search(tv_blob) or "movistar golf" in blob:
            return ("", "", "", False, False, "", "")
        tour = "WTA" if WTA_RE.search(blob) else "ATP"
        comp = raw_tournament if raw_tournament and raw_tournament.lower() not in {"tenis", "atp", "wta", ""} else f"{tour} Tour"
        is_fav = bool(SPANISH_TENNIS_PLAYERS_RE.search(blob))
        return ("Tenis", "🎾", comp, is_fav, True, "", "tenis")

    if BASKET_ALLOWED_COMPETITIONS_RE.search(blob):
        if WOMEN_RE.search(blob) or BASKET_WOMEN_RE.search(blob):
            return ("", "", "", False, False, "", "")
        if NBA_RE.search(blob):
            comp_name = "NBA"
            comp_key = "nba"
        elif EUROLIGA_RE.search(blob):
            comp_name = "Euroliga"
            comp_key = "euroliga"
        else:
            comp_name = "Liga Endesa / ACB"
            comp_key = "ligaendesa"
        is_fav = bool(REAL_MADRID_RE.search(blob) and not YOUTH_BASKET_RE.search(blob))
        return ("Baloncesto", "🏀", comp_name, is_fav, True, "", comp_key)

    if WOMEN_RE.search(blob) or any(p.search(blob) for p, _ in WOMEN_FOOTBALL_COMPETITIONS):
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(blob) or ("femenina" in blob and name.lower() in blob):
                comp_match = name
                break
        if comp_match and (REAL_MADRID_RE.search(blob) or SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized):
            return ("Fútbol", "⚽", comp_match, True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    if COPA_DEL_REY_RE.search(blob) and not WOMEN_RE.search(blob) and not BASKET_CONTEXT_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob) or SPAIN_SELECTION_RE.search(blob))
        return ("Fútbol", "⚽", "Copa del Rey", is_fav, True, "", "copadelrey")

    if CHAMPIONS_RE.search(blob) and not WOMEN_RE.search(blob) and not CHAMPIONS_NON_FOOTBALL_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob))
        return ("Fútbol", "⚽", "UEFA Champions League", is_fav, True, "", "champions")

    if LALIGA_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob))
        return ("Fútbol", "⚽", "LaLiga EA Sports", is_fav, True, "", "laliga")

    if PREMIER_RE.search(blob):
        return ("Fútbol", "⚽", "Premier League", False, True, "", "premier")

    if SERIE_A_RE.search(blob) and not ("brasil" in blob or "serie a brasil" in blob):
        return ("Fútbol", "⚽", "Serie A", False, True, "", "seriea")

    if BUNDESLIGA_RE.search(blob) and not BUNDESLIGA_2_RE.search(blob):
        return ("Fútbol", "⚽", "Bundesliga", False, True, "", "bundesliga")

    if LIGUE1_RE.search(blob):
        return ("Fútbol", "⚽", "Ligue 1", False, True, "", "ligue1")

    if EREDIVISIE_RE.search(blob):
        return ("Fútbol", "⚽", "Eredivisie", False, True, "", "eredivisie")

    if LIGA_PORTUGAL_RE.search(blob):
        return ("Fútbol", "⚽", "Liga Portugal Betclic", False, True, "", "ligaportugal")

    if WORLD_CUP_RE.search(blob):
        is_fav = bool(SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "Copa Mundial de la FIFA", is_fav, True, "", "mundial")

    if EURO_FINAL_RE.search(blob) and not EUROCUP_RE.search(blob):
        is_fav = bool(SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "Eurocopa", is_fav, True, "", "eurocopa")

    if NATIONS_LEAGUE_RE.search(blob):
        is_fav = bool(REAL_MADRID_RE.search(blob) or SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized)
        return ("Fútbol", "⚽", "UEFA Nations League", is_fav, True, "", "nationsleague")

    if PRIMERA_RFEF_RE.search(blob) or "primera federacion" in blob or "primera rfef" in blob:
        if CASTILLA_RE.search(blob):
            return ("Fútbol", "⚽", "España - Primera Federación", True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    return ("", "", "", False, False, "", "")


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

    competition_terms = (
        "liga", "primera", "segunda", "tercera", "federacion", "division", "grupo", "torneo", "serie a",
        "endesa", "bundesliga", "atp", "wta", "masters", "copa", "champions", "superbike", "eredivisie", "euroliga", "euroleague", "nba", "portugal", "portuguesa"
    )

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
        is_competition_line = any(term in part_lower for term in competition_terms)
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
        tournament = tournament_candidates[0]
        event_lines = [part for part in matchup_candidates if part != tournament]
    else:
        tournament = text_lines[0]
        event_lines = text_lines[1:]

    matchup = " - ".join(event_lines) if event_lines else tournament
    matchup = EVENT_CLEANUP_TRAIL_RE.sub("", matchup).strip()

    return time_clean, matchup, channels, tournament, text_lines


def fetch_and_parse_agenda() -> list[dict]:
    futbolenlatv_results = []
    seen_events = set()
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    current_date_obj = today_date

    dynamic_domain = get_dynamic_domain()
    if dynamic_domain:
        fctv_events_by_sport = fetch_fctv_events(dynamic_domain, today_date)
        for sport_key, events_list in fctv_events_by_sport.items():
            for ev in events_list:
                event_key = (ev["date_obj"], ev["hora"], normalize_search_text(ev["competicion"]), normalize_search_text(ev["evento"]))
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    futbolenlatv_results.append(ev)
    else:
        print("Aviso: FCTV33 se omitirá en esta generación: no hay un dominio activo válido (Taplink no disponible).")

    try:
        with create_http_session() as session:
            response = session.get(WIDGET_URL, headers=REQUEST_HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
        soup = BeautifulSoup(response.content, "html.parser")

        elements = soup.find_all("tr")
        if not elements:
            elements = soup.find_all(["article", "li", "div", "section", "p"])
        if not elements:
            elements = [node for node in soup.descendants if getattr(node, "name", None)]

        for element in elements:
            if not hasattr(element, "get_text"):
                continue

            el_text = element.get_text(" ", strip=True)
            date_match = DATE_RE.search(el_text)
            if date_match:
                try:
                    d, m, y = map(int, date_match.groups())
                    current_date_obj = date(y, m, d)
                except ValueError:
                    pass

            time_clean, event_str, channels, tournament, text_lines = parse_row_elements(element)
            if not time_clean or not channels:
                continue

            tv_blob = " ".join(channels).lower()
            blob = normalize_search_text(f"{' '.join(text_lines)} {tournament} {tv_blob}")

            comp_name, motor_event_title, is_fav = parse_motor_event(blob, tournament, text_lines)
            if comp_name:
                event_key = (current_date_obj, time_clean, comp_name, normalize_search_text(motor_event_title))
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                futbolenlatv_results.append({
                    "date_obj": current_date_obj,
                    "hora": time_clean,
                    "deporte": "MOTOR",
                    "icono": "🏆",
                    "competicion": comp_name.upper(),
                    "evento": motor_event_title.upper(),
                    "tv_list": channels,
                    "fctv_url": "",
                    "is_filtered": is_fav,
                    "is_configured": True,
                    "comp_key": "motor",
                    "source": "futbolenlatv"
                })
                continue

            sport, icon, competition, is_favorite, is_configured, custom_event, comp_key = get_sport_and_competition(
                blob, tournament, tv_blob, text_lines
            )
            
            is_movistar_plus_channel = any(normalize_search_text(ch) in {"movistar plus+", "movistar plus", "movistar+"} for ch in channels)
            if not sport and is_movistar_plus_channel:
                sport = "Otros"
                icon = "📺"
                competition = tournament if tournament else "Movistar Plus+"
                is_favorite = True
                is_configured = True
                comp_key = "other_movistar"

            if not sport:
                continue

            normalized_competition = normalize_search_text(competition)
            if (
                not is_movistar_plus_channel and (
                    normalized_competition == "brasil serie a"
                    or ("brasil" in normalized_competition and "serie a" in normalized_competition)
                )
            ):
                continue

            final_event = custom_event if custom_event else event_str
            if competition:
                comp_clean_pattern = re.compile(re.escape(competition), re.IGNORECASE)
                final_event = comp_clean_pattern.sub("", final_event)
            
            final_event = re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", final_event).strip()
            final_event = EVENT_CLEANUP_TRAIL_RE.sub("", final_event).strip()

            if not EVENT_TEXT_RE.search(final_event):
                continue

            event_key = (current_date_obj, time_clean, normalize_search_text(competition), normalize_search_text(final_event))
            if event_key in seen_events: 
                continue
            seen_events.add(event_key)

            futbolenlatv_results.append({
                "date_obj": current_date_obj,
                "hora": time_clean,
                "deporte": sport.upper(),
                "icono": icon,
                "competicion": competition.upper(),
                "evento": final_event.upper(),
                "tv_list": channels,
                "fctv_url": "",
                "is_filtered": is_favorite,
                "is_configured": is_configured,
                "comp_key": comp_key,
                "source": "futbolenlatv"
            })

    except Exception as e:
        print(f"Error cargando la agenda general: {e}")

    futbolenlatv_results.sort(key=lambda x: (x["date_obj"], x["hora"]))
    return futbolenlatv_results


# ============================================================================
# PLANTILLA HTML
# ============================================================================
HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Agenda Deportiva</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root { --bg-color: #0f172a; --card-bg: #1e293b; --border-color: #334155; --text-main: #f8fafc; --text-muted: #94a3b8; --accent-blue: #3b82f6; }
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 16px 12px; display: flex; justify-content: center; }
        .container { width: 100%; max-width: 1150px; }
        .sticky-panel { position: sticky; top: 0; z-index: 1000; background: var(--bg-color); padding-top: 8px; margin-top: -8px; box-shadow: 0 8px 14px -12px rgba(0,0,0,.9); }
        header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 8px; }
        h1 { font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: flex; align-items: center; gap: 6px; }
        .icon-link { text-decoration: none; display: inline-flex; align-items: center; cursor: pointer; transition: transform 0.2s; }
        .icon-link:hover { transform: scale(1.15); }
        .header-controls { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }
        .btn-update { background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
        .nav-tab-btn { background: var(--card-bg); color: var(--text-main); border: 1px solid var(--border-color); padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }
        .nav-tab-btn.active { background: var(--accent-blue); color: white; border-color: var(--accent-blue); }
        .last-update { font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; display: flex; justify-content: space-between; align-items: center; }
        
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-bottom: 12px; }
        .stat-card { background: var(--card-bg); padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }
        .stat-card.active-card { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }
        .stat-card .val { font-size: 1.1rem; font-weight: 700; color: var(--accent-blue); }
        .stat-card .lbl { font-size: 0.72rem; color: var(--text-muted); }

        .comp-filter-panel { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; margin-bottom: 12px; font-size: 0.85rem; overflow: hidden; }
        .comp-filter-header { padding: 8px 12px; display: flex; justify-content: space-between; align-items: center; font-weight: 600; color: #38bdf8; background: rgba(56, 189, 248, 0.05); user-select: none; flex-wrap: wrap; gap: 8px; }
        .comp-checkboxes label { display: flex; align-items: center; gap: 6px; cursor: pointer; color: var(--text-main); font-size: 0.85rem; font-weight: 700; white-space: nowrap; min-width: 0; }
        .comp-checkboxes input[type="checkbox"] { accent-color: var(--accent-blue); width: 16px; height: 16px; cursor: pointer; flex: 0 0 16px; margin: 0; }
        
        .table-card { background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: visible !important; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); margin-bottom: 80px; }
        table { width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }
        th { position: sticky; top: var(--sticky-panel-height, 0px); z-index: 900; background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }
        td { padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; overflow: visible !important; }
        tr.event-row:hover { background-color: #243146; }
        tr.event-row.previous-event td { background: rgba(56, 189, 248, 0.075); border-top: 1px solid rgba(56, 189, 248, 0.42); border-bottom: 1px solid rgba(56, 189, 248, 0.42); }
        tr.event-row.previous-event td:first-child { border-left: 3px solid #38bdf8; }
        tr.event-row.previous-event .time-badge { background: #0369a1; box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.35); }
        tr.event-row.previous-event .event-title::before { content: "EN JUEGO"; display: block; color: #38bdf8; font-size: 0.62rem; font-weight: 800; letter-spacing: 0.65px; margin-bottom: 4px; }
        
        .sport-col { width: 155px !important; min-width: 155px !important; white-space: nowrap; }
        .time-col, .date-col { white-space: nowrap; }
        .sport-tag { font-weight: 600; white-space: nowrap; }
        .favorite-pin { display: inline-block; margin-right: 6px; color: #c4b5fd; font-size: 0.88rem; line-height: 1; vertical-align: 1px; }
        body.favorites-view .favorite-pin { display: none; }
        .date-badge { display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
        .date-badge.today { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }
        .time-badge { background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }
        .comp-title { font-weight: 600; color: #38bdf8; font-size: 0.85rem; }
        .event-title { font-weight: 700; color: #ffffff; font-size: 0.9rem; line-height: 1.35; overflow-wrap: anywhere; }
        .tv-container { display: flex; flex-direction: column; gap: 4px; }
        .tv-badge { display: inline-block; background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; white-space: nowrap; text-decoration: none; transition: all 0.2s ease; }
        .tv-badge.channel-chip-link { cursor: pointer; }
        .tv-badge.channel-chip-link:hover { background: rgba(99, 102, 241, 0.35); color: #a5b4fc; border-color: #818cf8; transform: translateY(-1px); }
        .empty-state { text-align: center; padding: 30px; color: var(--text-muted); font-size: 1rem; }

        .channels-grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; padding: 16px; }
        .channel-card { background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 10px; padding: 12px; display: flex; align-items: center; justify-content: space-between; gap: 10px; transition: all 0.2s; }
        .channel-card:hover { border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.05); }
        .channel-info { display: flex; align-items: center; gap: 10px; overflow: hidden; }
        .channel-logo { width: 32px; height: 32px; object-fit: contain; border-radius: 4px; background: #111827; flex-shrink: 0; }
        .channel-name { font-size: 0.85rem; font-weight: 600; color: var(--text-main); line-height: 1.2; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; text-overflow: ellipsis; }
        .channel-actions { display: flex; align-items: center; gap: 6px; }
        .channel-fav-btn { background: none; border: none; font-size: 1.1rem; cursor: pointer; padding: 2px; transition: transform 0.2s; color: #64748b; }
        .channel-fav-btn:hover { transform: scale(1.2); }
        .channel-fav-btn.is-fav { color: #f59e0b; }
        .channel-action { background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 4px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; cursor: pointer; white-space: nowrap; text-decoration: none; }
        .channel-action:hover { background: rgba(56, 189, 248, 0.3); color: #fff; }

        .guides-banner { display: grid; grid-template-columns: repeat(auto-fit, minmax(140px, 1fr)); gap: 8px; margin-top: 10px; padding-bottom: 10px; }
        .guide-btn { background: linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(167, 139, 250, 0.2)); border: 1px solid rgba(59, 130, 246, 0.4); color: #f8fafc; padding: 10px 12px; border-radius: 8px; font-weight: 600; font-size: 0.8rem; cursor: pointer; display: flex; align-items: center; justify-content: center; gap: 6px; transition: all 0.2s; text-decoration: none; text-align: center; }
        .guide-btn:hover { background: rgba(59, 130, 246, 0.35); border-color: var(--accent-blue); transform: translateY(-1px); }

        .letter-btn { background: var(--card-bg); color: var(--text-main); border: 1px solid var(--border-color); padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; font-weight: 600; cursor: pointer; transition: all 0.2s; min-width: 28px; text-align: center; }
        .letter-btn.active { background: var(--accent-blue); color: white; border-color: var(--accent-blue); }
        .letter-btn:hover { background: rgba(59, 130, 246, 0.3); }

        #player-dialog { background: var(--card-bg); color: var(--text-main); border: 1px solid var(--border-color); border-radius: 12px; padding: 0; width: 90%; max-width: 900px; box-shadow: 0 25px 50px -12px rgba(0, 0, 0, 0.7); margin: auto; }
        #player-dialog::backdrop { background: rgba(0, 0, 0, 0.8); }
        .player-head { display: flex; justify-content: space-between; align-items: center; padding: 12px 16px; border-bottom: 1px solid var(--border-color); background: #111827; }
        .player-body { position: relative; width: 100%; aspect-ratio: 16/9; background: #000; }

        @media (max-width: 768px) {
            body { padding: 8px 4px; }
            .container { max-width: 100%; }
            header { flex-direction: column; align-items: stretch; gap: 8px; }
            .header-controls { justify-content: center; }
            .stats-grid { grid-template-columns: repeat(3, 1fr); gap: 6px; }
            .stat-card { padding: 6px 8px; }
            .stat-card .val { font-size: 0.95rem; }
            .stat-card .lbl { font-size: 0.68rem; }
            
            .comp-filter-header { flex-direction: column; align-items: stretch; gap: 8px; }
            .comp-filter-header > div { width: 100%; justify-content: space-between; }
            .comp-checkboxes { width: 100%; display: grid !important; grid-template-columns: repeat(2, 1fr); gap: 8px !important; }
            
            .table-card { background: transparent; border: none; box-shadow: none; margin-bottom: 60px; }
            table, thead, tbody, tr, td { display: block; width: 100% !important; }
            thead { display: none; }
            
            tr.event-row {
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 10px;
                margin-bottom: 10px;
                padding: 10px 12px;
                box-shadow: 0 4px 10px rgba(0,0,0,0.25);
            }
            tr.event-row td {
                padding: 3px 0;
                border: none;
                background: transparent !important;
            }
            
            .cell-date, .cell-time {
                display: inline-block;
                margin-right: 6px;
                margin-bottom: 4px;
            }
            .cell-sport {
                float: right;
                font-weight: 600;
                color: #38bdf8;
                font-size: 0.82rem;
            }
            .cell-comp {
                clear: both;
                font-size: 0.78rem;
                color: var(--text-muted);
                margin-bottom: 2px;
            }
            .cell-event {
                font-size: 0.9rem;
                font-weight: 700;
                color: #fff;
                margin-bottom: 8px;
            }
            .cell-tv {
                border-top: 1px solid var(--border-color);
                padding-top: 6px;
                margin-top: 4px;
            }
            .tv-container {
                flex-direction: row;
                flex-wrap: wrap;
                gap: 5px;
            }
            .channels-grid {
                grid-template-columns: 1fr !important;
                padding: 8px;
                gap: 6px;
            }
            .guides-banner { grid-template-columns: repeat(2, 1fr); gap: 6px; margin-top: 8px; padding-bottom: 8px; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="sticky-panel" id="stickyPanel">
    <header>
        <div><h1><a href="https://daddylive.pk/" target="_blank" class="icon-link" title="Abrir DaddyLive HD">⚡</a> Agenda Deportiva</h1></div>
        <div class="header-controls">
            <button class="nav-tab-btn active" id="btn-view-futbolenlatv" onclick="switchView('futbolenlatv')">AGENDA</button>
            <button class="nav-tab-btn" id="btn-view-channels" onclick="switchView('channels')">CANALES</button>
            <button class="btn-update" onclick="location.reload()">🔄 Actualizar</button>
        </div>
        <div class="last-update">
            <span>Hora actual: <strong id="liveClock">--:--:--</strong></span>
            <span>Última actualización: <strong>{FECHA_ACT}</strong></span>
        </div>
    </header>
    
    <div id="futbolenlatv-controls">
        <div class="stats-grid">
            <div class="stat-card" id="card-favoritos" onclick="setFilter('favoritos')">
                <div><div class="lbl">Favoritos</div><div class="val" style="color:#a78bfa">0</div></div><div style="font-size:1.1rem">📌</div>
            </div>
            <div class="stat-card" id="card-madrugada" onclick="setFilter('madrugada')">
                <div><div class="lbl">Madrugada</div><div class="val" style="color:#60a5fa">0</div></div><div style="font-size:1.1rem">💤</div>
            </div>
            <div class="stat-card" id="card-manana" onclick="setFilter('manana')">
                <div><div class="lbl">Mañana</div><div class="val" style="color:#fbbf24">0</div></div><div style="font-size:1.1rem">☀️</div>
            </div>
            <div class="stat-card" id="card-tarde" onclick="setFilter('tarde')">
                <div><div class="lbl">Tarde</div><div class="val" style="color:#f97316">0</div></div><div style="font-size:1.1rem">🌇</div>
            </div>
            <div class="stat-card" id="card-noche" onclick="setFilter('noche')">
                <div><div class="lbl">Noche</div><div class="val" style="color:#a78bfa">0</div></div><div style="font-size:1.1rem">🌙</div>
            </div>
            <div class="stat-card" id="card-proximamente" onclick="setFilter('proximamente')">
                <div><div class="lbl">Próximamente</div><div class="val">0</div></div><div style="font-size:1.1rem">📅</div>
            </div>
        </div>
        
        <div class="comp-filter-panel">
            <div class="comp-filter-header">
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                    <span>⚙️ Deportes</span>
                    <div class="comp-checkboxes" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                        <label><input type="checkbox" class="comp-chk" value="futbol" checked onchange="applyFilters()"> ⚽ FÚTBOL</label>
                        <label><input type="checkbox" class="comp-chk" value="baloncesto" checked onchange="applyFilters()"> 🏀 BALONCESTO</label>
                        <label><input type="checkbox" class="comp-chk" value="tenis" checked onchange="applyFilters()"> 🎾 TENIS</label>
                        <label><input type="checkbox" class="comp-chk" value="motor" checked onchange="applyFilters()"> 🏆 MOTOR</label>
                    </div>
                </div>
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                    <div class="comp-checkboxes" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                        <label><input type="checkbox" class="source-chk" id="chk-futbolenlatv" value="futbolenlatv" onchange="handleSourceChange('futbolenlatv')"> FUTBOLENLATV</label>
                        <label><input type="checkbox" class="source-chk" id="chk-fctv33" value="fctv33" checked onchange="handleSourceChange('fctv33')"> FCTV33</label>
                    </div>
                </div>
            </div>
        </div>

        <input type="text" id="agendaSearch" placeholder="Buscar por competición o evento..." oninput="applyFilters()" style="width: 100%; padding: 10px 14px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); font-size: 0.9rem; margin-bottom: 12px;">
    </div>

    <div id="channels-controls" style="display: none; margin-bottom: 4px;">
        <input type="text" id="channelSearch" placeholder="Buscar canal..." oninput="filterChannels()" style="width: 100%; padding: 10px 14px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); font-size: 0.9rem; margin-bottom: 8px;">
        <div style="display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;">
            <button class="letter-btn active" onclick="filterChannelsByLetter('FAVORITOS')">⭐ Favoritos</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('Todos')">Todos</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('#')">#</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('A')">A</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('B')">B</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('C')">C</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('D')">D</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('E')">E</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('F')">F</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('G')">G</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('H')">H</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('I')">I</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('J')">J</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('K')">K</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('L')">L</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('M')">M</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('N')">N</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('Ñ')">Ñ</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('O')">O</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('P')">P</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('Q')">Q</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('R')">R</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('S')">S</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('T')">T</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('U')">U</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('V')">V</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('W')">W</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('X')">X</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('Y')">Y</button>
            <button class="letter-btn" onclick="filterChannelsByLetter('Z')">Z</button>
        </div>
        <div class="guides-banner">
            <button class="guide-btn" onclick="openGuideView('⚽ Guía de Fútbol', 'https://sport-tv-guide.live/es/live/futbol')">⚽ Guía Fútbol</button>
            <button class="guide-btn" onclick="openGuideView('🏀 Guía de Baloncesto', 'https://sport-tv-guide.live/es/live/baloncesto')">🏀 Guía Baloncesto</button>
            <button class="guide-btn" onclick="openGuideView('🎾 Guía de Tenis', 'https://sport-tv-guide.live/es/live/tenis')">🎾 Guía Tenis</button>
            <button class="guide-btn" onclick="openGuideView('🏆 Guía de Motor', 'https://sport-tv-guide.live/es/live/deportes-de-motor')">🏆 Guía Motor</button>
        </div>
    </div>
    </div>

    <div class="table-card" id="futbolenlatv-view-container">
        <table>
            <thead>
                <tr>
                    <th class="date-col" style="width: 70px;">Fecha</th>
                    <th class="time-col" style="width: 70px;">Hora</th>
                    <th class="sport-col" style="width: 155px;">Deporte</th>
                    <th class="comp-col" style="width: 140px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 250px;">Canal TV</th>
                </tr>
            </thead>
            <tbody id="futbolenlatvTable">
                {FUTBOLENLATV_ROWS_HTML}
            </tbody>
        </table>
    </div>

    <div class="table-card" id="channels-view-container" style="display: none;">
        <div id="channelsGrid" class="channels-grid">
            <div class="empty-state">Cargando canales...</div>
        </div>
    </div>

    <div class="table-card" id="guide-view-container" style="display: none; padding: 20px; text-align: center;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px;">
            <button onclick="switchView('channels')" style="background: var(--card-bg); color: var(--text-main); border: 1px solid var(--border-color); padding: 8px 16px; border-radius: 8px; font-weight: 600; cursor: pointer;">← Volver a Canales</button>
            <strong id="guide-title" style="color: #38bdf8; font-size: 1.1rem;">Guía de TV</strong>
            <div style="display: flex; gap: 10px;">
                <a id="guide-external-link" href="" class="btn-update" style="text-decoration: none; background: #8b5cf6;">🚀 Abrir Guía a Pantalla Completa</a>
            </div>
        </div>
        <div style="background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 12px; padding: 40px 20px;">
            <p style="color: var(--text-muted); font-size: 0.95rem; line-height: 1.5;">
                Para mantener activas tus credenciales y tu sesión personalizada, las guías se abren directamente en una pestaña optimizada a pantalla completa. Utiliza las flechas de navegacion para volver a esta pantalla.
            </p>
        </div>
    </div>
</div>

<dialog id="player-dialog">
    <div class="player-head">
        <strong id="player-title" style="color: #38bdf8; font-size: 0.95rem;">Reproductor</strong>
        <button onclick="closePlayerModal()" style="background: none; border: none; color: var(--text-muted); font-size: 1.2rem; cursor: pointer;">✕</button>
    </div>
    <div class="player-body" id="player-content"></div>
</dialog>

<script>
const TODAY_DATE_STR = "{TODAY_DATE_STR}";
let currentFilter = 'favoritos';
let currentActiveView = 'futbolenlatv';
let currentLetterFilter = 'FAVORITOS';
let allCatalogChannels = [];
let lastNonFavSource = 'fctv33';

const AGENDA_CHANNEL_ALIASES = new Map([
  ['tennis channel', 'Tennis Channel HD US'],
  ['m+ laliga', 'LaLiga TV FHD UK'],
  ['m+ la liga', 'LaLiga TV FHD UK'],
  ['teledeporte', 'Teledeporte FHD'],
  ['m+ deportes', 'Movistar Deportes 1 FHD']
]);

function getFavoriteChannels() {
    try {
        const stored = localStorage.getItem('favorite_channels');
        return stored ? JSON.parse(stored) : [];
    } catch {
        return [];
    }
}

function toggleChannelFavorite(channelName) {
    let favs = getFavoriteChannels();
    const idx = favs.indexOf(channelName);
    if (idx > -1) {
        favs.splice(idx, 1);
    } else {
        favs.push(channelName);
    }
    try {
        localStorage.setItem('favorite_channels', JSON.stringify(favs));
    } catch (e) {
        console.error("Error guardando favoritos en localStorage:", e);
    }
    filterChannels();
}

function updateLiveClock() {
    const now = new Date();
    const options = { timeZone: 'Europe/Madrid', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
    const timeStr = new Intl.DateTimeFormat('es-ES', options).format(now);
    const clockElem = document.getElementById('liveClock');
    if (clockElem) clockElem.textContent = timeStr;
}
setInterval(updateLiveClock, 1000);
updateLiveClock();

function cleanStr(str) {
    return (str || '')
        .toLowerCase()
        .replace(/á/g, 'a').replace(/é/g, 'e').replace(/í/g, 'i')
        .replace(/ó/g, 'o').replace(/ú/g, 'u').replace(/ç/g, 'c')
        .replace(/ñ/g, 'n')
        .replace(new RegExp('[|,;:/]+', 'g'), ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function updateStickyHeadingOffset() {
    const panel = document.getElementById('stickyPanel');
    if (!panel) return;
    document.documentElement.style.setProperty('--sticky-panel-height', panel.getBoundingClientRect().height + 'px');
}

function handleSourceChange(changedSource) {
    if (currentFilter === 'favoritos') return;

    const chkFutbol = document.getElementById('chk-futbolenlatv');
    const chkFctv = document.getElementById('chk-fctv33');
    
    if (changedSource === 'futbolenlatv' && chkFutbol.checked) {
        chkFctv.checked = false;
        lastNonFavSource = 'futbolenlatv';
    } else if (changedSource === 'fctv33' && chkFctv.checked) {
        chkFutbol.checked = false;
        lastNonFavSource = 'fctv33';
    } else if (!chkFutbol.checked && !chkFctv.checked) {
        lastNonFavSource = '';
    }
    applyFilters();
}

function setFilter(filterType) {
    const prevFilter = currentFilter;
    currentFilter = cleanStr(filterType);
    const isFavView = (currentFilter === 'favoritos');
    
    document.body.classList.toggle('favorites-view', isFavView);
    document.querySelectorAll('#futbolenlatv-controls .stat-card').forEach(card => card.classList.remove('active-card'));
    
    const activeCard = document.getElementById('card-' + currentFilter);
    if (activeCard) activeCard.classList.add('active-card');

    const compCheckboxes = document.querySelectorAll('.comp-chk');
    compCheckboxes.forEach(chk => {
        if (isFavView) {
            chk.checked = true;
            chk.disabled = true;
            chk.parentElement.style.opacity = '0.6';
            chk.parentElement.style.cursor = 'not-allowed';
        } else {
            chk.disabled = false;
            chk.parentElement.style.opacity = '1';
            chk.parentElement.style.cursor = 'pointer';
        }
    });

    const chkFutbol = document.getElementById('chk-futbolenlatv');
    const chkFctv = document.getElementById('chk-fctv33');

    if (isFavView) {
        if (prevFilter !== 'favoritos') {
            if (chkFctv && chkFctv.checked) lastNonFavSource = 'fctv33';
            else if (chkFutbol && chkFutbol.checked) lastNonFavSource = 'futbolenlatv';
        }
        if (chkFutbol) {
            chkFutbol.checked = true;
            chkFutbol.disabled = true;
            chkFutbol.parentElement.style.opacity = '0.6';
            chkFutbol.parentElement.style.cursor = 'not-allowed';
        }
        if (chkFctv) {
            chkFctv.checked = false;
            chkFctv.disabled = true;
            chkFctv.parentElement.style.opacity = '0.6';
            chkFctv.parentElement.style.cursor = 'not-allowed';
        }
    } else {
        if (chkFutbol) {
            chkFutbol.disabled = false;
            chkFutbol.parentElement.style.opacity = '1';
            chkFutbol.parentElement.style.cursor = 'pointer';
        }
        if (chkFctv) {
            chkFctv.disabled = false;
            chkFctv.parentElement.style.opacity = '1';
            chkFctv.parentElement.style.cursor = 'pointer';
        }
        if (prevFilter === 'favoritos') {
            if (chkFutbol) chkFutbol.checked = (lastNonFavSource === 'futbolenlatv');
            if (chkFctv) chkFctv.checked = (lastNonFavSource !== 'futbolenlatv');
        }
    }

    applyFilters();
}

function updateStatsForActiveView() {
    if (currentActiveView === 'futbolenlatv') {
        const table = document.getElementById('futbolenlatvTable');
        if (!table) return;
        const trs = table.getElementsByClassName('event-row');

        let favCount = 0;
        let madCount = 0;
        let manCount = 0;
        let tarCount = 0;
        let nocCount = 0;
        let proxCount = 0;

        const checkedSources = new Set();
        if (currentFilter === 'favoritos') {
            if (lastNonFavSource) checkedSources.add(lastNonFavSource);
        } else {
            document.querySelectorAll('.source-chk:checked').forEach(chk => { checkedSources.add(chk.value); });
        }

        const checkedSports = new Set();
        document.querySelectorAll('.comp-chk:checked').forEach(chk => { checkedSports.add(chk.value); });

        const searchQuery = cleanStr(document.getElementById('agendaSearch')?.value || '');

        for (let i = 0; i < trs.length; i++) {
            const tr = trs[i];
            const rowSlot = cleanStr(tr.getAttribute('data-slot'));
            const isFiltered = tr.getAttribute('data-filtered') === 'true';
            const source = cleanStr(tr.getAttribute('data-source'));
            const sport = cleanStr(tr.getAttribute('data-sport'));
            const rowDate = tr.getAttribute('data-date');
            const searchData = cleanStr(tr.getAttribute('data-search'));
            const isToday = (rowDate === TODAY_DATE_STR);

            let matchesSource = checkedSources.has(source);
            let matchesSport = checkedSports.has(sport);
            let matchesSearch = !searchQuery || searchData.includes(searchQuery);

            if (isFiltered && source === 'futbolenlatv' && matchesSearch) {
                favCount++;
            }

            if (rowDate > TODAY_DATE_STR && matchesSport && matchesSource && matchesSearch) proxCount++;

            if (isToday && matchesSport && matchesSource && matchesSearch) {
                if (rowSlot === 'madrugada') madCount++;
                else if (rowSlot === 'manana') manCount++;
                else if (rowSlot === 'tarde') tarCount++;
                else if (rowSlot === 'noche') nocCount++;
            }
        }

        const cardFav = document.querySelector('#card-favoritos .val');
        const cardMad = document.querySelector('#card-madrugada .val');
        const cardMan = document.querySelector('#card-manana .val');
        const cardTar = document.querySelector('#card-tarde .val');
        const cardNoc = document.querySelector('#card-noche .val');
        const cardProx = document.querySelector('#card-proximamente .val');

        if (cardFav) cardFav.textContent = favCount;
        if (cardMad) cardMad.textContent = madCount;
        if (cardMan) cardMan.textContent = manCount;
        if (cardTar) cardTar.textContent = tarCount;
        if (cardNoc) cardNoc.textContent = nocCount;
        if (cardProx) cardProx.textContent = proxCount;
    }
}

function switchView(viewName) {
    currentActiveView = viewName;
    const btnFutbolenlatv = document.getElementById('btn-view-futbolenlatv');
    const btnChannels = document.getElementById('btn-view-channels');
    
    const futbolenlatvContainer = document.getElementById('futbolenlatv-view-container');
    const channelsContainer = document.getElementById('channels-view-container');
    const guideContainer = document.getElementById('guide-view-container');
    
    const futbolenlatvControls = document.getElementById('futbolenlatv-controls');
    const channelsControls = document.getElementById('channels-controls');

    if (btnFutbolenlatv) btnFutbolenlatv.classList.remove('active');
    if (btnChannels) btnChannels.classList.remove('active');

    futbolenlatvContainer.style.display = 'none';
    channelsContainer.style.display = 'none';
    guideContainer.style.display = 'none';
    futbolenlatvControls.style.display = 'none';
    channelsControls.style.display = 'none';

    if (viewName === 'futbolenlatv') {
        if (btnFutbolenlatv) btnFutbolenlatv.classList.add('active');
        futbolenlatvContainer.style.display = 'block';
        futbolenlatvControls.style.display = 'block';
        updateStatsForActiveView();
        applyFilters();
    } else if (viewName === 'channels') {
        if (btnChannels) btnChannels.classList.add('active');
        channelsContainer.style.display = 'block';
        channelsControls.style.display = 'block';
        loadChannelsCatalog();
    }
    updateStickyHeadingOffset();
}

function openGuideView(title, url) {
    currentActiveView = 'guide';
    const btnFutbolenlatv = document.getElementById('btn-view-futbolenlatv');
    const btnChannels = document.getElementById('btn-view-channels');
    
    if (btnFutbolenlatv) btnFutbolenlatv.classList.remove('active');
    if (btnChannels) btnChannels.classList.remove('active');

    document.getElementById('futbolenlatv-view-container').style.display = 'none';
    document.getElementById('channels-view-container').style.display = 'none';
    document.getElementById('guide-view-container').style.display = 'block';
    
    document.getElementById('futbolenlatv-controls').style.display = 'none';
    document.getElementById('channels-controls').style.display = 'none';

    document.getElementById('guide-title').textContent = title;
    
    const externalLinkBtn = document.getElementById('guide-external-link');
    externalLinkBtn.href = url;
    externalLinkBtn.target = '_self';
    
    updateStickyHeadingOffset();
}

async function initApp() {
    try {
        const response = await fetch('./channels.json');
        const jsonResult = await response.json();
        
        if (Array.isArray(jsonResult)) {
            allCatalogChannels = jsonResult;
        } else {
            allCatalogChannels = jsonResult.channels || jsonResult.data?.channels || jsonResult.data || [];
        }

        allCatalogChannels.sort((a, b) => {
            const nameA = (a.name || '').trim();
            const nameB = (b.name || '').trim();
            return nameA.localeCompare(nameB, 'es', { sensitivity: 'accent', numeric: true });
        });

        filterChannels();
        linkAgendaChannelsToCdn();
    } catch (e) {
        console.error("Error cargando canales:", e);
    }
}

async function loadChannelsCatalog() {
    if (allCatalogChannels.length > 0) {
        filterChannels();
        return;
    }
    await initApp();
}

function normalizeChannelName(name) {
    return String(name || '').toLowerCase()
        .normalize('NFD').replace(/[\u0300-\u036f]/g, '')
        .replace(/\b(hd|fhd|sd|hevc|4k|us|uk|pt|es)\b/g, '')
        .replace(/[^a-z0-9]/g, '')
        .trim();
}

function findCatalogChannel(channelName) {
    const wanted = normalizeChannelName(channelName);
    if (!wanted) return null;

    const aliasTarget = AGENDA_CHANNEL_ALIASES.get(cleanStr(channelName));
    if (aliasTarget) {
        const found = allCatalogChannels.find(ch => normalizeChannelName(ch.name) === normalizeChannelName(aliasTarget));
        if (found) return found;
    }

    let found = allCatalogChannels.find(ch => normalizeChannelName(ch.name) === wanted);
    if (found) return found;

    found = allCatalogChannels.find(ch => {
        const cName = normalizeChannelName(ch.name);
        return cName.includes(wanted) || wanted.includes(cName);
    });
    if (found) return found;

    return null;
}

function safePlayerUrl(channel) {
    const value = channel?.player_url || channel?.url;
    if (!value) return null;
    try {
        const u = new URL(value);
        if (u.protocol !== 'https:' || !['cdnlivetv.tv', 'www.cdnlivetv.tv'].includes(u.hostname)) return null;
        return u.href;
    } catch {
        return null;
    }
}

function linkAgendaChannelsToCdn() {
    document.querySelectorAll('.event-row').forEach(row => {
        const source = row.getAttribute('data-source');
        if (source === 'futbolenlatv') {
            row.querySelectorAll('.tv-badge').forEach(badge => {
                badge.removeAttribute('href');
                badge.classList.remove('channel-chip-link');
                badge.onclick = null;
                badge.textContent = badge.textContent.replace(' 🔗', '').replace(' ▶', '').trim();
            });
        }
    });

    document.querySelectorAll('.tv-badge').forEach(badge => {
        const textContent = badge.textContent.trim();
        if (textContent.startsWith('FCTV33')) return;

        const row = badge.closest('.event-row');
        if (row && row.getAttribute('data-source') === 'futbolenlatv') {
            return;
        }

        const channelName = textContent.replace(' 🔗', '').replace(' ▶', '').trim();
        
        if (/dazn|disney\+/i.test(channelName)) {
            badge.removeAttribute('href');
            badge.classList.remove('channel-chip-link');
            badge.onclick = null;
            return;
        }

        const catalogCh = findCatalogChannel(channelName);
        const playerUrl = catalogCh ? safePlayerUrl(catalogCh) : null;

        if (playerUrl) {
            badge.setAttribute('href', '#reproductor');
            badge.classList.add('channel-chip-link');
            badge.textContent = channelName + ' 🔗';
            badge.onclick = (e) => {
                e.preventDefault();
                openPlayerModal(channelName, playerUrl);
            };
        } else {
            badge.removeAttribute('href');
            badge.classList.remove('channel-chip-link');
            badge.onclick = null;
        }
    });
}

function renderChannelsGrid(channels) {
    const grid = document.getElementById('channelsGrid');
    if (!grid) return;

    if (channels.length === 0) {
        grid.innerHTML = '<div class="empty-state">😴 No hay canales disponibles.</div>';
        return;
    }

    const favs = getFavoriteChannels();

    grid.innerHTML = channels.map(ch => {
        const playable = Boolean(safePlayerUrl(ch));
        const url = safePlayerUrl(ch);
        const isFav = favs.includes(ch.name);
        const img = ch.image ? `<img src="${ch.image}" class="channel-logo" alt="" loading="lazy" onerror="this.style.display='none'">` : `<div class="channel-logo"></div>`;
        
        return `
            <div class="channel-card">
                <div class="channel-info">
                    ${img}
                    <div class="channel-name" title="${ch.name}">${ch.name}</div>
                </div>
                <div class="channel-actions">
                    <button class="channel-fav-btn ${isFav ? 'is-fav' : ''}" onclick="toggleChannelFavorite('${ch.name.replace(/'/g, "\\'")}')" title="${isFav ? 'Quitar de favoritos' : 'Añadir a favoritos'}">⭐</button>
                    ${playable ? `<a href="#reproductor" class="channel-action" onclick="openPlayerModal('${ch.name.replace(/'/g, "\\'")}', '${url}')">▶ Ver</a>` : '<span style="font-size:0.7rem; color:var(--text-muted)">No disponible</span>'}
                </div>
            </div>
        `;
    }).join('');
}

function filterChannelsByLetter(letter) {
    currentLetterFilter = letter;
    document.querySelectorAll('.letter-btn').forEach(btn => {
        btn.classList.toggle('active', btn.textContent.trim() === letter);
    });
    filterChannels();
}

function filterChannels() {
    const query = document.getElementById('channelSearch').value.toLowerCase();
    const favs = getFavoriteChannels();

    const filtered = allCatalogChannels.filter(ch => {
        const name = (ch.name || '').trim();
        const lowerName = name.toLowerCase();
        
        const matchesQuery = lowerName.includes(query);
        
        let matchesLetter = true;
        if (currentLetterFilter === 'FAVORITOS') {
            matchesLetter = favs.includes(name);
        } else if (currentLetterFilter !== 'Todos') {
            const firstChar = name.charAt(0).toUpperCase();
            if (currentLetterFilter === '#') {
                matchesLetter = /^[^A-ZÑ]/i.test(firstChar);
            } else {
                matchesLetter = (firstChar === currentLetterFilter);
            }
        }
        
        return matchesQuery && matchesLetter;
    });
    
    filtered.sort((a, b) => {
        const nameA = (a.name || '').trim();
        const nameB = (b.name || '').trim();
        return nameA.localeCompare(nameB, 'es', { sensitivity: 'accent', numeric: true });
    });

    renderChannelsGrid(filtered);
}

function openPlayerModal(name, url) {
    document.getElementById('player-title').textContent = `Reproduciendo: ${name}`;
    document.getElementById('player-content').innerHTML = `<iframe src="${url}" style="width:100%; height:100%; border:none;" allowfullscreen></iframe>`;
    document.getElementById('player-dialog').showModal();
}

function closePlayerModal() {
    const dialog = document.getElementById('player-dialog');
    document.getElementById('player-content').innerHTML = '';
    dialog.close();
}

function highlightPreviousEvents() {
    const THREE_HOURS_MS = 3 * 60 * 60 * 1000;
    const nowMs = Date.now();
    const currentMinuteTimestamp = Math.floor(nowMs / 60000) * 60000;
    const rows = Array.from(document.querySelectorAll('#futbolenlatvTable tr.event-row[data-ts]'));

    const currentlyLiveRows = rows.filter(row => row.classList.contains('previous-event'));
    for (const row of currentlyLiveRows) {
        const ts = Number(row.getAttribute('data-ts'));
        if (Number.isFinite(ts) && (nowMs - ts) > THREE_HOURS_MS) {
            location.reload();
            return;
        }
    }

    rows.forEach(row => row.classList.remove('previous-event'));
    let previousTimestamp = null;

    rows.forEach(row => {
        if (row.getAttribute('data-date') !== TODAY_DATE_STR) return;
        const timestamp = Number(row.getAttribute('data-ts'));
        if (!Number.isFinite(timestamp) || timestamp >= currentMinuteTimestamp) return;
        if ((nowMs - timestamp) > THREE_HOURS_MS) return;
        if (previousTimestamp === null || timestamp > previousTimestamp) {
            previousTimestamp = timestamp;
        }
    });

    if (previousTimestamp === null) return;

    rows.forEach(row => {
        if (row.getAttribute('data-date') === TODAY_DATE_STR && Number(row.getAttribute('data-ts')) === previousTimestamp) {
            row.classList.add('previous-event');
        }
    });
}

window.addEventListener('load', async () => {
    const nowMadrid = new Date(new Date().toLocaleString("en-US", {timeZone: "Europe/Madrid"}));
    const h = nowMadrid.getHours();
    const m = nowMadrid.getMinutes();
    const totalMins = h * 60 + m;
    let initialSlot = 'noche';
    if (totalMins <= 419) initialSlot = 'madrugada';
    else if (totalMins <= 779) initialSlot = 'manana';
    else if (totalMins <= 1229) initialSlot = 'tarde';
    else initialSlot = 'noche';

    await initApp();
    highlightPreviousEvents();
    setInterval(highlightPreviousEvents, 60000);
    setFilter(initialSlot);
    updateStickyHeadingOffset();
});

window.addEventListener('resize', () => { updateStickyHeadingOffset(); });

if ('ResizeObserver' in window) {
    const stickyPanel = document.getElementById('stickyPanel');
    if (stickyPanel) {
        const stickyObserver = new ResizeObserver(updateStickyHeadingOffset);
        stickyObserver.observe(stickyPanel);
    }
}

function applyFilters() {
    if (currentActiveView === 'futbolenlatv') {
        const checkedSources = new Set();
        if (currentFilter === 'favoritos') {
            checkedSources.add('futbolenlatv');
        } else {
            document.querySelectorAll('.source-chk:checked').forEach(chk => { checkedSources.add(chk.value); });
        }

        const checkedSports = new Set();
        document.querySelectorAll('.comp-chk:checked').forEach(chk => { checkedSports.add(chk.value); });

        const searchQuery = cleanStr(document.getElementById('agendaSearch')?.value || '');

        const table = document.getElementById('futbolenlatvTable');
        if (!table) return;
        const trs = table.getElementsByClassName('event-row');
        let visibleCount = 0;

        for (let i = 0; i < trs.length; i++) {
            const tr = trs[i];
            if (tr.id === 'dynamicEmptyState') continue;

            const rowSlot = cleanStr(tr.getAttribute('data-slot'));
            const isFiltered = tr.getAttribute('data-filtered') === 'true';
            const source = cleanStr(tr.getAttribute('data-source'));
            const sport = cleanStr(tr.getAttribute('data-sport')); 
            const rowDate = tr.getAttribute('data-date');
            const searchData = cleanStr(tr.getAttribute('data-search'));

            let matchesFilter = false;
            let matchesSource = checkedSources.has(source);
            let matchesSport = (currentFilter === 'favoritos') ? true : checkedSports.has(sport);
            let matchesSearch = !searchQuery || searchData.includes(searchQuery);

            if (currentFilter === 'favoritos') {
                matchesFilter = isFiltered;
            } else if (currentFilter === 'proximamente') {
                matchesFilter = (rowDate > TODAY_DATE_STR);
            } else {
                const isToday = (rowDate === TODAY_DATE_STR);
                matchesFilter = isToday && (rowSlot === currentFilter);
            }

            if (matchesFilter && matchesSport && matchesSource && matchesSearch) {
                tr.style.display = '';
                visibleCount++;
            } else {
                tr.style.display = 'none';
            }
        }

        updateStatsForActiveView();

        let emptyRow = table.querySelector('#dynamicEmptyState');
        if (visibleCount === 0) {
            if (!emptyRow) {
                emptyRow = document.createElement('tr');
                emptyRow.id = 'dynamicEmptyState';
                emptyRow.innerHTML = '<td colspan="6" class="empty-state">😴 No hay eventos que coincidan con la selección.</td>';
                table.appendChild(emptyRow);
            } else { emptyRow.style.display = ''; }
        } else { if (emptyRow) emptyRow.style.display = 'none'; }
    }
}
</script>
</body>
</html>
"""


def generate_html(futbolenlatv_events):
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")
    
    filtered_cnt = sum(1 for event in futbolenlatv_events if event["is_filtered"])
    slot_counts = Counter(get_time_slot(event["hora"]) for event in futbolenlatv_events if event["date_obj"] == today_date)
    total_cnt = sum(1 for event in futbolenlatv_events if event["date_obj"] > today_date)

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not futbolenlatv_events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
    else:
        for ev in futbolenlatv_events:
            tv_badges_list = []
            for channel in ev["tv_list"]:
                safe_channel = escape(str(channel), quote=True)
                tv_badges_list.append(
                    f'<span class="tv-badge" title="Canal {safe_channel}">{safe_channel}</span>'
                )

            if ev.get("fctv_url"):
                fctv_safe_url = escape(ev["fctv_url"], quote=True)
                tv_badges_list.append(
                    f'<a href="{fctv_safe_url}" target="_blank" class="tv-badge channel-chip-link" title="Ver en FCTV33">FCTV33 🔗</a>'
                )

            tv_badges = "".join(tv_badges_list)
            
            ev_date = ev["date_obj"]
            if ev_date == today_date:
                date_badge_html = '<span class="date-badge today">Hoy</span>'
            else:
                date_badge_html = f'<span class="date-badge">{ev_date.strftime("%d/%m")}</span>'

            slot = get_time_slot(ev["hora"])
            safe_slot = escape(clean_key(slot), quote=True)

            search_text = normalize_search_text(" ".join(
                [str(ev_date), ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
            ))
            safe_search = escape(search_text, quote=True)
            
            if ev["hora"] == "LIVE":
                safe_time = '<span class="time-badge" style="background:#10b981;">LIVE</span>'
                event_timestamp = int(datetime.now(spain_tz).timestamp() * 1000)
            else:
                try:
                    time_obj = datetime.strptime(ev["hora"], "%H:%M").time()
                except ValueError:
                    time_obj = datetime.strptime("00:00", "%H:%M").time()
                event_datetime = datetime.combine(ev_date, time_obj).replace(tzinfo=spain_tz)
                event_timestamp = int(event_datetime.timestamp() * 1000)
                safe_time = f'<span class="time-badge">{escape(str(ev["hora"]))}</span>'

            safe_timestamp = str(event_timestamp)
            safe_date_str = escape(ev_date.isoformat(), quote=True)
            safe_sport_key = escape(clean_key(ev["deporte"]), quote=True)
            safe_source = escape(clean_key(ev.get("source", "futbolenlatv")), quote=True)
            safe_comp_key = escape(str(ev.get("comp_key", "")), quote=True)
            safe_icon = escape(str(ev["icono"]))
            safe_sport = escape(str(ev["deporte"]))
            safe_competition = escape(str(ev["competicion"]))
            safe_event = escape(str(ev["evento"]))

            is_filtered_str = str(ev["is_filtered"]).lower()
            is_configured_str = str(ev["is_configured"]).lower()
            
            is_fctv_event = bool(ev.get("fctv_url"))
            favorite_pin_html = (
                '<span class="favorite-pin" title="Favorito" aria-label="Favorito">📌</span>'
                if ev["is_filtered"] and not is_fctv_event else ""
            )
            rows_list.append(
                f'<tr class="event-row" data-date="{safe_date_str}" data-ts="{safe_timestamp}" data-time="{escape(str(ev["hora"]))}" data-slot="{safe_slot}" data-sport="{safe_sport_key}" data-source="{safe_source}" data-comp-key="{safe_comp_key}" data-filtered="{is_filtered_str}" data-configured="{is_configured_str}" data-search="{safe_search}">'
                f'<td class="date-col cell-date">{date_badge_html}</td>'
                f'<td class="time-col cell-time">{safe_time}</td>'
                f'<td class="sport-col cell-sport"><span class="sport-tag">{safe_icon} {safe_sport}</span></td>'
                f'<td class="comp-col cell-comp"><div class="comp-title">{favorite_pin_html}{safe_competition}</div></td>'
                f'<td class="event-col cell-event"><div class="event-title">{safe_event}</div></td>'
                f'<td class="tv-col cell-tv"><div class="tv-container">{tv_badges}</div></td>'
                f'</tr>'
            )
            
    futbolenlatv_rows_html = "".join(rows_list)

    html = HTML_TEMPLATE.replace("{FECHA_ACT}", fecha_act)
    html = html.replace("{FILTERED_CNT}", str(filtered_cnt))
    html = html.replace("{MADRUGADA_CNT}", str(slot_counts["madrugada"]))
    html = html.replace("{MANANA_CNT}", str(slot_counts["manana"]))
    html = html.replace("{TARDE_CNT}", str(slot_counts["tarde"]))
    html = html.replace("{NOCHE_CNT}", str(slot_counts["noche"]))
    html = html.export if hasattr(html, 'export') else html # fallback
    html = html.replace("{TOTAL_CNT}", str(total_cnt))
    html = html.replace("{TODAY_DATE_STR}", today_date.isoformat())
    html = html.replace("{FUTBOLENLATV_ROWS_HTML}", futbolenlatv_rows_html)
    return html


if __name__ == "__main__":
    update_channels_json_from_api()
    
    futbolenlatv_events = fetch_and_parse_agenda()
    html_content = generate_html(futbolenlatv_events)
    with open("index.html", "w", encoding="utf-8") as f:
        f.write(html_content)
    print(
        "Archivo index.html generado con éxito. "
        f"Eventos totales en la agenda unificada: {len(futbolenlatv_events)}"
    )
