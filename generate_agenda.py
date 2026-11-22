from collections import Counter
from datetime import datetime, date, timedelta
from html import escape
from playwright.sync_api import sync_playwright
import zoneinfo
import os
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

SPORT_TV_GUIDE_LOGIN_URL = "https://sport-tv-guide.live/es/user/login"
SPORT_TV_GUIDE_SPORT_URLS = {
    "futbol": ("FÚTBOL", "⚽", "https://sport-tv-guide.live/es/live/futbol"),
    "baloncesto": ("BALONCESTO", "🏀", "https://sport-tv-guide.live/es/live/baloncesto"),
    "tenis": ("TENIS", "🎾", "https://sport-tv-guide.live/es/live/tenis"),
    "motor": ("MOTOR", "🏆", "https://sport-tv-guide.live/es/live/deportes-de-motor"),
}


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


def dismiss_consent_banner(page) -> None:
    """Intenta cerrar o aceptar el banner de consentimiento (fc-consent-root) si bloquea la vista."""
    try:
        consent_root = page.locator(".fc-consent-root").first
        if consent_root.count() == 0 or not consent_root.is_visible():
            return

        candidate_buttons = consent_root.locator(
            "button.fc-cta-consent, button[aria-label*='consent' i], button[aria-label*='accept' i], "
            "button[aria-label*='aceptar' i], button[aria-label*='consentir' i], "
            "button:has-text('Consentir'), button:has-text('Aceptar'), "
            "button:has-text('Accept'), button:has-text('Consent'), button:has-text('Agree')"
        )
        for i in range(candidate_buttons.count()):
            btn = candidate_buttons.nth(i)
            try:
                if btn.is_visible() and btn.is_enabled():
                    btn.click(timeout=3000)
                    page.wait_for_timeout(800)
                    return
            except Exception:
                continue

        page.evaluate("""() => {
            for (const el of document.querySelectorAll('.fc-consent-root')) {
                el.style.display = 'none';
            }
        }""")
        page.wait_for_timeout(300)
    except Exception:
        pass


def _parse_sport_tv_time(raw_time: str) -> str:
    txt = re.sub(r"\s+", "", str(raw_time or "")).upper()
    if not txt:
        return ""
    m12 = re.match(r"^(\d{1,2}):(\d{2})(AM|PM)$", txt)
    if m12:
        hour = int(m12.group(1))
        minute = int(m12.group(2))
        period = m12.group(3)
        if not (1 <= hour <= 12 and 0 <= minute <= 59):
            return ""
        if period == "AM":
            hour = 0 if hour == 12 else hour
        else:
            hour = 12 if hour == 12 else hour + 12
        return f"{hour:02d}:{minute:02d}"
    m24 = re.match(r"^(\d{1,2}):(\d{2})$", txt)
    if m24:
        hour = int(m24.group(1))
        minute = int(m24.group(2))
        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
    return clean_time(raw_time)


