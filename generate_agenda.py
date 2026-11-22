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


def is_allowed_competition_name(sport_upper: str, comp_norm: str) -> bool:
    """Valida que la competición normalizada pertenezca explícitamente a las permitidas por deporte."""
    if not comp_norm:
        return False
    if sport_upper == "MOTOR":
        return comp_norm in {"formula 1", "motogp", "formula e", "indycar"}
    if sport_upper == "TENIS":
        if any(bad in comp_norm for bad in ("padel", "hockey", "golf", "basketball", "baloncesto", "futbol", "football")):
            return False
        return True
    if sport_upper == "BALONCESTO":
        return comp_norm in {"nba", "euroliga", "liga endesa / acb"}
    if sport_upper == "FÚTBOL":
        allowed_football = {
            "laliga ea sports",
            "premier league",
            "serie a",
            "bundesliga",
            "ligue 1",
            "eredivisie",
            "liga portugal betclic",
            "uefa champions league",
            "copa del rey",
            "copa mundial de la fifa",
            "eurocopa",
            "uefa nations league",
            "liga f",
            "copa de la reina",
            "supercopa de espana femenina",
            "uefa women's champions league",
            "uefa womens champions league",
            "espana - primera federacion",
        }
        return comp_norm in allowed_football
    return False


def _has_non_english_league_qualifier(norm_text: str) -> bool:
    """Detecta calificadores de país/región/división no permitidos (p. ej. bolivian, armenian, russian, bosnia, etc.)."""
    disallowed_prefixes = (
        "bolivian ", "bolivia ", "armenian ", "armenia ",
        "russian ", "russia ", "bosnia ", "bosnian ", "herzegovina ",
        "serbian ", "serbia ", "croatian ", "croatia ", "bulgarian ", "bulgaria ",
        "romanian ", "romania ", "polish ", "poland ", "ukrainian ", "ukraine ",
        "greek ", "greece ", "turkish ", "turkey ", "czech ", "hungarian ", "hungary ",
        "austrian ", "austria ", "swiss ", "belgian ", "belgium ", "scottish ", "scotland ",
        "welsh ", "wales ", "irish ", "ireland ", "northern ireland ",
        "danish ", "denmark ", "swedish ", "sweden ", "norwegian ", "norway ",
        "finnish ", "finland ", "icelandic ", "iceland ",
        "mexican ", "mexico ", "liga mx ", "colombian ", "colombia ",
        "chilean ", "chile ", "peruvian ", "peru ", "uruguayan ", "uruguay ",
        "paraguayan ", "paraguay ", "ecuadorian ", "ecuador ", "venezuelan ", "venezuela ",
        "brazilian ", "brasil ", "argentine ", "argentina ", "mls ", "major league soccer",
        "saudi ", "arabia ", "qatar ", "chinese ", "china ", "japanese ", "japan ",
        "korean ", "korea ", "australian ", "australia ", "indian ", "india ",
        "egyptian ", "egypt ", "moroccan ", "morocco ", "tunisian ", "tunisia ",
        "algerian ", "algeria ", "south african ", "south africa ",
    )
    return any(norm_text.startswith(p) or f" {p}" in norm_text for p in disallowed_prefixes)


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

    comp_norm_check = normalize_search_text(raw_comp)
    if _has_non_english_league_qualifier(comp_norm_check):
        return (False, False, "", "", "", "", "")

    blob = normalize_search_text(f"{raw_comp} {raw_ev} {' '.join(lines)}")

    sport_up = str(sport_label or "").strip().upper()
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
        m_comp_label = normalize_competition_label(comp_name)
        if not is_allowed_competition_name("MOTOR", normalize_search_text(m_comp_label)):
            return (False, False, "", "", "", "", "")
        return (
            True,
            bool(is_fav),
            "MOTOR",
            "🏆",
            m_comp_label,
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
    if _has_non_english_league_qualifier(norm_comp):
        return (False, False, "", "", "", "", "")

    sp_up = sport.upper()
    if not is_allowed_competition_name(sp_up, norm_comp):
        return (False, False, "", "", "", "", "")

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
        sp_up,
        icon,
        comp_label,
        final_ev.upper(),
        comp_key,
    )


