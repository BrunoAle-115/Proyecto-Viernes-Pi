"""
Pipeline de Audio Bidireccional (Micrófono + Parlante) para V.I.E.R.N.E.S.
Manejo de audio PCM (16kHz entrada / 24kHz salida) con medidor de espectro para el HUD.
"""

import asyncio
import numpy as np
import logging
from typing import Optional, Callable
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.audio")

# Detección de sounddevice
try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice no disponible. El pipeline de audio funcionará en modo headless / web.")


class AudioPipeline:
    def __init__(self, sample_rate_in: int = 16000, sample_rate_out: int = 24000, channels: int = 1):
        self.sample_rate_in = sample_rate_in
        self.sample_rate_out = sample_rate_out
        self.channels = channels
        self.is_recording = False
        self.is_playing = False
        self._in_stream = None
        self._out_stream = None
        self.audio_queue_in: asyncio.Queue = asyncio.Queue()
        self.audio_queue_out: asyncio.Queue = asyncio.Queue()
        self.current_volume_rms = 0.0

    async def start(self):
        """Inicia los flujos de captura y reproducción de audio."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.info("Modo de audio sin hardware local (interfaz web habilitada).")
            return

        try:
            loop = asyncio.get_running_loop()

            def _in_callback(indata, frames, time_info, status):
                if status:
                    logger.debug(f"Audio In Status: {status}")
                pcm_data = (indata * 32767).astype(np.int16).tobytes()
                # Calcular RMS para visualizador HUD
                rms = float(np.sqrt(np.mean(indata**2)))
                self.current_volume_rms = min(1.0, rms * 5.0)
                try:
                    loop.call_soon_threadsafe(self.audio_queue_in.put_nowait, pcm_data)
                except Exception:
                    pass

            self._in_stream = sd.InputStream(
                samplerate=self.sample_rate_in,
                channels=self.channels,
                dtype="float32",
                callback=_in_callback,
                blocksize=1024,
            )
            self._in_stream.start()
            self.is_recording = True
            logger.info("Captura de micrófono iniciada (16kHz PCM).")

            # Iniciar reproductor en segundo plano
            asyncio.create_task(self._playback_worker())
        except Exception as e:
            logger.error(f"Error iniciando dispositivos de audio locales: {e}")

    async def _playback_worker(self):
        """Consume chunks PCM de 24kHz desde la cola y los reproduce por el parlante."""
        if not SOUNDDEVICE_AVAILABLE:
            return

        try:
            # Crear stream de salida 24kHz
            out_stream = sd.RawOutputStream(
                samplerate=self.sample_rate_out,
                channels=self.channels,
                dtype="int16",
                blocksize=1024,
            )
            out_stream.start()
            self.is_playing = True

            while self.is_playing:
                data = await self.audio_queue_out.get()
                if data:
                    out_stream.write(data)
                self.audio_queue_out.task_done()
        except Exception as e:
            logger.error(f"Error en worker de reproducción de audio: {e}")

    async def play_pcm_chunk(self, pcm_bytes: bytes):
        """Encola un fragmento de audio PCM recibido de Gemini Live para reproducción."""
        await self.audio_queue_out.put(pcm_bytes)
        await bus.publish("audio/playback_chunk", {"size": len(pcm_bytes)}, sender="audio_pipeline")

    async def stop(self):
        """Detiene los streams de audio."""
        self.is_recording = False
        self.is_playing = False
        if self._in_stream:
            self._in_stream.stop()
            self._in_stream.close()
        logger.info("Pipeline de audio detenido.")


audio_pipeline = AudioPipeline()
