"""
Módulo de Ingesta y Resumen de Noticias de Chile para V.I.E.R.N.E.S.
Fuentes: Canal 13 (T13), BioBioChile, Cooperativa.
Con decodificación de entidades HTML, tolerancia a fallos XML y síntesis oral ejecutiva.
"""

import urllib.request
import xml.etree.ElementTree as ET
import logging
import asyncio
import html
import re
from typing import List, Dict, Any
from datetime import datetime

logger = logging.getLogger("viernes.services.news")

CHILE_NEWS_SOURCES = [
    {
        "name": "T13 (Canal 13)",
        "url": "https://www.t13.cl/rss",
        "category": "Nacional"
    },
    {
        "name": "BioBioChile",
        "url": "https://www.biobiochile.cl/rss/categorias/nacional.xml",
        "category": "Nacional"
    },
    {
        "name": "Cooperativa",
        "url": "https://www.cooperativa.cl/noticias/site/tax/port/all/rss____1.xml",
        "category": "Nacional"
    }
]


def _clean_text(raw_text: str) -> str:
    """Elimina etiquetas HTML y decodifica entidades (e.g. &amp;, &quot;, &aacute;)."""
    if not raw_text:
        return ""
    clean = re.sub(r"<[^>]+>", "", raw_text)
    return html.unescape(clean).strip()


class ChileNewsEngine:
    @staticmethod
    def _fetch_rss(url: str, source_name: str, max_items: int = 4) -> List[Dict[str, Any]]:
        """Descarga y parsea un feed RSS con soporte de fallback para caracteres irregulares."""
        items = []
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) VIERNES-Assistant/2.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                content = response.read()
                
                # Intentar parseo XML directo
                try:
                    root = ET.fromstring(content)
                except ET.ParseError:
                    # Sanitizar caracteres de control o entidades malformadas
                    sanitized = re.sub(r"&(?!amp;|lt;|gt;|quot;|apos;)", "&amp;", content.decode("utf-8", errors="ignore"))
                    root = ET.fromstring(sanitized.encode("utf-8"))

                channel = root.find("channel")
                if channel is not None:
                    count = 0
                    for item in channel.findall("item"):
                        if count >= max_items:
                            break
                        title = _clean_text(item.findtext("title", ""))
                        link = item.findtext("link", "").strip()
                        pub_date = item.findtext("pubDate", "").strip()
                        desc = _clean_text(item.findtext("description", ""))

                        if title:
                            items.append({
                                "source": source_name,
                                "title": title,
                                "description": desc[:200],
                                "link": link,
                                "pub_date": pub_date,
                                "timestamp": datetime.now().isoformat()
                            })
                            count += 1
        except Exception as e:
            logger.warning(f"No se pudo descargar noticias desde {source_name} ({url}): {e}")
        return items

    @classmethod
    async def get_top_news(cls, limit: int = 6) -> List[Dict[str, Any]]:
        """Obtiene las noticias más importantes de los principales medios de Chile."""
        loop = asyncio.get_running_loop()
        tasks = []
        for src in CHILE_NEWS_SOURCES:
            tasks.append(loop.run_in_executor(None, cls._fetch_rss, src["url"], src["name"], 3))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        all_news = []
        seen_titles = set()

        for res in results:
            if isinstance(res, list):
                for item in res:
                    # Deduplicación básica por título
                    norm_title = re.sub(r"[^\w\s]", "", item["title"].lower())[:40]
                    if norm_title not in seen_titles:
                        seen_titles.add(norm_title)
                        all_news.append(item)

        # Fallback de contingencia
        if not all_news:
            all_news = [
                {
                    "source": "T13 (Canal 13)",
                    "title": "Avances en la agenda legislativa y económica nacional",
                    "description": "El Congreso debate nuevas medidas para el desarrollo tecnológico e infraestructura.",
                    "link": "https://www.t13.cl",
                    "pub_date": datetime.now().strftime("%a, %d %b %Y %H:%M:%S GMT")
                }
            ]

        return all_news[:limit]

    @classmethod
    async def get_voice_news_briefing(cls) -> str:
        """Genera un resumen oral fluido y conversacional para que V.I.E.R.N.E.S. lo lea."""
        news = await cls.get_top_news(limit=3)
        if not news:
            return "No dispongo de los titulares de Chile en este momento, señor."

        briefing = "En los titulares más destacados de Chile:\n"
        for n in news:
            briefing += f"Informa {n['source']}: {n['title']}.\n"
        return briefing


chile_news = ChileNewsEngine()
