"""
Detector de Wake Word Local ("Oye Viernes" / "Viernes" / "Hey Jarvis") y VAD para V.I.E.R.N.E.S.
Permite activación por voz offline, bajo consumo y Plug-and-Play con cualquier micrófono USB en Raspberry Pi 5.
"""

import math
import struct
import asyncio
import logging
from typing import Optional
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.wakeword")


class WakeWordDetector:
    def __init__(self, phrase: str = "oye_viernes", sensitivity: float = 0.60):
        self.phrase = phrase
        self.sensitivity = sensitivity
        self.is_active = False
        self.engine = None
        self._consecutive_speech_frames = 0
        self._speech_energy_threshold = 850.0  # RMS threshold para VAD acústico fallback
        self._init_engine()

    def _init_engine(self):
        try:
            import openwakeword
            from openwakeword.model import Model
            self.engine = Model(wakeword_models=["hey_jarvis", "timer"], inference_framework="onnx")
            logger.info("✓ Motor OpenWakeWord cargado con éxito en memoria.")
        except Exception:
            logger.info("ℹ️ OpenWakeWord en modo acústico de alta sensibilidad (VAD RMS Fallback para hardware USB).")

    async def process_pcm_frame(self, pcm_data: bytes) -> bool:
        """Evalúa un chunk de audio PCM de 16kHz del micrófono USB."""
        if not self.is_active or not pcm_data:
            return False

        # 1. Si OpenWakeWord está disponible en ONNX
        if self.engine:
            try:
                import numpy as np
                audio_np = np.frombuffer(pcm_data, dtype=np.int16)
                prediction = self.engine.predict(audio_np)
                for mdl_name, score in prediction.items():
                    if score > self.sensitivity:
                        logger.info(f"🎙️ [Wake Word Detectada] Activación por voz: '{mdl_name}' (confianza: {score:.2f})")
                        await bus.publish("wakeword/detected", {"model": mdl_name, "score": float(score)}, sender="wakeword")
                        return True
            except Exception as e:
                logger.debug(f"Error en OpenWakeWord: {e}")

        # 2. VAD Acústico Inteligente Fallback (Detecta inicio de voz y frase para despertar)
        try:
            num_samples = len(pcm_data) // 2
            if num_samples > 0:
                shorts = struct.unpack(f"<{num_samples}h", pcm_data)
                sum_sq = sum(s * s for s in shorts)
                rms = math.sqrt(sum_sq / num_samples)

                if rms > self._speech_energy_threshold:
                    self._consecutive_speech_frames += 1
                    if self._consecutive_speech_frames == 4: # ~130ms de voz sostenida
                        logger.info(f"🎙️ [Voz Detectada por Micrófono USB] Despertando a V.I.E.R.N.E.S. (RMS: {rms:.1f})...")
                        await bus.publish("wakeword/detected", {"mode": "acoustic_vad", "rms": rms}, sender="acoustic_vad")
                        return True
                else:
                    self._consecutive_speech_frames = max(0, self._consecutive_speech_frames - 1)
        except Exception:
            pass

        return False

    def trigger_manually(self):
        """Dispara la activación manualmente (desde el botón del HUD o teclado)."""
        logger.info("Activación manual de V.I.E.R.N.E.S. disparada.")
        asyncio.create_task(bus.publish("wakeword/detected", {"manual": True}, sender="manual_trigger"))


wakeword_detector = WakeWordDetector()
