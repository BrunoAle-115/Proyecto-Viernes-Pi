"""
Mini-RAG y Base de Conocimiento Personal para V.I.E.R.N.E.S.
Almacena y recupera semánticamente información personal, preferencias, rutinas y recordatorios del usuario.
"""

import os
import sqlite3
import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime

logger = logging.getLogger("viernes.memory")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
MEMORY_DB = os.path.join(DATA_DIR, "memory.db")


class PersonalRAG:
    def __init__(self, db_path: str = MEMORY_DB):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _get_conn(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS personal_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL, -- 'routine', 'preference', 'project', 'note', 'contact'
                    key_concept TEXT NOT NULL,
                    content TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

            # Sembrar datos y rutinas por defecto si está vacía
            cursor = conn.execute("SELECT COUNT(*) as count FROM personal_memories")
            if cursor.fetchone()["count"] == 0:
                now = datetime.now().isoformat()
                defaults = [
                    ("preference", "nombre_usuario", "El usuario principal se llama Bruno (cuenta GitHub: BrunoAle-115, correo: brunourrea502@gmail.com).", now),
                    ("routine", "rutina_matutina", "Bruno inicia su día a las 08:00 AM. Desea recibir el Morning Briefing con el clima de Santiago, lluvia, correos urgentes y estado de PRs de GitHub.", now),
                    ("project", "proyecto_viernes", "Proyecto principal activo: 'Proyecto Viernes Pi' en GitHub, framework de IA táctica en Raspberry Pi 5.", now),
                    ("routine", "pc_gamer_habit", "El PC Gamer principal de Bruno suele encenderse para sesiones de desarrollo y trabajo en la IP 192.168.1.150.", now),
                    ("preference", "tono_asistente", "V.I.E.R.N.E.S. debe dirigirse a Bruno como 'Señor' o 'Jefe' con respuestas ejecutivas, leales y precisas.", now)
                ]
                conn.executemany("""
                    INSERT INTO personal_memories (category, key_concept, content, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?)
                """, [(d[0], d[1], d[2], d[3], d[3]) for d in defaults])
                conn.commit()
                logger.info("Memoria y rutinas iniciales sembradas en Mini-RAG.")

    async def store_memory(self, category: str, key_concept: str, content: str) -> Dict[str, Any]:
        """Guarda o actualiza un hecho o rutina en la memoria personal."""
        loop = asyncio.get_running_loop()
        now = datetime.now().isoformat()

        def _insert():
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT id FROM personal_memories WHERE key_concept = ?", (key_concept,))
                row = cursor.fetchone()
                if row:
                    conn.execute("""
                        UPDATE personal_memories
                        SET category = ?, content = ?, updated_at = ?
                        WHERE id = ?
                    """, (category, content, now, row["id"]))
                    mem_id = row["id"]
                else:
                    cur = conn.execute("""
                        INSERT INTO personal_memories (category, key_concept, content, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (category, key_concept, content, now, now))
                    mem_id = cur.lastrowid
                conn.commit()
                return mem_id

        mem_id = await loop.run_in_executor(None, _insert)
        return {
            "success": True,
            "id": mem_id,
            "category": category,
            "key_concept": key_concept,
            "message": f"Información sobre '{key_concept}' guardada en la memoria personal de V.I.E.R.N.E.S."
        }

    async def recall_memories(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Recupera recuerdos relevantes buscando por coincidencia semántica/texto."""
        loop = asyncio.get_running_loop()
        q = query.lower().strip()

        def _search():
            with self._get_conn() as conn:
                # Búsqueda LIKE en conceptos y contenido
                pattern = f"%{q}%"
                cursor = conn.execute("""
                    SELECT * FROM personal_memories
                    WHERE LOWER(key_concept) LIKE ? OR LOWER(content) LIKE ? OR LOWER(category) LIKE ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                """, (pattern, pattern, pattern, limit))
                rows = cursor.fetchall()
                if not rows and len(q.split()) > 1:
                    # Búsqueda por palabras individuales
                    words = q.split()
                    conditions = " OR ".join(["LOWER(content) LIKE ?"] * len(words))
                    params = [f"%{w}%" for w in words] + [limit]
                    cursor = conn.execute(f"SELECT * FROM personal_memories WHERE {conditions} ORDER BY updated_at DESC LIMIT ?", params)
                    rows = cursor.fetchall()

                return [dict(r) for r in rows]

        return await loop.run_in_executor(None, _search)

    async def get_all_memories(self) -> List[Dict[str, Any]]:
        """Retorna todas las memorias guardadas para el HUD."""
        loop = asyncio.get_running_loop()
        def _fetch_all():
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT * FROM personal_memories ORDER BY category, updated_at DESC")
                return [dict(r) for r in cursor.fetchall()]
        return await loop.run_in_executor(None, _fetch_all)


personal_rag = PersonalRAG()
