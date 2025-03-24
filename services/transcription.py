import asyncio
from concurrent.futures import ThreadPoolExecutor
import signal
import threading
from deepgram import DeepgramClient, Microphone, LiveOptions, LiveTranscriptionEvents, DeepgramClientOptions

from core.automation.mic.main import MicrophoneManager
from events.event_bus import EventBus
from services.speech import SileroSpeech

is_finals = []
class TranscriptionService:
    def __init__(self, event_bus: EventBus, mode : str = 'CHAT'):
        self.event_bus = event_bus
        self.mode = 'CHAT'
        self.microphoneManager = MicrophoneManager()
        # todo env oclusion fix 
    async def real_time_transcription(self, queue):
        
        try:
            micManager = self.microphoneManager
            print('Mic status', micManager.getMicStatus())
            config = DeepgramClientOptions(options={"keepalive": "true"})
            deepgram = DeepgramClient("", config)
            dg_connection = deepgram.listen.asyncwebsocket.v("1")

            async def on_open(self, open, **kwargs):
                print("Neuma is listening")

            async def on_message(self, result, **kwargs):
                # mute validation to avoid clash between devices streaming audio
                if microphone.is_muted() and not micManager.getMicStatus():
                    microphone.unmute()
          
                    
                sentence = result.channel.alternatives[0].transcript
                if len(sentence) == 0:
                    return
                if result.is_final:
                # We need to collect these and concatenate them together when we get a speech_final=true
                # See docs: https://developers.deepgram.com/docs/understand-endpointing-interim-results
                    is_finals.append(sentence)

                # Speech Final means we have detected sufficent silence to consider this end of speech
                # Speech final is the lowest latency result as it triggers as soon an the endpointing value has triggered
                if result.speech_final:
                    # Concatenate and process the accumulated sentences
                    utterance = " ".join(is_finals)
                    if utterance.strip():  # Ensure we don't print empty strings
                        
                        await queue.put(utterance)
                        # Mute the microphone and wait for playback to complete
                        microphone.mute()
                        micManager.mute()
                        
                    is_finals.clear()
                    
            dg_connection.on(LiveTranscriptionEvents.Open, on_open)
            dg_connection.on(LiveTranscriptionEvents.Transcript, on_message)

            # Retry connection
            options = LiveOptions(
                 model="nova-2",
                language="en-US",
                smart_format=True,
                encoding="linear16",
                channels=1,           
                sample_rate=16000,
                interim_results=True,
                endpointing=300,    
            )
            addons = {"no_delay": "true"}

            max_retries = 5
            retry_delay = 2

            for attempt in range(max_retries):
                try:
                    if await dg_connection.start(options, addons=addons):
                        break
                except Exception as e:
                    print(f"Retry {attempt + 1}/{max_retries}: {e}")
                    await asyncio.sleep(retry_delay)
            else:
                print("Failed to connect after retries.")
                return

            microphone = Microphone(dg_connection.send)
            threading.Thread(target=microphone.start, daemon=True).start()

            # Handle shutdown
            stop_event = asyncio.Event()

            def handle_shutdown():
                microphone.finish()
                stop_event.set()

            for sig_name in ('SIGINT', 'SIGTERM'):
                signal.signal(getattr(signal, sig_name), lambda s, f: handle_shutdown())

            while not stop_event.is_set():
                await asyncio.sleep(2)

        except Exception as e:
            print(f"Could not open socket: {e}")
    
    async def transcription_worker(self, queue, assitantLLM, set_audio_level):
    
        """Processes transcripts using NeumaLLM."""
        while True:
            transcript = await queue.get()  
            # PASS TROUGT AUTOMATIONS EVENT BUSS
            
            await self.event_bus.emit_event('neuma_automations_handler', {  'text': transcript,  'assitantLLM':  assitantLLM })
            
            await self.event_bus.emit_event('logger_handler', {  'user': True,  'message':  transcript })

            loop = asyncio.get_running_loop()
            
            result = await loop.run_in_executor(None, assitantLLM.ask, transcript)

            await self.event_bus.emit_event('logger_handler', {  'agent': True,  'message':  result['aIText'] })
            # todo evaluate if WE GOT A CODE to run an automation save it and open it in vs code
            
            try:
                if 'aIText' in result:
                    with ThreadPoolExecutor() as executor:
                        await loop.run_in_executor(executor, SileroSpeech.save_and_play,  result['aIText'] ,'test.wav', set_audio_level)
                        self.microphoneManager.unmute()
                    
                    await self.event_bus.emit_event('logger_handler', {  'agent': True,  'message':  'Neuma is Listening....' }) 

            except Exception as e:
                await self.event_bus.emit_event('logger_handler', {  'error': True,  'message':  e })
                print(f"Error generating speech: {e}")        