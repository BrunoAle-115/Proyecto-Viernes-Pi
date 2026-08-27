"""
Pruebas Unitarias para el Servidor de AudioSocket y VAD
"""

import asyncio
import struct
import uuid
import pytest
from telephony.telephony_engine.audiosocket_server import AudioSocketServer, AudioSocketType
from telephony.telephony_engine.vad_barge_in import VoiceActivityDetector


def test_audiosocket_framing_header():
    # Simular empaquetado de encabezado de audio de 320 bytes
    payload_len = 320
    msg_type = AudioSocketType.AUDIO
    header = struct.pack("!BH", msg_type, payload_len)
    
    unpacked_type, unpacked_len = struct.unpack("!BH", header)
    assert unpacked_type == AudioSocketType.AUDIO
    assert unpacked_len == 320


def test_vad_detection_and_barge_in():
    barge_in_called = []
    speech_started = []
    speech_ended = []

    vad = VoiceActivityDetector(
        energy_threshold=300,
        voice_debounce_ms=50,
        silence_timeout_ms=100,
        on_speech_started=lambda: speech_started.append(True),
        on_speech_ended=lambda: speech_ended.append(True),
        on_barge_in=lambda: barge_in_called.append(True),
    )

    # Indicar que el asistente está hablando actualmente
    vad.set_assistant_speaking(True)

    # Crear señal PCM sintética de alta energía (habla humana)
    loud_pcm = struct.pack("<500h", *[5000 if i % 2 == 0 else -5000 for i in range(500)])

    # Enviar paquetes
    vad.process_pcm_chunk(loud_pcm)
    import time
    time.sleep(0.06)
    vad.process_pcm_chunk(loud_pcm)

    assert vad.is_speaking is True
    assert len(barge_in_called) > 0, "Barge-in debe haberse activado ante la voz del usuario mientras el asistente habla"
