"""
Bus de Eventos Asíncrono de V.I.E.R.N.E.S.
Permite la comunicación reactiva desacoplada entre módulos (IoT, Audio, SIP, GitHub, Mail, HUD).
"""

import asyncio
import logging
from typing import Callable, Coroutine, Dict, List, Any
from datetime import datetime

logger = logging.getLogger("viernes.event_bus")


class Event:
    def __init__(self, topic: str, data: Any = None, sender: str = "system"):
        self.topic = topic
        self.data = data or {}
        self.sender = sender
        self.timestamp = datetime.now().isoformat()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "data": self.data,
            "sender": self.sender,
            "timestamp": self.timestamp,
        }


class EventBus:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(EventBus, cls).__new__(cls)
            cls._instance._subscribers: Dict[str, List[Callable[[Event], Coroutine[Any, Any, None]]]] = {}
            cls._instance._history: List[Event] = []
            cls._instance._max_history = 100
        return cls._instance

    def subscribe(self, topic: str, callback: Callable[[Event], Coroutine[Any, Any, None]]):
        """Suscribe una corrutina a un tópico de eventos."""
        if topic not in self._subscribers:
            self._subscribers[topic] = []
        if callback not in self._subscribers[topic]:
            self._subscribers[topic].append(callback)
            logger.debug(f"Subscrito a '{topic}': {callback.__name__}")

    def unsubscribe(self, topic: str, callback: Callable[[Event], Coroutine[Any, Any, None]]):
        """Desuscribe una corrutina de un tópico."""
        if topic in self._subscribers and callback in self._subscribers[topic]:
            self._subscribers[topic].remove(callback)

    async def publish(self, topic: str, data: Any = None, sender: str = "system") -> Event:
        """Publica un evento a todos los suscriptores del tópico y tópicos wildcard ('*')."""
        event = Event(topic=topic, data=data, sender=sender)
        self._history.append(event)
        if len(self._history) > self._max_history:
            self._history.pop(0)

        targets = list(self._subscribers.get(topic, []))
        wildcards = list(self._subscribers.get("*", []))
        all_callbacks = set(targets + wildcards)

        if all_callbacks:
            tasks = [asyncio.create_task(self._safe_call(cb, event)) for cb in all_callbacks]
            await asyncio.gather(*tasks, return_exceptions=True)

        return event

    async def _safe_call(self, callback: Callable[[Event], Coroutine[Any, Any, None]], event: Event):
        try:
            await callback(event)
        except Exception as e:
            logger.error(f"Error en callback {callback.__name__} para evento {event.topic}: {e}", exc_info=True)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return [e.to_dict() for e in self._history[-limit:]]


# Instancia global singleton
bus = EventBus()
