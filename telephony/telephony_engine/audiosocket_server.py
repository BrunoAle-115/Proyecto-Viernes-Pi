"""
V.I.E.R.N.E.S. - Servidor de Streaming de Audio en Tiempo Real (Asterisk AudioSocket)
=====================================================================================
Implementa el protocolo Asterisk AudioSocket (res_audiosocket / app_audiosocket)
para transmisión full-duplex de baja latencia (<30ms) entre canales SIP y el Core de IA.

Protocolo AudioSocket Framing:
- Byte 0: Tipo de Mensaje
    0x01: UUID de Sesión (16 bytes UUID binario)
    0x10: Audio PCM Payload (Linear PCM 16-bit Little-Endian, 8kHz o 16kHz Mono)
    0x00: Hangup / Desconexión de Canal
    0x02: Error en Canal Asterisk
- Bytes 1-2: Longitud del Payload (uint16 Big-Endian)
- Bytes 3..N: Payload de datos
"""

import asyncio
import logging
import struct
import uuid
from typing import Callable, Coroutine, Dict, Optional

logger = logging.getLogger("VIERNES.AudioSocket")


class AudioSocketType:
    HANGUP = 0x00
    UUID = 0x01
    ERROR = 0x02
    AUDIO = 0x10


class AudioSocketSession:
    """Representa una sesión activa de audio bidireccional entre Asterisk y V.I.E.R.N.E.S."""

    def __init__(self, session_uuid: str, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        self.session_uuid: str = session_uuid
        self.reader: asyncio.StreamReader = reader
        self.writer: asyncio.StreamWriter = writer
        self.is_active: bool = True
        self.inbound_audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self.outbound_audio_queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=100)
        self._sample_rate: int = 8000  # Default G.711 / Asterisk standard
        self._channels: int = 1        # Mono
        self._bytes_per_sample: int = 2 # 16-bit PCM

    async def send_audio_frame(self, pcm_chunk: bytes):
        """Envia un fragmento de audio PCM hacia Asterisk."""
        if not self.is_active or self.writer.is_closing():
            return
        
        try:
            length = len(pcm_chunk)
            header = struct.pack("!BH", AudioSocketType.AUDIO, length)
            self.writer.write(header + pcm_chunk)
            await self.writer.drain()
        except Exception as e:
            logger.error(f"Error enviando frame a AudioSocket {self.session_uuid}: {e}")
            self.is_active = False

    async def send_hangup(self):
        """Notifica a Asterisk el fin de la llamada y cierra el canal."""
        if not self.is_active or self.writer.is_closing():
            return
        try:
            header = struct.pack("!BH", AudioSocketType.HANGUP, 0)
            self.writer.write(header)
            await self.writer.drain()
        except Exception as e:
            logger.debug(f"Error enviando hangup a AudioSocket: {e}")
        finally:
            self.is_active = False
            self.writer.close()
            try:
                await self.writer.wait_closed()
            except Exception:
                pass


class AudioSocketServer:
    """
    Servidor TCP para manejar conexiones AudioSocket desde Asterisk.
    """

    def __init__(
        self,
        host: str = "0.0.0.0",
        port: int = 9099,
        on_session_start: Optional[Callable[[AudioSocketSession], Coroutine]] = None,
        on_audio_received: Optional[Callable[[str, bytes], Coroutine]] = None,
        on_session_end: Optional[Callable[[str], Coroutine]] = None,
    ):
        self.host = host
        self.port = port
        self.on_session_start = on_session_start
        self.on_audio_received = on_audio_received
        self.on_session_end = on_session_end
        self.active_sessions: Dict[str, AudioSocketSession] = {}
        self._server: Optional[asyncio.Server] = None
        self._is_running = False

    async def start(self):
        """Inicia el servidor TCP de AudioSocket."""
        self._server = await asyncio.start_server(self._handle_client, self.host, self.port)
        self._is_running = True
        addr = self._server.sockets[0].getsockname() if self._server.sockets else (self.host, self.port)
        logger.info(f"🚀 AudioSocket Server escuchando en {addr[0]}:{addr[1]}")

    async def stop(self):
        """Detiene el servidor y cierra todas las sesiones activas."""
        self._is_running = False
        for session in list(self.active_sessions.values()):
            await session.send_hangup()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        logger.info("🛑 AudioSocket Server detenido.")

    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        peer = writer.get_extra_info("peername")
        logger.info(f"📞 Conexión entrante AudioSocket desde Asterisk: {peer}")

        session: Optional[AudioSocketSession] = None
        session_uuid_str: Optional[str] = None

        try:
            while self._is_running:
                # Leer el encabezado de 3 bytes (1 byte tipo + 2 bytes longitud)
                header = await reader.readexactly(3)
                if not header or len(header) < 3:
                    break

                msg_type, payload_len = struct.unpack("!BH", header)

                # Leer payload según longitud
                payload = b""
                if payload_len > 0:
                    payload = await reader.readexactly(payload_len)

                # Procesar según tipo de mensaje
                if msg_type == AudioSocketType.UUID:
                    # El payload contiene 16 bytes de UUID binario
                    if len(payload) == 16:
                        session_uuid_str = str(uuid.UUID(bytes=payload))
                    else:
                        session_uuid_str = str(uuid.uuid4())
                    
                    logger.info(f"🆔 AudioSocket UUID Registrado: {session_uuid_str}")
                    session = AudioSocketSession(session_uuid_str, reader, writer)
                    self.active_sessions[session_uuid_str] = session

                    if self.on_session_start:
                        asyncio.create_task(self.on_session_start(session))

                elif msg_type == AudioSocketType.AUDIO:
                    if session_uuid_str and self.on_audio_received:
                        # Enviar el fragmento PCM (8kHz/16kHz) al pipeline STT / VAD
                        await self.on_audio_received(session_uuid_str, payload)

                elif msg_type == AudioSocketType.HANGUP:
                    logger.info(f"📴 Asterisk notificó Hangup para sesión {session_uuid_str}")
                    break

                elif msg_type == AudioSocketType.ERROR:
                    logger.warning(f"⚠️ Asterisk reportó Error en sesión {session_uuid_str}")
                    break

        except asyncio.IncompleteReadError:
            logger.debug(f"Canal cerrado por el cliente Asterisk ({session_uuid_str})")
        except Exception as e:
            logger.error(f"Excepción en bucle AudioSocket ({session_uuid_str}): {e}", exc_info=True)
        finally:
            if session_uuid_str and session_uuid_str in self.active_sessions:
                del self.active_sessions[session_uuid_str]
                if self.on_session_end:
                    try:
                        await self.on_session_end(session_uuid_str)
                    except Exception as ex:
                        logger.error(f"Error en on_session_end: {ex}")

            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            logger.info(f"🔒 Sesión AudioSocket cerrada ({session_uuid_str})")
