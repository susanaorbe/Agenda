from collections import Counter
from datetime import datetime
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
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15

CHANNEL_DICT = {
    'la 1': ['https://dlive.sx/stream/stream-533.php', 'https://dlive.sx/hub/stream-533.php', 'https://dlive.sx/watch/stream-533.php', 'https://dlive.sx/cast/stream-533.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'la 2': ['https://dlive.sx/stream/stream-536.php', 'https://dlive.sx/hub/stream-536.php', 'https://dlive.sx/watch/stream-536.php', 'https://dlive.sx/cast/stream-536.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'antena 3': ['https://dlive.sx/stream/stream-531.php', 'https://dlive.sx/hub/stream-531.php', 'https://dlive.sx/watch/stream-531.php', 'https://dlive.sx/cast/stream-531.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'cuatro': ['https://dlive.sx/stream/stream-535.php', 'https://dlive.sx/hub/stream-535.php', 'https://dlive.sx/watch/stream-535.php', 'https://dlive.sx/cast/stream-535.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'telecinco': ['https://dlive.sx/stream/stream-532.php', 'https://dlive.sx/hub/stream-532.php', 'https://dlive.sx/watch/stream-532.php', 'https://dlive.sx/cast/stream-532.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'la sexta': ['https://dlive.sx/stream/stream-534.php', 'https://dlive.sx/hub/stream-534.php', 'https://dlive.sx/watch/stream-534.php', 'https://dlive.sx/cast/stream-534.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'movistar plus+': ['https://dlive.sx/stream/stream-437.php', 'https://dlive.sx/hub/stream-437.php', 'https://dlive.sx/watch/stream-437.php', 'https://dlive.sx/cast/stream-437.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ vamos': ['https://dlive.sx/stream/stream-521.php', 'https://dlive.sx/hub/stream-521.php', 'https://dlive.sx/watch/stream-521.php', 'https://dlive.sx/cast/stream-521.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ vamos 2': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es/'],
    'm+ vamos 3': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es/'],
    'dazn laliga': ['https://dlive.sx/stream/stream-538.php', 'https://dlive.sx/hub/stream-538.php', 'https://dlive.sx/watch/stream-538.php', 'https://dlive.sx/cast/stream-538.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ laliga': ['https://dlive.sx/stream/stream-84.php', 'https://dlive.sx/hub/stream-84.php', 'https://dlive.sx/watch/stream-84.php', 'https://dlive.sx/cast/stream-84.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ liga de campeones': ['https://dlive.sx/stream/stream-435.php', 'https://dlive.sx/hub/stream-435.php', 'https://dlive.sx/watch/stream-435.php', 'https://dlive.sx/cast/stream-435.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://www.dazn.com/es-ES/home'],
    'dazn app gratis': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://www.dazn.com/es-ES/home'],
    'dazn 1': ['https://dlive.sx/stream/stream-445.php', 'https://dlive.sx/hub/stream-445.php', 'https://dlive.sx/watch/stream-445.php', 'https://dlive.sx/cast/stream-445.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn 2': ['https://dlive.sx/stream/stream-446.php', 'https://dlive.sx/hub/stream-446.php', 'https://dlive.sx/watch/stream-446.php', 'https://dlive.sx/cast/stream-446.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn 3': ['https://dlive.sx/stream/stream-447.php', 'https://dlive.sx/hub/stream-447.php', 'https://dlive.sx/watch/stream-447.php', 'https://dlive.sx/cast/stream-447.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn 4': ['https://dlive.sx/stream/stream-448.php', 'https://dlive.sx/hub/stream-448.php', 'https://dlive.sx/watch/stream-448.php', 'https://dlive.sx/cast/stream-448.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn f1': ['https://dlive.sx/stream/stream-537.php', 'https://dlive.sx/hub/stream-537.php', 'https://dlive.sx/watch/stream-537.php', 'https://dlive.sx/cast/stream-537.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'dazn baloncesto 3': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://www.dazn.com/es-ES/home'],
    'eurosport 1': ['https://dlive.sx/stream/stream-524.php', 'https://dlive.sx/hub/stream-524.php', 'https://dlive.sx/watch/stream-524.php', 'https://dlive.sx/cast/stream-524.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'eurosport 2': ['https://dlive.sx/stream/stream-525.php', 'https://dlive.sx/hub/stream-525.php', 'https://dlive.sx/watch/stream-525.php', 'https://dlive.sx/cast/stream-525.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ deportes': ['https://dlive.sx/stream/stream-436.php', 'https://dlive.sx/hub/stream-436.php', 'https://dlive.sx/watch/stream-436.php', 'https://dlive.sx/cast/stream-436.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ deportes 2': ['https://dlive.sx/stream/stream-438.php', 'https://dlive.sx/hub/stream-438.php', 'https://dlive.sx/watch/stream-438.php', 'https://dlive.sx/cast/stream-438.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ deportes 3': ['https://dlive.sx/stream/stream-526.php', 'https://dlive.sx/hub/stream-526.php', 'https://dlive.sx/watch/stream-526.php', 'https://dlive.sx/cast/stream-526.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'm+ deportes 4': ['https://dlive.sx/stream/stream-527.php', 'https://dlive.sx/hub/stream-527.php', 'https://dlive.sx/watch/stream-527.php', 'https://dlive.sx/cast/stream-527.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'tennis channel - orange tv': ['https://dlive.sx/stream/stream-40.php', 'https://dlive.sx/hub/stream-40.php', 'https://dlive.sx/watch/stream-40.php', 'https://dlive.sx/cast/stream-40.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'real madrid tv': ['https://dlive.sx/stream/stream-523.php', 'https://dlive.sx/hub/stream-523.php', 'https://dlive.sx/watch/stream-523.php', 'https://dlive.sx/cast/stream-523.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'replay': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es'],
    'teledeporte': ['https://dlive.sx/stream/stream-529.php', 'https://dlive.sx/hub/stream-529.php', 'https://dlive.sx/watch/stream-529.php', 'https://dlive.sx/cast/stream-529.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'laliga hypermotion': ['https://dlive.sx/stream/stream-539.php', 'https://dlive.sx/hub/stream-539.php', 'https://dlive.sx/watch/stream-539.php', 'https://dlive.sx/cast/stream-539.php', 'https://hubu.ru/fctvlink', 'https://daddylive.pk/'],
    'laliga hypermotion 2': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es/'],
    'laliga hypermotion 3': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es/'],
    'laliga tv hypermotion': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://www.dazn.com/es-ES/home'],
    'primera federación': ['https://hubu.ru/fctvlink', 'https://daddylive.pk/', 'https://ver.movistarplus.es']
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


def get_channel_urls(channel_name: str) -> list[str]:
    norm = normalize_search_text(channel_name)
    clean_name = re.sub(r"\([^)]*\)", "", norm).strip()
    clean_name = normalize_search_text(clean_name)

    if clean_name in CHANNEL_DICT:
        return CHANNEL_DICT[clean_name]

    for k, v in CHANNEL_DICT.items():
        if normalize_search_text(k) == clean_name or clean_name in normalize_search_text(k):
            return v
            
    if clean_name in {"#vamos", "m+ #vamos", "#vamos spain", "m+ vamos 8 y 50"}:
        if "m+ vamos" in CHANNEL_DICT:
            return CHANNEL_DICT["m+ vamos"]
    elif clean_name in {"movistar plus", "movistar+"}:
        if "movistar plus+" in CHANNEL_DICT:
            return CHANNEL_DICT["movistar plus+"]
    elif clean_name in {"tennis channel", "tennis channel orange tv"}:
        if "tennis channel - orange tv" in CHANNEL_DICT:
            return CHANNEL_DICT["tennis channel - orange tv"]
    elif clean_name in {"tdp", "teledeporte spain (tdp)"}:
        if "teledeporte" in CHANNEL_DICT:
            return CHANNEL_DICT["teledeporte"]

    return ['https://hubu.ru/fctvlink', 'https://daddylive.pk/']


EXCLUDED_CHANNELS = {
    "* sin tv en directo *",
    "antel tv internacional",
    "aragón play",
    "aragón tv",
    "asobal tv",
    "atp tennis tv",
    "athletic-club.eus",
    "baloncesto tv",
    "baloncesto tv ppv",
    "barclays women's super league youtube",
    "be mad",
    "betevé web",
    "beisbolplay",
    "canal 9 soria youtube",
    "cayotv youtube",
    "cmmplay",
    "conmebol libertadores youtube",
    "dazn 1 bar(m148)",
    "dazn 1 bar"
    "dazn 2 bar(m149)",
    "dazn 2 bar",
    "deportes tvcanaria youtube",
    "eleventv youtube",
    "esport3 web",
    "esport3(cataluña)",
    "etb1(país vasco)",
    "fanatiz",
    "fanplay",
    "fanplay tv",
    "fanseat",
    "fff tv youtube",
    "fiba youtube",
    "flamengo tv youtube",
    "hbo max",
    "la 7",
    "la 7 tv",
    "la ocho mediterráneo",
    "la xarxa+",
    "laliga tv bar",
    "laliga tv m2",
    "laliga tv m3",
    "laliga tv m4",
    "laliga tv m5",
    "laliga+ plus",
    "liga futve youtube",
    "ligafutve app",
    "lleida televisió",
    "m+ #vamos bar 2",
    "m+ #vamos bar 2(308)",
    "m+ #vamos bar(307)",
    "m+ laliga hdr",
    "m+ laliga hdr(m440 o111)",
    "mediaset infinity",
    "motogp videopass",
    "movistar+ lite",
    "nba league pass",
    "nwsl+",
    "onefootball",
    "onefootball ppv",
    "orange fútbol 1(107)",
    "orange fútbol 2(108)",
    "orange fútbol 3(109)",
    "prosieben maxx(m+ astra)",
    "rcd deportivo tv youtube",
    "rcdeportivo tv youtube",
    "rcn nuestra tele",
    "red bull tv",
    "rfef tv youtube",
    "rfef.es",
    "rtve play",
    "sefutbol youtube",
    "sevilla fc +",
    "siroko tv",
    "tv 3",
    "tv footballclub(acceder)",
    "tv canaria",
    "tv galicia",
    "tv3(cataluña)",
    "tvg(galicia)",    
    "tv footballclub ▾",
    "tvg",
    "tv5monde",
    "uefa tv",
    "uefa youtube",
    "win sports tv youtube",
    "wta tv",
    "web directo",
    "zapping internacional",
}

# ============================================================================
# REGEX Y CLASIFICACIÓN
# ============================================================================

def rx(*patterns: str) -> re.Pattern:
    return re.compile(r"(?:%s)" % "|".join(patterns), re.IGNORECASE)


REAL_MADRID_RE = rx(r"\breal madrid\b", r"\brm castilla\b", r"\br\.?\s*madrid\b")
CASTILLA_RE = rx(r"\breal madrid castilla\b", r"\brm castilla\b", r"\bcastilla\b")

BARCA_REAL_ATLETICO_RE = rx(
    r"\breal madrid\b", r"\bbarcelona\b", r"\bfc barcelona\b", r"\bbarca\b",
    r"\batletico de madrid\b", r"\batletico\b", r"\batleti\b", r"\basasuna\b",
    r"\bracing santander\b", r"\bcelta\b", r"\balaves\b", r"\bmalaga\b", r"\breal sociedad\b",
    r"\bsevilla\b"
)

BARCA_REAL_RE = rx(
    r"\breal madrid\b", r"\bbarcelona\b", r"\bfc barcelona\b", r"\bbarca\b",
    r"\bbarca basket\b", r"\bfc barcelona basket\b", r"\bjoventut\b"
)

PSG_RE = rx(r"\bparis saint germain\b", r"\bpsg\b")
ARSENAL_RE = rx(r"\barsenal\b")
BAYERN_RE = rx(r"\bbayern munich\b", r"\bbayern\b")
INTER_RE = rx(r"\binter de milan\b", r"\binter milan\b", r"\binter\b", r"\bac milan\b", r"\bmilan\b", r"\batalanta\b", r"\bjuventus\b", r"\blazio\b")

TENNIS_ALLOWED_PLAYERS_RE = rx(
    r"\bjannik sinner\b", r"\bsinner\b",
    r"\balexander zverev\b", r"\bzverev\b",
    r"\belena rybakina\b", r"\brybakina\b",
    r"\baryna sabalenka\b", r"\bsabalenka\b",
    r"\bcarlos alcaraz\b", r"\balcaraz\b",
    r"\balejandro davidovich\b", r"\bdavidovich\b",
    r"\bcristina bucsa\b", r"\bbucsa\b",
    r"\bpaula badosa\b", r"\bbadosa\b",
    r"\bjaume munar\b", r"\bmunar\b",
    r"\bjessica bouzas\b", r"\bbouzas\b",
    r"\brafael jodar\b", r"\bjodar\b"
)

TENNIS_SPANISH_FAVORITES_RE = rx(
    r"\bcarlos alcaraz\b", r"\balcaraz\b",
    r"\balejandro davidovich\b", r"\bdavidovich\b",
    r"\bcristina bucsa\b", r"\bbucsa\b",
    r"\bpaula badosa\b", r"\bbadosa\b",
    r"\bjaume munar\b", r"\bmunar\b",
    r"\bjessica bouzas\b", r"\bbouzas\b",
    r"\brafael jodar\b", r"\bjodar\b"
)

TENNIS_RE = rx(
    r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bwimbledon\b", r"\broland garros\b",
    r"\bus open\b", r"\bopen de australia\b", r"\bmasters\b", r"\bdavis\b",
    r"\bcopa davis\b", r"\bbillie jean king cup\b", r"\blaver cup\b",
    r"\bpekin\b", r"\bbeijing\b", r"\bchina open\b", r"\btorneo de pekin\b",
    r"\bhangzhou\b", r"\bchengdu\b", r"\btokio\b", r"\btokyo\b", r"\bjapan open\b",
    r"\btennis channel\b", r"\btennis tv\b"
)

WTA_RE = re.compile(r"\bwta\b", re.IGNORECASE)
ATP_RE = re.compile(r"\batp\b", re.IGNORECASE)
WOMEN_RE = rx(r"\bfemenina\b", r"\bfemenino\b", r"\bfrauen\b", r"\bwomen\b")

F1_RE = re.compile(r"\bf1(?![\s\-]*(?:academy|2|3|f2|f3))\b", re.IGNORECASE)
MOTO2_RE = re.compile(r"\bmoto2\b", re.IGNORECASE)
MOTO3_RE = re.compile(r"\bmoto3\b", re.IGNORECASE)

MOTOR_GENERAL_RE = rx(
    r"\bformula 1\b", r"\bf1(?![\s\-]*(?:academy))\b", r"\bmotogp\b",
    r"\bindycar\b", r"\bindy car\b", r"\bformula e\b"
)

PRIMERA_RFEF_RE = rx(
    r"\bprimera federacion\b",
    r"\bprimera rfef\b",
    r"\b1[ªa]\s*federacion\b",
)

HYPERMOTION_RE = rx(
    r"\blaliga hypermotion\b", r"\bhypermotion\b", r"\bsegunda division\b",
    r"\bsmartbank\b", r"\blaliga2\b", r"\blaliga 1\|2\|3\b", r"\b2[ªa]\s*division\b"
)

TIME_RE = re.compile(r"\b\d{1,2}:\d{2}\b")
CLEAN_TV_RE = re.compile(
    r"\(ver en directo\)|\(ver gratis\)|\(acceder\)|\(ver\)|\(m\d+[^)]*\)|ver partido|acceder", 
    re.IGNORECASE
)
EVENT_TEXT_RE = re.compile(r"[a-zA-Z0-9]")
MOTOR_GROUP_CLEAN_RE = re.compile(
    r"(libres|fp\d|practica|entrenamientos|clasificacion|warm up|sprint|shootout|carrera|q\d).*$",
    re.IGNORECASE,
)
MOTOR_EVENT_SUFFIX_RE = re.compile(
    r"\s*[-–—]\s*(libres|fp\d|practica|entrenamientos|clasificacion|warm up|sprint|shootout|carrera|q\d).*$",
    re.IGNORECASE,
)

TV_IDENTIFIERS_RE = rx(
    r"(?:m\+|movistar|dazn|channel|eurosport|rtve|laliga|teledeporte|tv|desport|disney\+?)"
)

CHANNEL_LINE_RE = rx(
    r"\btennis channel\b", r"\borange tv\b", r"\bchannel\s*[-–—]\s*orange tv\b"
)

EXCLUDED_SPORTS_RE = rx(
    r"\btorneo betplay dimayor\b",
    r"\bbetplay dimayor\b",
    r"\bmls\b",
    r"\bnfl\b",
    r"\bwnba\b",
    r"\bprimera feb\b",
    r"\bliga u\b",
    r"\bliga futve\b",
    r"\bncaaf\b"
)

EXCLUDED_BLOB_RE = rx(
    r"preolimpico femenino",
    r"nfl pretemporada",
    r"f1 academy",
    r"segunda federacion",
    r"segunda rfef",
    r"tercera federacion",
    r"tercera\b",
    r"liga nacional juvenil",
    r"fifa asean cup",
    r"laliga futures",
    r"academy\b",
    r"\breplay\b",
    r"\bprimera feb\b",
    r"\bliga u\b",
    r"\bncaa\b",
    r"\bncaaf\b",
    r"\bnational league\b",
    r"\bprimera catalana\b",
    r"\bu20 elite league\b",
    r"segunda uruguay",
    r"\bwrc\b",
    r"primera division argentina",
    r"primera nacional argentina",
    r"primera c\b",
    r"torneo federal\b",
    r"liga auf uruguaya",
    r"liga 1 peru",
    r"j1 league",
    r"j\.league",
    r"bundesliga sub-19",
    r"bundesliga u19",
    r"liga pro ecuador",
    r"liga colombiana",
    r"liga futve",
    r"\bvelada\b",
    r"rotterdam open",
    r"giro dell['\s]*emilia",
    r"\btop 14\b",
    r"\bnascar\b",
    r"\bmoto2\b",
    r"\bmoto3\b",
    r"\brugby\b",
    r"\bdivision de honor\b",
    r"\bgallagher\b",
    r"\bpremiership\b",
    r"\buci\b",
    r"\behf\b",
    r"\bboxeo\b",
    r"\bboxing\b",
    r"\btitulo internacional\b",
    r"\bpadel\b",
    r"\bpádel\b",
    r"\bmilan open\b",
    r"\balemania open\b",
    r"\bchallenger\b",
    r"\bvillena\b",
    r"liga guerreras iberdrola",
    r"test match",
    r"\bgolf\b",
    r"\blpga\b",
    r"\bdp world\b",
    r"\bciclismo\b",
    r"\beneco tour\b",
    r"\btour de holanda\b",
    r"\btour of holland\b",
    r"\btour of the netherlands\b",
    r"\bsimac ladies tour\b",
    r"\bclasica del veneto\b",
    r"\bveneto\b",
    r"\bcampeonato mundo pista\b",
    r"\bbalonmano\b",
    r"\basobal\b",
    r"\bfrauen[\s\-]*bundesliga\b",
    r"\bbundesliga femenina\b",
    r"\b2\.?\s*bundesliga\b",
    r"\bworldwcr\b",
    r"\bsportbike\b",
    r"\bsupersport\b",
    r"\bsuperbike\b",
    r"\bmaraton\b",
    r"\bmarathon\b",
    r"\bcross\b",
    r"\brugby\b",
    r"\bcadete\b",
    r"\bsub-17\b",
    r"\beurofeo sub-17\b",
    r"\bveikkausliiga\b",
    r"\bdamallsvenskan\b",
    r"\badmiral bundesliga\b",
    r"\bsuperliga de letonia\b",
    r"\bserie b\b",
    r"\bnfl\b",
    r"\bliga elite\b",
    r"\bjuvenil\b",
    r"\bsenior\b",
    r"\bchampions cup\b",
    r"\b3\.?\s*liga\b",
    r"\bliga polaca\b",
    r"\bnwsl\b",
    r"\blvbp\b",
    r"\bliga sudamericana\b",
    r"\bliga premier islandia\b",
    r"\bcopa libertadores femenina\b",
    r"\bd1 feminine\b",
    r"d1 féminine",
    r"nascar cup series"
)

WOMEN_FOOTBALL_COMPETITIONS = (
    (rx(r"\bliga f\b", r"\bprimera division femenina\b"), "Liga F"),
    (rx(r"\bcopa de la reina\b"), "Copa de la Reina"),
    (rx(r"\bsupercopa de espana femenina\b", r"\bsupercopa femenina\b"), "Supercopa de España Femenina"),
    (rx(r"\bwomen'?s champions league\b", r"\bchampions league femenina\b"), "UEFA Women's Champions League"),
)

MEN_FOOTBALL_COMPETITIONS = (
    (rx(r"\blaliga ea sports\b", r"\blaliga ea\b", r"\bprimera division\b", r"\blaliga(?![\s\-]*(?:hypermotion|smartbank|tv hypermotion|123))\b"), "LaLiga"),
    (HYPERMOTION_RE, "LaLiga Hypermotion"),
    (rx(r"\bligue 1\b"), "Ligue 1"),
    (rx(r"\bpremier league\b", r"\bpremier\b"), "Premier League"),
    (rx(r"\bbundesliga\b"), "Bundesliga"),
    (rx(r"\bserie a\b"), "Serie A"),
    (rx(r"\bcopa del rey\b"), "Copa del Rey"),
    (rx(r"\bsupercopa de espana\b"), "Supercopa de España"),
    (rx(r"\bchampions league\b", r"\bchampions\b"), "UEFA Champions League"),
    (rx(r"\bsupercopa de la uefa\b", r"\bsupercopa uefa\b", r"\bsupercopa de europa\b"), "Supercopa de la UEFA"),
    (rx(r"\bcopa intercontinental\b", r"\bintercontinental\b"), "Copa Intercontinental de la FIFA"),
    (rx(r"\bmundial de clubes\b", r"\bclub world cup\b"), "Mundial de Clubes"),
    (rx(r"\bserie a brasil\b", r"\bbrasileirao\b"), "Serie A Brasil"),
)

BASKETBALL_CHAMPIONS_LEAGUE_RE = rx(
    r"\bbasketball champions league\b",
    r"\bnanterre 92\b", r"\brytas vilnius\b",
    r"\bpallacanestro varese\b", r"\bperisteri(?: bc| betsson)?\b",
    r"\balba berlin\b", r"\b(?:kk )?igokea(?: m:tel)?\b",
    r"\bbamberg baskets\b", r"\bucam murcia\b",
    r"\bbilbao basket\b", r"\bslavia prague(?: era nbk)?\b",
    r"\bsurne bilbao\b", r"\bcholet basket\b",
    r"\bhapoel holon\b", r"\bspartak office shoes\b",
    r"\bsig strasbourg\b", r"\bcibona\b",
    r"\blegia warszawa\b", r"\bgalatasaray mct technic\b",
    r"\baek bc\b", r"\bfalco kc szombathely\b",
    r"\bwindrose giants antwerp\b", r"\bfc porto\b",
    r"\bjuventus utena\b", r"\bbk kvis pardubice\b",
    r"\bpallacanestro reggiana\b", r"\bbnei penlink herzliya\b",
    r"\btrabzonspor\b", r"\bsabah bc\b",
    r"\btelekom baskets bonn\b", r"\basisa joventut\b",
    r"\brasta vechta\b", r"\bbma365 bamberg baskets\b",
)

EUROLEAGUE_WOMEN_RE = rx(
    r"\beuroliga femenina\b",
    r"\beuroliga femenino\b",
    r"\beuroleague women\b",
    r"\bwomen'?s euroleague\b",
    r"\beuroliga f\b",
)

BASKET_COMPETITIONS = (
    (rx(r"\bbasketball champions league\b"), "Basketball Champions League"),
    (rx(r"\bliga endesa\b", r"\bacb\b"), "Liga Endesa"),
    (rx(r"\bcopa del rey\b", r"\bcopa acb\b"), "Copa del Rey"),
    (rx(r"\bsupercopa endesa\b", r"\bsupercopa de espana\b"), "Supercopa de España"),
    (EUROLEAGUE_WOMEN_RE, "Euroliga Femenina"),
    (rx(r"\beuroliga\b", r"\beuroleague\b", r"\beuro league\b"), "Euroliga"),
)

TENNIS_COMPETITIONS = (
    (rx(r"\bmasters de shanghai\b", r"\bmasters shanghai\b", r"\bshanghai\b"), "Masters de Shanghái"),
    (rx(r"\bchina open\b", r"\bbeijing\b", r"\bpekin\b", r"\btorneo de pekin\b"), "China Open"),
    (rx(r"\btorneo de tokio\b", r"\btokio\b", r"\btokyo\b", r"\bjapan open\b"), "Japan Open"),
    (rx(r"\blaver cup\b"), "Laver Cup"),
    (rx(r"\bcopa davis\b", r"\bdavis cup\b", r"\bdavis\b"), "Copa Davis"),
    (rx(r"\bbillie jean king cup\b"), "Billie Jean King Cup"),
    (rx(r"\bus open\b"), "US Open"),
    (rx(r"\bwimbledon\b"), "Wimbledon"),
    (rx(r"\broland garros\b"), "Roland Garros"),
    (rx(r"\bopen de australia\b"), "Open de Australia"),
)

GENERIC_TOURNAMENTS = frozenset({
    "", "competicion", "futbol", "baloncesto", "basket", "tenis",
    "atp", "wta", "ciclismo", "motor",
})

EXCLUDED_CHANNELS_RE = rx(*(re.escape(channel) for channel in EXCLUDED_CHANNELS))

def channel_key(value: str) -> str:
    """Clave comparable de canal: ignora acentos, espacios y signos."""
    return re.sub(r"[^a-z0-9]+", "", normalize_search_text(value))


EXCLUDED_CHANNEL_KEYS = {channel_key(channel) for channel in EXCLUDED_CHANNELS}


def is_excluded_channel(channel: str) -> bool:
    key = channel_key(channel)
    if not key:
        return True
    return any(key == excluded or key.startswith(excluded)
               for excluded in EXCLUDED_CHANNEL_KEYS)



def contains(pattern: re.Pattern, text: str) -> bool:
    return bool(pattern.search(text))


def is_excluded_basketball_champions_league(blob: str) -> bool:
    return bool(BASKETBALL_CHAMPIONS_LEAGUE_RE.search(normalize_search_text(blob)))


def is_excluded_event(blob: str) -> bool:
    normalized = normalize_search_text(blob)

    # Competiciones que no deben aparecer en la agenda.
    # Primera Federación solo se permite cuando participa el Real Madrid Castilla.
    excluded_competitions = (
        r"\b1[ªa]?\s*division\s*[-–—]\s*femenin",
        r"\bprimera division femenina\b",
        r"\bliga f\b",
        r"\bliga femenina(?: endesa)?\b",
        r"\bliga femenina endesa\b",
        r"\beredivisie\s*[-–—]?\s*femenin",
        r"\beredivisie vrouwen\b",
    )
    if any(re.search(pattern, normalized, re.IGNORECASE) for pattern in excluded_competitions):
        return True

    is_primera_federacion = bool(
        re.search(r"\bprimera federacion\b|\bprimera rfef\b|\b1[ªa]\s*federacion\b", normalized)
    )
    has_real_madrid_castilla = bool(
        re.search(r"\breal madrid castilla\b|\brm castilla\b", normalized)
    )
    if is_primera_federacion and not has_real_madrid_castilla:
        return True

    return bool(
        EXCLUDED_SPORTS_RE.search(normalized)
        or EXCLUDED_BLOB_RE.search(normalized)
        or is_excluded_basketball_champions_league(normalized)
    )


def clean_tournament(raw: str, fallback: str) -> str:
    value = (raw or "").strip()
    norm_val = normalize_search_text(value)
    if len(norm_val) > 2 and norm_val not in GENERIC_TOURNAMENTS:
        return value
    return fallback


def classify_tennis(blob: str, raw_tournament: str, tv_blob: str) -> str:
    tennis_text = normalize_search_text(f"{blob} {raw_tournament} {tv_blob}")
    tour = "WTA" if "wta" in tennis_text else "ATP"

    for pattern, comp_name in TENNIS_COMPETITIONS:
        if pattern.search(tennis_text):
            return f"{tour} {comp_name}"

    return clean_tournament(raw_tournament, f"{tour} Tour")


def time_to_minutes(time_str: str) -> int:
    try:
        parts = time_str.strip().split(":")
        return int(parts[0]) * 60 + int(parts[1])
    except (AttributeError, ValueError, IndexError):
        return 0


def classify_motor_sessions(events_list: list[dict]):
    groups = {}
    current_weekday = datetime.now().weekday()
    for ev in events_list:
        if ev["deporte"] != "Motor":
            continue
        base_comp = ev["competicion"]
        for key_prefix in ["Fórmula 1", "MotoGP", "Indycar", "Formula E"]:
            if base_comp.startswith(key_prefix):
                base_comp = key_prefix
                break
        
        clean_gp_name = MOTOR_GROUP_CLEAN_RE.sub("", ev["evento"]).strip()
        if not clean_gp_name:
            clean_gp_name = ev["evento"]

        key = (base_comp, clean_gp_name)
        if key not in groups:
            groups[key] = []
        groups[key].append(ev)

    for key, group in groups.items():
        comp_base, _ = key
        group.sort(key=lambda x: time_to_minutes(x["hora"]))
        total_sessions = len(group)
        for idx, ev in enumerate(group):
            session_name = ""
            ev_lower = normalize_search_text(ev["evento"])
            event_time_min = time_to_minutes(ev["hora"])

            if "carrera" in ev_lower or "race" in ev_lower:
                session_name = "Carrera Principal"
            elif "warm up" in ev_lower or "warm-up" in ev_lower:
                session_name = "Warm Up"
            elif "sprint" in ev_lower:
                session_name = "Carrera Sprint"
            elif "clasificacion" in ev_lower or "qualifying" in ev_lower or "q1" in ev_lower or "q2" in ev_lower:
                session_name = "Clasificación"
            
            if not session_name:
                if comp_base == "MotoGP":
                    if current_weekday == 6:
                        if event_time_min < 300 and total_sessions > 1 and idx == 0:
                            session_name = "Warm Up"
                        else:
                            session_name = "Carrera Principal"
                    elif current_weekday == 5:
                        if idx == 0 and total_sessions > 2: session_name = "Libres 2 (FP2)"
                        elif idx == 1 or (idx == 0 and total_sessions == 2): session_name = "Clasificación / Clasificación Sprint"
                        else: session_name = "Carrera Sprint"
                    else:
                        session_name = "Carrera Principal"

                elif comp_base == "Fórmula 1":
                    if current_weekday == 6:
                        session_name = "Carrera Principal"
                    elif current_weekday == 5:
                        if idx == 0 and total_sessions > 1: session_name = "Libres 3 / Carrera Sprint"
                        else: session_name = "Clasificación"
                    else:
                        if total_sessions == 1:
                            session_name = "Carrera Principal"
                        else:
                            if idx == 0:
                                session_name = "Sesión 1"
                            elif idx == 1:
                                session_name = "Sesión 2 / Clasificación Sprint"
                            elif idx == 2:
                                session_name = "Sesión 3 / Carrera Sprint"
                            else:
                                session_name = f"Sesión {idx + 1}"
                else:
                    session_name = "Carrera"

            ev["competicion"] = comp_base
            
            if session_name:
                clean_base_event = MOTOR_EVENT_SUFFIX_RE.sub("", ev["evento"]).strip()
                ev["evento"] = f"{clean_base_event} - {session_name}"

            final_ev_lower = normalize_search_text(ev["evento"])
            if comp_base == "MotoGP":
                is_moto_classification = "clasificacion" in final_ev_lower
                ev["is_filtered"] = (
                    ("sprint" in final_ev_lower or "carrera principal" in final_ev_lower or "carrera" in final_ev_lower)
                    and not is_moto_classification
                )
            elif comp_base == "Fórmula 1":
                ev["is_filtered"] = any(term in final_ev_lower for term in ["sprint", "carrera principal", "carrera", "clasificacion", "shootout"])
            elif comp_base in ["Indycar", "Formula E"]:
                ev["is_filtered"] = "carrera principal" in final_ev_lower or "carrera" in final_ev_lower
            else:
                ev["is_filtered"] = False


def detect_general_sport(blob: str, raw_tournament: str) -> tuple[str, str]:
    text = f"{blob} {raw_tournament}".lower()
    
    if HYPERMOTION_RE.search(text):
        return ("Fútbol", "⚽")
        
    if contains(TENNIS_RE, text) or "tenis" in text:
        return ("Tenis", "🎾")
    if any(term in text for term in ["baloncesto", "basket", "acb", "euroliga", "nba", "euroleague"]):
        return ("Baloncesto", "🏀")
    if any(term in text for term in ["f1", "formula 1", "motogp", "motor", "indycar", "formula e"]):
        return ("Motor", "🏆")
    return ("Fútbol", "⚽")


def get_sport_and_competition(blob: str, raw_tournament: str, tv_blob: str) -> tuple[str, str, str, bool, bool]:
    # 1. Tenis
    if contains(TENNIS_RE, blob) or contains(TENNIS_ALLOWED_PLAYERS_RE, blob):
        if contains(TENNIS_ALLOWED_PLAYERS_RE, blob):
            comp = classify_tennis(blob, raw_tournament, tv_blob)
            is_fav = contains(TENNIS_SPANISH_FAVORITES_RE, blob)
            return ("Tenis", "🎾", comp, is_fav, True)

    # 2. Baloncesto
    if any(p.search(blob) for p, _ in BASKET_COMPETITIONS):
        comp_match = None
        for pattern, name in BASKET_COMPETITIONS:
            if pattern.search(blob):
                comp_match = name
                break
        if comp_match:
            if comp_match not in ["Euroliga Femenina", "Basketball Champions League"]:
                if comp_match not in ["Euroliga", "Liga Endesa"] or contains(BARCA_REAL_RE, blob):
                    is_fav = contains(REAL_MADRID_RE, blob)
                    return ("Baloncesto", "🏀", comp_match, is_fav, True)

    # 3. Fútbol Femenino
    is_women = contains(WOMEN_RE, blob) or any(p.search(blob) for p, _ in WOMEN_FOOTBALL_COMPETITIONS)
    if is_women:
        comp_match = None
        for pattern, name in WOMEN_FOOTBALL_COMPETITIONS:
            if pattern.search(blob) or ("femenina" in blob and name.lower() in blob):
                comp_match = name
                break
        if comp_match and contains(REAL_MADRID_RE, blob):
            return ("Fútbol", "⚽", comp_match, True, True)

    # 4. Primera Federación
    if PRIMERA_RFEF_RE.search(blob) or "primera federacion" in blob or "primera rfef" in blob:
        if contains(CASTILLA_RE, blob):
            return ("Fútbol", "⚽", "Primera Federación", True, True)

    # 5. Fútbol Masculino
    comp_match = None
    for pattern, name in MEN_FOOTBALL_COMPETITIONS:
        if pattern.search(blob):
            comp_match = name
            break
    if comp_match:
        if comp_match == "LaLiga Hypermotion":
            return ("Fútbol", "⚽", "LaLiga Hypermotion", False, False)

        valid = False
        if comp_match == "LaLiga":
            valid = contains(BARCA_REAL_ATLETICO_RE, blob)
        elif comp_match == "Ligue 1":
            valid = contains(PSG_RE, blob)
        elif comp_match == "Premier League":
            valid = contains(ARSENAL_RE, blob)
        elif comp_match == "Bundesliga":
            valid = contains(BAYERN_RE, blob)
        elif comp_match == "Serie A":
            valid = contains(INTER_RE, blob)
        elif comp_match == "Serie A Brasil":
            if any(ch in tv_blob for ch in ["m+ vamos", "movistar", "m+ liga de campeones"]):
                valid = True

        if valid:
            is_fav = contains(REAL_MADRID_RE, blob) or contains(ARSENAL_RE, blob) or ("bahia" in blob and "flamengo" in blob)
            return ("Fútbol", "⚽", comp_match, is_fav, True)

    # 6. Motor
    if contains(MOTOR_GENERAL_RE, blob):
        is_f1 = ("formula 1" in blob or F1_RE.search(blob)) and "academy" not in blob
        is_motogp = "motogp" in blob and not MOTO2_RE.search(blob) and not MOTO3_RE.search(blob) and "rookies" not in blob
        is_indycar = "indycar" in blob or "indy car" in blob
        is_formulae = "formula e" in blob

        if is_f1:
            return ("Motor", "🏆", "Fórmula 1", False, True)
        elif is_motogp:
            return ("Motor", "🏆", "MotoGP", False, True)
        elif is_indycar:
            return ("Motor", "🏆", "Indycar", False, True)
        elif is_formulae:
            return ("Motor", "🏆", "Formula E", False, True)

    sport, icon = detect_general_sport(blob, raw_tournament)
    comp = clean_tournament(raw_tournament, f"{sport} General")
    return (sport, icon, comp, False, False)


# ============================================================================
# PARSER CORREGIDO PARA EVITAR INVERSIÓN
# ============================================================================

def parse_row_elements(item) -> tuple[str, str, list[str], str]:
    text_full = item.get_text(" | ", strip=True)
    time_match = TIME_RE.search(text_full)
    time_clean = time_match.group(0) if time_match else ""

    raw_parts = [
        part.strip()
        for part in item.get_text("\n", strip=True).split("\n")
        if part.strip()
    ]
    if not 2 <= len(raw_parts) <= 25:
        return "", "", [], ""

    channels: list[str] = []
    text_lines = []

    competition_terms = (
        "liga", "primera", "segunda", "tercera", "federacion",
        "division", "grupo", "torneo", "serie a", "premier",
        "endesa", "bundesliga", "atp", "wta", "masters",
        "copa", "champions", "superbike", "gran premio",
        "gp ", "eredivisie", "euroliga", "euroleague"
    )

    for part in raw_parts:
        part_lower = normalize_search_text(part)
        if TIME_RE.fullmatch(part) or part_lower in {
            "ver partido", "directo", "(ver en directo)", "ver gratis",
            "(ver)", "acceder", "(acceder)"
        }:
            continue
        if re.fullmatch(r"[\s,.|;:/-]*", part):
            continue
        if re.fullmatch(r"\(?[mo]\+?\d+.*\)?", part_lower):
            continue

        looks_like_channel = (
            TV_IDENTIFIERS_RE.search(part)
            or CHANNEL_LINE_RE.search(part_lower)
            or any(term in part_lower for term in (
                "m+", "dazn", "youtube", "fanatiz", "onefootball",
                "siroko", "tv footballclub", "aragon tv", "aragon play",
                "cmmplay", "etb1", "tvg", "tv3", "hbo max"
            ))
        )
        if looks_like_channel:
            clean_part = CLEAN_TV_RE.sub("", part).strip()
            clean_part = re.sub(r"\(m\d+[^)]*\)", "", clean_part, flags=re.IGNORECASE).strip()
            for channel in clean_part.split(","):
                channel = channel.strip().rstrip(":").strip()
                channel_lower = normalize_search_text(channel)
                if (
                    channel
                    and not is_excluded_channel(channel)
                    and channel not in channels
                    and not re.fullmatch(r"\(?[mo]\+?\d+.*\)?", channel_lower)
                    and channel_lower not in {"acceder", "(acceder)", "ver en directo"}
                ):
                    channels.append(channel)
            continue

        text_lines.append(part)

    # Los guiones de "España - 1ª División - Femenino" son competición,
    # no un enfrentamiento entre equipos.
    tournament_candidates = []
    matchup_candidates = []
    for part in text_lines:
        part_lower = normalize_search_text(part)
        is_competition_line = any(term in part_lower for term in competition_terms)
        has_match_separator = bool(
            re.search(r"\s+-\s+|\s+vs\.?\s+|\s+v\.\s+", part, re.IGNORECASE)
            or re.search(r"\s\(f\)\s*-\s*", part, re.IGNORECASE)
        )
        if is_competition_line:
            tournament_candidates.append(part)
        elif has_match_separator and len(part.split()) >= 3:
            matchup_candidates.append(part)

    matchup = matchup_candidates[0] if matchup_candidates else ""
    tournament = tournament_candidates[0] if tournament_candidates else ""

    if not matchup:
        matchup = next((part for part in text_lines if part != tournament), "")
    if not tournament:
        tournament = next((part for part in text_lines if part != matchup), "")

    if not matchup and tournament:
        matchup, tournament = tournament, "General"
    elif matchup and not tournament:
        tournament = "General"

    return time_clean, matchup, channels, tournament


def fetch_and_parse_agenda() -> list[dict]:
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

                if is_excluded_basketball_champions_league(
                    f"{event_str} {tournament}"
                ):
                    continue

                if not EVENT_TEXT_RE.search(event_str):
                    continue

                if not channels:
                    continue

                tv_blob = " ".join(channels).lower()
                blob = normalize_search_text(f"{event_str} {tournament} {tv_blob}")

                if is_excluded_event(blob): continue

                event_key = (time_clean, normalize_search_text(tournament) if tournament else normalize_search_text(event_str), normalize_search_text(event_str))
                if event_key in seen_events: continue
                seen_events.add(event_key)

                sport, icon, competition, is_favorite, is_configured = get_sport_and_competition(blob, tournament, tv_blob)

                results.append({
                    "hora": time_clean,
                    "deporte": sport,
                    "icono": icon,
                    "competicion": competition,
                    "evento": event_str,
                    "tv_list": channels,
                    "is_filtered": is_favorite,
                    "is_configured": is_configured,
                })
            except Exception:
                continue
        
        classify_motor_sessions(results)

    except Exception as e:
        print(f"Error cargando la agenda: {e}")

    return results


# ============================================================================
# GENERACIÓN DE HTML
# ============================================================================

def generate_html(events):
    spain_tz = zoneinfo.ZoneInfo("Europe/Madrid")
    fecha_act = datetime.now(spain_tz).strftime("%d/%m/%Y - %H:%M")
    
    total_cnt = len(events)
    filtered_cnt = sum(1 for event in events if event["is_filtered"])
    sport_counts = Counter(event["deporte"] for event in events if event["is_configured"])

    def clean_key(s):
        return normalize_search_text(s)

    rows_list = []
    if not events:
        rows_list.append('<tr><td colspan="6" class="empty-state">😴 No hay eventos disponibles en este momento.</td></tr>')
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
                        is_dlive = "dlive.sx" in urls[0]
                        css_cls = "tv-badge alt-link" if is_dlive else "tv-badge"
                        tv_badges_list.append(
                            f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" '
                            f'class="{css_cls}" title="Abrir canal {safe_channel}">'
                            f'{safe_channel} 🔗</a>'
                        )
                else:
                    tv_badges_list.append(
                        f'<span class="tv-badge alt-link" style="cursor:default;" title="Canal sin enlace">'
                        f'{safe_channel}</span>'
                    )

            tv_badges = "".join(tv_badges_list)
            search_text = normalize_search_text(" ".join(
                [ev["hora"], ev["deporte"], ev["competicion"], ev["evento"], *ev["tv_list"]]
            ))
            safe_search = escape(search_text, quote=True)
            safe_sport_key = escape(clean_key(ev["deporte"]), quote=True)
            safe_time = escape(str(ev["hora"]))
            safe_icon = escape(str(ev["icono"]))
            safe_sport = escape(str(ev["deporte"]))
            safe_competition = escape(str(ev["competicion"]))
            safe_event = escape(str(ev["evento"]))

            rows_list.append(
                f"""
                <tr class="event-row" data-sport="{safe_sport_key}" data-filtered="{str(ev['is_filtered']).lower()}" data-configured="{str(ev['is_configured']).lower()}" data-search="{safe_search}">
                    <td class="date-col"><span class="date-badge today">Hoy</span></td>
                    <td class="time-col"><span class="time-badge">{safe_time}</span></td>
                    <td class="sport-col"><span class="sport-tag">{safe_icon} {safe_sport}</span></td>
                    <td class="comp-col"><div class="comp-title">{safe_competition}</div></td>
                    <td class="event-col"><div class="event-title">{safe_event}</div></td>
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
    <title>Agenda Deportiva - Hoy</title>
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
    <style>
        :root {{ --bg-color: #0f172a; --card-bg: #1e293b; --border-color: #334155; --text-main: #f8fafc; --text-muted: #94a3b8; --accent-blue: #3b82f6; }}
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{ font-family: 'Inter', sans-serif; background-color: var(--bg-color); color: var(--text-main); padding: 16px 12px; display: flex; justify-content: center; }}
        .container {{ width: 100%; max-width: 1150px; }}
        header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; padding-bottom: 10px; border-bottom: 1px solid var(--border-color); flex-wrap: wrap; gap: 8px; }}
        h1 {{ font-size: 1.5rem; font-weight: 800; background: linear-gradient(135deg, #60a5fa, #a78bfa); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
        .header-controls {{ display: flex; gap: 10px; align-items: center; flex-wrap: wrap; }}
        .btn-update {{ background: #10b981; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; transition: all 0.2s; }}
        .btn-alt {{ background: #6366f1; color: white; border: none; padding: 6px 14px; border-radius: 8px; font-weight: 600; cursor: pointer; font-size: 0.85rem; text-decoration: none; transition: all 0.2s; display: inline-flex; align-items: center; }}
        .btn-alt:hover {{ background: #4f46e5; }}
        .last-update {{ font-size: 0.75rem; color: var(--text-muted); background: var(--card-bg); padding: 4px 10px; border-radius: 20px; border: 1px solid var(--border-color); width: 100%; text-align: right; }}
        
        .stats-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(100px, 1fr)); gap: 8px; margin-bottom: 16px; }}
        .stat-card {{ background: var(--card-bg); padding: 8px 10px; border-radius: 10px; border: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center; cursor: pointer; transition: all 0.2s ease; }}
        .stat-card.active-card {{ border-color: var(--accent-blue); background: rgba(59, 130, 246, 0.15); box-shadow: 0 0 10px rgba(59, 130, 246, 0.2); }}
        .stat-card .val {{ font-size: 1.1rem; font-weight: 700; color: var(--accent-blue); }}
        .stat-card .lbl {{ font-size: 0.72rem; color: var(--text-muted); }}
        
        .filter-container {{ display: flex; gap: 10px; margin-bottom: 14px; }}
        .search-input {{ padding: 10px 14px; border-radius: 8px; background: var(--card-bg); border: 1px solid var(--border-color); color: var(--text-main); font-size: 0.9rem; outline: none; width: 100%; }}
        .search-input:focus {{ border-color: var(--accent-blue); }}
        
        .table-card {{ background: var(--card-bg); border-radius: 12px; border: 1px solid var(--border-color); overflow: visible !important; box-shadow: 0 10px 25px -5px rgba(0, 0, 0, 0.3); margin-bottom: 80px; }}
        table {{ width: 100%; border-collapse: collapse; text-align: left; table-layout: fixed; }}
        th {{ background: #111827; color: var(--text-muted); font-weight: 600; font-size: 0.75rem; text-transform: uppercase; padding: 12px 10px; border-bottom: 1px solid var(--border-color); }}
        td {{ padding: 12px 10px; border-bottom: 1px solid #283548; font-size: 0.88rem; word-break: break-word; }}
        tr.event-row:hover {{ background-color: #243146; }}
        
        .sport-col {{ width: 155px !important; min-width: 155px !important; white-space: nowrap; }}
        .time-col, .date-col {{ white-space: nowrap; }}
        .sport-tag {{ font-weight: 600; white-space: nowrap; }}
        .date-badge {{ display: inline-block; background: #334155; color: #f8fafc; font-weight: 600; padding: 4px 8px; border-radius: 6px; font-size: 0.75rem; white-space: nowrap; }}
        .date-badge.today {{ background: rgba(59, 130, 246, 0.2); color: #60a5fa; border-color: rgba(59, 130, 246, 0.5); }}
        .time-badge {{ background: #0284c7; color: white; font-weight: 700; padding: 4px 8px; border-radius: 6px; font-size: 0.85rem; white-space: nowrap; display: inline-block; }}
        .comp-title {{ font-weight: 600; color: #38bdf8; font-size: 0.85rem; }}
        .event-title {{ font-weight: 700; color: #ffffff; font-size: 0.9rem; }}
        .tv-container {{ display: flex; flex-direction: column; gap: 4px; }}
        
        .tv-badge {{ display: inline-block; background: rgba(99, 102, 241, 0.15); color: #818cf8; border: 1px solid rgba(99, 102, 241, 0.3); padding: 3px 7px; border-radius: 5px; font-size: 0.75rem; font-weight: 600; word-break: break-word; white-space: normal; text-decoration: none; transition: all 0.2s ease; cursor: pointer; }}
        .tv-badge:hover {{ background: rgba(99, 102, 241, 0.35); color: #a5b4fc; border-color: #818cf8; transform: translateY(-1px); }}

        .alt-link {{ background: rgba(16, 185, 129, 0.15); color: #34d399; border-color: rgba(16, 185, 129, 0.3); }}
        .alt-link:hover {{ background: rgba(16, 185, 129, 0.35); color: #6ee7b7; border-color: #34d399; }}

        .dropdown-tv {{ position: relative; display: inline-block; }}
        .tv-dropdown-btn {{ background: rgba(99, 102, 241, 0.2); color: #a5b4fc; border: 1px solid rgba(99, 102, 241, 0.4); text-align: left; width: 100%; }}
        .dropdown-content {{ 
            display: none; 
            position: absolute; 
            background-color: #111827; 
            min-width: 200px; 
            box-shadow: 0px 8px 16px 0px rgba(0,0,0,0.5); 
            z-index: 1000; 
            border: 1px solid var(--border-color); 
            border-radius: 8px; 
            padding: 4px 0; 
            left: 0; 
            top: 100%; 
        }}
        .dropdown-tv.dropup .dropdown-content {{
            top: auto;
            bottom: 100%;
            margin-bottom: 4px;
        }}
        .dropdown-content a {{ color: #f8fafc; padding: 8px 12px; text-decoration: none; display: block; font-size: 0.78rem; transition: background 0.2s; }}
        .dropdown-content a:hover {{ background-color: #1e293b; color: #60a5fa; }}
        .dropdown-tv.show .dropdown-content {{ display: block; }}

        .empty-state {{ text-align: center; padding: 30px; color: var(--text-muted); font-size: 1rem; }}

        @media screen and (max-width: 768px) and (orientation: portrait) and (pointer: coarse) {{
            body {{ padding: 8px 6px; }}
            h1 {{ font-size: 1.25rem; }}
            .stats-grid {{ grid-template-columns: repeat(3, 1fr); gap: 6px; }}
            .stat-card {{ padding: 6px 8px; }}
            
            thead {{ display: none; }}
            table, tbody {{ display: block; width: 100%; }}
            .table-card {{ background: transparent; border: none; box-shadow: none; }}
            
            tr.event-row {{
                display: flex;
                flex-direction: column;
                background: var(--card-bg);
                border: 1px solid var(--border-color);
                border-radius: 12px;
                padding: 12px;
                margin-bottom: 10px;
                gap: 6px;
            }}
            
            td {{ padding: 0; border: none; width: auto !important; white-space: normal; }}
            .date-col {{ display: none; }}
            .time-col {{ order: 1; display: inline-block; }}
            .sport-col {{ order: 2; margin-left: 8px; display: inline-block; font-size: 0.95rem; width: auto !important; min-width: 0 !important; }}
            .comp-col {{ order: 3; margin-top: 4px; }}
            .comp-title {{ font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.5px; }}
            .event-col {{ order: 4; margin: 2px 0 4px 0; }}
            .event-title {{ font-size: 1rem; line-height: 1.35; }}
            .tv-col {{ order: 5; margin-top: 4px; border-top: 1px solid rgba(255,255,255,0.05); padding-top: 6px; }}
            .tv-badge {{ font-size: 0.72rem; padding: 4px 8px; }}
        }}
    </style>
</head>
<body>
<div class="container">
    <header>
        <div><h1>⚡ Agenda Deportiva - Hoy</h1></div>
        <div class="header-controls">
            <a href="https://hubu.ru/fctvlink" target="_blank" class="btn-alt">FCTV33</a>
            <a href="https://daddylive.pk/" target="_blank" class="btn-alt">DLHD</a>
            <button class="btn-update" onclick="location.reload()">🔄 Actualizar</button>
        </div>
        <div class="last-update">Última actualización: <strong>{fecha_act} (España)</strong></div>
    </header>
    <div class="stats-grid">
        <div class="stat-card active-card" id="card-todos" onclick="setFilter('todos')">
            <div><div class="lbl">Todos</div><div class="val">{total_cnt}</div></div><div style="font-size:1.1rem">📺</div>
        </div>
        <div class="stat-card" id="card-favoritos" onclick="setFilter('favoritos')">
            <div><div class="lbl">Favoritos</div><div class="val" style="color:#a78bfa">{filtered_cnt}</div></div><div style="font-size:1.1rem">📌</div>
        </div>
        <div class="stat-card" id="card-futbol" onclick="setFilter('futbol')">
            <div><div class="lbl">Fútbol</div><div class="val" style="color:#10b981">{sport_counts['Fútbol']}</div></div><div style="font-size:1.1rem">⚽</div>
        </div>
        <div class="stat-card" id="card-baloncesto" onclick="setFilter('baloncesto')">
            <div><div class="lbl">Baloncesto</div><div class="val" style="color:#f97316">{sport_counts['Baloncesto']}</div></div><div style="font-size:1.1rem">🏀</div>
        </div>
        <div class="stat-card" id="card-tenis" onclick="setFilter('tenis')">
            <div><div class="lbl">Tenis</div><div class="val" style="color:#f59e0b">{sport_counts['Tenis']}</div></div><div style="font-size:1.1rem">🎾</div>
        </div>
        <div class="stat-card" id="card-motor" onclick="setFilter('motor')">
            <div><div class="lbl">Motor</div><div class="val" style="color:#ef4444">{sport_counts['Motor']}</div></div><div style="font-size:1.1rem">🏆</div>
        </div>
    </div>
    <div class="filter-container">
        <input type="text" id="searchInput" class="search-input" onkeyup="filterTable()" placeholder="🔍 Filtrar partido, equipo, tenista o canal TV...">
    </div>
    <div class="table-card">
        <table>
            <thead>
                <tr>
                    <th class="date-col" style="width: 70px;">Fecha</th>
                    <th class="time-col" style="width: 70px;">Hora</th>
                    <th class="sport-col" style="width: 155px;">Deporte</th>
                    <th class="comp-col" style="width: 140px;">Competición</th>
                    <th>Evento</th>
                    <th style="width: 210px;">Canal TV</th>
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
    
    document.querySelectorAll('.dropdown-tv').forEach(item => {{
        if (item !== dropdown) {{
            item.classList.remove('show', 'dropup');
        }}
    }});

    const rect = btn.getBoundingClientRect();
    const spaceBelow = window.innerHeight - rect.bottom;
    
    if (spaceBelow < 160) {{
        dropdown.classList.add('dropup');
    }} else {{
        dropdown.classList.remove('dropup');
    }}

    dropdown.classList.toggle('show');
}}

window.onclick = function(event) {{
    if (!event.target.matches('.tv-dropdown-btn')) {{
        document.querySelectorAll('.dropdown-tv').forEach(item => {{
            item.classList.remove('show', 'dropup');
        }});
    }}
}}

let currentFilter = 'todos';

function setFilter(filterType) {{
    currentFilter = cleanStr(filterType);
    document.querySelectorAll('.stat-card').forEach(card => card.classList.remove('active-card'));
    const activeCard = document.getElementById('card-' + currentFilter);
    if (activeCard) activeCard.classList.add('active-card');
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

        const rowSport = cleanStr(tr.getAttribute('data-sport'));
        const isFiltered = tr.getAttribute('data-filtered') === 'true';
        const isConfigured = tr.getAttribute('data-configured') === 'true';
        const text = cleanStr(tr.getAttribute('data-search'));

        let matchesFilter = false;
        if (currentFilter === 'todos') {{
            matchesFilter = true;
        }} else if (currentFilter === 'favoritos') {{
            matchesFilter = isFiltered;
        }} else {{
            matchesFilter = (rowSport === currentFilter && isConfigured);
        }}

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
    print(f"Archivo index.html generado con éxito. Eventos encontrados: {len(events)}")
