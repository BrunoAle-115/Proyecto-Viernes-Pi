"""
Pipeline de Audio Bidireccional Full-Dúplex con DSP, Control de Latencia y RMS Ballistics para V.I.E.R.N.E.S.
Optimizado para Raspberry Pi 5 (ARM64) y Gemini Live Multimodal API.
"""

import asyncio
import logging
import numpy as np
from typing import Optional
from viernes.core.event_bus import bus

logger = logging.getLogger("viernes.audio")

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice no disponible. Operando en modo headless.")


class AudioPipeline:
    def __init__(self, sample_rate_in: int = 16000, sample_rate_out: int = 24000, channels: int = 1):
        self.sample_rate_in = sample_rate_in
        self.sample_rate_out = sample_rate_out
        self.channels = channels
        self.is_recording = False
        self.is_playing = False
        self._in_stream: Optional[sd.InputStream] = None
        
        # Colas acotadas para prevenir buffer bloat (~500ms máx)
        self.audio_queue_in: asyncio.Queue = asyncio.Queue(maxsize=20)
        self.audio_queue_out: asyncio.Queue = asyncio.Queue(maxsize=30)
        
        self.current_volume_rms = 0.05
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._playback_task: Optional[asyncio.Task] = None

        # Parámetros de Envelope Follower (RMS Ballistics)
        self._attack_coeff = 0.35  # ~10ms attack
        self._release_coeff = 0.08 # ~150ms release

    async def start(self):
        """Inicia los flujos de captura y reproducción de audio no bloqueantes."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.info("Modo de audio sin hardware local (interfaz web habilitada).")
            return

        try:
            self._loop = asyncio.get_running_loop()

            def _in_callback(indata, frames, time_info, status):
                if status:
                    logger.debug(f"Audio In Status: {status}")

                # Cálculo de RMS con balística temporal logarítmica
                raw_rms = float(np.sqrt(np.mean(indata**2))) + 1e-6
                # Normalización en rango [0, 1]
                target_rms = min(1.0, raw_rms * 6.0)

                # Suavizado de curva para HUD Canvas
                if target_rms >= self.current_volume_rms:
                    self.current_volume_rms += self._attack_coeff * (target_rms - self.current_volume_rms)
                else:
                    self.current_volume_rms += self._release_coeff * (target_rms - self.current_volume_rms)

                # Conversión a PCM 16-bit Little Endian
                pcm_data = (indata * 32767.0).astype(np.int16).tobytes()

                # Despacho thread-safe a la cola de entrada
                if self.is_recording and self._loop:
                    try:
                        self.audio_queue_in.put_nowait(pcm_data)
                    except asyncio.QueueFull:
                        try:
                            self.audio_queue_in.get_nowait()
                        except Exception:
                            pass
                        self.audio_queue_in.put_nowait(pcm_data)

            self._in_stream = sd.InputStream(
                samplerate=self.sample_rate_in,
                channels=self.channels,
                dtype="float32",
                callback=_in_callback,
                blocksize=512, # ~32ms de latencia ultra-baja
            )
            self._in_stream.start()
            self.is_recording = True
            logger.info("Captura de micrófono iniciada (16kHz PCM + RMS Ballistics).")

            # Iniciar reproductor no bloqueante en hilo separado
            self._playback_task = asyncio.create_task(self._playback_worker())
        except Exception as e:
            logger.error(f"Error iniciando dispositivos de audio locales: {e}")

    async def _playback_worker(self):
        """Reproduce chunks PCM de 24kHz en thread separado para no congelar asyncio."""
        if not SOUNDDEVICE_AVAILABLE:
            return

        try:
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
                if data and out_stream.active:
                    # Ejecutar escritura en hilo de PortAudio para no congelar el event loop
                    await self._loop.run_in_executor(None, out_stream.write, data)
                self.audio_queue_out.task_done()
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Error en worker de reproducción de audio: {e}")
        finally:
            if 'out_stream' in locals() and out_stream:
                out_stream.stop()
                out_stream.close()

    async def play_pcm_chunk(self, pcm_bytes: bytes):
        """Encola un fragmento de audio PCM recibido de Gemini Live para reproducción."""
        if self.is_playing:
            try:
                self.audio_queue_out.put_nowait(pcm_bytes)
                await bus.publish("audio/playback_chunk", {"size": len(pcm_bytes)}, sender="audio_pipeline")
            except asyncio.QueueFull:
                pass

    def interrupt_playback(self):
        """Vacia el búfer de reproducción inmediatamente al detectar interrupción del usuario (Barge-In)."""
        while not self.audio_queue_out.empty():
            try:
                self.audio_queue_out.get_nowait()
                self.audio_queue_out.task_done()
            except Exception:
                break
        logger.info("Búfer de reproducción vaciado por interrupción (Barge-in).")

    async def stop(self):
        """Detiene y libera los streams de audio de forma limpia."""
        self.is_recording = False
        self.is_playing = False
        if self._playback_task:
            self._playback_task.cancel()
        if self._in_stream:
            self._in_stream.stop()
            self._in_stream.close()
        logger.info("Pipeline de audio detenido.")


audio_pipeline = AudioPipeline()
