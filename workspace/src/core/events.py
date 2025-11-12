# masha_lang/core/events.py
from collections import defaultdict

class EventBus:
    def __init__(self):
        self._listeners = defaultdict(list)

    def on(self, event_name, fn):
        self._listeners[event_name].append(fn)

    def emit(self, event_name, **kwargs):
        results = []
        for fn in self._listeners.get(event_name, []):
            results.append(fn(**kwargs))
        return results
