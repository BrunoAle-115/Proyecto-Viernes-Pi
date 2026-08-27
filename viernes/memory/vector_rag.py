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
import re
from datetime import datetime, time


# --- EXTRACTOR DE ENTIDADES Y DISPARADORES SEMÁNTICOS DE HÁBITOS ---
class HabitEntityExtractor:
    """Extrae parámetros estructurados (hora, días, objetos, lugares, acciones) del lenguaje natural."""

    TIME_REGEX = re.compile(
        r'\b(?:a\s+las?|tipo|cerca\s+de\s+las?|a\s+eso\s+de\s+las?|hora)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|de\s+la\s+mañana|de\s+la\s+tarde|de\s+la\s+noche)?\b',
        re.IGNORECASE
    )

    DAYS_MAP = {
        "lunes": "lunes",
        "martes": "martes",
        "miercoles": "miércoles",
        "miércoles": "miércoles",
        "jueves": "jueves",
        "viernes": "viernes",
        "sabado": "sábado",
        "sábado": "sábado",
        "domingo": "domingo",
        "dias de semana": "lunes_a_viernes",
        "días de semana": "lunes_a_viernes",
        "fin de semana": "sabado_domingo",
        "fines de semana": "sabado_domingo",
        "todos los dias": "diario",
        "todos los días": "diario",
    }

    SPATIAL_REGEX = re.compile(
        r'\b(?:dej[ée]|guard[ée]|puse|est[áa]n?)\s+(?:las?|los?|mi|mis)\s+(?P<item>llaves|billetera|tarjetas?|documentos?|reloj|lentes?|celular|cargador|aud[íi]fonos?|mochila|auto|tarro|computador)\s+(?:en|sobre|debajo\s+de|adentro\s+de|junto\s+a)\s+(?P<place>.+)',
        re.IGNORECASE
    )

    @classmethod
    def extract_time_target(cls, text: str) -> Optional[str]:
        """Extrae y normaliza una hora en formato HH:MM (24h)."""
        match = cls.TIME_REGEX.search(text)
        if not match:
            # Búsqueda secundaria de patrón simple HH:MM
            simple = re.search(r'\b(\d{1,2}):(\d{2})\b', text)
            if simple:
                h, m = int(simple.group(1)), int(simple.group(2))
                if 0 <= h <= 23 and 0 <= m <= 59:
                    return f"{h:02d}:{m:02d}"
            return None

        hour = int(match.group(1))
        minute = int(match.group(2)) if match.group(2) else 0
        period = (match.group(3) or "").lower()

        if "pm" in period or "tarde" in period or "noche" in period:
            if hour < 12:
                hour += 12
        elif ("am" in period or "mañana" in period) and hour == 12:
            hour = 0

        if 0 <= hour <= 23 and 0 <= minute <= 59:
            return f"{hour:02d}:{minute:02d}"
        return None

    @classmethod
    def extract_recurrence_days(cls, text: str) -> List[str]:
        """Extrae días de recurrencia mencionados en el texto."""
        text_lower = text.lower()
        found_days = []
        for key, val in cls.DAYS_MAP.items():
            if re.search(rf'\b{re.escape(key)}\b', text_lower):
                if val not in found_days:
                    found_days.append(val)
        return found_days or ["diario"]

    @classmethod
    def extract_spatial_entity(cls, text: str) -> Optional[Dict[str, str]]:
        """Extrae objeto físico y su ubicación de un hecho espacial."""
        match = cls.SPATIAL_REGEX.search(text)
        if match:
            return {
                "item": match.group("item").lower().strip(),
                "place": match.group("place").strip().rstrip(".,;!")
            }
        return None


