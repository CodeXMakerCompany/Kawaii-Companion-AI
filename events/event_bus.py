import asyncio


class EventBus:
    def __init__(self):
        self._events = {}

    def register_event(self, event_name, handler):
        """Register a handler for a specific event."""
        self._events[event_name] = handler

    async def emit_event(self, event_name, data, returnable: bool = False):
        """Emit an event and call the associated handler."""
        if event_name in self._events:
            handler = self._events[event_name]

            if asyncio.iscoroutinefunction(handler):
               data = await handler(data)  # Await async handlers
            else:
               data = handler(data)  # Call sync handlers directly
            
            if returnable:
                return data
        else:
            raise ValueError(f"No handler registered for event: {event_name}")