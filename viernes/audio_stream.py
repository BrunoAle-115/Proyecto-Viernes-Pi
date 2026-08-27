"""
Gestor de transmisión y reproducción de audio en tiempo real (PCM 16kHz entrada / 24kHz salida).
Incluye búfer circular asíncrono y control de interrupción instantánea (Barge-in).
"""

import asyncio
import logging
from typing import Optional

try:
    import pyaudio
    PYAUDIO_AVAILABLE = True
except ImportError:
    PYAUDIO_AVAILABLE = False

from viernes import config

logger = logging.getLogger("VIERNES.Audio")


class AudioStreamManager:
    """Administra la captura de micrófono a 16kHz y la reproducción a altavoces a 24kHz."""

    def __init__(self):
        self.pyaudio_instance: Optional[pyaudio.PyAudio] = None if not PYAUDIO_AVAILABLE else pyaudio.PyAudio()
        self.input_stream = None
        self.output_stream = None

        # Colas asíncronas para desacoplar el hardware de la red WebSocket
        self.input_queue: asyncio.Queue[bytes] = asyncio.Queue()
        self.output_queue: asyncio.Queue[bytes] = asyncio.Queue()
        
        self.is_running = False
        self._playback_task: Optional[asyncio.Task] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop):
        """Inicializa los dispositivos de hardware de audio y los flujos."""
        self._loop = loop
        self.is_running = True

        if not PYAUDIO_AVAILABLE:
            logger.warning("[Audio] PyAudio no está instalado. Operando en modo silencioso/simulado.")
            return

        try:
            # 1. Flujo de Entrada de Micrófono (16kHz, 16-bit Mono)
            self.input_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=config.AUDIO_INPUT_CHANNELS,
                rate=config.AUDIO_INPUT_SAMPLE_RATE,
                input=True,
                frames_per_buffer=config.AUDIO_INPUT_CHUNK_SIZE,
                stream_callback=self._mic_callback
            )
            self.input_stream.start_stream()
            logger.info(f"[Audio] Micrófono iniciado: {config.AUDIO_INPUT_SAMPLE_RATE} Hz, 16-bit LE Mono.")

            # 2. Flujo de Salida de Altavoces (24kHz, 16-bit Mono)
            self.output_stream = self.pyaudio_instance.open(
                format=pyaudio.paInt16,
                channels=config.AUDIO_OUTPUT_CHANNELS,
                rate=config.AUDIO_OUTPUT_SAMPLE_RATE,
                output=True,
                frames_per_buffer=config.AUDIO_OUTPUT_CHUNK_SIZE
            )
            self.output_stream.start_stream()
            logger.info(f"[Audio] Altavoces iniciados: {config.AUDIO_OUTPUT_SAMPLE_RATE} Hz, 16-bit LE Mono.")

            # Iniciar consumidor de reproducción
            self._playback_task = asyncio.create_task(self._playback_worker())

        except Exception as e:
            logger.error(f"[Audio] Error al inicializar dispositivos de audio: {e}")

    def _mic_callback(self, in_data, frame_count, time_info, status):
        """Callback ejecutado por el hilo de PyAudio cuando hay nuevos frames del micrófono."""
        if self.is_running and in_data and self._loop:
            # Enviar los bytes PCM a la cola asíncrona de manera segura entre hilos
            self._loop.call_soon_threadsafe(self.input_queue.put_nowait, in_data)
        return (None, pyaudio.paContinue)

    async def get_input_chunk(self) -> bytes:
        """Obtiene el siguiente trozo de audio PCM de 16kHz del micrófono."""
        return await self.input_queue.get()

    def put_output_chunk(self, pcm_data: bytes):
        """Encola datos de audio PCM de 24kHz recibidos de Gemini para ser reproducidos."""
        if self.is_running:
            self.output_queue.put_nowait(pcm_data)

    async def _playback_worker(self):
        """Consume datos de la cola de salida y los escribe en los altavoces de forma no bloqueante."""
        while self.is_running:
            try:
                data = await self.output_queue.get()
                if self.output_stream and self.output_stream.is_active():
                    # Ejecutar la escritura en el executor para no bloquear el bucle de eventos asyncio
                    await self._loop.run_in_executor(None, self.output_stream.write, data)
                self.output_queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"[Audio] Error en reproducción: {e}")
                await asyncio.sleep(0.01)

    def interrupt_playback(self):
        """Interrupción inmediata (Barge-in): limpia el búfer de audio pendiente para callar a la IA."""
        logger.info("🛑 [Audio Interruption] Usuario hablando. Vaciando búfer de reproducción de V.I.E.R.N.E.S.")
        cleared_chunks = 0
        while not self.output_queue.empty():
            try:
                self.output_queue.get_nowait()
                self.output_queue.task_done()
                cleared_chunks += 1
            except (asyncio.QueueEmpty, ValueError):
                break
        logger.debug(f"[Audio] Se descartaron {cleared_chunks} trozos de audio del búfer.")

    def stop(self):
        """Detiene y libera todos los recursos de audio."""
        self.is_running = False
        if self._playback_task:
            self._playback_task.cancel()

        if self.input_stream:
            try:
                self.input_stream.stop_stream()
                self.input_stream.close()
            except Exception:
                pass

        if self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except Exception:
                pass

        if self.pyaudio_instance:
            try:
                self.pyaudio_instance.terminate()
            except Exception:
                pass
        logger.info("[Audio] Recursos de audio liberados exitosamente.")