def fetch_sport_tv_guide_favorite_events() -> list[dict]:
    """Inicia sesión en sport-tv-guide.live y extrae eventos, fecha/hora, competición y canales."""
    username = (os.environ.get("SPORT_TV_GUIDE_USER") or "").strip()
    password = os.environ.get("SPORT_TV_GUIDE_PASS") or ""

    if not username or not password:
        print("Aviso: SPORT_TV_GUIDE_USER o SPORT_TV_GUIDE_PASS no están definidas. Se omite sport-tv-guide.live.")
        return []

    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    events: list[dict] = []
    seen: set[tuple[str, str, str, str]] = set()

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
        )
        context = browser.new_context(
            user_agent=REQUEST_HEADERS["User-Agent"],
            timezone_id="Europe/Madrid"
        )
        page = context.new_page()

        try:
            page.goto(SPORT_TV_GUIDE_LOGIN_URL, timeout=35000, wait_until="domcontentloaded")
            page.wait_for_timeout(1500)
            dismiss_consent_banner(page)

            user_input = page.locator(
                "form input[type='email'], form input[type='text'], "
                "form input[name*='user' i], form input[name*='login' i], form input[name*='email' i]"
            ).first
            pass_input = page.locator("form input[type='password']").first

            if user_input.count() == 0 or pass_input.count() == 0:
                print("Aviso: No se localizaron los campos de usuario o contraseña en el formulario.")
                return []

            user_input.fill(username)
            pass_input.fill(password)
            dismiss_consent_banner(page)

            submit_btn = page.locator(
                "form button[type='submit'], form input[type='submit'], form button:not([type='button'])"
            ).first
            if submit_btn.count() > 0:
                submit_btn.click(timeout=15000)
            else:
                pass_input.press("Enter")

            page.wait_for_load_state("domcontentloaded", timeout=20000)
            page.wait_for_timeout(2500)
            dismiss_consent_banner(page)

            still_on_login = "/user/login" in page.url and page.locator("form input[type='password']").count() > 0
            if still_on_login:
                print("Aviso: No se completó el inicio de sesión en sport-tv-guide.live.")
                return []

            for sport_key, (sport_label, sport_icon, sport_url) in SPORT_TV_GUIDE_SPORT_URLS.items():
                try:
                    page.goto(sport_url, timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(2000)
                    dismiss_consent_banner(page)

                    raw_items = page.evaluate("""() => {
                        const out = [];
                        let currentDayText = '';
                        const dayPattern = /\\b(\\d{1,2})\\s*(?:de\\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|lun|mar|mié|mie|jue|vie|sáb|sab|dom)/i;

                        const nodes = document.querySelectorAll('div.row, h2, h3, h4, .dateHeader, .day-header, [class*="date"]');
                        for (const el of nodes) {
                            if (el.matches('div.row')) {
                                const timeEl = el.querySelector('.main.time b, .main b');
                                const inlineCols = el.querySelectorAll('.col-inline > div');
                                if (!timeEl || inlineCols.length === 0) continue;

                                const hora = (timeEl.innerText || timeEl.textContent || '').trim();
                                const evento = (inlineCols[0]?.innerText || inlineCols[0]?.textContent || '').replace(/\\s+/g, ' ').trim();
                                const competicion = (inlineCols[1]?.innerText || inlineCols[1]?.textContent || '').replace(/\\s+/g, ' ').trim();
                                const linkEl = el.querySelector('a[href]') || el.closest('a[href]');
                                const href = linkEl ? (linkEl.href || linkEl.getAttribute('href') || '') : '';

                                const channelImgs = el.querySelectorAll('.col-xs-4.mobile-normal img, img[data-src*="tvm-station"], img[src*="tvm-station"]');
                                const canales = [];
                                const seenCh = new Set();
                                for (const img of channelImgs) {
                                    const chName = (img.getAttribute('title') || img.getAttribute('alt') || '').replace(/\\s+/g, ' ').trim();
                                    const src = (img.getAttribute('data-src') || img.getAttribute('src') || '').toLowerCase();
                                    if (!chName) continue;
                                    let countryHint = '';
                                    if (src.includes('tvm-station-pt-')) countryHint = 'PT';
                                    else if (src.includes('tvm-station-fr-')) countryHint = 'FR';
                                    else if (src.includes('tvm-station-uk-')) countryHint = 'UK';
                                    else if (src.includes('tvm-station-es-')) countryHint = 'ES';
                                    else if (src.includes('tvm-station-it-')) countryHint = 'IT';
                                    else if (src.includes('tvm-station-de-')) countryHint = 'DE';
                                    else if (src.includes('tvm-station-us-')) countryHint = 'US';

                                    const key = chName.toLowerCase() + '|' + countryHint;
                                    if (!seenCh.has(key)) {
                                        seenCh.add(key);
                                        canales.push({ name: chName, country: countryHint });
                                    }
                                }

                                out.push({
                                    dayText: currentDayText,
                                    hora,
                                    evento,
                                    competicion,
                                    href,
                                    canales
                                });
                            } else {
                                const txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ').trim();
                                if (txt && txt.length <= 40 && dayPattern.test(txt)) {
                                    currentDayText = txt;
                                }
                            }
                        }
                        return out;
                    }""")

                    sport_count = 0
                    for item in raw_items:
                        hora = _parse_sport_tv_time(item.get("hora", ""))
                        raw_ev_stg = re.sub(r"[\u00a0\u200b\ufeff]+", " ", str(item.get("evento", ""))).strip()
                        raw_ev_stg = re.sub(r"\s{2,}", " - ", raw_ev_stg)
                        evento = re.sub(r"\s+", " ", raw_ev_stg).strip().upper()
                        raw_stg_comp = str(item.get("competicion", "")).strip()
                        stg_href_low = str(item.get("href", "")).lower()
                        if (
                            "bundesliga-f" in stg_href_low
                            or re.search(r"\bbundesliga\s*\(f\)", raw_stg_comp, flags=re.IGNORECASE)
                            or (re.search(r"\bbundesliga\b", raw_stg_comp, flags=re.IGNORECASE) and re.search(r"\(f\)|\(w\)|frauen|femenin", evento, flags=re.IGNORECASE))
                        ):
                            competicion = "Bundesliga (F)"
                        elif "2-bundesliga" in stg_href_low or re.search(r"\b2\.?\s*bundesliga\b", raw_stg_comp, flags=re.IGNORECASE):
                            competicion = "2. Bundesliga"
                        else:
                            competicion = canonical_competition_name(raw_stg_comp).upper()
                        canales = item.get("canales") or []

                        if not hora or not evento or not canales:
                            continue
                        if EXCLUDED_SPORTS_RE.search(f" {normalize_search_text(evento)} {normalize_search_text(competicion)} "):
                            continue

                        ev_date = today_date
                        day_txt = str(item.get("dayText", ""))
                        day_num_match = re.search(r"\b(\d{1,2})\b", day_txt)
                        if day_num_match:
                            try:
                                d_num = int(day_num_match.group(1))
                                if 1 <= d_num <= 31:
                                    if d_num >= today_date.day:
                                        ev_date = today_date.replace(day=d_num)
                                    else:
                                        next_month = (today_date.replace(day=28) + timedelta(days=4)).replace(day=1)
                                        ev_date = next_month.replace(day=d_num)
                            except ValueError:
                                ev_date = today_date

                        dedup_key = (ev_date.isoformat(), hora, sport_key, normalize_search_text(evento))
                        if dedup_key in seen:
                            continue
                        seen.add(dedup_key)

                        try:
                            t_obj = datetime.strptime(hora, "%H:%M").time()
                        except ValueError:
                            t_obj = datetime.strptime("00:00", "%H:%M").time()
                        ev_ts = int(datetime.combine(ev_date, t_obj).replace(tzinfo=spain_tz).timestamp() * 1000)

                        events.append({
                            "date_iso": ev_date.isoformat(),
                            "ts": ev_ts,
                            "fecha_label": "Hoy" if ev_date == today_date else ev_date.strftime("%d/%m"),
                            "hora": hora,
                            "deporte": sport_label,
                            "icono": sport_icon,
                            "competicion": competicion,
                            "evento": evento,
                            "canales": canales,
                        })
                        sport_count += 1

                    print(f"   -> [{sport_label}] Eventos con canales extraídos de sport-tv-guide.live: {sport_count}")
                except Exception as e:
                    print(f"   [{sport_label}] Error extrayendo {sport_url}: {e}")

        except Exception as e:
            print(f"Error en sport-tv-guide.live: {e}")
        finally:
            context.close()
            browser.close()

    events.sort(key=lambda x: (x["date_iso"], x["hora"], normalize_search_text(x["evento"])))
    return events


def normalize_search_text(text: str) -> str:
    value = str(text or "").lower().replace("\u00a0", " ").replace("\u200b", "").replace("\ufeff", "")
    value = (
        value.replace("á", "a").replace("é", "e").replace("í", "i")
        .replace("ó", "o").replace("ú", "u").replace("ç", "c")
        .replace("ñ", "n").replace("º", "ª")
    )
    value = re.sub(r"[|,;:/]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


EXCLUDED_COMPETITIONS_EXACT = {
    normalize_search_text(c) for c in [
        "NCAA",
        "BWF HONG KONG OPEN",
        "AFLW",
        "NCAA WOMEN",
        "FORMULA 4",
        "A-LEAGUE",
        "PRO PADEL LEAGUE",
        "JAPANESE J3 LEAGUE",
        "NINJA A-LEAGUE",
        "B2 LEAGUE",
        "NATIONAL BASKETBALL LEAGUE",
        "NEW ZEALAND BASKETBALL LEAGUE WOMENS",
        "JAPANESE J1 LEAGUE",
        "NEXZTER BRIC SUPERBIKE 2026 ROUND 4",
        "CBA CLUB CUP",
        "KOREAN K LEAGUE 1",
        "KOREAN K LEAGUE 2",
        "INDONESIAN WOMENS LIGA 1",
        "JAPAN WOMENS BASKETBALL LEAGUE",
        "WOMENS NATIONAL BASKETBALL LEAGUE",
        "INDONESIAN CHAMPIONSHIP",
        "INDONESIAN SUPER LEAGUE",
        "THAI LEAGUE 3",
        "VIETNAM NATIONAL FIRST CLASS LEAGUE",
        "AUSTRALIA A LEAGUE",
        "MYANMAR PROFESSIONAL LEAGUE",
        "VTB UNITED LEAGUE",
        "FUTSAL TL 2026 PLAY OFF",
        "ANDORRAN PRIMERA DIVISIO",
        "FREE PRACTICE 2 AND QUALIFYING",
        "ITALIAN CAMPIONATO PRIMAVERA 1",
        "LIGA 2",
        "RUSSIAN FIRST LEAGUE",
        "TURKISH FIRST LEAGUE",
        "TURKISH SUPER LEAGUE",
        "SYC PR",
        "INDONESIA WOMENS LEAGUE 26 27",
        "TAÇA DE PORTUGAL",
        "BELARUSIAN FIRST LEAGUE",
        "SEGUNDA FEDERACIÓN",
        "TERCERA FEDERACIÓN",
        "LIGA VASCA CADETE",
        "LIGA NUSANTARA 2026 27",
        "INTERNATIONAL FRIENDLY VIETNAM WOMENS FUTSAL TEAM",
        "RUSSIAN PREMIER LEAGUE",
        "AZERBAIJAN PREMIER LEAGUE",
        "ARMENIAN PREMIER LEAGUE",
        "BELARUSIAN PREMIER LEAGUE",
        "BURUNDI PREMIER LEAGUE",
        "CAMBODIAN PREMIER LEAGUE",
        "THAI LEAGUE 1",
        "THAI LEAGUE 2",
        "UKRAINIAN PREMIER LEAGUE",
        "VIETNAM NATIONAL CHAMPION LEAGUE",
        "AFC BEACH SOCCER 2026",
        "INDIAN SUPER LEAGUE",
        "ITALIAN WOMENS SERIE A",
        "SINGAPORE PREMIER LEAGUE",
        "HUNAN FOOTBALL LEAGUE",
        "LIVE U18S 26 27",
        "FIA F4 WORLD CUP",
        "GRAND PRIX DE DUBA",
        "ASSOCIAO PORTUGUESA DE SIM RACING",
        "RUSSIAN WOMENS BASKETBALL PREMIER LEAGUE",
        "CHINA WOMENS BASKETBALL ASSOCIATION",
        "AUSTRIAN 3 LIGA",
        "BELGIAN WOMENS SUPER LEAGUE",
        "BOSNIA AND HERZEGOVINA PREMIER LEAGUE",
        "BULGARIAN FIRST LEAGUE",
        "BUNDESLIGA (F)",
        "BUNDESLIGA FEMENINA",
        "2. BUNDESLIGA",
        "CHAMPIONSHIP",
        "CONGO PREMIER LEAGUE",
        "DANISH 1ST DIVISION",
        "DANISH WOMENS DIVISON 1",
        "ENGLISH FA WOMENS SUPER LEAGUE",
        "ENGLISH FOOTBALL LEAGUE CHAMPIONSHIP",
        "ENGLISH NATIONAL LEAGUE",
        "ETHIOPIA PREMIER LEAGUE",
        "FA WSL (F)",
        "FIFA U17 WORLD CUP",
        "FIFA MUNDIAL SUB-17",
        "FIFA MUNDIAL SUB 17",
        "FRENCH LIGUE 2",
        "GER JBH",
        "GERMAN 3 LIGA",
        "GERMAN BUNDESLIGA 2",
        "GREEK WOMENS SUPER LEAGUE",
        "HUNGARY FIZZ LIGA",
        "KENYA WOMENS FOOTBALL LEAGUE",
        "LALIGA HYPERMOTION",
        "LEBANESE PREMIER LEAGUE",
        "LIGA 1",
        "LIGA PRIME",
        "LIGA PRIME FUTSAL",
        "LIGUE 2",
        "LIBYAN PREMIER LEAGUE",
        "MALAWI PREMIER LEAGUE",
        "MALAYSIAN SUPER LEAGUE",
        "MALTA FIRST DIVISION LEAGUE",
        "MOLDOVAN SUPER LIGA",
        "NATIONAL LEAGUE",
        "NETHERLANDS TWEEDE DIVISIE",
        "QATAR STARS LEAGUE",
        "ROMANIAN SUPER LIGA",
        "SAND2",
        "SERIE A FEMMINILE",
        "SERBIAN MOZZART BET SUPERLIGA",
        "SPANISH SEGUNDA DIVISION",
        "SUPER LIG",
        "S R C",
        "SVK WD1",
        "UNITED ARAB EMIRATES ADNOC PRO LEAGUE",
        "UNITED ARAB EMIRATES DIVISION 1 GROUP A",
        "UGANDA PREMIER LEAGUE",
        "UZBEKISTAN SUPER LEAGUE",
        "ZAMBIA SUPER LEAGUE",
        "ALBANIAN SUPER LEAGUE",
        "AUSTRIAN 2 LIGA",
        "BASKETBOL SUPER LIGI",
        "BELGIAN CHALLENGER PRO LEAGUE",
        "BELGIAN PRO LEAGUE",
        "BENIN LIGUE 1",
        "BRAZILIAN PAULISTA WOMENS LEAGUE",
        "CHI LIGA DE PRIMERA",
        "CROATIAN FOOTBALL LEAGUE",
        "CYPRIOT FIRST DIVISION",
        "CZECH WOMENS LIGA1",
        "D1 FÉMININE",
        "DIVISION 1 FEMININ",
        "ENGLISH CONFERENCE SOUTH DIVISION",
        "ENGLISH FOOTBALL LEAGUE ONE",
        "ENGLISH FOOTBALL LEAGUE TWO",
        "ENGLISH NORTHERN PREMIER LEAGUE",
        "FIBA 3X3 BASKETBALL WORLD TOUR",
        "ITALIAN SERIE B",
        "ITALIAN SERIE C",
        "EKSTRAKLASA",
        "FRENCH LIGUE 3",
        "NARODNI BASKETBALOVA LIGA",
        "PFL",
        "PKO BANK POLSKI EKSTRAKLASA",
        "PORTUGUESE CUP",
        "SAN MARINO CAMPIONATO DI CALCIO",
        "SLOVENIA 1 LIGA",
        "SWEDEN ALLSVENSKAN",
        "SWITZERLAND NLB",
        "ADMIRALBET ABA LEAGUE",
        "ARGENTINE DIVISION 1",
        "ARGENTINE GROUP B TEBOLIDUN LEAGUE MANCHESTER",
        "AUSTRIA B BASKETBALL LEAGUE",
        "AUSTRIAN BUNDESLIGA",
        "BASKETBALL BUNDESLIGA",
        "BBL",
        "EREDIVISIE",
        "FIRST DIVISION",
        "FRENCH DIVISION 1 FEMININE",
        "GREEK BASKET LEAGUE",
        "GREEK SUPER LEAGUE",
        "JUPILER PRO LEAGUE",
        "LEGA BASKET SERIE A",
        "LF 2",
        "LIGA ESPANOLA DE BALONCESTO ORO",
        "LIGA FEMENINA CHALLENGE",
        "FEMININA DE BASQUETEBOL",
        "LIGAT HAAL",
        "LIGUE NATIONALE DE BASKET PRO A",
        "MALI PREMIERE DIVISION",
        "NETHERLANDS EREDIVISIE",
        "NIGER PREMIER LEAGUE",
        "PORTUGAL LIGA DE BASQUETEBOL",
        "SCOTTISH LEAGUE ONE",
        "SCOTTISH PREMIERSHIP",
        "SEGUNDA FEB",
        "SWITZERLAND SUPER LEAGUE",
        "SWISS BASKETBALL LEAGUE",
        "SUPERLIGA FEMENINA",
        "ZENSKA BASKETBALOVA LIGA",
        "CUP U17",
        "ANDORRAN SECOND DIVISION",
        "ANTIGUA BARBUDA PREMIER DIVISION",
        "ARUBA DIVISION DI HONOR",
        "ARG PRIMERA NACIONAL",
        "AUS CHAMP",
        "AUSTRALIA W LEAGUE",
        "BOLIVIAN PRIMERA DIVISION",
        "BRAZILIAN SERIE A",
        "BRITISH BASKETBALL LEAGUE",
        "CANADIAN PREMIER LEAGUE",
        "CATEGORIA PRIMERA A",
        "CFA WOMENS SUPER LEAGUE",
        "CHINA TAIPEI PROFESSIONAL BASKETBALL LEAGUE",
        "CHINESE FOOTBALL LEAGUE 1",
        "CONMEBOL COPA SUDAMERICANA",
        "COPA SUDAMERICANA",
        "COSTA RICA PRIMERA DIVISION",
        "DIVISION 1 (F)",
        "EL SALVADOR PRIMERA DIVISION",
        "FERRARI CHALLENGE EUROPE",
        "HONDURAS PRIMERA DIVISION",
        "J LEAGUE U 21",
        "JAPANESE FOOTBALL LEAGUE",
        "JAPANESE J2 LEAGUE",
        "KOREAN WOMENS BASKETBALL LEAGUE",
        "LIGA FEMENINA DE BALONCESTO",
        "LIGA FEMENINA ENDESA",
        "NACIONAL DE FUTSAL CRESOL",
        "LIGAPRO SERIE A",
        "MEXICO ASCENSO MX",
        "MEXICO LIGA MX",
        "MOTORSPORT: FR WORLD CUP",
        "NASCAR LOCAL RACING SERIES",
        "PREMIERSHIP",
        "NATIONAL BASKETBALL ASSOCIATION G LEAGUE",
        "NEW ZEALAND WOMENS PREMIER DIVISION",
        "NICARAGUA LIGA PRIMERA",
        "PHILIPPINES FOOTBALL LEAGUE",
        "PRIMERA FEB",
        "RWANDAN WOMENS LEAGUE",
        "SAINT KITTS NEVIS PREMIER LEAGUE",
        "SERIE A BRASIL",
        "SUPERCROSS DE PARIS",
        "SURINAME MAJOR LEAGUE",
        "UNITED STATES WOMENS PREMIER LEAGUE",
        "VENEZUELA SEGUNDA DIVISION",
        "NHL",
        "ALBANIAN DIVISION 1",
        "BRAZILIAN CAMPEONATO PAULISTA YOUTH",
        "BRAZILIAN SERIE B",
        "BURKINA FASO DIVISION 1",
        "COSTA RICA 2 LIGA",
        "CZECH CHANCE LIGA",
        "DANISH SUPERLIGA",
        "DIVISIÓN HONOR INFANTIL",
        "DIVISIÓN HONOR JUVENIL",
        "GERMAN WOMENS BUNDESLIGA II",
        "JAMAICA PREMIER LEAGUE",
        "JORNADA 8 BALONCESTO",
        "JORNADA 9 BALONCESTO",
        "LIGA U",
        "LITHUANIAN I LYGA",
        "PARAGUAYAN PRIMERA DIVISION",
        "PORTUGAL CAMPEONATO NACIONAL FEMININO",
        "PRIMERA DIVISIÓN ARGENTINA",
        "SERIE A2 BASKET",
        "SIERRA LEONE PREMIER LEAGUE",
        "SLOVAK NIKE LIGA",
        "SWEDEN DAMALLSVENSKAN",
        "SWITZERLAND DIVISON 2 LEAGUE",
        "SWITZERLAND DIVISION 2 LEAGUE",
        "TC 2000",
        "UNITED STATES WOMENS NATIONAL SOCCER LEAGUE",
        "ZANZIBAR PREMIER LEAGUE",
    ]
}

EXCLUDED_EVENT_SUBSTRINGS = {
    normalize_search_text(sub) for sub in [
        "F1 ACADEMY",
        "ATP CHALLENGER",
        "PREVIO",
        "LIBRES 3",
        "UWC 60",
        "LIBRES 2",
        "TREINOS LIVRES",
        "PRACTICE 3",
        "MOTO2 AND MOTO3",
        "AUTOMOBILISMO: GT CAMP. MUNDO",
        "FIA GT WORLD CUP – QUALIFICATION RACE",
        "FIA GT WORLD CUP - QUALIFICATION RACE",
        "FIA GT WORLD CUP QUALIFICATION RACE",
        "AUTOMOBILISMO: FR CAMP. MUNDO",
        "FIA FR WORLD CUP – QUALIFICATION RACE",
        "FIA FR WORLD CUP - QUALIFICATION RACE",
        "FIA FR WORLD CUP QUALIFYING RACE",
        "SUB 17 CAMP. NACIONAL 1.ª DIVISÃO",
        "SUB 17 CAMP. NACIONAL 1.a DIVISÃO",
        "F1 ACADÉMIE",
        "F1 ACADEMIE",
        "FIA FR CAMP. MUNDO",
        "FIA FR WORLD CUP",
        "FIA GT CAMP. MUNDO",
        "FIA GT WORLD CUP",
        "FÚTBOL COLOMBIANO PRIMERA DIVISIÓN",
        "MOTO2",
        "MOTO3",
        "WARM UP",
    ]
}

COMPETITION_SYNONYMS: dict[str, str] = {
    # Fútbol
    "laliga": "LaLiga EA Sports",
    "laliga ea sports": "LaLiga EA Sports",
    "la liga ea sports": "LaLiga EA Sports",
    "liga ea sports": "LaLiga EA Sports",
    "liga ea": "LaLiga EA Sports",
    "espana - la liga": "LaLiga EA Sports",
    "spanish la liga": "LaLiga EA Sports",
    "laliga hypermotion": "LaLiga Hypermotion",
    "segunda division": "LaLiga Hypermotion",
    "hypermotion": "LaLiga Hypermotion",
    "liga f": "Liga F",
    "primera division femenina": "Liga F",
    "spanish primera division de la liga de futbol femenino": "Liga F",
    "uefa champions league": "UEFA Champions League",
    "champions league": "UEFA Champions League",
    "champions": "UEFA Champions League",
    "women's champions league": "UEFA Women's Champions League",
    "uefa women's champions league": "UEFA Women's Champions League",
    "champions league femenina": "UEFA Women's Champions League",
    "copa del rey": "Copa del Rey",
    "copa de la reina": "Copa de la Reina",
    "premier league": "Premier League",
    "english premier league": "Premier League",
    "premier": "Premier League",
    "inglaterra - premier league": "Premier League",
    "serie a": "Serie A",
    "italian serie a": "Serie A",
    "bundesliga": "Bundesliga",
    "alemania - bundesliga": "Bundesliga",
    "ligue 1": "Ligue 1",
    "french ligue 1": "Ligue 1",
    "francia - ligue 1": "Ligue 1",
    "eredivisie": "Eredivisie",
    "liga portugal betclic": "Liga Portugal Betclic",
    "liga portuguesa": "Liga Portugal Betclic",
    "portuguesa": "Liga Portugal Betclic",
    "betclic": "Liga Portugal Betclic",
    "primera federacion": "PRIMERA FEDERACIÓN",
    "primera rfef": "PRIMERA FEDERACIÓN",
    "espana - primera federacion": "PRIMERA FEDERACIÓN",
    "spanish primera division rfef": "PRIMERA FEDERACIÓN",
    "nations league": "UEFA Nations League",
    "uefa nations league": "UEFA Nations League",
    "eurocopa": "Eurocopa",
    "copa mundial de la fifa": "Copa Mundial de la FIFA",
    "world cup": "Copa Mundial de la FIFA",
    # Baloncesto
    "nba": "NBA",
    "national basketball association": "NBA",
    "euroliga": "Euroliga",
    "euroleague": "Euroliga",
    "euro league": "Euroliga",
    "liga endesa": "Liga Endesa / ACB",
    "acb": "Liga Endesa / ACB",
    "liga endesa / acb": "Liga Endesa / ACB",
    "liga asociacion de clubs de baloncesto": "Liga Endesa / ACB",
    "liga asociacion de clubes de baloncesto": "Liga Endesa / ACB",
    "copa acb": "Copa ACB",
    "supercopa endesa": "Supercopa Endesa",
    # Tenis
    "atp": "ATP Tour",
    "atp tour": "ATP Tour",
    "wta": "WTA Tour",
    "wta tour": "WTA Tour",
    "masters": "ATP Masters 1000",
    "atp masters 1000": "ATP Masters 1000",
    # Motor
    "formula 1": "Fórmula 1",
    "f1": "Fórmula 1",
    "motogp": "MotoGP",
    "formula e": "Fórmula E",
    "fórmula e": "Fórmula E",
    "indycar": "IndyCar",
    "indy car": "IndyCar",
}


def deduplicate_repeated_phrase(text: str) -> str:
    cleaned = re.sub(r"[\s\u00a0\u200b\ufeff]+", " ", str(text or "")).strip()
    if not cleaned:
        return ""
    tokens = cleaned.split(" ")
    if len(tokens) >= 2 and len(tokens) % 2 == 0:
        half = len(tokens) // 2
        if [t.lower() for t in tokens[:half]] == [t.lower() for t in tokens[half:]]:
            return " ".join(tokens[:half])
    return cleaned


def canonical_competition_name(raw_comp: str) -> str:
    cleaned = deduplicate_repeated_phrase(raw_comp)
    if not cleaned:
        return ""
    norm = normalize_search_text(cleaned)
    if re.search(r"\bbundesliga\s*\(f\)|\bbundesliga\s+femenina\b|\bfrauen\s*bundesliga\b", norm):
        return "BUNDESLIGA (F)" if "(f)" in norm else "BUNDESLIGA FEMENINA"
    if re.search(r"\b2\.?\s*bundesliga\b", norm):
        return "2. BUNDESLIGA"
    if norm in COMPETITION_SYNONYMS:
        return COMPETITION_SYNONYMS[norm].upper()
    return cleaned.upper()


def is_globally_excluded_event(competicion: str, evento: str) -> bool:
    comp_norm = normalize_search_text(competicion)
    event_norm = normalize_search_text(evento)
    combined_norm = normalize_search_text(f"{evento} {competicion}")
    if comp_norm and comp_norm in EXCLUDED_COMPETITIONS_EXACT:
        return True
    for exc_comp in EXCLUDED_COMPETITIONS_EXACT:
        if exc_comp and re.search(rf"\b{re.escape(exc_comp)}\b", combined_norm):
            return True
    for sub in EXCLUDED_EVENT_SUBSTRINGS:
        if sub and (sub in event_norm or sub in combined_norm):
            return True
    return False


FCTV_ALLOWED_URL_SEGMENTS = ("/football/", "/basketball/", "/tennis/", "/motorsport/")


def is_fctv_event_allowed(parsed_url_path: str, sport_key: str) -> bool:
    """Excluye automáticamente eventos de FCTV33 cuya URL no contenga /football/, /basketball/, /tennis/ o /motorsport/."""
    path_low = str(parsed_url_path or "").lower()
    if not any(seg in path_low for seg in FCTV_ALLOWED_URL_SEGMENTS):
        return False
    return sport_key in {"football", "basketball", "tennis", "motorsport"}


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

            non_target_cat_tokens = (
                "american-football", "aussie-rules", "badminton", "baseball", "cricket",
                "cycling", "fighting", "handball", "hockey", "others", "rugby", "volleyball", "padel"
            )
            valid_categories = set()
            for link in category_links:
                if link.startswith("mailto:") or "javascript:" in link or "taplink" in link:
                    continue
                parsed_l = urlparse(link)
                path_l = parsed_l.path.strip("/")
                if path_l and "." in path_l and not path_l.endswith(".html"):
                    continue
                path_low = path_l.lower()
                if any(tok in path_low for tok in non_target_cat_tokens):
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
                            let cardText = (a.innerText || a.textContent || '').trim();
                            let bestNode = a;

                            for (let level = 0; level < 6 && node && node.parentElement; level++) {
                                const parent = node.parentElement;
                                const matchLinks = parent.querySelectorAll('a[href*="-match-"]');
                                if (matchLinks.length > 1) {
                                    break;
                                }
                                bestNode = parent;
                                const txt = (parent.innerText || parent.textContent || '').trim();
                                if (timePattern.test(txt)) {
                                    cardText = txt;
                                }
                                node = parent;
                            }

                            cardText = (bestNode.innerText || bestNode.textContent || cardText).trim();

                            const dataAttrs = [];
                            for (const el of [bestNode, ...bestNode.querySelectorAll('*')]) {
                                for (const attr of el.attributes) {
                                    if (attr.name.startsWith('data-') || attr.name === 'datetime' || attr.name === 'title') {
                                        dataAttrs.push(attr.name + '=' + attr.value);
                                    }
                                }
                            }

                            out.push({
                                href: absolute,
                                cardText,
                                dataAttrs: dataAttrs.join(' | ')
                            });
                        }
                        return out;
                    }""")

                    valid_candidates = [
                        item for item in candidate_cards
                        if is_event_detail_url(item.get("href", ""))
                    ]

                    month_map = {
                        "ene": 1, "jan": 1, "feb": 2, "mar": 3, "abr": 4, "apr": 4,
                        "may": 5, "jun": 6, "jul": 7, "ago": 8, "aug": 8,
                        "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dic": 12, "dec": 12
                    }

                    def parse_fctv_datetime(item_dict: dict) -> tuple[date | None, str]:
                        card_text = item_dict.get("cardText", "")
                        data_attrs = item_dict.get("dataAttrs", "")
                        combined = f"{card_text}\n{data_attrs}"

                        ts_match = re.search(r"\b(1[6-9]\d{8}|2\d{9})(\d{3})?\b", data_attrs)
                        if ts_match:
                            try:
                                ts_sec = int(ts_match.group(1))
                                dt_spain = datetime.fromtimestamp(ts_sec, tz=spain_tz)
                                return dt_spain.date(), f"{dt_spain.hour:02d}:{dt_spain.minute:02d}"
                            except Exception:
                                pass

                        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2}))?", combined)
                        if iso_match:
                            try:
                                y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                                ev_d = date(y, m, d)
                                if iso_match.group(4) and iso_match.group(5):
                                    return ev_d, f"{int(iso_match.group(4)):02d}:{int(iso_match.group(5)):02d}"
                                t_m = time_re.search(card_text)
                                if t_m:
                                    return ev_d, f"{int(t_m.group(1)):02d}:{t_m.group(2)}"
                            except ValueError:
                                pass

                        t_match = time_re.search(card_text)
                        if not t_match:
                            return None, ""
                        extracted_t = f"{int(t_match.group(1)):02d}:{t_match.group(2)}"

                        text_norm = normalize_search_text(card_text)

                        if any(k in text_norm for k in ["en vivo", "en directo", "directo", "live", "hoy", "today"]):
                            return today_date, extracted_t
                        if any(k in text_norm for k in ["manana", "tomorrow"]):
                            return today_date + timedelta(days=1), extracted_t
                        if any(k in text_norm for k in ["ayer", "yesterday"]):
                            return today_date - timedelta(days=1), extracted_t

                        dm_match = re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](20\d{2}))?\b", card_text)
                        if dm_match:
                            try:
                                d_val, m_val = int(dm_match.group(1)), int(dm_match.group(2))
                                y_val = int(dm_match.group(3)) if dm_match.group(3) else today_date.year
                                if not dm_match.group(3) and m_val < today_date.month - 6:
                                    y_val += 1
                                return date(y_val, m_val, d_val), extracted_t
                            except ValueError:
                                pass

                        txt_date_match = re.search(
                            r"\b(\d{1,2})\s+(?:de\s+)?([a-z]{3,10})\b|\b([a-z]{3,10})\s+(\d{1,2})\b",
                            text_norm
                        )
                        if txt_date_match:
                            if txt_date_match.group(1) and txt_date_match.group(2):
                                d_str, mon_str = txt_date_match.group(1), txt_date_match.group(2)[:3]
                            else:
                                mon_str, d_str = txt_date_match.group(3)[:3], txt_date_match.group(4)
                            if mon_str in month_map:
                                try:
                                    m_val = month_map[mon_str]
                                    d_val = int(d_str)
                                    y_val = today_date.year + (1 if m_val < today_date.month - 6 else 0)
                                    return date(y_val, m_val, d_val), extracted_t
                                except ValueError:
                                    pass

                        return today_date, extracted_t

                    for item in valid_candidates:
                        href = item.get("href", "")
                        if not href:
                            continue

                        full_url = urljoin(base_url, href)
                        parsed_url = urlparse(full_url)

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

                        if not is_fctv_event_allowed(parsed_url.path, detected_sport_key):
                            continue

                        canonical_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                        if canonical_url in global_seen_urls:
                            continue
                        global_seen_urls.add(canonical_url)

                        current_event_date, extracted_time = parse_fctv_datetime(item)
                        if not current_event_date or not extracted_time or extracted_time == "LIVE":
                            continue

                        if current_event_date < today_date:
                            continue

                        path_parts = [part for part in parsed_url.path.split("/") if part]
                        comp_str = ""
                        event_str = ""
                        try:
                            match_idx = next((i for i, part in enumerate(path_parts) if "-match-" in part), -1)
                            if match_idx >= 0:
                                comp_segment = path_parts[match_idx]
                                raw_comp_slug = comp_segment.split("-match-", 1)[0]
                                filename = path_parts[match_idx + 1] if match_idx + 1 < len(path_parts) else ""
                            else:
                                filename = path_parts[-1] if path_parts else ""
                                comp_segment = path_parts[-2] if len(path_parts) >= 2 else ""
                                raw_comp_slug = re.sub(r"-match-\d+$", "", comp_segment, flags=re.IGNORECASE)

                            raw_comp_clean = raw_comp_slug.replace("-", " ").strip().upper()
                            raw_comp_clean = re.sub(r"\s+", " ", raw_comp_clean).strip()
                            if raw_comp_clean and is_globally_excluded_event(raw_comp_clean, ""):
                                continue
                            comp_str = canonical_competition_name(raw_comp_clean) if raw_comp_clean else detected_sport_label

                            filename = re.sub(r"\.html?$", "", filename, flags=re.IGNORECASE)
                            clean_slug = re.sub(r"-\d{1,2}-\d{4}$", "", filename)
                            clean_slug = re.sub(r"-vs-", " @VS_SEP@ ", clean_slug, flags=re.IGNORECASE)
                            event_str = clean_slug.replace("-", " ").replace("@VS_SEP@", " - ").upper()
                            event_str = re.sub(r"\s+", " ", event_str).strip()
                        except Exception:
                            pass

                        if not event_str or event_str == "EVENTO FCTV33":
                            continue
                        if not comp_str:
                            comp_str = detected_sport_label

                        query = parsed_url.query
                        if "icg=" not in query:
                            query = f"{query}&" if query else ""
                            query += "icg=RVM&ilang=es"
                        elif "ilang=" not in query:
                            query += "&ilang=es"
                        normalized_url = f"{parsed_url.scheme or 'https'}://{parsed_url.netloc}{parsed_url.path}?{query}"

                        if is_globally_excluded_event(comp_str, event_str):
                            continue
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
    "tv melilla", "tvg", "tv5monde", "uefa tv", "uefa youtube",
    "win sports tv youtube", "wta tv", "web directo", "zapping internacional",
    "a-leagues youtube", "liga u youtube", "marca youtube", "german football youtube", "l1 max youtube",
    "the afc hub youtube", "hc eivissa youtube", "vinxtv youtube",
    "valencia cf youtube", "valencia cf app", "à punt", "à punt mèdia", "osasuna tv",
    "fip - international padel federation youtube", "fip youtube",
    "cd tenerife youtube", "real betis balompié youtube", "real betis balompie youtube",
    "real betis tv", "real sociedad tv youtube"
}


def channel_exclusion_key(channel: str) -> str:
    base = re.sub(r"\([^)]*\)", "", normalize_search_text(channel))
    return re.sub(r"[^a-z0-9]+", "", base)


EXCLUDED_CHANNEL_KEYS = {channel_exclusion_key(c) for c in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = channel_exclusion_key(channel)
    if not key:
        return True
    if "movistargolf" in key:
        return True
    return key in EXCLUDED_CHANNEL_KEYS


def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r" real madrid ", r" rm castilla ", r" r\.?\s*madrid ")
CASTILLA_RE = rx(r" real madrid castilla ", r" rm castilla ", r" castilla ")
YOUTH_BASKET_RE = rx(r" sub\s*[-]?\d+ ", r" junior ", r" cadete ", r" infantil ")
SPAIN_SELECTION_RE = rx(r"\bspain\b", r"\bespaña\b", r"\bespana\b")

EXCLUDED_SPORTS_RE = rx(
    r" hockey ", r" nhl ", r" ahl ", r" khl ", r" patines ", r" nfl ", r" cowboys ", r" packers ",
    r" balonmano ", r" asobal ", r" handball ", r" waterpolo ", r" rugby ", r" rutby ", r" rucby ", r" rubgy ",
    r" ehf ", r" ihf ", r"\bfutsal\b", r"\bfutbol\s+sala\b", r"\bfs\b", r" golf ", r" beisbol ",
    r" padel ", r" padell ", r"\bgolf\b", r"\blpga\b", r"\bpga\s+tour\b", r"\bdp\s+world\s+tour\b"
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
GOLF_RE = rx(r"\bgolf\b", r"\blpga\b", r"\bpga\s+tour\b", r"\bdp\s+world\s+tour\b")
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


MOTOR_CONTEXT_RE = rx(
    r" formula 1 ", r" f1 ", r" f1 academy ", r" motogp ", r" formula e ", r" formula e ",
    r" indycar ", r" indy car ", r" motor ", r" automovilismo ", r" motociclismo ",
    r" g\.?\s*p\.?\s+", r" gran premio ", r" carrera ", r" clasificacion ", r" sprint ", r" libres "
)


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
        if BUNDESLIGA_RE.search(blob) and not BUNDESLIGA_2_RE.search(blob):
            is_fav = bool(REAL_MADRID_RE.search(blob) or SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized)
            return ("Fútbol", "⚽", "Bundesliga Femenina", is_fav, True, "", "other_football")
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(blob) or ("femenina" in blob and name.lower() in blob):
                comp_match = name
                break
        if comp_match and (REAL_MADRID_RE.search(blob) or SPAIN_SELECTION_RE.search(blob) or "espana" in blob_normalized):
            return ("Fútbol", "⚽", comp_match, True, True, "", "other_football")
        return ("", "", "", False, False, "", "")

    if BUNDESLIGA_2_RE.search(blob):
        return ("Fútbol", "⚽", "2. Bundesliga", False, True, "", "other_football")

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

    if BUNDESLIGA_RE.search(blob) and not BUNDESLIGA_2_RE.search(blob) and not WOMEN_RE.search(blob):
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
        comp_rfef = canonical_competition_name(raw_tournament) if raw_tournament else "PRIMERA FEDERACIÓN"
        is_castilla = bool(CASTILLA_RE.search(blob))
        return ("Fútbol", "⚽", comp_rfef, is_castilla, True, "", "other_football")

    return ("", "", "", False, False, "", "")


COMBAT_SPORT_RE = re.compile(
    r"\b(?:velada|boxeo|boxing|ufc|mma|artes\s+marciales|peso\s+(?:mosca|gallo|pluma|ligero|superligero|welter|superwelter|medio|supermedio|semipesado|pesado|crucero)|combat|fight|wrestling|wwe)\b",
    re.IGNORECASE,
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

    competition_terms = (
        "liga", "primera", "segunda", "tercera", "federacion", "division", "grupo", "torneo", "serie a",
        "endesa", "bundesliga", "atp", "wta", "masters", "copa", "champions", "superbike", "eredivisie", "euroliga", "euroleague", "nba", "portugal", "portuguesa",
        "mundial", "fifa", "uefa", "eurocopa", "nations league"
    )
    stage_lines_re = re.compile(
        r"^(?:liga\s+regular|regular\s+season|fase\s+regular|fase\s+de\s+grupos|octavos\s+de\s+final|cuartos\s+de\s+final|semifinales?|final|tercer\s+(?:y\s+cuarto\s+)?puesto|play[-\s]?offs?|jornada(?:\s+\d+)?|ronda(?:\s+\d+)?|ida|vuelta)$",
        re.IGNORECASE,
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

        has_dial_suffix = bool(re.search(r"\(\s*[mo]\+?\d+", part_lower))
        is_primera_federacion_comp_header = bool(re.fullmatch(r"primera\s+federaci[oó]n(?:\s*(?:[-–—]\s*)?grupo\s*\d+)?", part_lower))
        is_primera_federacion_channel = bool(re.match(r"^primera\s+federaci[oó]n\b", part_lower)) and (has_dial_suffix or len(text_lines) >= 2)
        is_laliga_competition = "laliga" in part_lower and not any(token in part_lower for token in (" tv", "m+", "movistar", "dazn"))
        is_tennis_tv_channel = bool(re.fullmatch(r"(?:atp|wta)\s+tennis\s+tv", part_lower))

        looks_like_channel = (
            is_primera_federacion_channel
            or (
                not is_primera_federacion_comp_header
                and (
                    is_tennis_tv_channel
                    or (TV_IDENTIFIERS_RE.search(part) and not is_laliga_competition)
                    or CHANNEL_LINE_RE.search(part_lower)
                    or any(term in part_lower for term in (
                        "m+", "dazn", "youtube", "fanatiz", "onefootball",
                        "siroko", "tv footballclub", "aragon tv", "aragon play",
                        "cmmplay", "etb1", "tvg", "tv3", "esport3", "hbo max", "ehf tv", "videopass", "prime video", "amazon", "à punt", "rcn", "beisbolplay", "app"
                    ))
                )
            )
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

    merged_text_lines = []
    idx_line = 0
    while idx_line < len(text_lines):
        curr_line = text_lines[idx_line]
        curr_norm = normalize_search_text(curr_line)
        if (
            curr_norm == "primera federacion"
            and idx_line + 1 < len(text_lines)
            and re.fullmatch(r"grupo\s*\d+", normalize_search_text(text_lines[idx_line + 1]))
        ):
            merged_text_lines.append(f"{curr_line} {text_lines[idx_line + 1]}")
            idx_line += 2
            continue
        merged_text_lines.append(curr_line)
        idx_line += 1
    text_lines = merged_text_lines

    tournament_candidates = []
    matchup_candidates = []
    for part in text_lines:
        part_lower = normalize_search_text(part)
        if stage_lines_re.fullmatch(part_lower):
            continue
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

    full_row_norm = normalize_search_text(f"{text_full} {tournament} {matchup}")
    if COMBAT_SPORT_RE.search(full_row_norm):
        return "", "", [], "", []

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

            tv_blob = " " + " ".join(channels).lower() + " "
            blob = " " + normalize_search_text(" ".join(text_lines) + " " + tournament + " " + tv_blob) + " "

            comp_name, motor_event_title, is_motor_fav = parse_motor_event(blob, tournament, text_lines)
            sport, icon, competition, is_favorite, is_configured, custom_event, comp_key = get_sport_and_competition(
                blob, tournament, tv_blob, text_lines
            )

            if COMBAT_SPORT_RE.search(blob):
                continue

            in_four_sports = bool(comp_name or sport)
            if not in_four_sports:
                if TENNIS_EVENT_RE.search(blob):
                    sport, icon, comp_key = "Tenis", "🎾", "tenis"
                    in_four_sports = True
                elif BASKET_CONTEXT_RE.search(blob) or NBA_RE.search(blob) or EUROLIGA_RE.search(blob):
                    sport, icon, comp_key = "Baloncesto", "🏀", "baloncesto"
                    in_four_sports = True
                elif MOTOR_CONTEXT_RE.search(blob):
                    continue
                else:
                    if not EXCLUDED_SPORTS_RE.search(blob) and not GOLF_RE.search(blob):
                        sport, icon, comp_key = "Fútbol", "⚽", "futbol"
                        in_four_sports = True

            if not in_four_sports:
                continue

            if comp_name:
                final_sport = "MOTOR"
                final_icon = "🏆"
                final_comp = comp_name.upper()
                final_event = motor_event_title.upper()
                final_fav = bool(is_motor_fav or is_favorite)
                final_comp_key = "motor"
            else:
                final_sport = sport.upper()
                final_icon = icon
                raw_comp = competition if competition else (tournament if tournament else sport)
                final_comp = canonical_competition_name(raw_comp).upper()
                raw_ev = custom_event if custom_event else event_str
                if raw_comp:
                    raw_ev = re.compile(re.escape(raw_comp), re.IGNORECASE).sub("", raw_ev)
                raw_ev = re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", raw_ev).strip()
                raw_ev = EVENT_CLEANUP_TRAIL_RE.sub("", raw_ev).strip()
                final_event = raw_ev.upper()
                final_fav = bool(is_favorite)
                final_comp_key = comp_key

            if not EVENT_TEXT_RE.search(final_event):
                continue

            if is_globally_excluded_event(final_comp, final_event):
                continue

            event_key = (current_date_obj, time_clean, normalize_search_text(final_comp), normalize_search_text(final_event))
            if event_key in seen_events:
                continue
            seen_events.add(event_key)

            futbolenlatv_results.append({
                "date_obj": current_date_obj,
                "hora": time_clean,
                "deporte": final_sport,
                "icono": final_icon,
                "competicion": final_comp,
                "evento": final_event,
                "tv_list": channels,
                "fctv_url": "",
                "is_filtered": final_fav,
                "is_configured": True,
                "comp_key": final_comp_key,
                "source": "futbolenlatv"
            })

    except Exception as e:
        print(f"Error cargando la agenda general: {e}")

    def event_similarity_key(x):
        comp_norm = normalize_search_text(x["competicion"])
        ev_norm = normalize_search_text(x["evento"])

        synonyms = {
            "euroleague": "euroliga",
            "national basketball association": "nba",
            "french ligue 1": "ligue 1",
            "spanish la liga": "laliga ea sports",
            "la liga ea sports": "laliga ea sports",
            "english premier league": "premier league",
            "italian serie a": "serie a",
            "liga asociacion de clubs de baloncesto": "liga endesa acb",
            "liga asociacion de clubes de baloncesto": "liga endesa acb",
            "liga endesa / acb": "liga endesa acb",
            "liga endesa": "liga endesa acb",
            "spanish primera division de la liga de futbol femenino": "liga f",
            "spanish primera division rfef": "espana - primera federacion",
            "uefa women's champions league": "uefa womens champions league",

            "ax olimpia milano": "milano",
            "gales": "wales",
            "northern ireland": "irlanda del norte",
            "olimpia milano": "milano",
            "paris basketball": "paris",
            "republica irlanda": "ireland",
            "rumania": "romania",
            "saski baskonia": "baskonia",
            "winterthur fc barcelona": "barcelona",
        }

        for k, v in synonyms.items():
            comp_norm = comp_norm.replace(k, v)
            ev_norm = ev_norm.replace(k, v)

        for w in [" vs ", " - ", "fc", "bc", "basket", "club", "mts", "red", "star"]:
            ev_norm = ev_norm.replace(w, " ")

        ev_core = " ".join(sorted(set([w for w in ev_norm.split() if len(w) > 2])))
        return (x["date_obj"], x["hora"], comp_norm, ev_core)

    futbolenlatv_results.sort(key=event_similarity_key)
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
        .events-stack { display: flex; flex-direction: column; gap: 8px; padding: 14px 16px; }

        .stg-event-card { display: flex; flex-direction: column; align-items: stretch; gap: 8px; padding: 10px 12px; background: var(--bg-color); border: 1px solid var(--border-color); border-radius: 8px; }
        .stg-event-card.previous-event { background: rgba(56, 189, 248, 0.075); border-color: rgba(56, 189, 248, 0.42); border-left: 3px solid #38bdf8; }
        .stg-event-card.previous-event .time-badge { background: #0369a1; box-shadow: 0 0 0 1px rgba(125, 211, 252, 0.35); }
        .stg-event-title::before { content: none; }
        .stg-event-card.previous-event .stg-event-title::before { content: "EN JUEGO"; display: block; color: #38bdf8; font-size: 0.62rem; font-weight: 800; letter-spacing: 0.65px; margin-bottom: 4px; }
        .stg-channels-row { display: flex; gap: 6px; flex-wrap: wrap; justify-content: flex-start; align-items: center; width: 100%; }

        .sport-tag { font-weight: 600; white-space: nowrap; color: #38bdf8; font-size: 0.82rem; }
        .comp-meta { color: var(--text-muted); font-size: 0.8rem; }
        .favorite-pin { display: inline-block; margin-right: 4px; color: #c4b5fd; font-size: 0.88rem; line-height: 1; vertical-align: 1px; }
        body.favorites-view .favorite-pin { display: none; }
        .date-badge { display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }
        .date-badge.today { background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }
        .time-badge { background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }
        .tv-badge { display: inline-block; background: rgba(56, 189, 248, 0.15); color: #38bdf8; border: 1px solid rgba(56, 189, 248, 0.3); padding: 4px 8px; border-radius: 6px; font-size: 0.72rem; font-weight: 600; white-space: nowrap; text-decoration: none; transition: all 0.2s ease; }
        .tv-badge.channel-chip-link { cursor: pointer; }
        .tv-badge.channel-chip-link:hover { background: rgba(56, 189, 248, 0.3); color: #fff; }
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
        .channel-action.disabled-ch { opacity: 0.55; cursor: default; color: var(--text-muted); border-color: var(--border-color); background: rgba(148, 163, 184, 0.08); }

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

            .table-card { margin-bottom: 60px; }
            .events-stack { padding: 10px 8px; }
            .channels-grid {
                grid-template-columns: 1fr !important;
                padding: 8px;
                gap: 6px;
            }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="sticky-panel" id="stickyPanel">
    <header>
        <div><h1><a href="https://daddylive.pk/" target="_blank" class="icon-link" title="Abrir DaddyLive HD">⚡</a> Agenda Deportiva</h1></div>
        <div class="header-controls">
            <button class="nav-tab-btn active" id="btn-view-futbolenlatv" onclick="switchView('futbolenlatv')">EVENTOS</button>
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
            <div class="stat-card active-card" id="card-favoritos" onclick="setFilter('favoritos')">
                <div><div class="lbl">Favoritos</div><div class="val" style="color:#a78bfa">0</div></div><div style="font-size:1.1rem">📌</div>
            </div>
            <div class="stat-card" id="card-madrugada" onclick="setFilter('madrugada')">
                <div><div class="lbl">00:00 - 06:59</div><div class="val" style="color:#60a5fa">0</div></div><div style="font-size:1.1rem">💤</div>
            </div>
            <div class="stat-card" id="card-manana" onclick="setFilter('manana')">
                <div><div class="lbl">07:00 - 12:59</div><div class="val" style="color:#fbbf24">0</div></div><div style="font-size:1.1rem">☀️</div>
            </div>
            <div class="stat-card" id="card-tarde" onclick="setFilter('tarde')">
                <div><div class="lbl">13:00 - 20:29</div><div class="val" style="color:#f97316">0</div></div><div style="font-size:1.1rem">🌇</div>
            </div>
            <div class="stat-card" id="card-noche" onclick="setFilter('noche')">
                <div><div class="lbl">20:30 - 23:59</div><div class="val" style="color:#a78bfa">0</div></div><div style="font-size:1.1rem">🌙</div>
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
                        <label><input type="checkbox" class="comp-chk" id="chk-futbol" value="futbol" checked onchange="handleSportChange('futbol')"> ⚽ FÚTBOL</label>
                        <label><input type="checkbox" class="comp-chk" id="chk-baloncesto" value="baloncesto" checked onchange="handleSportChange('baloncesto')"> 🏀 BALONCESTO</label>
                        <label><input type="checkbox" class="comp-chk" id="chk-tenis" value="tenis" checked onchange="handleSportChange('tenis')"> 🎾 TENIS</label>
                        <label><input type="checkbox" class="comp-chk" id="chk-motor" value="motor" checked onchange="handleSportChange('motor')"> 🏆 MOTOR</label>
                        <label><input type="checkbox" class="comp-chk" id="chk-todos" value="todos" checked onchange="handleSportChange('todos')"> TODOS</label>
                    </div>
                </div>
                <div style="display: flex; gap: 15px; align-items: center; flex-wrap: wrap;">
                    <div class="comp-checkboxes" style="display: flex; gap: 12px; align-items: center; flex-wrap: wrap;">
                        <label><input type="checkbox" class="source-chk" id="chk-futbolenlatv" value="futbolenlatv" checked onchange="applyFilters()"> FUTBOLENLATV</label>
                        <label><input type="checkbox" class="source-chk" id="chk-fctv33" value="fctv33" onchange="applyFilters()"> FCTV33</label>
                        <label><input type="checkbox" class="source-chk" id="chk-cdnlive" value="cdnlive" onchange="applyFilters()"> CDN LIVE</label>
                    </div>
                </div>
            </div>
        </div>

        <div class="search-wrapper" style="position: relative; margin-bottom: 12px;">
            <input type="text" id="agendaSearch" placeholder="Buscar por hora, competición o evento..." oninput="toggleClearBtn('agendaSearch', 'clearAgendaSearch'); applyFilters()" style="width: 100%; padding: 10px 36px 10px 14px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); font-size: 0.9rem;">
            <button type="button" id="clearAgendaSearch" onclick="clearSearchInput('agendaSearch', 'clearAgendaSearch', applyFilters)" title="Borrar búsqueda" style="display: none; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: var(--text-muted); font-size: 1rem; font-weight: 700; cursor: pointer; padding: 2px 6px; line-height: 1;">✕</button>
        </div>
    </div>

    <div id="channels-controls" style="display: none; margin-bottom: 10px;">
        <div class="search-wrapper" style="position: relative; margin-bottom: 8px;">
            <input type="text" id="channelSearch" placeholder="Buscar canal..." oninput="toggleClearBtn('channelSearch', 'clearChannelSearch'); filterChannels()" style="width: 100%; padding: 10px 36px 10px 14px; background: var(--card-bg); border: 1px solid var(--border-color); border-radius: 8px; color: var(--text-main); font-size: 0.9rem;">
            <button type="button" id="clearChannelSearch" onclick="clearSearchInput('channelSearch', 'clearChannelSearch', filterChannels)" title="Borrar búsqueda" style="display: none; position: absolute; right: 10px; top: 50%; transform: translateY(-50%); background: none; border: none; color: var(--text-muted); font-size: 1rem; font-weight: 700; cursor: pointer; padding: 2px 6px; line-height: 1;">✕</button>
        </div>
        <div style="display: flex; flex-wrap: wrap; gap: 4px; justify-content: center;">
            <button class="letter-btn active" data-mode="FAVORITOS" onclick="filterChannelsByLetter('FAVORITOS')">⭐ Favoritos</button>
            <button class="letter-btn" data-mode="Todos" onclick="filterChannelsByLetter('Todos')">Todos</button>
            <button class="letter-btn" data-mode="#" onclick="filterChannelsByLetter('#')">#</button>
            <button class="letter-btn" data-mode="A" onclick="filterChannelsByLetter('A')">A</button>
            <button class="letter-btn" data-mode="B" onclick="filterChannelsByLetter('B')">B</button>
            <button class="letter-btn" data-mode="C" onclick="filterChannelsByLetter('C')">C</button>
            <button class="letter-btn" data-mode="D" onclick="filterChannelsByLetter('D')">D</button>
            <button class="letter-btn" data-mode="E" onclick="filterChannelsByLetter('E')">E</button>
            <button class="letter-btn" data-mode="F" onclick="filterChannelsByLetter('F')">F</button>
            <button class="letter-btn" data-mode="G" onclick="filterChannelsByLetter('G')">G</button>
            <button class="letter-btn" data-mode="H" onclick="filterChannelsByLetter('H')">H</button>
            <button class="letter-btn" data-mode="I" onclick="filterChannelsByLetter('I')">I</button>
            <button class="letter-btn" data-mode="J" onclick="filterChannelsByLetter('J')">J</button>
            <button class="letter-btn" data-mode="K" onclick="filterChannelsByLetter('K')">K</button>
            <button class="letter-btn" data-mode="L" onclick="filterChannelsByLetter('L')">L</button>
            <button class="letter-btn" data-mode="M" onclick="filterChannelsByLetter('M')">M</button>
            <button class="letter-btn" data-mode="N" onclick="filterChannelsByLetter('N')">N</button>
            <button class="letter-btn" data-mode="O" onclick="filterChannelsByLetter('O')">O</button>
            <button class="letter-btn" data-mode="P" onclick="filterChannelsByLetter('P')">P</button>
            <button class="letter-btn" data-mode="Q" onclick="filterChannelsByLetter('Q')">Q</button>
            <button class="letter-btn" data-mode="R" onclick="filterChannelsByLetter('R')">R</button>
            <button class="letter-btn" data-mode="S" onclick="filterChannelsByLetter('S')">S</button>
            <button class="letter-btn" data-mode="T" onclick="filterChannelsByLetter('T')">T</button>
            <button class="letter-btn" data-mode="U" onclick="filterChannelsByLetter('U')">U</button>
            <button class="letter-btn" data-mode="V" onclick="filterChannelsByLetter('V')">V</button>
            <button class="letter-btn" data-mode="W" onclick="filterChannelsByLetter('W')">W</button>
            <button class="letter-btn" data-mode="X" onclick="filterChannelsByLetter('X')">X</button>
            <button class="letter-btn" data-mode="Y" onclick="filterChannelsByLetter('Y')">Y</button>
            <button class="letter-btn" data-mode="Z" onclick="filterChannelsByLetter('Z')">Z</button>
        </div>
    </div>
    </div>

    <div class="table-card" id="futbolenlatv-view-container">
        <div class="events-stack" id="futbolenlatvTable">
            {FUTBOLENLATV_ROWS_HTML}
        </div>
    </div>

    <div class="table-card" id="channels-view-container" style="display: none;">
        <div id="sportTvGuideEventsPanel" style="display: none; padding: 14px 16px;"></div>
        <div id="channelsGrid" class="channels-grid">
            <div class="empty-state">Cargando canales...</div>
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
const SPORT_TV_GUIDE_FAV_EVENTS = {SPORT_TV_GUIDE_EVENTS_JSON};
const EMBEDDED_CHANNELS = {EMBEDDED_CHANNELS_JSON};
let currentFilter = 'favoritos';
let currentActiveView = 'futbolenlatv';
let currentLetterFilter = 'FAVORITOS';
let allCatalogChannels = [];

function toggleClearBtn(inputId, btnId) {
    const inp = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    if (!inp || !btn) return;
    btn.style.display = inp.value.length > 0 ? 'block' : 'none';
}

function clearSearchInput(inputId, btnId, callback) {
    const inp = document.getElementById(inputId);
    const btn = document.getElementById(btnId);
    if (inp) {
        inp.value = '';
        inp.focus();
    }
    if (btn) btn.style.display = 'none';
    if (typeof callback === 'function') callback();
}

const AGENDA_CHANNEL_ALIASES = new Map([
  ['tennis channel', 'Tennis Channel HD US'],
  ['m+ laliga', 'LaLiga TV FHD UK'],
  ['m+ la liga', 'LaLiga TV FHD UK'],
  ['m. laliga', 'LaLiga TV FHD UK'],
  ['teledeporte', 'Teledeporte FHD'],
  ['m+ deportes', 'Movistar Deportes 1 FHD'],
  ['movistar deportes', 'Movistar Deportes 1 FHD'],
  ['dazn f1', 'DAZN F1 FHD'],
  ['dazn laliga', 'DAZN La Liga HD'],
  ['dazn eleven 1', 'DAZN 1 FHD PT'],
  ['dazn eleven 2', 'DAZN 2 FHD PT'],
  ['dazn eleven 3', 'DAZN 3 HD PT'],
  ['dazn eleven 4', 'DAZN 4 FHD PT'],
  ['dazn eleven 5', 'DAZN 5 FHD PT'],
  ['dazn eleven 6', 'DAZN 6 FHD PT'],
  ['sport tv +', 'Sport TV+ PT'],
  ['sport tv+', 'Sport TV+ PT'],
  ['sport tv 1', 'Sport TV 1 FHD PT'],
  ['sport tv 2', 'Sport TV 2 FHD PT'],
  ['sport tv 3', 'Sport TV 3 HD PT'],
  ['sport tv 4', 'Sport TV 4 HD PT'],
  ['sport tv 5', 'Sport TV 5 HD PT'],
  ['sport tv 6', 'Sport TV 6 FHD PT'],
  ['sky sports f1', 'Sky Sports F1 FHD UK'],
  ['sky sports tennis', 'Sky Sports Tennis FHD UK'],
  ['v sport motor', 'V Sport Motor SE'],
  ['espn deportes', 'ESPN Deportes US'],
  ['dazn 1 deutschland', 'DAZN 1 FHD DE'],
  ['dazn 2 deutschland', 'DAZN 2 FHD DE']
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
        .replace(/[|,;/]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function normalizeTimeQuery(rawQuery) {
    const q = (rawQuery || '').toLowerCase().trim();
    if (!q) return '';
    const exactTimeMatch = q.match(/^(\d{1,2}):(\d{2})$/);
    if (exactTimeMatch) {
        const hh = exactTimeMatch[1].padStart(2, '0');
        const mm = exactTimeMatch[2];
        return `${hh}:${mm}`;
    }
    const hourColonMatch = q.match(/^(\d{1,2}):$/);
    if (hourColonMatch) {
        return `${hourColonMatch[1].padStart(2, '0')}:`;
    }
    const colonMinMatch = q.match(/^:(\d{1,2})$/);
    if (colonMinMatch) {
        return `:${colonMinMatch[1]}`;
    }
    if (q === ':') {
        return ':';
    }
    if (/^\d{1,2}$/.test(q)) {
        return q;
    }
    return '';
}

function matchesTimeOrTextSearch(tr, rawQuery) {
    const trimmed = (rawQuery || '').trim();
    if (!trimmed) return true;

    const rowTime = (tr.getAttribute('data-time') || '').trim();
    const compText = cleanStr(tr.querySelector('.comp-meta')?.textContent || '');
    const eventText = cleanStr(tr.querySelector('.stg-event-title')?.textContent || '');
    const normQuery = cleanStr(trimmed);

    const timeNorm = normalizeTimeQuery(trimmed);
    if (timeNorm && rowTime) {
        if (/^\d{1,2}$/.test(timeNorm)) {
            const hh = rowTime.split(':')[0] || '';
            const mm = rowTime.split(':')[1] || '';
            if (
                hh === timeNorm.padStart(2, '0') ||
                hh.startsWith(timeNorm) ||
                String(parseInt(hh, 10)) === timeNorm ||
                mm.startsWith(timeNorm)
            ) {
                return true;
            }
        } else if (timeNorm.endsWith(':')) {
            const hhWanted = timeNorm.slice(0, -1).padStart(2, '0');
            if (rowTime.startsWith(`${hhWanted}:`)) return true;
        } else if (timeNorm.startsWith(':')) {
            if (timeNorm === ':') {
                if (rowTime.includes(':')) return true;
            } else {
                const mmWanted = timeNorm.slice(1);
                const mmActual = rowTime.split(':')[1] || '';
                if (mmActual.startsWith(mmWanted)) return true;
            }
        } else {
            if (rowTime === timeNorm || rowTime.startsWith(timeNorm)) return true;
        }
    }

    return compText.includes(normQuery) || eventText.includes(normQuery);
}

function updateStickyHeadingOffset() {
    const panel = document.getElementById('stickyPanel');
    if (!panel) return;
    document.documentElement.style.setProperty('--sticky-panel-height', panel.getBoundingClientRect().height + 'px');
}

function handleSourceChange(changedSource) {
    applyFilters();
}

function handleSportChange(changedSport) {
    if (currentFilter === 'favoritos') return;

    const chkFutbol = document.getElementById('chk-futbol');
    const chkBaloncesto = document.getElementById('chk-baloncesto');
    const chkTenis = document.getElementById('chk-tenis');
    const chkMotor = document.getElementById('chk-motor');
    const chkTodos = document.getElementById('chk-todos');

    const sportCheckboxes = [chkFutbol, chkBaloncesto, chkTenis, chkMotor];

    if (changedSport === 'todos') {
        const state = chkTodos.checked;
        sportCheckboxes.forEach(chk => chk.checked = state);
    } else {
        const allChecked = sportCheckboxes.every(chk => chk.checked);
        if (allChecked) {
            chkTodos.checked = true;
        } else {
            chkTodos.checked = false;
        }
    }
    applyFilters();
}

function setFilter(filterType) {
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

    const chkFutbolenlatv = document.getElementById('chk-futbolenlatv');
    const chkFctv = document.getElementById('chk-fctv33');
    const chkCdnlive = document.getElementById('chk-cdnlive');

    if (isFavView) {
        if (chkFutbolenlatv) {
            chkFutbolenlatv.checked = true;
            chkFutbolenlatv.disabled = true;
            chkFutbolenlatv.parentElement.style.opacity = '0.6';
            chkFutbolenlatv.parentElement.style.cursor = 'not-allowed';
        }
        if (chkFctv) {
            chkFctv.checked = false;
            chkFctv.disabled = true;
            chkFctv.parentElement.style.opacity = '0.6';
            chkFctv.parentElement.style.cursor = 'not-allowed';
        }
        if (chkCdnlive) {
            chkCdnlive.checked = false;
            chkCdnlive.disabled = true;
            chkCdnlive.parentElement.style.opacity = '0.6';
            chkCdnlive.parentElement.style.cursor = 'not-allowed';
        }
    } else {
        [chkFutbolenlatv, chkFctv, chkCdnlive].forEach(chk => {
            if (chk) {
                chk.checked = true;
                chk.disabled = false;
                chk.parentElement.style.opacity = '1';
                chk.parentElement.style.cursor = 'pointer';
            }
        });
    }

    applyFilters();
}

function getActiveSourcesSet() {
    const set = new Set();
    if (currentFilter === 'favoritos') {
        set.add('futbolenlatv');
        return set;
    }
    document.querySelectorAll('.source-chk:checked').forEach(chk => {
        set.add(cleanStr(chk.value));
    });
    return set;
}

function getActiveSportsSet() {
    const set = new Set();
    document.querySelectorAll('.comp-chk:checked').forEach(chk => {
        set.add(cleanStr(chk.value));
    });
    return set;
}

function updateStatsForActiveView() {
    if (currentActiveView === 'futbolenlatv') {
        const table = document.getElementById('futbolenlatvTable');
        if (!table) return;
        const trs = table.getElementsByClassName('stg-event-card');

        let favCount = 0;
        let madCount = 0;
        let manCount = 0;
        let tarCount = 0;
        let nocCount = 0;
        let proxCount = 0;

        const checkedSources = getActiveSourcesSet();
        const checkedSports = getActiveSportsSet();
        const allSourcesSet = new Set(['futbolenlatv', 'fctv33', 'cdnlive']);
        const allSportsSet = new Set(['futbol', 'baloncesto', 'tenis', 'motor', 'todos']);
        const rawSearchQuery = document.getElementById('agendaSearch')?.value || '';
        const isFavView = (currentFilter === 'favoritos');

        const slotSources = isFavView ? allSourcesSet : checkedSources;
        const slotSports = isFavView ? allSportsSet : checkedSports;

        for (let i = 0; i < trs.length; i++) {
            const tr = trs[i];
            if (tr.id === 'dynamicEmptyState') continue;
            const rowSlot = cleanStr(tr.getAttribute('data-slot'));
            const isFiltered = tr.getAttribute('data-filtered') === 'true';
            const source = cleanStr(tr.getAttribute('data-source'));
            const sport = cleanStr(tr.getAttribute('data-sport'));
            const rowDate = tr.getAttribute('data-date');
            const isToday = (rowDate === TODAY_DATE_STR);
            const matchesSearch = matchesTimeOrTextSearch(tr, rawSearchQuery);

            const matchesFavSource = checkedSources.has(source);
            const matchesFavSport = isFavView ? true : checkedSports.has(sport);
            if (isFiltered && matchesFavSource && matchesFavSport && matchesSearch) {
                favCount++;
            }

            const matchesSlotSource = slotSources.has(source);
            const matchesSlotSport = slotSports.has(sport);

            if (rowDate > TODAY_DATE_STR && matchesSlotSource && matchesSlotSport && matchesSearch) {
                proxCount++;
            }

            if (isToday && matchesSlotSource && matchesSlotSport && matchesSearch) {
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

    const futbolenlatvControls = document.getElementById('futbolenlatv-controls');
    const channelsControls = document.getElementById('channels-controls');

    if (btnFutbolenlatv) btnFutbolenlatv.classList.remove('active');
    if (btnChannels) btnChannels.classList.remove('active');

    futbolenlatvContainer.style.display = 'none';
    channelsContainer.style.display = 'none';
    futbolenlatvControls.style.display = 'none';
    channelsControls.style.display = 'none';

    if (viewName === 'futbolenlatv') {
        if (btnFutbolenlatv) btnFutbolenlatv.classList.add('active');
        futbolenlatvContainer.style.display = 'block';
        futbolenlatvControls.style.display = 'block';
        setFilter('favoritos');
    } else if (viewName === 'channels') {
        if (btnChannels) btnChannels.classList.add('active');
        channelsContainer.style.display = 'block';
        channelsControls.style.display = 'block';
        currentLetterFilter = 'FAVORITOS';
        document.querySelectorAll('.letter-btn').forEach(btn => {
            btn.classList.toggle('active', (btn.getAttribute('data-mode') || btn.textContent.trim()) === 'FAVORITOS');
        });
        loadChannelsCatalog();
    }
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
    } catch (e) {
        allCatalogChannels = [];
    }

    if (!Array.isArray(allCatalogChannels) || allCatalogChannels.length === 0) {
        allCatalogChannels = Array.isArray(EMBEDDED_CHANNELS) ? EMBEDDED_CHANNELS : [];
    }

    allCatalogChannels.sort((a, b) => {
        const nameA = (a.name || '').trim();
        const nameB = (b.name || '').trim();
        return nameA.localeCompare(nameB, 'es', { sensitivity: 'accent', numeric: true });
    });

    filterChannels();
    linkAgendaChannelsToCdn();
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
        .replace(/\b(hd|fhd|sd|hevc|4k|us|uk|pt|es|fr|it|de)\b/g, '')
        .replace(/[^a-z0-9]/g, '')
        .trim();
}

function cleanSportTvGuideChannelLabel(rawName) {
    return String(rawName || '')
        .replace(/\[\s*\]/g, '')
        .replace(/\s+/g, ' ')
        .trim();
}

function resolveMappedFavoriteName(channelName, countryHint = '') {
    const cleanKey = cleanStr(cleanSportTvGuideChannelLabel(channelName));
    const countryUpper = String(countryHint || '').toUpperCase().trim();

    if (cleanKey === 'sky sport tennis' || cleanKey === 'sky sports tennis') {
        return countryUpper === 'DE' ? 'Sky Sport Tennis FHD DE' : 'Sky Sports Tennis FHD UK';
    }

    if (AGENDA_CHANNEL_ALIASES.has(cleanKey)) {
        return AGENDA_CHANNEL_ALIASES.get(cleanKey);
    }
    return null;
}

function findCatalogChannel(channelName, countryHint = '') {
    const mappedName = resolveMappedFavoriteName(channelName, countryHint);
    const targetName = mappedName || channelName;
    const wanted = normalizeChannelName(targetName);
    if (!wanted) return null;

    if (mappedName) {
        const directMapped = allCatalogChannels.find(ch =>
            cleanStr(ch.name) === cleanStr(mappedName) || normalizeChannelName(ch.name) === wanted
        );
        if (directMapped) return directMapped;
    }

    const hintLower = String(countryHint || '').toLowerCase().trim();
    if (hintLower) {
        const exactWithCountry = allCatalogChannels.find(ch => {
            const rawLower = String(ch.name || '').toLowerCase();
            return normalizeChannelName(ch.name) === wanted && rawLower.includes(` ${hintLower}`);
        });
        if (exactWithCountry) return exactWithCountry;
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

function safePlayerUrl(ch) {
    if (!ch) return null;
    const raw = String(ch.player_url || ch.url || '').trim();
    if (!raw) return null;
    try {
        const u = new URL(raw);
        if (u.protocol !== 'https:' || !['cdnlivetv.tv', 'www.cdnlivetv.tv'].includes(u.hostname)) {
            return null;
        }
        return u.href;
    } catch (_) {
        return null;
    }
}

function linkAgendaChannelsToCdn() {
    document.querySelectorAll('#futbolenlatvTable .stg-cdn-channel').forEach(btn => {
        const rawName = cleanSportTvGuideChannelLabel(btn.getAttribute('data-ch-name') || '');
        const countryHint = String(btn.getAttribute('data-ch-country') || '').trim();
        const mappedName = resolveMappedFavoriteName(rawName, countryHint);
        const catalogCh = findCatalogChannel(rawName, countryHint);
        const playerUrl = catalogCh ? safePlayerUrl(catalogCh) : null;
        const displayLabel = catalogCh?.name || mappedName || rawName;

        btn.textContent = '▶ ' + displayLabel;
        btn.onclick = (e) => {
            e.preventDefault();
            openPlayerModal(displayLabel, playerUrl || '');
        };
    });

    document.querySelectorAll('#futbolenlatvTable .stg-event-card').forEach(row => {
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
        if (textContent.includes('FCTV33')) return;

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

function computeMadridEventTimestamp(dateIso, timeStr) {
    if (!dateIso || !timeStr || timeStr === 'LIVE') return null;
    const match = String(timeStr).match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return null;
    const [y, m, d] = String(dateIso).split('-').map(Number);
    if (!y || !m || !d) return null;
    const hh = Number(match[1]);
    const mm = Number(match[2]);

    const utcGuess = new Date(Date.UTC(y, m - 1, d, hh, mm, 0));
    const parts = new Intl.DateTimeFormat('en-CA', {
        timeZone: 'Europe/Madrid',
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
    }).formatToParts(utcGuess);
    const map = {};
    for (const p of parts) {
        if (p.type !== 'literal') map[p.type] = p.value;
    }
    const madridAsUtc = Date.UTC(
        Number(map.year),
        Number(map.month) - 1,
        Number(map.day),
        Number(map.hour),
        Number(map.minute),
        Number(map.second)
    );
    const offsetMs = madridAsUtc - utcGuess.getTime();
    return utcGuess.getTime() - offsetMs;
}

function isEventInPlay(dateIso, timestamp, nowMs = Date.now()) {
    const TWO_HOURS_MS = 2 * 3600 * 1000;
    if (dateIso !== TODAY_DATE_STR) return false;
    return Number.isFinite(timestamp) && timestamp <= nowMs && (nowMs - timestamp) <= TWO_HOURS_MS;
}

function highlightSportTvGuideLiveEvents() {
    const now = Date.now();
    document.querySelectorAll('#sportTvGuideEventsPanel .stg-event-card[data-ts]').forEach(card => {
        const dateIso = card.getAttribute('data-date') || '';
        const ts = Number(card.getAttribute('data-ts'));
        if (isEventInPlay(dateIso, ts, now)) {
            card.classList.add('previous-event');
        } else {
            card.classList.remove('previous-event');
        }
    });
}

function scrollToSportTvGuideTargetEvent() {
    if (currentActiveView !== 'channels' || currentLetterFilter !== 'EVENTOS') return;
    const panel = document.getElementById('sportTvGuideEventsPanel');
    if (!panel || panel.style.display === 'none') return;

    const cards = Array.from(panel.querySelectorAll('.stg-event-card'));
    if (cards.length === 0) return;

    const liveCard = cards.find(card => card.classList.contains('previous-event'));
    if (!liveCard) return;

    const stickyPanel = document.getElementById('stickyPanel');
    const stickyOffset = stickyPanel ? stickyPanel.getBoundingClientRect().height + 12 : 12;
    const cardTop = liveCard.getBoundingClientRect().top + window.scrollY;
    const targetScrollTop = Math.max(0, cardTop - stickyOffset);

    window.scrollTo({
        top: targetScrollTop,
        behavior: 'smooth'
    });
}

function renderSportTvGuideEventsView() {
    const panel = document.getElementById('sportTvGuideEventsPanel');
    const grid = document.getElementById('channelsGrid');
    if (!panel || !grid) return;

    if (currentLetterFilter !== 'EVENTOS') {
        panel.style.display = 'none';
        panel.innerHTML = '';
        grid.style.display = 'grid';
        return;
    }

    grid.style.display = 'none';
    panel.style.display = 'block';

    const query = cleanStr(document.getElementById('channelSearch')?.value || '');
    const sortedEvents = [...(Array.isArray(SPORT_TV_GUIDE_FAV_EVENTS) ? SPORT_TV_GUIDE_FAV_EVENTS : [])].sort((a, b) => {
        const cmpDate = String(a.date_iso || '').localeCompare(String(b.date_iso || ''));
        if (cmpDate !== 0) return cmpDate;
        return String(a.hora || '').localeCompare(String(b.hora || ''));
    });

    const filteredEvents = sortedEvents.filter(ev => {
        if (!query) return true;
        const chNames = (ev.canales || []).map(c => c.name || '').join(' ');
        const haystack = cleanStr(`${ev.fecha_label || ''} ${ev.hora || ''} ${ev.deporte || ''} ${ev.competicion || ''} ${ev.evento || ''} ${chNames}`);
        return haystack.includes(query);
    });

    if (filteredEvents.length === 0) {
        panel.innerHTML = '<div class="empty-state">😴 No hay eventos disponibles en Sport TV Guide.</div>';
        return;
    }

    const nowMs = Date.now();

    panel.innerHTML = `
        <div style="display: flex; flex-direction: column; gap: 8px;">
            ${filteredEvents.map(ev => {
                const seenLabels = new Set();
                const channelButtons = (ev.canales || []).map(chObj => {
                    const chName = cleanSportTvGuideChannelLabel(chObj.name);
                    if (!chName) return '';

                    const chCountry = String(chObj.country || '').trim();
                    const mappedName = resolveMappedFavoriteName(chName, chCountry);
                    const catalogCh = findCatalogChannel(chName, chCountry);
                    const playerUrl = catalogCh ? safePlayerUrl(catalogCh) : null;
                    const displayLabel = catalogCh?.name || mappedName || chName;

                    const dedupKey = cleanStr(displayLabel);
                    if (seenLabels.has(dedupKey)) return '';
                    seenLabels.add(dedupKey);

                    const safeTitle = displayLabel.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '&quot;');
                    const safeUrlArg = playerUrl ? playerUrl.replace(/\\/g, '\\\\').replace(/'/g, "\\'") : '';

                    return `<a href="#reproductor" class="channel-action" onclick="event.preventDefault(); openPlayerModal('${safeTitle}', '${safeUrlArg}')">▶ ${displayLabel}</a>`;
                }).filter(Boolean).join('');

                const evTs = Number.isFinite(Number(ev.ts))
                    ? Number(ev.ts)
                    : computeMadridEventTimestamp(ev.date_iso, ev.hora);
                const liveClass = isEventInPlay(ev.date_iso, evTs, nowMs) ? ' previous-event' : '';

                return `
                    <div class="stg-event-card${liveClass}" data-date="${ev.date_iso || ''}" data-ts="${Number.isFinite(evTs) ? evTs : ''}">
                        <div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">
                            <span class="date-badge ${ev.fecha_label === 'Hoy' ? 'today' : ''}">${ev.fecha_label || 'Hoy'}</span>
                            <span class="time-badge">${ev.hora}</span>
                            <span class="sport-tag" style="color: #38bdf8; font-size: 0.82rem;">${ev.icono || ''} ${ev.deporte || ''}</span>
                            ${ev.competicion ? `<span style="color: var(--text-muted); font-size: 0.8rem;">(${ev.competicion})</span>` : ''}
                            <strong class="stg-event-title" style="color: #fff; font-size: 0.9rem;">${ev.evento}</strong>
                        </div>
                        <div class="stg-channels-row">
                            ${channelButtons}
                        </div>
                    </div>
                `;
            }).join('')}
        </div>
    `;

    scrollToSportTvGuideTargetEvent();
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
                    ${playable ? `<a href="#reproductor" class="channel-action" onclick="event.preventDefault(); openPlayerModal('${ch.name.replace(/'/g, "\\'")}', '${url}')">▶ Ver</a>` : '<span style="font-size:0.7rem; color:var(--text-muted)">No disponible</span>'}
                </div>
            </div>
        `;
    }).join('');
}

function filterChannelsByLetter(mode) {
    currentLetterFilter = mode;
    document.querySelectorAll('.letter-btn').forEach(btn => {
        btn.classList.toggle('active', (btn.getAttribute('data-mode') || btn.textContent.trim()) === mode);
    });
    filterChannels();
}

function filterChannels() {
    const panel = document.getElementById('sportTvGuideEventsPanel');
    const grid = document.getElementById('channelsGrid');
    if (panel) {
        panel.style.display = 'none';
        panel.innerHTML = '';
    }
    if (grid) {
        grid.style.display = 'grid';
    }

    const query = (document.getElementById('channelSearch')?.value || '').toLowerCase();
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
                matchesLetter = /^[^A-Z]/i.test(firstChar);
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
    const validUrl = safePlayerUrl({ url });
    if (!validUrl) {
        document.getElementById('player-content').innerHTML =
            `<div style="display:flex;height:100%;align-items:center;justify-content:center;padding:20px;text-align:center;color:#94a3b8;">No hay URL válida en channels.json para <strong>${name}</strong>.</div>`;
    } else {
        document.getElementById('player-content').innerHTML =
            `<iframe src="${validUrl}" style="width:100%; height:100%; border:none;" allowfullscreen></iframe>`;
    }
    document.getElementById('player-dialog').showModal();
}

function closePlayerModal() {
    const dialog = document.getElementById('player-dialog');
    document.getElementById('player-content').innerHTML = '';
    dialog.close();
}

function highlightPreviousEvents() {
    const now = Date.now();
    const rows = Array.from(document.querySelectorAll('#futbolenlatvTable .stg-event-card[data-ts]'));

    rows.forEach(row => {
        const dateIso = row.getAttribute('data-date') || '';
        const timestamp = Number(row.getAttribute('data-ts'));
        if (isEventInPlay(dateIso, timestamp, now)) {
            row.classList.add('previous-event');
        } else {
            row.classList.remove('previous-event');
        }
    });

    highlightSportTvGuideLiveEvents();
}

function scrollToTargetEvent() {
    const table = document.getElementById('futbolenlatvTable');
    if (!table) return;
    const visibleRows = Array.from(table.getElementsByClassName('stg-event-card')).filter(r => r.style.display !== 'none');
    if (visibleRows.length === 0) return;

    let targetRow = visibleRows.find(r => r.classList.contains('previous-event'));

    if (!targetRow) {
        const now = Date.now();
        targetRow = visibleRows.find(r => {
            const ts = Number(r.getAttribute('data-ts'));
            return Number.isFinite(ts) && ts > now;
        });
    }

    if (!targetRow) {
        targetRow = visibleRows[visibleRows.length - 1];
    }

    if (targetRow) {
        targetRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
}

window.addEventListener('load', async () => {
    await initApp();
    highlightPreviousEvents();
    setInterval(highlightPreviousEvents, 60000);
    setFilter('favoritos');
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
        const checkedSources = getActiveSourcesSet();
        const checkedSports = getActiveSportsSet();

        const table = document.getElementById('futbolenlatvTable');
        if (!table) return;
        const trs = table.getElementsByClassName('stg-event-card');
        let visibleCount = 0;

        for (let i = 0; i < trs.length; i++) {
            const tr = trs[i];
            if (tr.id === 'dynamicEmptyState') continue;

            const rowSlot = cleanStr(tr.getAttribute('data-slot'));
            const isFiltered = tr.getAttribute('data-filtered') === 'true';
            const source = cleanStr(tr.getAttribute('data-source'));
            const sport = cleanStr(tr.getAttribute('data-sport'));
            const rowDate = tr.getAttribute('data-date');

            let matchesFilter = false;
            let matchesSource = checkedSources.has(source);
            let matchesSport = (currentFilter === 'favoritos') ? true : checkedSports.has(sport);
            const rawSearchQuery = document.getElementById('agendaSearch')?.value || '';
            const matchesSearch = matchesTimeOrTextSearch(tr, rawSearchQuery);

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
                emptyRow = document.createElement('div');
                emptyRow.id = 'dynamicEmptyState';
                emptyRow.className = 'empty-state';
                emptyRow.textContent = '😴 No hay eventos que coincidan con la selección.';
                table.appendChild(emptyRow);
            } else { emptyRow.style.display = ''; }
        } else {
            if (emptyRow) emptyRow.style.display = 'none';
            scrollToTargetEvent();
        }
    }
}
</script>
</body>
</html>
"""


