import asyncio


class EventBus:
    def __init__(self):
        self._events = {}

    def register_event(self, event_name, handler):
        """Register a handler for a specific event."""
        self._events[event_name] = handler

    async def emit_event(self, event_name, data):
        """Emit an event and call the associated handler."""
        if event_name in self._events:
            handler = self._events[event_name]

            if asyncio.iscoroutinefunction(handler):
                await handler(data)  # Await async handlers
            else:
                handler(data)  # Call sync handlers directly
        else:
            raise ValueError(f"No handler registered for event: {event_name}")