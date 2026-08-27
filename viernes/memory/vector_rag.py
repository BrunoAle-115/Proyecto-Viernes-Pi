"""
Base de Datos Vectorial y Motor RAG de Auto-Alimentación para V.I.E.R.N.E.S.
Implementa embeddings densos de 768 dimensiones, cálculo de similitud de coseno y extracción autónoma de memoria.
"""

import os
import json
import sqlite3
import logging
import asyncio
import urllib.request
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

logger = logging.getLogger("viernes.vector_rag")

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
VECTOR_DB_PATH = os.path.join(DATA_DIR, "vector_memory.db")
EMBEDDING_DIM = 768


class VectorEmbeddingService:
    """Generador de embeddings vectoriales usando Gemini text-embedding-004 o generador denso determinístico."""

    @staticmethod
    def _generate_remote_embedding(text: str, api_key: str) -> Optional[List[float]]:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={api_key}"
        payload = {
            "model": "models/text-embedding-004",
            "content": {
                "parts": [{"text": text[:2048]}]
            }
        }
        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "VIERNES-VectorRAG/2.0"}
            )
            with urllib.request.urlopen(req, timeout=4) as response:
                res = json.loads(response.read().decode("utf-8"))
                values = res.get("embedding", {}).get("values", [])
                if values and len(values) == EMBEDDING_DIM:
                    return values
        except Exception as e:
            logger.debug(f"API remota de embeddings no disponible ({e}), usando vectorizador local de alta densidad.")
        return None

    @classmethod
    def get_embedding(cls, text: str) -> np.ndarray:
        """Retorna un vector unitario normalizado de 768 dimensiones."""
        clean_text = text.strip()
        api_key = os.getenv("GEMINI_API_KEY", "")

        if api_key and not api_key.startswith("AIzaSyYour"):
            remote_vec = cls._generate_remote_embedding(clean_text, api_key)
            if remote_vec:
                vec = np.array(remote_vec, dtype=np.float32)
                norm = np.linalg.norm(vec)
                return vec / norm if norm > 0 else vec

        # Vectorizador denso local determinístico (TF-IDF + Trigram Character Hash Hashing Trick)
        vec = np.zeros(EMBEDDING_DIM, dtype=np.float32)
        words = clean_text.lower().split()
        for i, word in enumerate(words):
            # Positional & semantic hash
            h = int(hashlib.sha256(word.encode("utf-8")).hexdigest(), 16)
            idx = h % EMBEDDING_DIM
            weight = 1.0 / (1.0 + np.log1p(i))
            vec[idx] += weight

            # Trigram subwords
            for j in range(len(word) - 2):
                tri = word[j:j+3]
                h_tri = int(hashlib.md5(tri.encode("utf-8")).hexdigest(), 16)
                idx_tri = h_tri % EMBEDDING_DIM
                vec[idx_tri] += 0.3

        norm = np.linalg.norm(vec)
        if norm > 0:
            vec = vec / norm
        return vec


import hashlib