def _extract_stg_slug_info(href: str) -> tuple[str, str]:
    """Extrae el segmento de competición y el slug del evento desde una URL de sport-tv-guide.live."""
    raw = str(href or "").strip()
    if not raw:
        return ("", "")
    parsed = urlparse(raw)
    path = (parsed.path or "").strip("/")
    m = re.search(r"(?:^|/)en-vivo-([a-z0-9-]+?)(?:/\d+/?$|$)", path, flags=re.IGNORECASE)
    if m:
        slug_body = m.group(1).lower()
        return (slug_body, slug_body)
    return ("", path.lower())


def fetch_sport_tv_guide_favorite_events() -> list[dict]:
    """Inicia sesión en sport-tv-guide.live y extrae los eventos permitidos según las reglas de FUTBOLENLATV."""
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
                                const evLink = el.querySelector('a[href*="/event/"], a[href*="en-vivo-"]');
                                const eventHref = evLink ? (evLink.getAttribute('href') || '') : '';

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
                                    eventHref,
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
                        evento_raw = re.sub(r"[\s\u00a0\u200b\ufeff]+", " ", str(item.get("evento", ""))).strip()
                        competicion_raw = re.sub(r"[\s\u00a0\u200b\ufeff]+", " ", str(item.get("competicion", ""))).strip()
                        event_href = str(item.get("eventHref", "")).strip()
                        canales = item.get("canales") or []

                        if not hora or not evento_raw or not canales:
                            continue

                        _, slug_body = _extract_stg_slug_info(event_href)
                        comp_for_check = competicion_raw
                        if sport_key == "futbol" and slug_body:
                            if "premier-league" in slug_body and normalize_search_text(competicion_raw) not in {"", "premier league", "inglaterra - premier league"}:
                                continue
                            if not comp_for_check and "premier-league" in slug_body:
                                comp_for_check = "Premier League"

                        allowed, is_fav, final_sport, final_icon, final_comp, final_event, comp_key = is_event_allowed_by_futbolenlatv_rules(
                            sport_label=sport_label,
                            competition_label=comp_for_check,
                            event_title=evento_raw,
                            raw_lines=[evento_raw, comp_for_check],
                        )
                        if not allowed:
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

                        dedup_key = (ev_date.isoformat(), hora, normalize_search_text(final_comp), normalize_search_text(final_event))
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
                            "deporte": final_sport,
                            "icono": final_icon,
                            "competicion": final_comp,
                            "evento": final_event,
                            "comp_key": comp_key,
                            "is_filtered": bool(is_fav),
                            "canales": canales,
                        })
                        sport_count += 1

                    print(f"   -> [{sport_label}] Eventos permitidos extraídos de sport-tv-guide.live: {sport_count}")
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
    r" padel ", r" padell ",
    r" badminton ", r" bwf ", r" cricket ", r" t20 ", r" list a ", r" emerging teams ",
    r" snooker ", r" darts ", r" dardos ", r" boxing ", r" ufc ", r" mma "
)

EXCLUDED_COMPETITIONS_RE = rx(
    r" national league ", r" vanarama national league ", r" liga u ",
    r" tercera ", r" 3[ªa]\s*(?:rfef|federacion|division|grupo) ", r" grupo 8 ", r" tercera federacion ",
    r" basketball champions league ", r" futsal champions ",
    r" 2\.?\s*bundesliga ", r" serie a femminile ",
    r" laliga hypermotion ", r" segunda division ", r" hypermotion ",
    r" brasil\s*[-–—]?\s*serie\s+a ",
    r" argentina ", r" torneo clausura ", r" torneo apertura ",
    r" liga profesional ", r" primera division argentina ",
    r" international cup ", r" eurocup ",
    r" hong kong open ", r" international league t20 ", r" emerging teams asia cup "
)

SPANISH_TENNIS_PLAYERS_RE = rx(
    r" carlos alcaraz ", r" alcaraz ", r" alejandro davidovich ", r" davidovich ",
    r" cristina bucsa ", r" bucsa ", r" paula badosa ", r" badosa ",
    r" jaume munar ", r" munar ", r" rafael jodar ", r" jodar ",
    r" dani merida ", r" merida "
)

