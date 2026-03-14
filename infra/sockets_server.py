import asyncio
import json
from aiohttp import web
import aiohttp


connected_clients = set()

# Global cache: set when client sends {"type": "save_model_expressions", ...}. Consume via: from infra.sockets_server import model_expressions_cache
model_expressions_cache = None

# WebSocket Configuration (0.0.0.0 so Docker port mapping can reach the server)
SOCKET_BASE = "0.0.0.0"
SOCKET_PORT = 7769
SOCKET_PREFIX = "waifu-client-ws"


class SocketsServer:
    def __init__(self, event_bus=None):
        self.event_bus = event_bus

    async def initialize(self):
        """Initialize the web application"""
        app = web.Application()
        app.router.add_get(f"/{SOCKET_PREFIX}", self.websocket_handler)
        return app

    async def websocket_handler(self, request):
        """Handle WebSocket connections"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        connected_clients.add(ws)
        print(f"Client connected. Total clients: {len(connected_clients)}")

        try:
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(f"Received message: {msg.data}")
                    try:
                        payload = json.loads(msg.data) if isinstance(msg.data, str) else msg.data
                    except (json.JSONDecodeError, TypeError):
                        payload = None
                    
                    if payload and payload.get("type") == "save_model_expressions":
                        global model_expressions_cache
                        model_expressions_cache = payload.get("expressions", [])

                    if payload and payload.get("type") == "voice_input" and self.event_bus:
                        await self.event_bus.emit_event("voice_input", payload)
                        await ws.send_str(json.dumps({"type": "voice_input_ack", "text": payload.get("text", "")}))
                    elif payload:
                        await ws.send_str(json.dumps({"type": "echo", "data": msg.data}))
                    else:
                        await ws.send_str(f"Echo: {msg.data}")
                elif msg.type == aiohttp.WSMsgType.ERROR:
                    print(f"WebSocket error: {ws.exception()}")
        finally:
            connected_clients.discard(ws)
            print(f"Client disconnected. Total clients: {len(connected_clients)}")

        return ws

    async def start_websocket_server(self):
        """Start the WebSocket server"""
        app = await self.initialize()
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, SOCKET_BASE, SOCKET_PORT)
        await site.start()
        print(
            f"WebSocket server started at ws://{SOCKET_BASE}:{SOCKET_PORT}/{SOCKET_PREFIX}"
        )
        return runner

    @staticmethod
    async def broadcast_message(message: str):
        """Broadcast message to all connected clients"""
        if connected_clients:
            await asyncio.gather(
                *[client.send_str(message) for client in connected_clients],
                return_exceptions=True,
            )
