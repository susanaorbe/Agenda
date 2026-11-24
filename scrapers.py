from datetime import date, datetime, timedelta
import json
import os
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

from config import (
    DATE_RE,
    EVENT_CLEANUP_TRAIL_RE,
    EVENT_TEXT_RE,
    REQUEST_HEADERS,
    REQUEST_TIMEOUT,
    SPORT_TV_GUIDE_LOGIN_URL,
    SPORT_TV_GUIDE_SPORT_URLS,
    TAPLINK_URL,
    WIDGET_URL,
    clean_time,
    contains_previo_or_previa,
    create_http_session,
    get_spain_timezone,
    normalize_search_text,
)
from rules import (
    event_similarity_key,
    get_sport_and_competition,
    is_event_allowed_by_futbolenlatv_rules,
    normalize_competition_label,
    parse_motor_event,
    parse_row_elements,
)


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

                    raw_items = page.evaluate(r"""() => {
                        const out = [];
                        let currentDayText = '';
                        const dayPattern = /\b(\d{1,2})\s*(?:de\s+)?(ene|feb|mar|abr|may|jun|jul|ago|sep|oct|nov|dic|lun|mar|mié|mie|jue|vie|sáb|sab|dom)/i;

                        const nodes = document.querySelectorAll('div.row, h2, h3, h4, .dateHeader, .day-header, [class*="date"]');
                        for (const el of nodes) {
                            if (el.matches('div.row')) {
                                const timeEl = el.querySelector('.main.time b, .main b');
                                const inlineCols = el.querySelectorAll('.col-inline > div');
                                if (!timeEl || inlineCols.length === 0) continue;

                                const hora = (timeEl.innerText || timeEl.textContent || '').trim();
                                const evento = (inlineCols[0]?.innerText || inlineCols[0]?.textContent || '').replace(/\s+/g, ' ').trim();
                                const competicion = (inlineCols[1]?.innerText || inlineCols[1]?.textContent || '').replace(/\s+/g, ' ').trim();

                                const channelImgs = el.querySelectorAll('.col-xs-4.mobile-normal img, img[data-src*="tvm-station"], img[src*="tvm-station"]');
                                const canales = [];
                                const seenCh = new Set();
                                for (const img of channelImgs) {
                                    const chName = (img.getAttribute('title') || img.getAttribute('alt') || '').replace(/\s+/g, ' ').trim();
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
                                    canales
                                });
                            } else {
                                const txt = (el.innerText || el.textContent || '').replace(/\s+/g, ' ').trim();
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
                        canales = item.get("canales") or []

                        if not hora or not evento_raw or not canales:
                            continue
                        if contains_previo_or_previa(evento_raw, competicion_raw):
                            continue

                        allowed, is_fav, final_sport, final_icon, final_comp, final_event, comp_key = is_event_allowed_by_futbolenlatv_rules(
                            sport_label=sport_label,
                            competition_label=competicion_raw,
                            event_title=evento_raw,
                            raw_lines=[evento_raw, competicion_raw],
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


def _navigate_and_settle_fctv_page(page, url: str) -> None:
    """Navega a una URL de FCTV33 tolerando redirecciones/ERR_ABORTED y estabilizando el contexto."""
    try:
        page.goto(url, timeout=20000, wait_until="domcontentloaded")
    except Exception as exc:
        if "ERR_ABORTED" not in str(exc):
            raise
        page.wait_for_timeout(1200)
        try:
            page.wait_for_load_state("domcontentloaded", timeout=10000)
        except Exception:
            pass

    page.wait_for_timeout(1000)
    try:
        page.wait_for_load_state("networkidle", timeout=4000)
    except Exception:
        pass
    page.wait_for_timeout(400)


def fetch_fctv_events(domain: str, today_date: date) -> dict:
    """Extrae eventos de FCTV33 filtrados estrictamente por las reglas de FUTBOLENLATV."""
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

    def is_relevant_fctv_category(path_str: str) -> bool:
        p_low = path_str.strip("/").lower()
        if not p_low or "-match-" in p_low:
            return False
        if p_low in {"es", "en", "pt", "fr", "de", "it"}:
            return False
        if re.search(r"-(?:19|20)\d{2}(?:\.html)?$", p_low):
            return False
        sport_tokens = (
            "football", "basketball", "tennis", "motorsport", "motor",
            "futbol", "baloncesto", "tenis", "euroleague", "euroliga",
            "nba", "acb", "laliga", "champions", "atp", "wta", "f1", "motogp"
        )
        return any(tok in p_low for tok in sport_tokens)

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
            _navigate_and_settle_fctv_page(page, target_url)

            category_links = page.evaluate(r"""() => {
                const links = [];
                for (const a of document.querySelectorAll('a[href]')) {
                    const href = a.getAttribute('href');
                    if (href && !links.includes(href)) {
                        links.push(href);
                    }
                }
                return links;
            }""")

            valid_categories = []
            seen_cats = set()
            for link in category_links:
                if link.startswith("mailto:") or "javascript:" in link or "taplink" in link:
                    continue
                parsed_l = urlparse(link)
                path_l = parsed_l.path.strip("/")
                if path_l and "." in path_l and not path_l.endswith(".html"):
                    continue
                if is_relevant_fctv_category(path_l) and path_l not in seen_cats:
                    seen_cats.add(path_l)
                    valid_categories.append(path_l)

            priority_cats = [
                "es/basketball.html", "es/basketball", "basketball.html", "basketball",
                "es/football.html", "es/football", "es/tennis.html", "es/tennis",
                "es/motorsport.html", "es/motorsport"
            ]
            ordered_cats = []
            for pc in priority_cats:
                if pc not in ordered_cats:
                    ordered_cats.append(pc)
            for c in valid_categories:
                if c not in ordered_cats:
                    ordered_cats.append(c)
            valid_categories = ordered_cats[:18]
            global_seen_urls = set()

            for cat in valid_categories:
                cat_url = urljoin(base_url, f"/{cat}")
                if "?" not in cat_url:
                    cat_url += "?ptst=1"

                try:
                    _navigate_and_settle_fctv_page(page, cat_url)
                    try:
                        page.wait_for_selector('a[href*="-match-"]', timeout=3500)
                    except Exception:
                        page.wait_for_timeout(600)

                    for _ in range(3):
                        try:
                            page.evaluate("window.scrollTo(0, document.documentElement.scrollHeight)")
                            page.wait_for_timeout(200)
                        except Exception:
                            break
                    try:
                        page.evaluate("window.scrollTo(0, 0)")
                    except Exception:
                        pass

                    candidate_cards = page.evaluate(r"""() => {
                        const out = [];
                        const seen = new Set();
                        const timePattern = /\b\d{1,2}:\d{2}\b/;
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
                        text_norm = normalize_search_text(card_text)

                        t_match = time_re.search(card_text)
                        if not t_match:
                            return None, ""
                        extracted_t = f"{int(t_match.group(1)):02d}:{t_match.group(2)}"

                        has_explicit_past_marker = any(k in text_norm for k in ["ayer", "yesterday"])
                        has_explicit_date = bool(
                            re.search(r"\b\d{1,2}[/-]\d{1,2}(?:[/-](?:20)?\d{2})?\b", card_text)
                            or re.search(
                                r"\b\d{1,2}\s+(?:de\s+)?(?:ene|jan|feb|mar|abr|apr|may|jun|jul|ago|aug|sep|sept|oct|nov|dic|dec)[a-z]*\b",
                                text_norm,
                            )
                        )

                        if has_explicit_past_marker:
                            return today_date - timedelta(days=1), extracted_t

                        ts_match = re.search(r"\b(1[6-9]\d{8}|2\d{9})(\d{3})?\b", data_attrs)
                        if ts_match:
                            try:
                                ts_sec = int(ts_match.group(1))
                                dt_spain = datetime.fromtimestamp(ts_sec, tz=spain_tz)
                                ev_d = dt_spain.date()
                                if ev_d < today_date and not has_explicit_date:
                                    ev_d = today_date
                                return ev_d, f"{dt_spain.hour:02d}:{dt_spain.minute:02d}"
                            except Exception:
                                pass

                        iso_match = re.search(r"\b(20\d{2})-(\d{1,2})-(\d{1,2})(?:[T\s]+(\d{1,2}):(\d{2}))?", combined)
                        if iso_match:
                            try:
                                y, m, d = int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))
                                ev_d = date(y, m, d)
                                if ev_d < today_date and not has_explicit_date:
                                    ev_d = today_date
                                if iso_match.group(4) and iso_match.group(5):
                                    return ev_d, f"{int(iso_match.group(4)):02d}:{int(iso_match.group(5)):02d}"
                                return ev_d, extracted_t
                            except ValueError:
                                pass

                        if any(k in text_norm for k in ["en vivo", "en directo", "directo", "live", "hoy", "today"]):
                            return today_date, extracted_t
                        if any(k in text_norm for k in ["manana", "tomorrow"]):
                            return today_date + timedelta(days=1), extracted_t

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
                        if any(tok in href.lower() for tok in ("2280700", "bayern", "2280705", "pamesa-valencia")):
                            print(
                                "DIAG FCTV MATCH:",
                                "| href=", href,
                                "| cardText=", repr(item.get("cardText", "")),
                                "| dataAttrs=", repr(item.get("dataAttrs", "")),
                            )
                        if contains_previo_or_previa(href, item.get("cardText", "")):
                            continue

                        full_url = urljoin(page.url or base_url, href)
                        parsed_url = urlparse(full_url)

                        path_lower = parsed_url.path.lower()
                        if any(k in path_lower for k in ["/volleyball/", "/es/volleyball/", "/voleibol/", "/es/voleibol/"]):
                            continue

                        detected_sport_key = "football"
                        detected_sport_label = "FÚTBOL"
                        detected_icon = "⚽"

                        if any(k in path_lower for k in ["/tennis/", "/es/tennis/", "/tenis/", "/es/tenis/"]):
                            detected_sport_key = "tennis"
                            detected_sport_label = "TENIS"
                            detected_icon = "🎾"
                        elif any(k in path_lower for k in ["/basketball/", "/es/basketball/", "/baloncesto/", "/es/baloncesto/"]):
                            detected_sport_key = "basketball"
                            detected_sport_label = "BALONCESTO"
                            detected_icon = "🏀"
                        elif any(k in path_lower for k in ["/motorsport/", "/es/motorsport/", "/motor/", "/es/motor/"]):
                            detected_sport_key = "motorsport"
                            detected_sport_label = "MOTOR"
                            detected_icon = "🏆"

                        canonical_url = f"{parsed_url.scheme}://{parsed_url.netloc}{parsed_url.path}"
                        if canonical_url in global_seen_urls:
                            continue

                        current_event_date, extracted_time = parse_fctv_datetime(item)
                        if not current_event_date or not extracted_time or extracted_time == "LIVE":
                            continue

                        if current_event_date < today_date:
                            continue

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
                        if contains_previo_or_previa(comp_str, event_str):
                            continue

                        raw_lines = [
                            re.sub(r"\s+", " ", ln).strip()
                            for ln in str(item.get("cardText", "")).splitlines()
                            if re.sub(r"\s+", " ", ln).strip()
                        ]
                        allowed, is_fav, final_sport_label, final_icon, final_comp, final_event, comp_key = is_event_allowed_by_futbolenlatv_rules(
                            sport_label=detected_sport_label,
                            competition_label=comp_str,
                            event_title=event_str,
                            raw_lines=raw_lines or [event_str],
                        )
                        if not allowed:
                            continue

                        bucket_map = {
                            "FÚTBOL": "football",
                            "BALONCESTO": "basketball",
                            "TENIS": "tennis",
                            "MOTOR": "motorsport",
                        }
                        bucket_key = bucket_map.get(final_sport_label, detected_sport_key)

                        if normalize_search_text(final_comp) == normalize_search_text(final_event):
                            final_comp = final_sport_label

                        query = parsed_url.query
                        if "icg=" not in query:
                            query = f"{query}&" if query else ""
                            query += "icg=RVM&ilang=es"
                        elif "ilang=" not in query:
                            query += "&ilang=es"
                        normalized_url = f"{parsed_url.scheme or 'https'}://{parsed_url.netloc}{parsed_url.path}?{query}"

                        global_seen_urls.add(canonical_url)

                        fctv_events_by_sport[bucket_key].append({
                            "date_obj": current_event_date,
                            "hora": extracted_time,
                            "deporte": final_sport_label,
                            "icono": final_icon,
                            "competicion": final_comp,
                            "evento": final_event,
                            "tv_list": [],
                            "fctv_url": normalized_url,
                            "is_filtered": False,
                            "is_configured": True,
                            "comp_key": comp_key,
                            "source": "fctv33"
                        })
                except Exception as e:
                    print(f"   Aviso escaneando categoría {cat}: {e}")

        except Exception as e:
            print(f"Error general en exploración FCTV: {e}")
        finally:
            browser.close()

    return fctv_events_by_sport


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
                ev_copy = dict(ev)
                ev_copy["source"] = "fctv33"
                ev_copy["is_filtered"] = False
                event_key = ("fctv33", ev_copy["date_obj"], ev_copy["hora"], normalize_search_text(ev_copy["competicion"]), normalize_search_text(ev_copy["evento"]))
                if event_key not in seen_events:
                    seen_events.add(event_key)
                    futbolenlatv_results.append(ev_copy)
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
            if contains_previo_or_previa(el_text, event_str, tournament, *text_lines):
                continue

            tv_blob = " ".join(channels).lower()
            blob = normalize_search_text(f"{' '.join(text_lines)} {tournament} {tv_blob}")

            comp_name, motor_event_title, is_fav = parse_motor_event(blob, tournament, text_lines)
            if comp_name:
                comp_label = normalize_competition_label(comp_name)
                event_key = ("futbolenlatv", current_date_obj, time_clean, comp_label, normalize_search_text(motor_event_title))
                if event_key in seen_events:
                    continue
                seen_events.add(event_key)

                futbolenlatv_results.append({
                    "date_obj": current_date_obj,
                    "hora": time_clean,
                    "deporte": "MOTOR",
                    "icono": "🏆",
                    "competicion": comp_label,
                    "evento": motor_event_title.upper(),
                    "tv_list": channels,
                    "fctv_url": "",
                    "is_filtered": bool(is_fav),
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

            competition_label = normalize_competition_label(competition)
            normalized_competition = normalize_search_text(competition_label)
            if (
                not is_movistar_plus_channel and (
                    normalized_competition == "brasil serie a"
                    or ("brasil" in normalized_competition and "serie a" in normalized_competition)
                )
            ):
                continue

            final_event = custom_event if custom_event else event_str
            if competition_label:
                comp_clean_pattern = re.compile(re.escape(competition_label), re.IGNORECASE)
                final_event = comp_clean_pattern.sub("", final_event)

            final_event = re.sub(r"^[\s\-–—]+|[\s\-–—]+$", "", final_event).strip()
            final_event = EVENT_CLEANUP_TRAIL_RE.sub("", final_event).strip()

            if not EVENT_TEXT_RE.search(final_event):
                continue

            event_key = ("futbolenlatv", current_date_obj, time_clean, normalize_search_text(competition_label), normalize_search_text(final_event))
            if event_key in seen_events:
                continue
            seen_events.add(event_key)

            futbolenlatv_results.append({
                "date_obj": current_date_obj,
                "hora": time_clean,
                "deporte": sport.upper(),
                "icono": icon,
                "competicion": competition_label,
                "evento": final_event.upper(),
                "tv_list": channels,
                "fctv_url": "",
                "is_filtered": bool(is_favorite),
                "is_configured": is_configured,
                "comp_key": comp_key,
                "source": "futbolenlatv"
            })

    except Exception as e:
        print(f"Error cargando la agenda general: {e}")

    futbolenlatv_results.sort(key=event_similarity_key)
    return futbolenlatv_results
