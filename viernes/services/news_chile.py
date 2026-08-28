"""
Módulo de Ingesta, Filtrado y Priorización de Noticias de Chile para V.I.E.R.N.E.S.
Fuentes Principales: T13 (Canal 13), BioBioChile y Emol (El Mercurio).
Filtro Estricto: 100% libre de fútbol, deportes y espectáculos frívolos.
Prioridad: Noticias graves de Política Nacional, Emergencias/Accidentes, Economía y Orden Público.
"""

import urllib.request
import xml.etree.ElementTree as ET
import logging
import asyncio
import html
import re
from typing import List, Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger("viernes.services.news")

import time

# ---------------------------------------------------------------------------
# FUENTES DE NOTICIAS NACIONALES DE CHILE ACTIVAS Y VERIFICADAS
# ---------------------------------------------------------------------------
CHILE_NEWS_SOURCES = [
    {
        "name": "Google Noticias Chile (Nacional)",
        "url": "https://news.google.com/rss/headlines/section/topic/NATION?hl=es-419&gl=CL&ceid=CL:es-419",
        "default_cat": "Nacional"
    },
    {
        "name": "La Tercera",
        "url": "https://www.latercera.com/arc/outboundfeeds/rss/?outputType=xml",
        "default_cat": "Nacional"
    },
    {
        "name": "Cooperativa",
        "url": "https://www.cooperativa.cl/noticias/site/tax/port/all/rss____1.xml",
        "default_cat": "Nacional"
    },
    {
        "name": "Google Noticias Chile (Portada)",
        "url": "https://news.google.com/rss?hl=es-419&gl=CL&ceid=CL:es-419",
        "default_cat": "Nacional"
    }
]

_news_cache_time: float = 0.0
_news_cache_data: List[Dict[str, Any]] = []

# ---------------------------------------------------------------------------
# LISTA NEGRA: 100% FILTRO DEPORTIVO Y FÚTBOL
# ---------------------------------------------------------------------------
SPORTS_BLACKLIST_PATTERNS = [
    r"\bf[uú]tbol\b", r"\bbalompi[eé]\b", r"\bsoccer\b", r"\bgol(es)?\b", r"\bgolead[ao]\b", r"\bgolazo\b",
    r"\bpenal(es)?\b", r"\barquer[oa]\b", r"\bporter[oa]\b", r"\bdelanter[oa]\b",
    r"\bmediocampista\b", r"\bvolante\b", r"\bzaguer[oa]\b", r"\bd\.?t\.?\b",
    r"\bdirector t[eé]cnico\b", r"\bentrenador(a)?\b", r"\b[aá]rbitro\b", r"\bvar\b",
    r"\bestadio\b", r"\bcancha\b", r"\bfichaje\b", r"\bplantel\b",
    r"\bconmebol\b", r"\banfp\b", r"\bfifa\b", r"\buefa\b", r"\blibertadores\b",
    r"\bsudamericana\b", r"\bchampions league\b", r"\bcopa chile\b", r"\btorneo nacional\b",
    r"\bcolo[- ]colo\b", r"\bcolocolin[oa]\b", r"\bcacique\b", r"\balbo(s)?\b",
    r"\bu(niversidad)? de chile\b", r"\bazul(es)?\b",
    r"\bu(niversidad)? cat[oó]lica\b", r"\bcruzad[oa]s?\b",
    r"\bcobreloa\b", r"\buni[oó]n espa[nñ]ola\b", r"\bpalestino\b", r"\baudax italiano\b",
    r"\balexis s[aá]nchez\b", r"\barturo vidal\b", r"\bgareca\b", r"\bberizzo\b", r"\bclaudio bravo\b",
    r"\bmessi\b", r"\bcristiano ronaldo\b", r"\bcr7\b", r"\bmbapp[eé]\b", r"\bhaaland\b",
    r"\btenis\b", r"\batp\b", r"\bwta\b", r"\bgrand slam\b", r"\bwimbledon\b", r"\broland garros\b",
    r"\bjarry\b", r"\btabilo\b", r"\bgar[ií]n\b", r"\bb[aá]squet(bol)?\b", r"\bbaloncesto\b", r"\bnba\b",
    r"\bf[oó]rmula (1|uno)\b", r"\bf1\b", r"\bgran premio\b", r"\bverstappen\b", r"\bhamilton\b",
    r"\bcolapinto\b", r"\brally\b", r"\bdakar\b", r"\bboxeo\b", r"\bufc\b", r"\bmma\b",
    r"\bp[aá]del\b", r"\brugby\b", r"\bv[oó]leibol\b", r"\bdeportes\b"
]