WTA_RE = re.compile(r" wta ", re.IGNORECASE)
WOMEN_RE = rx(r" femenina ", r" femenino ", r" frauen ", r" women ", r"\(f\) ", r"\(w\) ")
PRIMERA_RFEF_RE = rx(
    r" primera federacion ", r" primera rfef ", r" 1[ªa]\s*federacion ",
    r" spanish primera division rfef ", r" primera division rfef "
)
LALIGA_RE = rx(
    r"\blaliga\s+ea\s+sports\b",
    r"\bliga\s+ea\s+sports\b",
    r"\bliga\s+ea\b",
    r"\bespana\s*-?\s*la\s+liga\b",
    r"\blaliga(?![\s\-]*(?:hypermotion|smartbank|tv\s*hypermotion|123))\b",
)
BASKET_ALLOWED_COMPETITIONS_RE = rx(
    r"\bliga\s+endesa\b",
    r"\bacb\b",
    r"\beuroliga\b",
    r"\beuroleague\b",
    r"\beuro\s*league\b",
    r"\bcopa\s+acb\b",
    r"\bsupercopa\s+endesa\b",
    r"\bsupercopa\s+de\s+espana\b",
    r"\bnba\b",
    r"\bnational\s+basketball\s+association\b",
)

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
NBA_RE = rx(r" nba ", r" national basketball association ")
EUROLIGA_RE = rx(r" euroliga ", r" euroleague ")
BASKET_WOMEN_RE = rx(r"\(f\) ", r"\(w\) ")
COPA_DEL_REY_RE = rx(r" copa del rey ")
BASKET_CONTEXT_RE = rx(r" basket ", r" baloncesto ", r" acb ")
CHAMPIONS_RE = rx(r" champions league ", r" champions ")
CHAMPIONS_NON_FOOTBALL_RE = rx(r" basketball ", r" cl ", r" afc ", r" asia ")
PREMIER_RE = rx(
    r"\binglaterra\s*-?\s*premier\s+league\b",
    r"\benglish\s+premier\s+league\b",
    r"(?<![a-z0-9-])premier\s+league(?![a-z0-9-])",
)
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
    if any(forbidden in blob_lower for forbidden in ["academy", "academie", "moto2", "moto 2", "moto3", "moto 3", "rookies", "supercars"]):
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

    is_fav = False
    if comp_name == "Fórmula 1":
        is_fav = any(k in clean_norm for k in ["carrera", "race", "clasificacion", "qualifying", "sprint"])
    else:
        is_fav = any(k in clean_norm for k in ["carrera", "race", "sprint"])

    return (comp_name, event_title, is_fav)


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str, text_lines: list[str]) -> tuple[str, str, str, bool, bool, str, str]:
    padded_blob = f" {normalize_search_text(blob)} "
    padded_tv = f" {normalize_search_text(tv_blob)} "

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

    if BASKET_ALLOWED_COMPETITIONS_RE.search(padded_blob):
        if WOMEN_RE.search(padded_blob) or BASKET_WOMEN_RE.search(padded_blob):
            return ("", "", "", False, False, "", "")
        if NBA_RE.search(padded_blob):
            comp_name = "NBA"
            comp_key = "nba"
        elif EUROLIGA_RE.search(padded_blob):
            comp_name = "Euroliga"
            comp_key = "euroliga"
        else:
            comp_name = "Liga Endesa / ACB"
            comp_key = "ligaendesa"
        is_fav = bool(REAL_MADRID_RE.search(padded_blob) and not YOUTH_BASKET_RE.search(padded_blob))
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

    if LALIGA_RE.search(padded_blob):
        is_fav = bool(REAL_MADRID_RE.search(padded_blob))
        return ("Fútbol", "⚽", "LaLiga EA Sports", is_fav, True, "", "laliga")

    if PREMIER_RE.search(padded_blob):
        return ("Fútbol", "⚽", "Premier League", False, True, "", "premier")

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