# --- TAXONOMÍA Y REGLAS DE MINERÍA DE HÁBITOS ---
HABIT_MINING_RULES = [
    # 1. Rutinas Matutinas
    {
        "category": "routine",
        "subcategory": "morning_awakening",
        "key_prefix": "rutina_despertar",
        "patterns": [
            r"suelo\s+(?:despertar|levantar)",
            r"acostumbro\s+a\s+(?:despertar|levantar)",
            r"normalmente\s+me\s+(?:despierto|levanto)",
            r"siempre\s+me\s+(?:despierto|levanto)",
            r"me\s+despierto\s+(?:a\s+las|tipo|cerca)",
            r"mi\s+alarma\s+(?:es|está)\s+a\s+las",
            r"en\s+las\s+mañanas\s+me\s+levanto"
        ],
        "default_action": "morning_briefing"
    },
    {
        "category": "routine",
        "subcategory": "morning_breakfast",
        "key_prefix": "rutina_cafe_desayuno",
        "patterns": [
            r"(?:tomo|bebo|preparo|mi)\s+(?:caf[ée]|desayuno|mate|t[ée])\s+(?:en\s+las\s+mañanas|al\s+despertar|antes\s+de)",
            r"mi\s+caf[ée]\s+favorito",
            r"desayuno\s+(?:a\s+las|tipo)",
            r"lo\s+primero\s+que\s+hago\s+es\s+tomar\s+caf[ée]"
        ],
        "default_action": "coffee_morning_reminder"
    },
    {
        "category": "routine",
        "subcategory": "morning_commute",
        "key_prefix": "rutina_salida_trabajo",
        "patterns": [
            r"salgo\s+(?:al\s+trabajo|a\s+la\s+oficina|a\s+la\s+pega|a\s+clases|a\s+la\s+u)",
            r"me\s+voy\s+(?:al\s+trabajo|a\s+la\s+oficina|a\s+la\s+pega)\s+a\s+las",
            r"salgo\s+de\s+la\s+casa\s+(?:a\s+las|tipo)",
            r"cuando\s+llueve\s+salgo"
        ],
        "default_action": "weather_and_commute_alert"
    },

    # 2. Preferencias Laborales y Flujo Técnico
    {
        "category": "preference",
        "subcategory": "workstation_setup",
        "key_prefix": "preferencia_estacion_pc",
        "patterns": [
            r"(?:mi\s+pc|mi\s+tarro|mi\s+computador)\s+(?:principal|gamer|de\s+trabajo|es)",
            r"trabajo\s+en\s+el\s+(?:pc|tarro|computador)",
            r"estaci[óo]n\s+de\s+trabajo",
            r"prender\s+el\s+tarro",
            r"enciende\s+el\s+pc\s+para\s+trabajar",
            r"wake-on-lan|wol"
        ],
        "default_action": "proactive_turn_on_pc"
    },
    {
        "category": "routine",
        "subcategory": "deep_work_focus",
        "key_prefix": "rutina_horario_trabajo",
        "patterns": [
            r"empiezo\s+a\s+(?:trabajar|programar|codear|desarrollar)",
            r"mi\s+horario\s+de\s+(?:trabajo|programaci[óo]n)",
            r"bloque\s+de\s+(?:foco|concentraci[óo]n|deep\s+work)",
            r"no\s+me\s+interrumpas\s+(?:cuando|de|entre)",
            r"modo\s+concentraci[óo]n"
        ],
        "default_action": "focus_mode_lighting"
    },
    {
        "category": "preference",
        "subcategory": "code_review_workflow",
        "key_prefix": "preferencia_github_prs",
        "patterns": [
            r"reviso\s+(?:mis\s+prs|pull\s+requests|github)",
            r"suelo\s+revisar\s+(?:prs|pull\s+requests)",
            r"notif[íi]came\s+si\s+(?:aprueban|comentan)\s+(?:mi\s+pr|el\s+pr)",
            r"en\s+github\s+mi\s+repo"
        ],
        "default_action": "github_pr_proactive_check"
    },
    {
        "category": "habit",
        "subcategory": "afternoon_break",
        "key_prefix": "habito_pausa_tarde",
        "patterns": [
            r"tomo\s+caf[ée]\s+(?:en\s+la\s+tarde|a\s+las\s+\d+|despu[ée]s\s+de\s+almorzar)",
            r"caf[ée]\s+cortado\s+(?:por\s+la\s+tarde|en\s+las\s+tardes)",
            r"pausa\s+de\s+la\s+tarde",
            r"almuerzo\s+(?:entre|a\s+las)"
        ],
        "default_action": "afternoon_break_prompt"
    },

    # 3. Notas Personales, Hechos Espaciales y Estilo de Vida
    {
        "category": "fact",
        "subcategory": "spatial_location",
        "key_prefix": "ubicacion_objeto",
        "patterns": [
            r"dej[ée]\s+(?:las?|los?|mi|mis)\s+(?:llaves|billetera|tarjeta|reloj|lentes|celular|cargador|aud[íi]fonos)",
            r"guard[ée]\s+(?:las?|los?|mi|mis)",
            r"puse\s+(?:las?|los?|mi|mis)",
            r"est[áa]n?\s+(?:las?|los?|mi|mis)\s+(?:llaves|billetera)"
        ],
        "default_action": "store_spatial_fact"
    },
    {
        "category": "routine",
        "subcategory": "fitness_workout",
        "key_prefix": "rutina_gimnasio",
        "patterns": [
            r"voy\s+al\s+(?:gimnasio|gym)",
            r"entreno\s+(?:en\s+el\s+gym|pesas|calistenia|crossfit|cardio)",
            r"d[íi]a\s+de\s+(?:pecho|espalda|pierna|entrenamiento)",
            r"hago\s+(?:ejercicio|deporte|running|pesas)"
        ],
        "default_action": "workout_reminder"
    },
    {
        "category": "preference",
        "subcategory": "user_identity_taste",
        "key_prefix": "preferencia_usuario",
        "patterns": [
            r"me\s+gusta\b",
            r"mi\s+comida\s+favorita",
            r"mi\s+restaurante\s+favorito",
            r"mi\s+m[úu]sica\s+favorita",
            r"mi\s+n[úu]mero\s+es",
            r"mi\s+correo\s+es",
            r"mi\s+cumplea[ñn]os\s+es",
            r"el\s+cumplea[ñn]os\s+de"
        ],
        "default_action": "store_user_preference"
    },
    {
        "category": "fact",
        "subcategory": "generic_reminder_note",
        "key_prefix": "nota_recordatorio",
        "patterns": [
            r"recuerda\s+que\b",
            r"no\s+olvides\s+que\b",
            r"acabo\s+de\s+comprar\b",
            r"tengo\s+que\s+comprar\b",
            r"anota\s+que\b",
            r"guarda\s+esta\s+nota\b"
        ],
        "default_action": "store_general_note"
    }
]