def generate_html(futbolenlatv_events, sport_tv_guide_events=None):
    spain_tz = get_spain_timezone()
    today_date = datetime.now(spain_tz).date()
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")

    unified_events = list(futbolenlatv_events or [])
    for stg in (sport_tv_guide_events or []):
        try:
            ev_d = date.fromisoformat(str(stg.get("date_iso", "")))
        except ValueError:
            ev_d = today_date
        sport_up = str(stg.get("deporte", "")).upper()
        comp_key_map = {
            "FÚTBOL": "futbol",
            "BALONCESTO": "baloncesto",
            "TENIS": "tenis",
            "MOTOR": "motor",
        }
        if is_globally_excluded_event(canonical_competition_name(stg.get("competicion", "")), str(stg.get("evento", ""))):
            continue
        unified_events.append({
            "date_obj": ev_d,
            "hora": str(stg.get("hora", "")),
            "deporte": sport_up,
            "icono": str(stg.get("icono", "")),
            "competicion": canonical_competition_name(stg.get("competicion", "")).upper(),
            "evento": str(stg.get("evento", "")).upper(),
            "tv_list": [str(c.get("name", "")) for c in (stg.get("canales") or []) if c.get("name")],
            "stg_channels": stg.get("canales") or [],
            "fctv_url": "",
            "is_filtered": False,
            "is_configured": True,
            "comp_key": comp_key_map.get(sport_up, ""),
            "source": "cdnlive",
        })

    unified_events.sort(
        key=lambda x: (
            x["date_obj"],
            x["hora"],
            normalize_search_text(x["competicion"]),
            normalize_search_text(x["evento"]),
        )
    )
    futbolenlatv_events = unified_events

    slot_counts = Counter(
        get_time_slot(event["hora"])
        for event in futbolenlatv_events
        if event["date_obj"] == today_date
    )
    total_cnt = sum(1 for event in futbolenlatv_events if event["date_obj"] > today_date)

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not futbolenlatv_events:
        rows_list.append(
            '<div class="empty-state">😴 No hay eventos disponibles en este momento.</div>'
        )
    else:
        for ev in futbolenlatv_events:
            tv_badges_list = []
            if ev.get("source") == "cdnlive":
                for ch_obj in ev.get("stg_channels", []):
                    raw_ch_name = str(ch_obj.get("name", "")).strip()
                    raw_ch_country = str(ch_obj.get("country", "")).strip()
                    if not raw_ch_name:
                        continue
                    safe_ch_name = escape(raw_ch_name, quote=True)
                    safe_ch_country = escape(raw_ch_country, quote=True)
                    tv_badges_list.append(
                        f'<a href="#reproductor" class="channel-action stg-cdn-channel" data-ch-name="{safe_ch_name}" data-ch-country="{safe_ch_country}">▶ {safe_ch_name}</a>'
                    )
            else:
                for channel in ev["tv_list"]:
                    safe_channel = escape(str(channel), quote=True)
                    tv_badges_list.append(
                        f'<span class="tv-badge" title="Canal {safe_channel}">{safe_channel}</span>'
                    )

            if ev.get("fctv_url"):
                fctv_safe_url = escape(ev["fctv_url"], quote=True)
                tv_badges_list.append(
                    f'<a href="{fctv_safe_url}" target="_blank" class="channel-action" title="Ver en FCTV33">▶ FCTV33</a>'
                )

            tv_badges = "".join(tv_badges_list)

            ev_date = ev["date_obj"]
            if ev_date == today_date:
                date_badge_html = '<span class="date-badge today">Hoy</span>'
            else:
                date_badge_html = f'<span class="date-badge">{ev_date.strftime("%d/%m")}</span>'

            slot = get_time_slot(ev["hora"])
            safe_slot = escape(clean_key(slot), quote=True)

            search_text = normalize_search_text(
                " ".join(
                    [str(ev_date), ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
                )
            )
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

            comp_html = (
                f'<span class="comp-meta">({safe_competition})</span>'
                if safe_competition else ""
            )

            rows_list.append(
                f'<div class="stg-event-card" data-date="{safe_date_str}" data-ts="{safe_timestamp}" data-time="{escape(str(ev["hora"]))}" data-slot="{safe_slot}" data-sport="{safe_sport_key}" data-source="{safe_source}" data-comp-key="{safe_comp_key}" data-filtered="{is_filtered_str}" data-configured="{is_configured_str}" data-search="{safe_search}">'
                f'<div style="display: flex; align-items: center; gap: 8px; flex-wrap: wrap;">'
                f'{date_badge_html}'
                f'{safe_time}'
                f'<span class="sport-tag">{safe_icon} {safe_sport}</span>'
                f'{comp_html}'
                f'<strong class="stg-event-title" style="color: #fff; font-size: 0.9rem;">{safe_event}</strong>'
                f'</div>'
                f'<div class="stg-channels-row">{tv_badges}</div>'
                f'</div>'
            )

    futbolenlatv_rows_html = "".join(rows_list)
    safe_stg_json = json.dumps(sport_tv_guide_events or [], ensure_ascii=False).replace("</", "<\\/")

    embedded_channels = []
    try:
        if os.path.exists("channels.json"):
            with open("channels.json", "r", encoding="utf-8") as f:
                raw_ch = json.load(f)
            if isinstance(raw_ch, list):
                embedded_channels = raw_ch
            elif isinstance(raw_ch, dict):
                embedded_channels = (
                    raw_ch.get("channels")
                    or raw_ch.get("data", {}).get("channels")
                    or raw_ch.get("data")
                    or []
                )
    except Exception:
        embedded_channels = []

    safe_channels_json = json.dumps(embedded_channels, ensure_ascii=False).replace("</", "<\\/")

    html = HTML_TEMPLATE.replace("{FECHA_ACT}", fecha_act)
    html = html.replace("{MADRUGADA_CNT}", str(slot_counts["madrugada"]))
    html = html.replace("{MANANA_CNT}", str(slot_counts["manana"]))
    html = html.replace("{TARDE_CNT}", str(slot_counts["tarde"]))
    html = html.replace("{NOCHE_CNT}", str(slot_counts["noche"]))
    html = html.replace("{TOTAL_CNT}", str(total_cnt))
    html = html.replace("{TODAY_DATE_STR}", today_date.isoformat())
    html = html.replace("{FUTBOLENLATV_ROWS_HTML}", futbolenlatv_rows_html)
    html = html.replace("{SPORT_TV_GUIDE_EVENTS_JSON}", safe_stg_json)
    html = html.replace("{EMBEDDED_CHANNELS_JSON}", safe_channels_json)
    return html


if __name__ == "__main__":
    update_channels_json_from_api()
    agenda_events = fetch_and_parse_agenda()
    stg_events = fetch_sport_tv_guide_favorite_events()
    final_html = generate_html(agenda_events, stg_events)
    with open("index.html", "w", encoding="utf-8") as out_f:
        out_f.write(final_html)
    print("index.html generado correctamente.")