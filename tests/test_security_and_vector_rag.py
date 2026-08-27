"""
Tests de Seguridad Avanzada y Motor Vector RAG para V.I.E.R.N.E.S. 2.0.
Verifica:
- Base de datos vectorial (768 dimensiones) y similitud de coseno
- Auto-alimentación autónoma de recuerdos (AutoMemoryFeeder)
- Protección anti-IDOR en endpoints protegidos
- Sanitización de entradas (Anti-XSS / Command Injection)
- Configuración de transporte SIP TLS (puertos 5060 y 5061) y mitigación de SIP Hacking
"""

import sys
import tempfile
import shutil
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import pytest
import asyncio
import numpy as np
from fastapi.testclient import TestClient

from viernes.memory.vector_rag import (
    VectorDatabaseRAG,
    VectorEmbeddingService,
    AutoMemoryFeeder,
    HabitEntityExtractor,
    ProactiveSuggestionEngine
)
from viernes.auth.security import sanitize_text, sanitize_ip_or_mac, rate_limiter, auth_rate_limiter
from viernes.web.server import app


def test_vector_embedding_and_cosine_similarity():
    temp_dir = tempfile.mkdtemp()
    test_db = str(Path(temp_dir) / "test_vector.db")

    try:
        rag = VectorDatabaseRAG(db_path=test_db)

        # 1. Verificar dimensiones del embedding
        vec1 = VectorEmbeddingService.get_embedding("Mi computador de juegos es un Ryzen 9")
        assert vec1.shape == (768,)
        assert np.isclose(np.linalg.norm(vec1), 1.0, atol=1e-3)

        # 2. Insertar memoria vectorial
        async def _run_rag():
            await rag.insert_memory(
                category="habit",
                key_concept="computador_principal",
                content="Bruno trabaja en su PC Gamer Ryzen con IP 192.168.1.150.",
                source="test"
            )
            await rag.insert_memory(
                category="routine",
                key_concept="ejercicio_gym",
                content="Bruno va al gimnasio a entrenar pecho y espalda los martes.",
                source="test"
            )

            # 3. Búsqueda semántica usando similitud de coseno
            results_pc = await rag.query_semantic_search("computador principal de Bruno", top_k=1)
            assert len(results_pc) >= 1
            assert "PC Gamer" in results_pc[0]["content"]

            results_gym = await rag.query_semantic_search("rutina gimnasio ejercicio", top_k=1)
            assert len(results_gym) >= 1
            assert "gimnasio" in results_gym[0]["content"]

        asyncio.run(_run_rag())
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_auto_memory_feeder():
    async def _test_autofeed():
        temp_dir = tempfile.mkdtemp()
        test_db = str(Path(temp_dir) / "test_auto_vector.db")
        try:
            from viernes.memory import vector_rag as vr_module
            old_rag = vr_module.vector_rag
            vr_module.vector_rag = VectorDatabaseRAG(db_path=test_db)

            # Simular que el usuario habla sobre un hábito
            await AutoMemoryFeeder.analyze_and_auto_feed("Normalmente me gusta tomar café cortado por las tardes")

            # Verificar si se indexó automáticamente
            memories = await vr_module.vector_rag.get_all_vector_memories()
            assert any("café cortado" in m["content"] for m in memories)

            vr_module.vector_rag = old_rag
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    asyncio.run(_test_autofeed())


def test_sanitization_and_anti_xss():
    # Sanitización de texto peligroso (XSS)
    malicious_script = "<script>alert('XSS_ATTACK');</script>"
    safe_text = sanitize_text(malicious_script)
    assert "<script>" not in safe_text
    assert "&lt;script&gt;" in safe_text

    # Sanitización de IPs para evitar Command Injection
    clean_ip = sanitize_ip_or_mac("192.168.1.150; rm -rf /")
    assert ";" not in clean_ip
    assert clean_ip == "192.168.1.150 rm -rf " # Caracteres peligrosos removidos

    valid_mac = sanitize_ip_or_mac("AA-BB-CC-DD-EE-FF")
    assert valid_mac == "aa:bb:cc:dd:ee:ff"


def test_api_security_and_idor_protection():
    client = TestClient(app)

    # 1. Petición no autenticada a endpoints protegidos debe responder 401 Unauthorized
    res_devices = client.get("/api/devices")
    assert res_devices.status_code == 401

    res_wol = client.post("/api/wol", json={"target": "192.168.1.150"})
    assert res_wol.status_code == 401

    res_settings = client.get("/api/settings")
    assert res_settings.status_code == 401

    # 2. Verificar cabeceras de seguridad CSP y Anti-Clickjacking
    res_home = client.get("/")
    assert res_home.status_code == 200
    assert "Content-Security-Policy" in res_home.headers
    assert res_home.headers["X-Frame-Options"] == "DENY"
    assert res_home.headers["X-Content-Type-Options"] == "nosniff"


