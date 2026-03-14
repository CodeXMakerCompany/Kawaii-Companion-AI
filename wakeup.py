import asyncio
import json

from dotenv import load_dotenv
from adapters.neumaLLM import NeumaLLM
from events.event_bus import EventBus
from infra.sockets_server import SocketsServer
load_dotenv()

from events.handlers import logger_handler, neuma_automations_handler

event_bus = EventBus()

event_bus.register_event("logger_handler", logger_handler)
event_bus.register_event("neuma_automations_handler", neuma_automations_handler)

transcript_queue = asyncio.Queue()


async def voice_input_handler(llm_service, payload: dict):
    """Event-bus handler: run LLM on voice text and broadcast response to WebSocket clients."""
    text = (payload.get("text") or "").strip()
    if not text:
        return
    try:
        result = await asyncio.to_thread(llm_service.ask, text)
        if not result:
            return
        out = {
            "type": "llm_response",
            "text": result.get("aIText", ""),
            "code": result.get("aICode"),
            "expression": result.get("expression"),
        }
        await SocketsServer.broadcast_message(json.dumps(out))
    except Exception as e:
        err_msg = str(e) or "LLM error"
        if "connect" in err_msg.lower() or "connection" in err_msg.lower():
            err_msg = "Cannot reach Ollama. Set OLLAMA_BASE_URL=http://host.docker.internal:11434 if running in Docker."
        await SocketsServer.broadcast_message(
            json.dumps({"type": "llm_error", "text": err_msg})
        )


async def AiAssistant():
    llmService = NeumaLLM()
    llmService.init()

    # voice_input: WebSocket -> event_bus -> LLM -> broadcast
    async def on_voice_input(data):
        await voice_input_handler(llmService, data)
    event_bus.register_event("voice_input", on_voice_input)

    socket_server = SocketsServer(event_bus=event_bus)
    runner = await socket_server.start_websocket_server()

    try:
        print("Neuma is listening")
        # Keep running until cancelled (e.g. Ctrl+C or docker stop)
        await asyncio.Future()
    except asyncio.CancelledError:
        print("Tasks were cancelled.")
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    finally:
        await runner.cleanup()
        print("All tasks terminated. Cleaning up.")


if __name__ == "__main__":
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    try:
        loop.run_until_complete(AiAssistant())
    except KeyboardInterrupt:
        pass
    finally:
        loop.close()