class VectorDatabaseRAG:
    """Base de datos vectorial con índice en memoria, cálculo de coseno y persistencia de blobs vectoriales."""

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
                    occurrence_count INTEGER DEFAULT 1,
                    metadata TEXT DEFAULT '{}',
                    temporal_trigger TEXT DEFAULT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Migración suave de columnas adicionales si la tabla ya existía
            cursor = conn.execute("PRAGMA table_info(vector_memories)")
            existing_cols = {row["name"] for row in cursor.fetchall()}
            if "occurrence_count" not in existing_cols:
                conn.execute("ALTER TABLE vector_memories ADD COLUMN occurrence_count INTEGER DEFAULT 1")
            if "metadata" not in existing_cols:
                conn.execute("ALTER TABLE vector_memories ADD COLUMN metadata TEXT DEFAULT '{}'")
            if "temporal_trigger" not in existing_cols:
                conn.execute("ALTER TABLE vector_memories ADD COLUMN temporal_trigger TEXT DEFAULT NULL")
            conn.commit()

            # Sembrar memoria vectorial inicial
            cursor = conn.execute("SELECT COUNT(*) as count FROM vector_memories")
            if cursor.fetchone()["count"] == 0:
                now = datetime.now().isoformat()
                initial_memories = [
                    ("preference", "usuario_principal", "El usuario y creador es Bruno. Su cuenta es BrunoAle-115 y su correo es brunourrea502@gmail.com.", "seed", {"type": "identity"}, None),
                    ("routine", "horario_matutino", "Bruno suele despertar a las 08:00 AM y requiere su Morning Briefing con clima, lluvia, noticias de Chile y estado de PRs.", "seed", {"time_target": "08:00", "action": "morning_briefing"}, "08:00"),
                    ("habit", "estacion_trabajo_pc", "El computador principal de trabajo de Bruno es el PC Gamer en la IP 192.168.1.150 con soporte Wake-on-LAN.", "seed", {"ip": "192.168.1.150", "device": "pc_principal"}, None),
                    ("project", "repo_viernes", "El proyecto principal en desarrollo se llama 'Proyecto Viernes Pi' alojado en GitHub en BrunoAle-115/Proyecto-Viernes-Pi.", "seed", {"repo": "BrunoAle-115/Proyecto-Viernes-Pi"}, None),
                    ("preference", "trato_asistente", "V.I.E.R.N.E.S. debe responder siempre con lealtad y precisión táctica dirigiéndose a Bruno como 'Señor' o 'Jefe'.", "seed", {"honorific": "Señor"}, None),
                ]
                for cat, key, content, src, meta, trig in initial_memories:
                    emb = VectorEmbeddingService.get_embedding(f"{key} {content}")
                    conn.execute("""
                        INSERT INTO vector_memories (category, key_concept, content, embedding, source, confidence, occurrence_count, metadata, temporal_trigger, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, 1.0, 1, ?, ?, ?, ?)
                    """, (cat, key, content, emb.tobytes(), src, json.dumps(meta), trig, now, now))
                conn.commit()
                logger.info("Memoria vectorial inicial sembrada con 5 vectores base estructurados.")

    async def insert_memory(
        self,
        category: str,
        key_concept: str,
        content: str,
        source: str = "user",
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
        temporal_trigger: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Vectoriza y almacena un recuerdo en la base vectorial con soporte de consolidación de hábitos
        (si el concepto ya existe, incrementa su frecuencia y refuerza su confianza).
        """
        loop = asyncio.get_running_loop()
        now = datetime.now().isoformat()
        meta_json = json.dumps(metadata or {})

        def _work():
            full_text = f"{key_concept}: {content}"
            emb_vector = VectorEmbeddingService.get_embedding(full_text)

            with self._get_conn() as conn:
                # Comprobar si ya existe un concepto idéntico para consolidar
                cursor = conn.execute("SELECT id, occurrence_count, confidence, metadata FROM vector_memories WHERE key_concept = ?", (key_concept,))
                row = cursor.fetchone()
                if row:
                    curr_count = row["occurrence_count"] or 1
                    new_count = curr_count + 1
                    new_conf = min(1.0, float(row["confidence"] or 0.8) + 0.05)

                    conn.execute("""
                        UPDATE vector_memories 
                        SET category = ?, content = ?, embedding = ?, source = ?, confidence = ?, occurrence_count = ?, metadata = ?, temporal_trigger = ?, updated_at = ?
                        WHERE id = ?
                    """, (category, content, emb_vector.tobytes(), source, new_conf, new_count, meta_json, temporal_trigger, now, row["id"]))
                    mem_id = row["id"]
                    is_reinforced = True
                else:
                    cur = conn.execute("""
                        INSERT INTO vector_memories (category, key_concept, content, embedding, source, confidence, occurrence_count, metadata, temporal_trigger, created_at, updated_at)
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)
                    """, (category, key_concept, content, emb_vector.tobytes(), source, confidence, meta_json, temporal_trigger, now, now))
                    mem_id = cur.lastrowid
                    is_reinforced = False
                conn.commit()
                return mem_id, is_reinforced

        mem_id, is_reinforced = await loop.run_in_executor(None, _work)
        action_verb = "reforzado y consolidado" if is_reinforced else "guardado e indexado"
        logger.info(f"Vector RAG: Recuerdo '{key_concept}' {action_verb} (Vector ID: {mem_id}).")
        return {
            "success": True,
            "id": mem_id,
            "key_concept": key_concept,
            "category": category,
            "is_reinforced": is_reinforced,
            "message": f"Recuerdo '{key_concept}' {action_verb} en el RAG."
        }

    async def query_semantic_search(
        self,
        query: str,
        top_k: int = 3,
        min_similarity: float = 0.01,
        category_filter: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda semántica vectorial por Similitud de Coseno con boost híbrido por palabras clave y contexto.
        Sim(A, B) = (A . B) / (||A|| * ||B||)
        """
        loop = asyncio.get_running_loop()

        def _search():
            query_vec = VectorEmbeddingService.get_embedding(query)
            query_terms = [w for w in query.lower().split() if len(w) > 2]
            candidates = []

            with self._get_conn() as conn:
                if category_filter:
                    cursor = conn.execute("SELECT id, category, key_concept, content, embedding, source, confidence, occurrence_count, metadata, temporal_trigger, updated_at FROM vector_memories WHERE category = ?", (category_filter,))
                else:
                    cursor = conn.execute("SELECT id, category, key_concept, content, embedding, source, confidence, occurrence_count, metadata, temporal_trigger, updated_at FROM vector_memories")
                rows = cursor.fetchall()

                for row in rows:
                    stored_vec = np.frombuffer(row["embedding"], dtype=np.float32)
                    cos_sim = float(np.dot(query_vec, stored_vec))

                    # Boost semántico si hay coincidencia léxica
                    content_lower = (row["key_concept"] + " " + row["content"]).lower()
                    term_matches = sum(1 for term in query_terms if term in content_lower)
                    
                    # Boost por confianza y ocurrencia
                    occ = row["occurrence_count"] or 1
                    conf = row["confidence"] or 1.0
                    occ_boost = min(0.1, (occ - 1) * 0.02)

                    hybrid_score = cos_sim + (term_matches * 0.15) + occ_boost

                    if hybrid_score >= min_similarity:
                        meta = {}
                        try:
                            meta = json.loads(row["metadata"] or "{}")
                        except Exception:
                            pass

                        candidates.append({
                            "id": row["id"],
                            "category": row["category"],
                            "key_concept": row["key_concept"],
                            "content": row["content"],
                            "source": row["source"],
                            "confidence": conf,
                            "occurrence_count": occ,
                            "metadata": meta,
                            "temporal_trigger": row["temporal_trigger"],
                            "similarity_score": round(hybrid_score, 4),
                            "updated_at": row["updated_at"]
                        })

            candidates.sort(key=lambda x: x["similarity_score"], reverse=True)
            return candidates[:top_k]

        return await loop.run_in_executor(None, _search)

    async def get_all_vector_memories(self) -> List[Dict[str, Any]]:
        """Retorna todas las memorias con su metadata para el HUD y motores proactivos."""
        loop = asyncio.get_running_loop()

        def _fetch():
            with self._get_conn() as conn:
                cursor = conn.execute("""
                    SELECT id, category, key_concept, content, source, confidence, occurrence_count, metadata, temporal_trigger, updated_at 
                    FROM vector_memories 
                    ORDER BY updated_at DESC
                """)
                rows = cursor.fetchall()
                results = []
                for r in rows:
                    item = dict(r)
                    try:
                        item["metadata"] = json.loads(item.get("metadata") or "{}")
                    except Exception:
                        item["metadata"] = {}
                    results.append(item)
                return results

        return await loop.run_in_executor(None, _fetch)


