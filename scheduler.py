import heapq
import threading
import time
from dataclasses import dataclass, field
from itertools import count
from typing import Any, Callable


@dataclass(order=True)
class _Event:
    due_time: float
    order: int
    callback: Callable[..., Any] = field(compare=False)
    args: tuple = field(compare=False, default_factory=tuple)
    kwargs: dict = field(compare=False, default_factory=dict)


class TimedEventScheduler:
    def __init__(self):
        self._events = []
        self._counter = count()
        self._cv = threading.Condition()
        self._running = False
        self._thread = None

    def start(self) -> None:
        with self._cv:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run, name="event-scheduler", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        with self._cv:
            self._running = False
            self._cv.notify_all()
        if self._thread is not None:
            self._thread.join(timeout=2.0)

    def schedule(self, delay_sec: float, callback: Callable[..., Any], *args, **kwargs) -> None:
        due = time.monotonic() + max(0.0, float(delay_sec))
        event = _Event(due, next(self._counter), callback, args, kwargs)
        with self._cv:
            heapq.heappush(self._events, event)
            self._cv.notify_all()

    def _run(self) -> None:
        while True:
            with self._cv:
                while self._running and not self._events:
                    self._cv.wait()

                if not self._running:
                    return

                now = time.monotonic()
                event = self._events[0]
                if event.due_time > now:
                    self._cv.wait(timeout=event.due_time - now)
                    continue

                heapq.heappop(self._events)

            try:
                event.callback(*event.args, **event.kwargs)
            except Exception as exc:
                print(f"[scheduler] callback error: {exc}")
