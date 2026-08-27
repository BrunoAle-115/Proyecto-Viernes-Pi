"""
Pipeline de Audio Bidireccional Full-Dúplex Plug-and-Play para V.I.E.R.N.E.S.
Soporte Universal para cualquier Micrófono y Parlante USB en Raspberry Pi 5 / Linux ALSA:
- Auto-descubrimiento de dispositivos de audio USB (Fifine, Blue Yeti, Jabra, PnP, etc.).
- Modo 'Ever Listen': Escucha continua 24/7 en segundo plano con Wake-Word local y VAD.
- Hot-Plug Watchdog: Auto-recuperación y conmutación automática si el micrófono/parlante USB se conecta o desconecta en caliente.
- DSP de latencia ultra-baja (16kHz entrada / 24kHz salida con RMS Ballistics).
"""

import os
import sys
import asyncio
import logging
import numpy as np
from typing import Optional, Tuple, Dict, Any, List
from viernes.core.event_bus import bus
from viernes.core.wake_word import wakeword_detector

logger = logging.getLogger("viernes.audio")

try:
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except Exception:
    SOUNDDEVICE_AVAILABLE = False
    logger.warning("sounddevice no disponible. Operando en modo headless.")


class UniversalAudioPipeline:
    def __init__(self, sample_rate_in: int = 16000, sample_rate_out: int = 24000, channels: int = 1):
        self.sample_rate_in = sample_rate_in
        self.sample_rate_out = sample_rate_out
        self.channels = channels
        self.is_recording = False
        self.is_playing = False
        self.ever_listen_enabled = True
        
        self.input_device_id: Optional[int] = None
        self.output_device_id: Optional[int] = None
        self.input_device_name: str = "Default Audio Input"
        self.output_device_name: str = "Default Audio Output"
        
        self._in_stream: Optional[sd.InputStream] = None
        self._out_stream: Optional[sd.RawOutputStream] = None
        
        # Colas acotadas anti-bufferbloat (~400ms)
        self.audio_queue_in: asyncio.Queue = asyncio.Queue(maxsize=25)
        self.audio_queue_out: asyncio.Queue = asyncio.Queue(maxsize=35)
        
        self.current_volume_rms = 0.03
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._playback_task: Optional[asyncio.Task] = None
        self._watchdog_task: Optional[asyncio.Task] = None

        # RMS Ballistics (Attack 10ms, Release 140ms)
        self._attack_coeff = 0.35
        self._release_coeff = 0.08

    # =========================================================================
    # AUTO-DESCUBRIMIENTO UNIVERSAL DE HARDWARE USB (PnP)
    # =========================================================================
    def discover_hardware_devices(self) -> Tuple[Optional[int], Optional[int]]:
        """
        Escanea todos los dispositivos ALSA/PulseAudio/PortAudio del sistema y
        prioriza automáticamente cualquier micrófono o parlante USB conectado.
        """
        if not SOUNDDEVICE_AVAILABLE:
            return None, None

        in_id = None
        out_id = None
        in_name = "Default"
        out_name = "Default"

        try:
            devices = sd.query_devices()
            logger.debug(f"Dispositivos de audio detectados: {len(devices)}")

            # 1. Buscar Micrófono USB prioritario
            for idx, dev in enumerate(devices):
                name = dev["name"].lower()
                max_in = dev["max_input_channels"]
                if max_in > 0:
                    # Priorizar USB Microphone / PnP / Soundcard externa
                    if any(k in name for k in ("usb", "mic", "input", "fifine", "yeti", "jabra", "headset", "audio")):
                        in_id = idx
                        in_name = dev["name"]
                        break
                    elif in_id is None:
                        in_id = idx
                        in_name = dev["name"]

            # 2. Buscar Parlante / Salida de Audio USB o HDMI/Default
            for idx, dev in enumerate(devices):
                name = dev["name"].lower()
                max_out = dev["max_output_channels"]
                if max_out > 0:
                    # Priorizar Parlante USB / DAC
                    if any(k in name for k in ("usb", "speaker", "output", "dac", "headset", "jabra", "audio")):
                        out_id = idx
                        out_name = dev["name"]
                        break
                    elif out_id is None:
                        out_id = idx
                        out_name = dev["name"]

        except Exception as e:
            logger.debug(f"Error consultando dispositivos sounddevice: {e}")

        self.input_device_id = in_id
        self.output_device_id = out_id
        self.input_device_name = in_name
        self.output_device_name = out_name

        logger.info(f"🎙️ Micrófono Seleccionado: [{in_id}] {in_name}")
        logger.info(f"🔊 Parlante Seleccionado: [{out_id}] {out_name}")
        return in_id, out_id

    # =========================================================================
    # INICIO DE STREAMS FULL-DÚPLEX
    # =========================================================================
    async def start(self):
        """Inicia captura y reproducción de audio no bloqueantes."""
        if not SOUNDDEVICE_AVAILABLE:
            logger.info("Modo de audio sin hardware local (interfaz web habilitada).")
            return

        self._loop = asyncio.get_running_loop()
        self.discover_hardware_devices()

        try:
            # 1. Configurar Callback de Captura de Micrófono (Ever-Listen)
            def _in_callback(indata, frames, time_info, status):
                if status:
                    logger.debug(f"Status Audio In: {status}")

                # Cálculo de RMS balístico para visualizador en tiempo real
                raw_rms = float(np.sqrt(np.mean(indata**2))) + 1e-6
                target_rms = min(1.0, raw_rms * 6.5)

                if target_rms >= self.current_volume_rms:
                    self.current_volume_rms += self._attack_coeff * (target_rms - self.current_volume_rms)
                else:
                    self.current_volume_rms += self._release_coeff * (target_rms - self.current_volume_rms)

                # Conversión a PCM 16-bit Little Endian (16kHz)
                pcm_data = (indata * 32767.0).astype(np.int16).tobytes()

                # Enviar a detector de Wake Word continuo (Ever-Listen)
                if self.ever_listen_enabled and self._loop:
                    asyncio.run_coroutine_threadsafe(
                        wakeword_detector.process_pcm_frame(pcm_data),
                        self._loop
                    )

                # Encolar para transmisión directa a Gemini Live
                if self.is_recording and self._loop:
                    try:
                        self.audio_queue_in.put_nowait(pcm_data)
                    except asyncio.QueueFull:
                        try:
                            self.audio_queue_in.get_nowait()
                        except Exception:
                            pass
                        self.audio_queue_in.put_nowait(pcm_data)

            # Iniciar InputStream con el dispositivo detectado
            self._in_stream = sd.InputStream(
                device=self.input_device_id,
                samplerate=self.sample_rate_in,
                channels=self.channels,
                dtype="float32",
                callback=_in_callback,
                blocksize=512, # ~32ms latencia ultra-baja
            )
            self._in_stream.start()
            self.is_recording = True
            wakeword_detector.is_active = True
            logger.info("✓ Micrófono USB en línea: Ever-Listen y detección 'Oye Viernes' activos.")

            # 2. Iniciar Worker de Reproducción en Parlante USB
            self._playback_task = asyncio.create_task(self._playback_worker())

            # 3. Iniciar Watchdog de Hot-Plug USB
            if not self._watchdog_task or self._watchdog_task.done():
                self._watchdog_task = asyncio.create_task(self._usb_hotplug_watchdog())

        except Exception as e:
            logger.warning(f"No se pudo inicializar micrófono local de inmediato: {e}. El watchdog intentará auto-conectar cuando se enchufe.")

    async def _playback_worker(self):
        """Reproduce chunks PCM de 24kHz en hilo de PortAudio para no congelar asyncio."""
        if not SOUNDDEVICE_AVAILABLE:
            return

        try:
            self._out_stream = sd.RawOutputStream(
                device=self.output_device_id,
                samplerate=self.sample_rate_out,
                channels=self.channels,
                dtype="int16",
                blocksize=1024,
            )
            self._out_stream.start()
            self.is_playing = True
            logger.info("✓ Parlante USB en línea: Reproducción PCM 24kHz lista.")

            while self.is_playing:
                data = await self.audio_queue_out.get()
                if data and self._out_stream and self._out_stream.active:
                    await self._loop.run_in_executor(None, self._out_stream.write, data)
                self.audio_queue_out.task_done()

        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.debug(f"Error en worker de reproducción: {e}")
        finally:
            if self._out_stream:
                try:
                    self._out_stream.stop()
                    self._out_stream.close()
                except Exception:
                    pass

    # =========================================================================
    # WATCHDOG DE CONEXIÓN EN CALIENTE (HOT-PLUG)
    # =========================================================================
    async def _usb_hotplug_watchdog(self):
        """Monitorea periódicamente la presencia de nuevos micrófonos/parlantes USB conectados."""
        last_in = self.input_device_id
        last_out = self.output_device_id

        while True:
            await asyncio.sleep(8)
            if not SOUNDDEVICE_AVAILABLE:
                continue

            try:
                cur_in, cur_out = self.discover_hardware_devices()
                # Si los dispositivos cambiaron (ej: se enchufó un nuevo micrófono USB)
                if cur_in != last_in or cur_out != last_out or not self.is_recording:
                    logger.info("🔄 [Audio Hot-Plug] Dispositivos de audio USB cambiaron. Re-inicializando pipeline...")
                    last_in = cur_in
                    last_out = cur_out
                    await self.restart()
            except Exception as e:
                logger.debug(f"Watchdog audio check: {e}")

    async def play_pcm_chunk(self, pcm_bytes: bytes):
        """Encola un fragmento de audio PCM recibido de Gemini Live para reproducción."""
        if self.is_playing:
            try:
                self.audio_queue_out.put_nowait(pcm_bytes)
                await bus.publish("audio/playback_chunk", {"size": len(pcm_bytes)}, sender="audio_pipeline")
            except asyncio.QueueFull:
                pass

    def interrupt_playback(self):
        """Vacia el búfer de reproducción inmediatamente (Barge-In)."""
        while not self.audio_queue_out.empty():
            try:
                self.audio_queue_out.get_nowait()
                self.audio_queue_out.task_done()
            except Exception:
                break

    async def restart(self):
        """Reinicia el pipeline de audio limpiamente."""
        await self.stop()
        await self.start()

    async def stop(self):
        """Detiene los streams de audio de forma limpia."""
        self.is_recording = False
        self.is_playing = False
        if self._playback_task and not self._playback_task.done():
            self._playback_task.cancel()
        if self._in_stream:
            try:
                self._in_stream.stop()
                self._in_stream.close()
            except Exception:
                pass
            self._in_stream = None
        if self._out_stream:
            try:
                self._out_stream.stop()
                self._out_stream.close()
            except Exception:
                pass
            self._out_stream = None


audio_pipeline = UniversalAudioPipeline()
