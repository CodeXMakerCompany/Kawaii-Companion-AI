import asyncio
import os

from dotenv import load_dotenv
from adapters.neumaLLM import NeumaLLM
from events.event_bus import EventBus
from services.transcription import TranscriptionService
from services.speech import SileroSpeech
from services.vtube import VTubeService

load_dotenv()


from events.handlers import (
    logger_handler,
    neuma_automations_handler
)
event_bus = EventBus()

event_bus.register_event('logger_handler', logger_handler)
event_bus.register_event('neuma_automations_handler', neuma_automations_handler)

transcript_queue = asyncio.Queue()


async def AiAssistant():
    transcriptionService = TranscriptionService(event_bus)
    vtubeService = VTubeService(
        os.getenv('VTUBE_API_KEY'),
        os.getenv('VTUBE_API_PORT')
    )
    llmService = NeumaLLM()
    
    # Services Initialize
    SileroSpeech.prepare()
    llmService.init()
    await vtubeService.start()
    
    transcription_task = asyncio.create_task(transcriptionService.real_time_transcription(transcript_queue))

    llm_task = asyncio.create_task(transcriptionService.transcription_worker(transcript_queue, llmService, vtubeService.set_audio_level))
    
    vtube_task = asyncio.create_task(vtubeService.listen_voice_level())
    
    try:
        await asyncio.gather(transcription_task, llm_task, vtube_task)
    except asyncio.CancelledError:
        print("Tasks were cancelled.")
    except KeyboardInterrupt:
        print("Shutdown requested by user.")
    finally:
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
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