# --- AUTO-FEEDER Y MOTOR DE MINERÍA DE HÁBITOS ---
class AutoMemoryFeeder:
    """
    Analizador en segundo plano con motor NLU que detecta hábitos, rutinas y datos del usuario,
    extrae entidades temporales y espaciales, y los auto-indexa en el Vector RAG con refuerzo continuo.
    """

    # Lista canónica preservada para compatibilidad retroactiva
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
    async def analyze_and_auto_feed(cls, user_text: str) -> Optional[Dict[str, Any]]:
        """
        Inspecciona el texto del usuario aplicando minería de hábitos semántica profunda.
        Extrae entidades, deduce la intención y consolida la memoria en la DB vectorial.
        """
        text_lower = user_text.lower().strip()
        matched_rule = None

        # 1. Evaluación de reglas de minería profunda
        for rule in HABIT_MINING_RULES:
            for pattern in rule["patterns"]:
                if re.search(pattern, text_lower, re.IGNORECASE):
                    matched_rule = rule
                    break
            if matched_rule:
                break

        # 2. Si no coincide con las reglas avanzadas, fallback a HABIT_PATTERNS clásico
        if not matched_rule:
            for trigger, category, key_prefix in cls.HABIT_PATTERNS:
                if trigger in text_lower:
                    matched_rule = {
                        "category": category,
                        "subcategory": "general",
                        "key_prefix": key_prefix,
                        "default_action": "store_fact"
                    }
                    break

        if not matched_rule:
            return None

        # 3. Extracción de entidades semánticas estructuradas
        time_target = HabitEntityExtractor.extract_time_target(user_text)
        recurrence_days = HabitEntityExtractor.extract_recurrence_days(user_text)
        spatial_data = HabitEntityExtractor.extract_spatial_entity(user_text)

        metadata = {
            "subcategory": matched_rule.get("subcategory", "general"),
            "action_trigger": matched_rule.get("default_action", "general_action"),
            "recurrence_days": recurrence_days,
            "mined_at": datetime.now().isoformat()
        }
        if time_target:
            metadata["time_target"] = time_target
        if spatial_data:
            metadata["spatial_item"] = spatial_data["item"]
            metadata["spatial_place"] = spatial_data["place"]

        # 4. Generación de clave canónica semántica (evita fragmentación aleatoria)
        key_prefix = matched_rule["key_prefix"]
        if spatial_data:
            canonical_key = f"ubicacion_{spatial_data['item'].replace(' ', '_')}"
        elif time_target and "despertar" in key_prefix:
            canonical_key = "rutina_despertar_diario"
        elif "pc" in key_prefix or "estacion" in key_prefix:
            canonical_key = "estacion_trabajo_pc"
        elif "cafe" in key_prefix:
            canonical_key = "habito_cafe_favorito"
        elif "gym" in key_prefix or "gimnasio" in key_prefix:
            canonical_key = "rutina_ejercicio_gym"
        elif "trabajo" in key_prefix or "deep_work" in matched_rule.get("subcategory", ""):
            canonical_key = "rutina_horario_trabajo"
        elif "github" in key_prefix:
            canonical_key = "preferencia_github_prs"
        else:
            clean_snippet = re.sub(r'[^a-zA-Z0-9_]', '', key_prefix)[:25]
            canonical_key = f"{clean_snippet}_{abs(hash(user_text)) % 1000}"

        logger.info(f"Auto-Feeder RAG: Minado hábito '{canonical_key}' [{matched_rule['category']}] -> Metadata: {metadata}")

        res = await vector_rag.insert_memory(
            category=matched_rule["category"],
            key_concept=canonical_key,
            content=user_text.strip(),
            source="auto_feeder_conversation",
            confidence=0.9,
            metadata=metadata,
            temporal_trigger=time_target
        )

        return {
            "matched": True,
            "key_concept": canonical_key,
            "category": matched_rule["category"],
            "metadata": metadata,
            "result": res
        }


