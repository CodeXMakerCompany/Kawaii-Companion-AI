import subprocess
import os
import psutil
import asyncio

import pyvts

VTS = pyvts.vts(
    plugin_info={
        "plugin_name": "neuma-model",
        "developer": "codexmaker",
        "authentication_token_path": "../token.txt"
    },
    vts_api_info={
        "version": "1.0",
        "name": "VTubeStudioPublicAPI",
        "port": os.environ.get("VTUBE_API_PORT", 8001)
    }
)

VOICE_PARAMETER = "MouthOpen"
VOICE_LEVEL = 0


class VTubeService:
    def __init__(self, api_key, api_port):
        self.is_connected = False
        self.api_key = api_key
        self.api_port = api_port
        self.websocket = None
        self.vtube_process_name = "VTube Studio.exe"  # Exact name including ".exe" for windows

    def is_vtube_running(self):
        """Check if VTube Studio is already running by matching process name."""
        for process in psutil.process_iter(['pid', 'name']):
            if self.vtube_process_name.lower() in process.info['name'].lower():
                return True
        return False

    async def wait_for_vtube(self):
        """Listener to keep checking if VTube Studio starts running."""
        while not self.is_vtube_running():
            print("VTube Studio not detected. Checking again...")
            await asyncio.sleep(2)

    def set_audio_level(self, level):
        global VOICE_LEVEL
        VOICE_LEVEL = level

    async def listen_voice_level(self):
        """Listener to adjust voice level in real-time."""
        global VOICE_LEVEL
        current_voice_level = 0
        try:
            while True:
                if VOICE_LEVEL != current_voice_level:
                    await VTS.request(
                        VTS.vts_request.requestSetParameterValue(parameter=VOICE_PARAMETER, value=VOICE_LEVEL)
                    )
                    current_voice_level = VOICE_LEVEL
                await asyncio.sleep(1 / 30)  # 30fps
        except asyncio.CancelledError:
            print("Voice level listener canceled.")
        except Exception as e:
            print(f"Error in voice listener: {e}")

    async def start(self):
        """Starts VTube Studio if it's not running, and listens until it starts."""
        if not self.is_vtube_running():
            print("Starting VTube Studio...")
            subprocess.run(["start", os.getenv('VTUBE_PATH')], shell=True)
            await self.wait_for_vtube()
        else:
            print("VTube Studio is already running.")

        await asyncio.sleep(8)

        print(f"Connecting to VTube Studio!")
        while True:
            try:
                if not self.is_connected:
                    await VTS.connect()
                    self.is_connected = True
                print(f"Authentication request sent to VTube Studio, click allow.")
                await VTS.request_authenticate_token()
                await VTS.request_authenticate()
                break
            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(5)

        print(f"VTube Studio connected!")