def test_sip_tls_and_anti_hacking_config():
    pjsip_path = Path(__file__).parent.parent / "telephony" / "config" / "asterisk" / "pjsip.conf"
    assert pjsip_path.exists()
    content = pjsip_path.read_text(encoding="utf-8")

    # Verificar soporte de puerto 5060 (UDP/TCP) y 5061 (TLS / SIPS)
    assert "bind=0.0.0.0:5060" in content
    assert "bind=0.0.0.0:5061" in content
    assert "protocol=tls" in content

    # Verificar mitigaciones de SIP Hacking
    assert "always_auth_reject=yes" in content
    assert "media_encryption=sdes" in content
    assert "allow_unauthenticated_options=no" in content


def test_habit_entity_extractor():
    # 1. Extracción de horas
    assert HabitEntityExtractor.extract_time_target("suelo despertar a las 08:30 AM") == "08:30"
    assert HabitEntityExtractor.extract_time_target("normalmente me levanto a las 7 am") == "07:00"
    assert HabitEntityExtractor.extract_time_target("entreno a las 19:30") == "19:30"
    assert HabitEntityExtractor.extract_time_target("salgo tipo 8 de la noche") == "20:00"

    # 2. Extracción de días
    days1 = HabitEntityExtractor.extract_recurrence_days("voy al gym los martes y jueves")
    assert "martes" in days1 and "jueves" in days1

    days2 = HabitEntityExtractor.extract_recurrence_days("trabajo en el tarro de lunes a viernes")
    assert "lunes" in days2 or "viernes" in days2 or "lunes_a_viernes" in days2

    # 3. Extracción espacial (objeto y ubicación)
    spatial = HabitEntityExtractor.extract_spatial_entity("dejé las llaves en la mesa de entrada")
    assert spatial is not None
    assert spatial["item"] == "llaves"
    assert "mesa de entrada" in spatial["place"]

    spatial2 = HabitEntityExtractor.extract_spatial_entity("guardé mi billetera sobre el escritorio")
    assert spatial2 is not None
    assert spatial2["item"] == "billetera"
    assert "escritorio" in spatial2["place"]


def test_advanced_habit_mining_and_consolidation():
    async def _test_mining():
        temp_dir = tempfile.mkdtemp()
        test_db = str(Path(temp_dir) / "test_advanced_habits.db")
        try:
            from viernes.memory import vector_rag as vr_module
            old_rag = vr_module.vector_rag
            vr_module.vector_rag = VectorDatabaseRAG(db_path=test_db)

            # 1. Minería de Rutina Matutina con entidad de hora
            res1 = await AutoMemoryFeeder.analyze_and_auto_feed("Suelo despertar a las 07:30 de la mañana")
            assert res1 is not None
            assert res1["matched"] is True
            assert res1["category"] == "routine"
            assert res1["metadata"]["time_target"] == "07:30"

            # 2. Refuerzo de Hábito (misma rutina repetida consolida y no duplica)
            res2 = await AutoMemoryFeeder.analyze_and_auto_feed("Normalmente me levanto a las 07:30 am")
            assert res2 is not None
            assert res2["result"]["is_reinforced"] is True

            # 3. Minería de Preferencia Laboral (WoL / PC Gamer)
            res3 = await AutoMemoryFeeder.analyze_and_auto_feed("Mi computador principal de trabajo es el PC Gamer")
            assert res3 is not None
            assert res3["category"] == "preference"

            # 4. Minería de Hecho Espacial
            res4 = await AutoMemoryFeeder.analyze_and_auto_feed("Dejé las llaves en la repisa del pasillo")
            assert res4 is not None
            assert res4["category"] == "fact"
            assert res4["metadata"]["spatial_item"] == "llaves"

            # 5. Búsqueda semántica híbrida enriquecida
            mems = await vr_module.vector_rag.query_semantic_search("dónde dejé las llaves", top_k=1)
            assert len(mems) == 1
            assert "repisa del pasillo" in mems[0]["content"]

            vr_module.vector_rag = old_rag
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    asyncio.run(_test_mining())


def test_proactive_suggestion_engine():
    async def _test_proactivity():
        temp_dir = tempfile.mkdtemp()
        test_db = str(Path(temp_dir) / "test_proactivity.db")
        try:
            rag = VectorDatabaseRAG(db_path=test_db)
            engine = ProactiveSuggestionEngine(rag)

            # Simular hora matutina (08:00 AM)
            from datetime import datetime
            dt_morning = datetime(2026, 8, 27, 8, 15)
            suggestions_morning = await engine.evaluate_proactive_suggestions(current_dt=dt_morning)
            assert len(suggestions_morning) >= 1
            types_m = [s["type"] for s in suggestions_morning]
            assert "morning_briefing" in types_m or "workstation_power" in types_m

            # Simular hora de descanso nocturno (23:30)
            dt_night = datetime(2026, 8, 27, 23, 30)
            suggestions_night = await engine.evaluate_proactive_suggestions(current_dt=dt_night)
            assert len(suggestions_night) >= 1
            assert suggestions_night[0]["type"] == "night_standby"

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    asyncio.run(_test_proactivity())

