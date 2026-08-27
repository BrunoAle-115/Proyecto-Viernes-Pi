"""
Motor de Recordatorios, Alarmas y Briefing Matutino con SQLite (soporta aiosqlite y sqlite3 estándar) y APScheduler.
"""

import os
import sqlite3
import asyncio
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.scheduler")

# Soporte para APScheduler si está instalado, con fallback de scheduler en bucle
try:
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    APSCHEDULER_AVAILABLE = True
except ImportError:
    APSCHEDULER_AVAILABLE = False
    logger.debug("APScheduler no instalado; usando temporizador asíncrono nativo.")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
DB_PATH = os.path.join(DATA_DIR, "viernes.db")


class ReminderEngine:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.scheduler = AsyncIOScheduler() if APSCHEDULER_AVAILABLE else None
        self._init_done = False
        self._pending_tasks = {}

    def _get_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    async def initialize(self):
        """Inicializa la base de datos SQLite y arranca el planificador."""
        if self._init_done:
            return

        def _init_tables():
            with self._get_db() as conn:
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS reminders (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        title TEXT NOT NULL,
                        description TEXT,
                        remind_time TEXT NOT NULL,
                        repeat_pattern TEXT,
                        is_alarm INTEGER DEFAULT 0,
                        is_active INTEGER DEFAULT 1,
                        created_at TEXT NOT NULL
                    )
                """)
                conn.commit()

        await asyncio.to_thread(_init_tables)

        if self.scheduler and not self.scheduler.running:
            self.scheduler.start()

        self._init_done = True
        logger.info("Motor de recordatorios y alarmas inicializado.")

    async def _trigger_notification(self, rem_id: int, title: str, is_alarm: bool):
        """Se ejecuta cuando un recordatorio o alarma vence."""
        logger.info(f"DISPARANDO ALERTA: '{title}' (ID: {rem_id}, Alarma={is_alarm})")

        def _deactivate():
            with self._get_db() as conn:
                conn.execute("UPDATE reminders SET is_active = 0 WHERE id = ?", (rem_id,))
                conn.commit()

        await asyncio.to_thread(_deactivate)

        event_name = "alarm/triggered" if is_alarm else "reminder/triggered"
        await bus.publish(event_name, {
            "id": rem_id,
            "title": title,
            "is_alarm": is_alarm,
            "timestamp": datetime.now().isoformat(),
        }, sender="scheduler")

    async def add_reminder(self, title: str, remind_time: str, is_alarm: bool = False, repeat: str = "once") -> Dict[str, Any]:
        """Agrega una nueva alarma o recordatorio."""
        await self.initialize()
        now = datetime.now().isoformat()

        def _insert():
            with self._get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO reminders (title, description, remind_time, repeat_pattern, is_alarm, is_active, created_at)
                    VALUES (?, ?, ?, ?, ?, 1, ?)
                """, (title, title, remind_time, repeat, 1 if is_alarm else 0, now))
                conn.commit()
                return cursor.lastrowid

        rem_id = await asyncio.to_thread(_insert)

        # Programar ejecución
        try:
            dt = datetime.fromisoformat(remind_time)
            delay = (dt - datetime.now()).total_seconds()
            if delay > 0:
                if self.scheduler:
                    self.scheduler.add_job(
                        self._trigger_notification,
                        "date",
                        run_date=dt,
                        args=[rem_id, title, is_alarm],
                        id=f"rem_{rem_id}",
                        replace_existing=True,
                    )
                else:
                    async def _delayed_task():
                        await asyncio.sleep(delay)
                        await self._trigger_notification(rem_id, title, is_alarm)
                    self._pending_tasks[rem_id] = asyncio.create_task(_delayed_task())
        except Exception as e:
            logger.error(f"Error programando recordatorio {rem_id}: {e}")

        tipo_str = "Alarma" if is_alarm else "Recordatorio"
        return {
            "success": True,
            "id": rem_id,
            "title": title,
            "remind_time": remind_time,
            "is_alarm": is_alarm,
            "message": f"{tipo_str} '{title}' programada para las {remind_time}.",
        }

    async def get_active_reminders(self) -> List[Dict[str, Any]]:
        """Obtiene la lista de recordatorios y alarmas activas."""
        await self.initialize()

        def _fetch():
            with self._get_db() as conn:
                cursor = conn.execute("SELECT * FROM reminders WHERE is_active = 1 ORDER BY remind_time ASC")
                return [dict(r) for r in cursor.fetchall()]

        return await asyncio.to_thread(_fetch)

    async def generate_morning_briefing(self) -> str:
        """Genera el texto de informe matutino consolidado para que V.I.E.R.N.E.S. lo lea."""
        from viernes.mail.gmail_client import gmail_client
        from viernes.mail.zoho_client import zoho_client
        from viernes.integrations.github_monitor import github_monitor
        from viernes.core.telemetry import SystemTelemetry
        from viernes.services.weather_engine import weather_engine
        from viernes.services.news_chile import chile_news

        now_str = datetime.now().strftime("%A %d de %B, %H:%M")
        unread_gmail = await gmail_client.get_unread_emails(max_results=5, only_important=True)
        unread_zoho = zoho_client.get_unread_emails(max_results=5, only_important=True)
        gh_data = await github_monitor.get_pull_requests_summary()
        telemetry = SystemTelemetry.get_full_status()
        weather = await weather_engine.get_forecast("santiago")
        top_news = await chile_news.get_top_news(limit=2)

        briefing = f"Buenos días, señor Bruno. Hoy es {now_str}.\n"
        briefing += f"El clima en {weather['city']} es de {weather['current_temp']} grados con {weather['condition'].lower()}.\n"
        if weather["will_rain"]:
            briefing += f"Atención: Hay un {weather['max_rain_probability']} por ciento de probabilidad de precipitaciones durante el día.\n"
        else:
            briefing += "No se esperan lluvias para el día de hoy.\n"

        total_mails = len(unread_gmail) + len(unread_zoho)
        if total_mails > 0:
            briefing += f"Tiene {total_mails} correos clasificados como prioritarios pendientes de revisión.\n"
        else:
            briefing += "Bandeja de entrada al día sin correos urgentes.\n"

        if gh_data.get("prs"):
            approved = [p for p in gh_data["prs"] if p.get("status") == "APPROVED"]
            if approved:
                briefing += f"En GitHub, su Pull Request '{approved[0].get('title')}' ya cuenta con aprobación.\n"

        if top_news:
            briefing += f"En las noticias destacadas de Chile: {top_news[0]['title']}.\n"

        briefing += f"Todos los sistemas de la Raspberry Pi 5 operan nominales a {telemetry['cpu']['temperature_c']} grados. ¿En qué puedo asistirle hoy?"
        return briefing


reminder_engine = ReminderEngine()
