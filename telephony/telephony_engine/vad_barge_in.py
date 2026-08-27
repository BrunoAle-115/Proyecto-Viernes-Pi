"""
V.I.E.R.N.E.S. - Detección de Actividad de Voz (VAD) y Manejo de Barge-In (Interrupción)
========================================================================================
Permite que el usuario interrumpa a V.I.E.R.N.E.S de manera natural mientras el asistente
está reproduciendo una respuesta por el canal telefónico.

Características:
- Análisis de energía RMS sobre fragmentos PCM lineales (16-bit).
- Compatible con Python 3.8, 3.9, 3.10, 3.11, 3.12 y Python 3.13+ (eliminación de audioop en PEP 594).
- Ventana de amortiguación (Debounce) para evitar falsos positivos por ruidos de línea PSTN.
- Detección de fin de habla (End of Speech Detection con timeout ajustable).
- Disparo de evento Barge-In para detener la reproducción TTS inmediatamente.
"""

import math
import struct
import logging
import time
from typing import Callable, Optional

# En Python 3.13+, 'audioop' fue removido de la librería estándar (PEP 594).
# Implementamos soporte dual: audioop si está disponible, o motor NumPy/struct optimizado.
try:
    import audioop
    HAVE_AUDIOOP = True
except (ImportError, ModuleNotFoundError):
    audioop = None
    HAVE_AUDIOOP = False

try:
    import numpy as np
    HAVE_NUMPY = True
except (ImportError, ModuleNotFoundError):
    np = None
    HAVE_NUMPY = False

logger = logging.getLogger("VIERNES.VAD")


def calculate_pcm16_rms(pcm_data: bytes) -> int:
    """
    Calcula el valor RMS (Root Mean Square) de audio Linear PCM 16-bit.
    Garantiza 100% de compatibilidad en Python 3.13+ sin dependencias de C obsoletas.
    """
    if not pcm_data or len(pcm_data) < 2:
        return 0

    if HAVE_AUDIOOP and audioop is not None:
        try:
            return audioop.rms(pcm_data, 2)
        except Exception:
            pass

    if HAVE_NUMPY and np is not None:
        try:
            # Vectorización SIMD rápida
            samples = np.frombuffer(pcm_data, dtype=np.int16)
            if len(samples) == 0:
                return 0
            return int(np.sqrt(np.mean(samples.astype(np.float64)**2)))
        except Exception:
            pass

    # Fallback puro Python con struct
    try:
        count = len(pcm_data) // 2
        shorts = struct.unpack(f"<{count}h", pcm_data[:count * 2])
        sum_sq = sum(s * s for s in shorts)
        return int(math.sqrt(sum_sq / count))
    except Exception:
        return 0


class VoiceActivityDetector:
    """
    Detector de voz en tiempo real optimizado para canales telefónicos G.711 (8kHz/16kHz).
    """

    def __init__(
        self,
        energy_threshold: int = 550,          # Umbral de energía RMS para habla humana
        voice_debounce_ms: int = 160,         # Milisegundos de habla continua para confirmar voz
        silence_timeout_ms: int = 750,        # Milisegundos de silencio para confirmar fin de frase
        on_speech_started: Optional[Callable[[], None]] = None,
        on_speech_ended: Optional[Callable[[], None]] = None,
        on_barge_in: Optional[Callable[[], None]] = None,
    ):
        self.energy_threshold = energy_threshold
        self.voice_debounce_ms = voice_debounce_ms
        self.silence_timeout_ms = silence_timeout_ms
        self.on_speech_started = on_speech_started
        self.on_speech_ended = on_speech_ended
        self.on_barge_in = on_barge_in

        # Estados
        self.is_speaking: bool = False
        self.is_assistant_speaking: bool = False
        self._speech_start_time: Optional[float] = None
        self._last_voice_time: Optional[float] = None
        self._audio_buffer: bytearray = bytearray()

    def set_assistant_speaking(self, speaking: bool):
        """Notifica al VAD si V.I.E.R.N.E.S está actualmente hablando."""
        self.is_assistant_speaking = speaking

    def process_pcm_chunk(self, pcm_data: bytes):
        """
        Procesa un chunk de audio PCM de 16 bits y evalúa inicio/fin de voz y barge-in.
        """
        if not pcm_data or len(pcm_data) < 2:
            return

        rms = calculate_pcm16_rms(pcm_data)
        now = time.time() * 1000  # ms

        if rms >= self.energy_threshold:
            # Detectada actividad acústica por encima del umbral
            if self._speech_start_time is None:
                self._speech_start_time = now

            duration_above_threshold = now - self._speech_start_time
            self._last_voice_time = now

            if not self.is_speaking and duration_above_threshold >= self.voice_debounce_ms:
                self.is_speaking = True
                logger.debug(f"🗣️ Inicio de habla de usuario detectado (RMS: {rms})")
                
                if self.on_speech_started:
                    self.on_speech_started()

                # Si V.I.E.R.N.E.S estaba hablando, activar interrupción (Barge-In)
                if self.is_assistant_speaking and self.on_barge_in:
                    logger.info("⚡ BARGE-IN: El usuario interrumpió la respuesta del asistente.")
                    self.on_barge_in()

        else:
            # Nivel por debajo del umbral de energía (Silencio / Ruido de fondo)
            if self.is_speaking and self._last_voice_time is not None:
                silence_duration = now - self._last_voice_time
                if silence_duration >= self.silence_timeout_ms:
                    # El usuario ha dejado de hablar
                    self.is_speaking = False
                    self._speech_start_time = None
                    self._last_voice_time = None
                    logger.debug(f"🤫 Fin de habla detectado tras {silence_duration:.0f}ms de silencio.")
                    if self.on_speech_ended:
                        self.on_speech_ended()
