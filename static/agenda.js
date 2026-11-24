const TODAY_DATE_STR = "{TODAY_DATE_STR}";
const SPORT_TV_GUIDE_FAV_EVENTS = {SPORT_TV_GUIDE_EVENTS_JSON};
const EMBEDDED_CHANNELS = {EMBEDDED_CHANNELS_JSON};
let currentFilter = getCurrentTimeSlotFilter();
function getCurrentTimeSlotFilter() {
    try {
        const now = new Date();
        const formatter = new Intl.DateTimeFormat('en-GB', {
            timeZone: 'Europe/Madrid',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
        const parts = formatter.formatToParts(now);
        const hh = parseInt(parts.find(p => p.type === 'hour')?.value || '0', 10);
        const mm = parseInt(parts.find(p => p.type === 'minute')?.value || '0', 10);
        const totalMins = hh * 60 + mm;
        if (totalMins <= 419) return 'madrugada';
        if (totalMins <= 779) return 'manana';
        if (totalMins <= 1229) return 'tarde';
        return 'noche';
    } catch (_) {
        return 'tarde';
    }
}

let currentActiveView = 'futbolenlatv';
let currentLetterFilter = 'FAVORITOS';
let allCatalogChannels = [];
let hasPerformedInitialScroll = false;
let fixedFavoritesCount = null;

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
    const previousFilter = currentFilter;
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

    const sourceCheckboxes = document.querySelectorAll('.source-chk');
    if (isFavView) {
        sourceCheckboxes.forEach(chk => {
            chk.checked = true;
            chk.disabled = true;
            chk.parentElement.style.opacity = '0.6';
            chk.parentElement.style.cursor = 'not-allowed';
        });
    } else {
        sourceCheckboxes.forEach(chk => {
            chk.disabled = false;
            chk.parentElement.style.opacity = '1';
            chk.parentElement.style.cursor = 'pointer';
        });
        if (previousFilter === 'favoritos') {
            sourceCheckboxes.forEach(chk => {
                chk.checked = (cleanStr(chk.value) !== 'cdnlive');
            });
        } else if (!Array.from(sourceCheckboxes).some(chk => chk.checked)) {
            sourceCheckboxes.forEach(chk => {
                chk.checked = (cleanStr(chk.value) !== 'cdnlive');
            });
        }
    }

    applyFilters();
}

function updateStatsForActiveView() {
    if (currentActiveView === 'futbolenlatv') {
        const table = document.getElementById('futbolenlatvTable');
        if (!table) return;
        const trs = table.getElementsByClassName('stg-event-card');

        if (fixedFavoritesCount === null) {
            let initialFavs = 0;
            for (let i = 0; i < trs.length; i++) {
                const tr = trs[i];
                if (tr.id === 'dynamicEmptyState') continue;
                const isFiltered = tr.getAttribute('data-filtered') === 'true';
                const source = cleanStr(tr.getAttribute('data-source'));
                if (isFiltered && source === 'futbolenlatv') {
                    initialFavs++;
                }
            }
            fixedFavoritesCount = initialFavs;
        }

        let madCount = 0;
        let manCount = 0;
        let tarCount = 0;
        let nocCount = 0;
        let proxCount = 0;

        const isFavoritesMode = (currentFilter === 'favoritos');

        const checkedSources = new Set();
        if (isFavoritesMode) {
            document.querySelectorAll('.source-chk').forEach(chk => {
                checkedSources.add(cleanStr(chk.value));
            });
        } else {
            document.querySelectorAll('.source-chk:checked').forEach(chk => {
                checkedSources.add(cleanStr(chk.value));
            });
        }

        const checkedSports = new Set();
        document.querySelectorAll('.comp-chk:checked').forEach(chk => { checkedSports.add(cleanStr(chk.value)); });

        const rawSearchQuery = document.getElementById('agendaSearch')?.value || '';

        for (let i = 0; i < trs.length; i++) {
            const tr = trs[i];
            if (tr.id === 'dynamicEmptyState') continue;

            const rowSlot = cleanStr(tr.getAttribute('data-slot'));
            const source = cleanStr(tr.getAttribute('data-source'));
            const sport = cleanStr(tr.getAttribute('data-sport'));
            const rowDate = tr.getAttribute('data-date');
            const isToday = (rowDate === TODAY_DATE_STR);

            const matchesSource = checkedSources.has(source);
            const matchesSport = checkedSports.has('todos') || checkedSports.has(sport);
            const matchesSearch = matchesTimeOrTextSearch(tr, rawSearchQuery);

            if (!isFavoritesMode && matchesSource && matchesSport && matchesSearch) {
                if (rowDate > TODAY_DATE_STR) proxCount++;
                else if (isToday) {
                    if (rowSlot === 'madrugada') madCount++;
                    else if (rowSlot === 'manana') manCount++;
                    else if (rowSlot === 'tarde') tarCount++;
                    else if (rowSlot === 'noche') nocCount++;
                }
            } else if (isFavoritesMode && matchesSource && matchesSport && matchesSearch) {
                if (rowDate > TODAY_DATE_STR) proxCount++;
                else if (isToday) {
                    if (rowSlot === 'madrugada') madCount++;
                    else if (rowSlot === 'manana') manCount++;
                    else if (rowSlot === 'tarde') tarCount++;
                    else if (rowSlot === 'noche') nocCount++;
                }
            }
        }

        const cardFav = document.querySelector('#card-favoritos .val');
        const cardMad = document.querySelector('#card-madrugada .val');
        const cardMan = document.querySelector('#card-manana .val');
        const cardTar = document.querySelector('#card-tarde .val');
        const cardNoc = document.querySelector('#card-noche .val');
        const cardProx = document.querySelector('#card-proximamente .val');

        if (cardFav) cardFav.textContent = fixedFavoritesCount;
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
        setFilter(getCurrentTimeSlotFilter());
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

function scrollToTargetEvent(forceScroll = false) {
    if (!forceScroll && typeof hasPerformedInitialScroll !== 'undefined' && hasPerformedInitialScroll) return;
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
        targetRow = visibleRows[0];
    }

    if (targetRow) {
        updateStickyHeadingOffset();
        const panelHeight = document.getElementById('stickyPanel')?.getBoundingClientRect().height || 0;
        const rect = targetRow.getBoundingClientRect();
        const absoluteTop = rect.top + window.scrollY - panelHeight - 14;
        window.scrollTo({
            top: Math.max(0, absoluteTop),
            behavior: 'auto'
        });
        hasPerformedInitialScroll = true;
    }
}

window.addEventListener('load', async () => {
    await initApp();
    highlightPreviousEvents();
    setInterval(highlightPreviousEvents, 60000);
    setFilter(getCurrentTimeSlotFilter());
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
        const isFavoritesMode = (currentFilter === 'favoritos');

        const checkedSources = new Set();
        document.querySelectorAll('.source-chk:checked').forEach(chk => {
            checkedSources.add(cleanStr(chk.value));
        });

        const checkedSports = new Set();
        document.querySelectorAll('.comp-chk:checked').forEach(chk => { checkedSports.add(cleanStr(chk.value)); });

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
            const matchesSource = checkedSources.has(source);
            const matchesSport = checkedSports.has('todos') || checkedSports.has(sport);
            const rawSearchQuery = document.getElementById('agendaSearch')?.value || '';
            const matchesSearch = matchesTimeOrTextSearch(tr, rawSearchQuery);

            if (currentFilter === 'favoritos') {
                matchesFilter = isFiltered && (source === 'futbolenlatv');
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
            scrollToTargetEvent(false);
        }
    }
}