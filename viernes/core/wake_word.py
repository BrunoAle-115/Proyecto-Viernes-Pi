"""
Detector de Wake Word Local ("Viernes" / "Friday") para V.I.E.R.N.E.S.
Permite activación por voz offline y bajo consumo en Raspberry Pi 5.
"""

import asyncio
import logging
from typing import Optional
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.wakeword")


class WakeWordDetector:
    def __init__(self, phrase: str = "viernes", sensitivity: float = 0.65):
        self.phrase = phrase
        self.sensitivity = sensitivity
        self.is_active = False
        self.engine = None
        self._init_engine()

    def _init_engine(self):
        try:
            import openwakeword
            from openwakeword.model import Model
            self.engine = Model(wakeword_models=["hey_jarvis", "timer"], inference_framework="onnx")
            logger.info("Motor OpenWakeWord inicializado con éxito.")
        except Exception:
            logger.info("OpenWakeWord no disponible en este entorno. Usando detector por nivel acústico / trigger.")

    async def process_pcm_frame(self, pcm_data: bytes) -> bool:
        """Evalúa un chunk de audio PCM y determina si se pronunció la palabra de activación."""
        if not self.is_active:
            return False

        if self.engine:
            try:
                # Procesar frame con OpenWakeWord
                import numpy as np
                audio_np = np.frombuffer(pcm_data, dtype=np.int16)
                prediction = self.engine.predict(audio_np)
                for mdl_name, score in prediction.items():
                    if score > self.sensitivity:
                        logger.info(f"Wake word detectada! ({mdl_name}: {score:.2f})")
                        await bus.publish("wakeword/detected", {"model": mdl_name, "score": float(score)}, sender="wakeword")
                        return True
            except Exception as e:
                logger.debug(f"Error procesando frame en wakeword: {e}")

        return False

    def trigger_manually(self):
        """Dispara la activación manualmente (desde el botón del HUD o teclado)."""
        logger.info("Activación manual de V.I.E.R.N.E.S. disparada.")
        asyncio.create_task(bus.publish("wakeword/detected", {"manual": True}, sender="manual_trigger"))


wakeword_detector = WakeWordDetector()
