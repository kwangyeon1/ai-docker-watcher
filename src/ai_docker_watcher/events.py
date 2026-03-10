from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable


@dataclass(slots=True)
class Event:
    name: str
    payload: dict[str, Any]
    source: str
    created_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


Subscriber = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Subscriber]] = defaultdict(list)
        self._queue: deque[Event] = deque()

    def subscribe(self, event_name: str, handler: Subscriber) -> None:
        self._subscribers[event_name].append(handler)

    def publish(self, event: Event) -> None:
        self._queue.append(event)

    def drain(self) -> None:
        while self._queue:
            event = self._queue.popleft()
            for handler in self._subscribers.get(event.name, []):
                handler(event)
