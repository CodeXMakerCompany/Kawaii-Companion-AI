import audioop
import torch
import os
import wave
import pyaudio 

DEVICE = torch.device(os.environ.get("TORCH_DEVICE", "cpu"))
LOCAL_FILE = 'model.pt'

class SileroSpeech:
    @staticmethod
    def prepare():
        """Download the model if not already available and set up the environment."""
        global DEVICE, LOCAL_FILE
        torch.set_num_threads(4)
        if not os.path.isfile(LOCAL_FILE):
            torch.hub.download_url_to_file(
                f'https://models.silero.ai/models/tts/{"en"}/{"v3_en"}.pt',
                LOCAL_FILE
            )
            print("Model downloaded successfully.")

    @staticmethod
    def silero_tts(message, language="en", model="v3_en", speaker="en_21"):
        """Generate speech from text and save it as a .wav file."""
        global DEVICE, LOCAL_FILE

        # Load the model
        model = torch.package.PackageImporter(LOCAL_FILE).load_pickle("tts_models", "model")
        model.to(DEVICE)

        # Set sample rate
        sample_rate = 48000

        # Generate the audio file
        audio_path = model.save_wav(
            text=message,
            speaker=speaker,
            put_accent=True,
            put_yo=True,
            sample_rate=sample_rate
        )
        return audio_path  # Return the generated file path

    @staticmethod
    def save_and_play(message, audio_path, audio_level_callback = None):
        
        try:
        
            audio_path = SileroSpeech.silero_tts(message, speaker="en_21")

        except Exception as e:
            print(f"Error during speech synthesis or playback: {e}")
            
        """Play a .wav audio file using PyAudio."""
        try:
            # Open the audio file
            with wave.open(audio_path, 'rb') as wf:
             
                p = pyaudio.PyAudio()
                stream = p.open(
                    format=p.get_format_from_width(wf.getsampwidth()),
                    channels=wf.getnchannels(),
                    rate=wf.getframerate(),
                    output=True
                )

             
                chunk = 1024
                data = wf.readframes(chunk)
                while data:
                    stream.write(data)
                    data = wf.readframes(chunk)
                    if audio_level_callback is not None:
                        volume = audioop.rms(data, 2)
                        audio_level_callback(volume / 10000)

               
                stream.stop_stream()
                stream.close()
                p.terminate()
                

        except Exception as e:
            print(f"Error during audio playback: {e}")