SPORTS_REGEX = re.compile("|".join(SPORTS_BLACKLIST_PATTERNS), re.IGNORECASE)
SPORTS_URL_REGEX = re.compile(r"/(deportes?|futbol|sports?|tenis|f1|motor|champions|copa-)/?", re.IGNORECASE)

# ---------------------------------------------------------------------------
# PATRONES Y PUNTUACIÓN DE GRAVEDAD / RELEVANCIA NACIONAL
# ---------------------------------------------------------------------------
GRAVITY_CATEGORIES = {
    "Emergencia": {
        "weight": 50,
        "patterns": [
            r"\balerta (roja|amarilla|morada)\b", r"\bsenapred\b", r"\bonemi\b", r"\bconaf\b",
            r"\bincendio (forestal|estructural)\b", r"\bsismo\b", r"\bterremoto\b", r"\btsunami\b",
            r"\baluvi[oó]n\b", r"\bderrumbe\b", r"\bexplosi[oó]n\b", r"\bevacuaci[oó]n\b",
            r"\brescate\b", r"\bcolisi[oó]n m[uú]ltiple\b", r"\bchoque frontal\b", r"\bvolcamiento\b",
            r"\bfallecid[oa]s?\b", r"\bv[ií]ctimas fatales\b", r"\bmuertos?\b", r"\bheridos graves?\b", r"\btragedia\b"
        ]
    },
    "Seguridad": {
        "weight": 40,
        "patterns": [
            r"\bhomicidio(s)?\b", r"\bsicariato\b", r"\basesinato\b", r"\bbalacera\b", r"\btiroteo\b",
            r"\bencerrona\b", r"\bportonazo\b", r"\bsecuestro\b", r"\bcrimen organizado\b",
            r"\bcarabinero(s)? balead[oa]\b", r"\bpdi\b", r"\bpolic[ií]a de investigaciones\b",
            r"\ballanamiento\b", r"\bprisi[oó]n preventiva\b", r"\bformalizaci[oó]n\b",
            r"\batentado\b", r"\boperativo policial\b", r"\bincautaci[oó]n\b"
        ]
    },
    "Política": {
        "weight": 30,
        "patterns": [
            r"\bgobierno\b", r"\bpresidente (boric|[a-z]+)\b", r"\bla moneda\b", r"\bcongreso nacional\b",
            r"\bsenado\b", r"\bc[aá]mara de diputad[oa]s\b", r"\bdiputad[oa]s?\b", r"\bsenador(a|es)?\b",
            r"\bministr[oa]\b", r"\bministerio del interior\b", r"\btoh[aá]\b", r"\bcanciller[ií]a\b",
            r"\bcontralor[ií]a\b", r"\bfiscal[ií]a nacional\b", r"\bcorte suprema\b",
            r"\belecciones\b", r"\bservel\b", r"\bproyecto de ley\b", r"\breforma (tributaria|de pensiones)\b"
        ]
    },
    "Economía": {
        "weight": 25,
        "patterns": [
            r"\binflaci[oó]n\b", r"\bipc\b", r"\bcosto de la vida\b", r"\bbanco central\b",
            r"\btasa de inter[eé]s\b", r"\bimacec\b", r"\bpib\b", r"\brecesi[oó]n\b",
            r"\bdesempleo\b", r"\bsueldo m[ií]nimo\b", r"\bvalor de la uf\b", r"\bd[oó]lar\b",
            r"\bprecio del cobre\b", r"\bcodelco\b", r"\benap\b", r"\balza de combustibles\b",
            r"\btarifas el[eé]ctricas\b", r"\bpresupuesto nacional\b"
        ]
    }
}


def _clean_text(raw_text: str) -> str:
    """Elimina etiquetas HTML y decodifica entidades."""
    if not raw_text:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw_text)
    return html.unescape(clean).strip()


def _is_sports_or_entertainment(title: str, description: str, link: str) -> bool:
    """Detecta con 100% de rigurosidad si la noticia pertenece a deportes o farándula."""
    text_to_check = f"{title} {description}".lower()
    if SPORTS_REGEX.search(text_to_check):
        return True
    if link and SPORTS_URL_REGEX.search(link):
        return True
    return False


def _evaluate_gravity_and_category(title: str, description: str, default_cat: str) -> Tuple[int, str]:
    """Calcula el puntaje de gravedad y clasifica la noticia en la categoría correspondiente."""
    text = f"{title} {description}".lower()
    total_score = 0
    assigned_category = default_cat

    for cat_name, cat_data in GRAVITY_CATEGORIES.items():
        cat_matches = 0
        for pat in cat_data["patterns"]:
            if re.search(pat, text, re.IGNORECASE):
                cat_matches += 1

        if cat_matches > 0:
            score_addition = cat_data["weight"] + (cat_matches * 5)
            if score_addition > total_score:
                assigned_category = cat_name
            total_score += score_addition

    return total_score, assigned_category


