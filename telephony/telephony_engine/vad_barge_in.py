"""
V.I.E.R.N.E.S. - Detección de Actividad de Voz (VAD) y Manejo de Barge-In (Interrupción)
========================================================================================
Permite que el usuario interrumpa a V.I.E.R.N.E.S de manera natural mientras el asistente
está reproduciendo una respuesta por el canal telefónico.

Características:
- Análisis de energía RMS sobre fragmentos PCM lineales (16-bit).
- Ventana de amortiguación (Debounce) para evitar falsos positivos por ruidos de línea PSTN.
- Detección de fin de habla (End of Speech Detection con timeout ajustable).
- Disparo de evento Barge-In para detener la reproducción TTS inmediatamente.
"""

import audioop
import logging
import time
from typing import Callable, Optional

logger = logging.getLogger("VIERNES.VAD")


class VoiceActivityDetector:
    """
    Detector de voz en tiempo real optimizado para canales telefónicos G.711 (8kHz/16kHz).
    """

    def __init__(
        self,
        energy_threshold: int = 550,          # Umbral de energía RMS para habla humana
        voice_debounce_ms: int = 160,          # Milisegundos de habla continua para confirmar voz
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
        Procesa un chunk de audio PCM de 16 bits.
        """
        if not pcm_data or len(pcm_data) < 2:
            return

        try:
            # Calcular nivel de energía RMS (Root Mean Square)
            rms = audioop.rms(pcm_data, 2)
        except Exception:
            rms = 0

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
            elif not self.is_speaking:
                self._speech_start_time = None

    def reset(self):
        """Reinicia los contadores y buffers del detector."""
        self.is_speaking = False
        self._speech_start_time = None
        self._last_voice_time = None
        self._audio_buffer.clear()
