import asyncio
import base64
import json
import time
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from viernes.core.event_bus import bus, Event
from viernes.core.gemini_live import GeminiLiveClient
from viernes.core.tools_registry import ToolsDispatcher
from viernes.web.server import ConnectionManager, on_system_event

class MockAudioBuffer:
    def __init__(self, num_samples: int, sample_rate: int = 24000):
        self.duration = num_samples / sample_rate
        self.num_samples = num_samples
        self.sample_rate = sample_rate

class SimulatedLiveAudioPlayer:
    def __init__(self, source_sample_rate: int = 24000, lead_time: float = 0.050, hangover_ms: float = 150.0):
        self.source_sample_rate = source_sample_rate
        self.lead_time = lead_time
        self.hangover_ms = hangover_ms
        self.next_start_time = 0.0
        self.active_sources = set()
        self.leftover_bytes = b""
        self.scheduled_timeline = []
        self.last_audio_end_time = 0.0
        self.is_speaking = False

    def play_chunk(self, base64_data: str, current_ctx_time: float) -> dict:
        if not base64_data:
            return {"scheduled": False}

        raw_bytes = base64.b64decode(base64_data)
        total_bytes = self.leftover_bytes + raw_bytes
        self.leftover_bytes = b""

        num_bytes = len(total_bytes)
        is_odd = num_bytes % 2 != 0
        processable_bytes = num_bytes - 1 if is_odd else num_bytes
        num_samples = processable_bytes // 2

        if is_odd:
            self.leftover_bytes = total_bytes[-1:]

        if num_samples == 0:
            return {"scheduled": False, "leftover": len(self.leftover_bytes)}

        buffer = MockAudioBuffer(num_samples, self.source_sample_rate)

        if self.next_start_time < current_ctx_time:
            self.next_start_time = current_ctx_time + self.lead_time

        scheduled_start = self.next_start_time
        scheduled_end = scheduled_start + buffer.duration
        self.next_start_time = scheduled_end

        source_id = f"src_{len(self.scheduled_timeline) + 1}"
        self.active_sources.add(source_id)
        self.is_speaking = True

        entry = {
            "source_id": source_id,
            "start": scheduled_start,
            "end": scheduled_end,
            "duration": buffer.duration,
            "samples": num_samples
        }
        self.scheduled_timeline.append(entry)
        return {"scheduled": True, "entry": entry}

    def on_source_ended(self, source_id: str, wall_clock_now: float):
        self.active_sources.discard(source_id)
        if len(self.active_sources) == 0:
            self.last_audio_end_time = wall_clock_now
            self.is_speaking = False

    def is_audio_actively_playing(self, wall_clock_now: float) -> bool:
        if len(self.active_sources) > 0:
            return True
        return (wall_clock_now - self.last_audio_end_time) < (self.hangover_ms / 1000.0)

    def stop_all(self, wall_clock_now: float):
        self.active_sources.clear()
        self.next_start_time = 0.0
        self.leftover_bytes = b""
        self.last_audio_end_time = 0.0
        self.is_speaking = False

def test_live_audio_player_gapless_sequential_scheduling():
    player = SimulatedLiveAudioPlayer(source_sample_rate=24000, lead_time=0.050)
    chunk_50ms_bytes = b"\x00\x00" * 1200
    b64_chunk = base64.b64encode(chunk_50ms_bytes).decode("ascii")

    res1 = player.play_chunk(b64_chunk, current_ctx_time=1.0)
    e1 = res1["entry"]
    assert e1["start"] == pytest.approx(1.050, rel=1e-4)
    assert e1["end"] == pytest.approx(1.100, rel=1e-4)

    res2 = player.play_chunk(b64_chunk, current_ctx_time=1.03)
    e2 = res2["entry"]
    assert e2["start"] == pytest.approx(1.100, rel=1e-4)
    assert e2["end"] == pytest.approx(1.150, rel=1e-4)

    res3 = player.play_chunk(b64_chunk, current_ctx_time=1.05)
    e3 = res3["entry"]
    assert e3["start"] == pytest.approx(1.150, rel=1e-4)
    assert e3["end"] == pytest.approx(1.200, rel=1e-4)

    assert e1["end"] == e2["start"]
    assert e2["end"] == e3["start"]