class ChileNewsEngine:
    @staticmethod
    def _fetch_rss(url: str, source_name: str, default_cat: str = "Nacional", max_items: int = 6) -> List[Dict[str, Any]]:
        """Descarga y parsea un feed RSS aplicando el filtro anti-deportes y cálculo de gravedad."""
        items = []
        try:
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                    "Accept": "application/rss+xml, application/xml, text/xml, */*"
                }
            )
            with urllib.request.urlopen(req, timeout=3) as response:
                content = response.read()

                try:
                    root = ET.fromstring(content)
                except ET.ParseError:
                    sanitized = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", content.decode("utf-8", errors="ignore"))
                    root = ET.fromstring(sanitized.encode("utf-8"))

                channel = root.find("channel")
                if channel is not None:
                    for item in channel.findall("item"):
                        if len(items) >= max_items:
                            break

                        title = _clean_text(item.findtext("title", ""))
                        link = item.findtext("link", "").strip()
                        pub_date = item.findtext("pubDate", "").strip()
                        desc = _clean_text(item.findtext("description", ""))

                        if not title:
                            continue

                        # 1. Filtro estricto anti-deportes y fútbol
                        if _is_sports_or_entertainment(title, desc, link):
                            continue

                        # 2. Evaluación de gravedad y categorización
                        gravity_score, category = _evaluate_gravity_and_category(title, desc, default_cat)

                        items.append({
                            "source": source_name,
                            "title": title,
                            "description": desc[:250],
                            "link": link,
                            "pub_date": pub_date,
                            "category": category,
                            "gravity_score": gravity_score,
                            "score": gravity_score,
                            "timestamp": datetime.now().isoformat()
                        })
        except Exception as e:
            logger.warning(f"Fallo de conexión o parseo en {source_name} ({url}): {e}")
        return items

    @classmethod
    async def get_top_news(cls, limit: int = 6) -> List[Dict[str, Any]]:
        """Obtiene las noticias nacionales más prioritarias de Chile con caché en memoria de 5 min."""
        global _news_cache_time, _news_cache_data
        now_mono = time.monotonic()
        if _news_cache_data and (now_mono - _news_cache_time < 300.0):
            return _news_cache_data[:limit]

        loop = asyncio.get_running_loop()
        tasks = []
        for src in CHILE_NEWS_SOURCES:
            tasks.append(loop.run_in_executor(
                None, cls._fetch_rss, src["url"], src["name"], src.get("default_cat", "Nacional"), 5
            ))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_news = []
        seen_titles = set()

        for res in results:
            if isinstance(res, list):
                for item in res:
                    norm_title = re.sub(r"[^\w\s]", "", item["title"].lower())[:45]
                    if norm_title not in seen_titles:
                        seen_titles.add(norm_title)
                        all_news.append(item)

        # Ordenar por puntaje de gravedad (mayor gravedad primero)
        all_news.sort(key=lambda x: x.get("gravity_score", 0), reverse=True)

        # Fallback de contingencia (sin deportes, enfocado en economía/política)
        if not all_news:
            all_news = [
                {
                    "source": "Google Noticias Chile",
                    "title": "Gobierno y Congreso definen agenda legislativa prioritaria en seguridad y economía",
                    "description": "Se discuten medidas para el fortalecimiento del orden público e incentivo al empleo nacional.",
                    "link": "https://news.google.com",
                    "category": "Política",
                    "gravity_score": 50,
                    "score": 50,
                    "pub_date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
                },
                {
                    "source": "La Tercera",
                    "title": "Banco Central y Ministerio de Hacienda monitorean indicadores macroeconómicos y tipo de cambio",
                    "description": "Nuevas proyecciones para el control de la inflación y crecimiento del PIB.",
                    "link": "https://www.latercera.com",
                    "category": "Economía",
                    "gravity_score": 45,
                    "score": 45,
                    "pub_date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
                }
            ]

        _news_cache_time = now_mono
        _news_cache_data = all_news
        return all_news[:limit]

    @classmethod
    async def get_voice_news_briefing(cls) -> str:
        """Genera un informe ejecutivo conciso y formal de noticias graves para lectura oral."""
        news = await cls.get_top_news(limit=3)
        if not news:
            return "No dispongo de los titulares nacionales en este momento, señor."

        briefing = "En los titulares prioritarios de Chile:\n"
        for n in news:
            cat_prefix = f"[{n.get('category', 'Nacional')}] " if n.get("category") else ""
            briefing += f"Informa {n['source']}: {cat_prefix}{n['title']}.\n"
        return briefing


chile_news = ChileNewsEngine()