# --- MOTOR DE PROACTIVIDAD Y SUGERENCIAS TÁCTICAS ---
class ProactiveSuggestionEngine:
    """
    Motor proactivo que analiza la telemetría temporal, hábitos minados en la DB vectorial
    y genera sugerencias contextuales automáticas para V.I.E.R.N.E.S.
    """

    def __init__(self, rag_instance: VectorDatabaseRAG):
        self.rag = rag_instance

    async def evaluate_proactive_suggestions(self, current_dt: Optional[datetime] = None) -> List[Dict[str, Any]]:
        """
        Evalúa los recuerdos y rutinas semánticas almacenadas para generar sugerencias tácticas
        según el momento actual del día.
        """
        now = current_dt or datetime.now()
        current_hour = now.hour
        current_min = now.minute
        current_time_str = f"{current_hour:02d}:{current_min:02d}"
        weekday_name = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"][now.weekday()]

        suggestions = []
        memories = await self.rag.get_all_vector_memories()

        # 1. Evaluación de Rutinas Matutinas (06:30 a 10:00)
        if 6 <= current_hour < 10:
            for m in memories:
                if m["category"] == "routine" and ("despertar" in m["key_concept"] or "matutino" in m["key_concept"]):
                    suggestions.append({
                        "type": "morning_briefing",
                        "priority": "HIGH",
                        "title": "Morning Briefing Táctico",
                        "suggested_speech": f"Buenos días, Señor Bruno. Son las {current_time_str}. ¿Desea que ejecute el informe matutino con el pronóstico de lluvia, noticias de Chile y estado de sus PRs?",
                        "recommended_tool": "get_morning_briefing",
                        "tool_args": {}
                    })

                if "estacion" in m["key_concept"] or "pc" in m["key_concept"]:
                    suggestions.append({
                        "type": "workstation_power",
                        "priority": "MEDIUM",
                        "title": "Encendido de Estación de Trabajo",
                        "suggested_speech": "Señor, su estación de trabajo PC Gamer (192.168.1.150) está lista. ¿Desea que envíe el Magic Packet Wake-on-LAN para encenderla?",
                        "recommended_tool": "turn_on_pc",
                        "tool_args": {"device_name": "pc_principal"}
                    })

        # 2. Evaluación de Jornada Laboral y Deep Work (10:00 a 18:00)
        elif 10 <= current_hour < 18:
            for m in memories:
                if "github" in m["key_concept"] or "prs" in m["key_concept"]:
                    suggestions.append({
                        "type": "github_review",
                        "priority": "MEDIUM",
                        "title": "Revisión de Pull Requests",
                        "suggested_speech": "Señor, en su flujo de trabajo habitual suele supervisar el repositorio. ¿Desea que revise si hay PRs pendientes o comentarios en GitHub?",
                        "recommended_tool": "check_github_status",
                        "tool_args": {}
                    })

            # Pausa de Café de la tarde (15:00 a 17:00)
            if 15 <= current_hour <= 17:
                for m in memories:
                    if "cafe" in m["key_concept"] or "pausa" in m["key_concept"]:
                        suggestions.append({
                            "type": "afternoon_coffee",
                            "priority": "LOW",
                            "title": "Pausa de Café Cortado",
                            "suggested_speech": "Son las horas habituales de su pausa de café por la tarde, Señor. Le sugiero tomar un descanso de 10 minutos de la pantalla.",
                            "recommended_tool": "control_smart_light",
                            "tool_args": {"target": "luces_escritorio", "action": "brightness", "brightness": 70}
                        })

        # 3. Evaluación de Rutina de Ejercicio / Gym (18:00 a 21:00)
        elif 18 <= current_hour < 21:
            for m in memories:
                if "gym" in m["key_concept"] or "gimnasio" in m["key_concept"]:
                    suggestions.append({
                        "type": "workout_alert",
                        "priority": "HIGH",
                        "title": "Entrenamiento Físico",
                        "suggested_speech": f"Señor, hoy {weekday_name} suele entrenar en el gimnasio. Los sistemas de la Raspberry Pi permanecerán en vigilancia activa durante su ausencia.",
                        "recommended_tool": "store_personal_memory",
                        "tool_args": {"category": "routine", "key_concept": "ultima_sesion_gym", "content": f"Entrenamiento completado el {weekday_name}"}
                    })

        # 4. Evaluación Nocturna y Modo Reposo (22:00 a 02:00)
        elif current_hour >= 22 or current_hour < 6:
            suggestions.append({
                "type": "night_standby",
                "priority": "MEDIUM",
                "title": "Modo Reposo y Apagado",
                "suggested_speech": "Señor, es hora de descanso. ¿Desea que apague las luces del escritorio y active el modo centinela de baja energía?",
                "recommended_tool": "control_smart_light",
                "tool_args": {"target": "luces_escritorio", "action": "off", "brightness": 0}
            })

        return suggestions


vector_rag = VectorDatabaseRAG()
proactive_engine = ProactiveSuggestionEngine(vector_rag)