def test_live_audio_player_resync_on_underrun():
    player = SimulatedLiveAudioPlayer(source_sample_rate=24000, lead_time=0.050)
    chunk_bytes = b"\x00\x00" * 1200
    b64_chunk = base64.b64encode(chunk_bytes).decode("ascii")

    res1 = player.play_chunk(b64_chunk, current_ctx_time=0.5)
    assert res1["entry"]["end"] == pytest.approx(0.600, rel=1e-4)

    res2 = player.play_chunk(b64_chunk, current_ctx_time=2.0)
    assert res2["entry"]["start"] == pytest.approx(2.050, rel=1e-4)
    assert res2["entry"]["end"] == pytest.approx(2.100, rel=1e-4)

def test_live_audio_player_stop_and_acoustic_hangover():
    player = SimulatedLiveAudioPlayer(source_sample_rate=24000, hangover_ms=150.0)
    chunk = base64.b64encode(b"\x00\x00" * 240).decode("ascii")
    
    player.play_chunk(chunk, current_ctx_time=0.0)
    assert player.is_speaking is True
    assert player.is_audio_actively_playing(wall_clock_now=10.0) is True

    player.on_source_ended("src_1", wall_clock_now=10.0)
    assert len(player.active_sources) == 0

    assert player.is_audio_actively_playing(wall_clock_now=10.050) is True
    assert player.is_audio_actively_playing(wall_clock_now=10.200) is False

    player.play_chunk(chunk, current_ctx_time=1.0)
    player.stop_all(wall_clock_now=20.0)
    assert len(player.active_sources) == 0
    assert player.next_start_time == 0.0
    assert player.leftover_bytes == b""

class MockWebSocket:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.sent_messages = []
        self.is_closed = False

    async def accept(self):
        pass

    async def send_json(self, data: dict):
        if self.is_closed:
            raise ConnectionResetError("Socket cerrado")
        self.sent_messages.append(data)

    async def close(self, code: int = 1000, reason: str = ""):
        self.is_closed = True

def test_websocket_manager_voice_master_unicast_routing():
    async def _test():
        mgr = ConnectionManager()
        ws1 = MockWebSocket("client_1")
        ws2 = MockWebSocket("client_2")

        await mgr.connect(ws1, session_id="sess_1")
        await mgr.connect(ws2, session_id="sess_2")
        assert len(mgr.active_connections) == 2

        test_msg = {"type": "event", "topic": "system/alert", "data": {"status": "ok"}}
        await mgr.broadcast(test_msg)
        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 1

        mgr.set_voice_master(ws2)

        audio_msg = {"type": "audio_out", "data": "b64pcm...", "mimeType": "audio/pcm;rate=24000"}
        await mgr.send_voice_audio(audio_msg)

        assert len(ws1.sent_messages) == 1
        assert len(ws2.sent_messages) == 2
        assert ws2.sent_messages[1]["type"] == "audio_out"

    asyncio.run(_test())

def test_websocket_manager_anti_zombie_eviction():
    async def _test():
        mgr = ConnectionManager()
        old_ws = MockWebSocket("old_socket")
        new_ws = MockWebSocket("new_socket")

        await mgr.connect(old_ws, session_id="same_user_token")
        assert old_ws in mgr.active_connections

        await mgr.connect(new_ws, session_id="same_user_token")
        assert old_ws.is_closed is True
        assert old_ws not in mgr.active_connections
        assert new_ws in mgr.active_connections
        assert mgr.active_voice_ws == new_ws

    asyncio.run(_test())