class VectorDatabaseRAG:
    """Base de datos vectorial con índice en memoria y persistencia de blobs vectoriales."""

    def __init__(self, db_path: str = VECTOR_DB_PATH):
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
                CREATE TABLE IF NOT EXISTS vector_memories (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    category TEXT NOT NULL, -- 'routine', 'preference', 'project', 'habit', 'fact'
                    key_concept TEXT NOT NULL,
                    content TEXT NOT NULL,
                    embedding BLOB NOT NULL, -- Float32 array serialized
                    source TEXT DEFAULT 'system',
                    confidence REAL DEFAULT 1.0,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)
            conn.commit()

            # Sembrar memoria vectorial inicial
            cursor = conn.execute("SELECT COUNT(*) as count FROM vector_memories")
            if cursor.fetchone()["count"] == 0:
                now = datetime.now().isoformat()
                initial_memories = [
                    ("preference", "usuario_principal", "El usuario y creador es Bruno. Su cuenta es BrunoAle-115 y su correo es brunourrea502@gmail.com.", "seed"),
                    ("routine", "horario_matutino", "Bruno suele despertar a las 08:00 AM y requiere su Morning Briefing con clima, lluvia, noticias de Chile y estado de PRs.", "seed"),
                    ("habit", "estacion_trabajo_pc", "El computador principal de trabajo de Bruno es el PC Gamer en la IP 192.168.1.150 con soporte Wake-on-LAN.", "seed"),
                    ("project", "repo_viernes", "El proyecto principal en desarrollo se llama 'Proyecto Viernes Pi' alojado en GitHub en BrunoAle-115/Proyecto-Viernes-Pi.", "seed"),
                    ("preference", "trato_asistente", "V.I.E.R.N.E.S. debe responder siempre con lealtad y precisión táctica dirigiéndose a Bruno como 'Señor' o 'Jefe'.", "seed"),
                ]
                for cat, key, content, src in initial_memories:
                    emb = VectorEmbeddingService.get_embedding(f"{key} {content}")
                    conn.execute("""
                        INSERT INTO vector_memories (category, key_concept, content, embedding, source, confidence, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1.0, ?, ?)
                    """, (cat, key, content, emb.tobytes(), src, now, now))
                conn.commit()
                logger.info("Memoria vectorial inicial sembrada con 5 vectores base.")

    async def insert_memory(self, category: str, key_concept: str, content: str, source: str = "user") -> Dict[str, Any]:
        """Vectoriza y almacena un nuevo recuerdo o rutina en la base vectorial."""
        loop = asyncio.get_running_loop()
        now = datetime.now().isoformat()

        def _work():
            # Generar embedding del texto
            full_text = f"{key_concept}: {content}"
            emb_vector = VectorEmbeddingService.get_embedding(full_text)

            with self._get_conn() as conn:
                # Comprobar si ya existe un concepto idéntico para actualizar su vector
                cursor = conn.execute("SELECT id FROM vector_memories WHERE key_concept = ?", (key_concept,))
                row = cursor.fetchone()
                if row:
                    conn.execute("""
                        UPDATE vector_memories 
                        SET category = ?, content = ?, embedding = ?, source = ?, updated_at = ?
                        WHERE id = ?
                    """, (category, content, emb_vector.tobytes(), source, now, row["id"]))
                    mem_id = row["id"]
                else:
                    cur = conn.execute("""
                        INSERT INTO vector_memories (category, key_concept, content, embedding, source, confidence, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1.0, ?, ?)
                    """, (category, key_concept, content, emb_vector.tobytes(), source, now, now))
                    mem_id = cur.lastrowid
                conn.commit()
                return mem_id

        mem_id = await loop.run_in_executor(None, _work)
        logger.info(f"Vector RAG: Recuerdo '{key_concept}' guardado exitosamente (Vector ID: {mem_id}).")
        return {
            "success": True,
            "id": mem_id,
            "key_concept": key_concept,
            "category": category,
            "message": f"Recuerdo '{key_concept}' vectorizado e indexado en el RAG."
        }

    async def query_semantic_search(self, query: str, top_k: int = 3, min_similarity: float = 0.01) -> List[Dict[str, Any]]:
        """
        Ejecuta una búsqueda semántica vectorial calculando la Similitud de Coseno:
        Sim(A, B) = (A . B) / (||A|| * ||B||)
        """
        loop = asyncio.get_running_loop()

        def _search():
            query_vec = VectorEmbeddingService.get_embedding(query)
            query_terms = [w for w in query.lower().split() if len(w) > 2]
            candidates = []

            with self._get_conn() as conn:
                cursor = conn.execute("SELECT id, category, key_concept, content, embedding, source, updated_at FROM vector_memories")
                rows = cursor.fetchall()

                for row in rows:
                    stored_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                    cos_sim = float(np.dot(query_vec, stored_vec))
                    
                    # Boost semántico si hay coincidencia de términos
                    content_lower = (row["key_concept"] + " " + row["content"]).lower()
                    term_matches = sum(1 for term in query_terms if term in content_lower)
                    hybrid_score = cos_sim + (term_matches * 0.15)

                    if hybrid_score >= min_similarity:
                        candidates.append({
                            "id": row["id"],
                            "category": row["category"],
                            "key_concept": row["key_concept"],
                            "content": row["content"],
                            "source": row["source"],
                            "similarity_score": round(hybrid_score, 4),
                            "updated_at": row["updated_at"]
                        })

            # Ordenar descendentemente por similitud vectorial
            candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
            return candidates[:top_k]

        return await loop.run_in_executor(None, _search)

    async def get_all_vector_memories(self) -> List[Dict[str, Any]]:
        """Retorna todas las memorias con su metadata para el HUD."""
        loop = asyncio.get_running_loop()
        def _fetch():
            with self._get_conn() as conn:
                cursor = conn.execute("SELECT id, category, key_concept, content, source, confidence, updated_at FROM vector_memories ORDER BY updated_at DESC")
                return [dict(r) for r in cursor.fetchall()]
        return await loop.run_in_executor(None, _fetch)


# --- AUTO-FEEDER CONTINUO (Aprende de forma autónoma durante las conversaciones) ---
class AutoMemoryFeeder:
    """Analizador en segundo plano que detecta hábitos, rutinas y datos del usuario y los auto-indexa en el Vector RAG."""

    # Patrones verbales de hábitos y preferencias
    HABIT_PATTERNS = [
        ("suelo despertar", "routine", "rutina_despertar"),
        ("suelo levantarme", "routine", "rutina_despertar"),
        ("me gusta", "preference", "preferencia_usuario"),
        ("mi comida favorita", "preference", "comida_favorita"),
        ("mi café favorito", "preference", "cafe_favorito"),
        ("voy al gimnasio", "routine", "rutina_gym"),
        ("dejé las llaves", "fact", "ubicacion_llaves"),
        ("dejé mi", "fact", "ubicacion_objeto"),
        ("recuerda que", "fact", "nota_recordatorio"),
        ("acabo de comprar", "fact", "compra_reciente"),
        ("mi número es", "preference", "contacto_telefono"),
    ]

    @classmethod
    async def analyze_and_auto_feed(cls, user_text: str):
        """Inspecciona el texto del usuario e inserta automáticamente en la DB vectorial si detecta un hecho."""
        text_lower = user_text.lower().strip()
        for trigger, category, key_prefix in cls.HABIT_PATTERNS:
            if trigger in text_lower:
                concept_name = f"{key_prefix}_{int(datetime.now().timestamp()) % 10000}"
                logger.info(f"Auto-Feeder RAG: Detectado nuevo patrón de memoria: '{trigger}' -> Guardando...")
                await vector_rag.insert_memory(
                    category=category,
                    key_concept=concept_name,
                    content=user_text.strip(),
                    source="auto_feeder_conversation"
                )
                break


vector_rag = VectorDatabaseRAG()
