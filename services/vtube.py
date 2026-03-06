import subprocess
import os
import psutil
import asyncio
import platform
from dotenv import load_dotenv

load_dotenv()
import pyvts

from speech import SileroSpeech

showModelMethods = os.environ.get("VTUBE_LOG_SHOW_AVAILABLE_METHODS_OF_MODEL", False)

vtube_port = os.environ.get("VTUBE_API_PORT", 8001)

VTS = pyvts.vts(
    plugin_info={
        "plugin_name": f"{os.environ.get('ASSISTANT_NAME', 'neuma')}-model",
        "developer": "codexmaker",
        "authentication_token_path": "outputs/vtube_token.txt",
    },
    vts_api_info={
        "version": "1.0",
        "name": "VTubeStudioPublicAPI",
        "port": vtube_port,
    },
)

VOICE_PARAMETER = "MouthOpen"  # Writable parameter for manual lip sync control
VOICE_LEVEL = 0

current_os = platform.system()


class VTubeService:
    def __init__(self):
        self.is_connected = False
        self.api_port = vtube_port
        self.websocket = None

    def get_vtube_process_name(self):
        if current_os == "Windows":
            return "VTube Studio.exe"
        if current_os == "Linux":
            return "VTube Studio.ex"

    def is_vtube_running(self):
        """Check if VTube Studio is already running by matching process name."""
        for process in psutil.process_iter(["pid", "name"]):
            if self.get_vtube_process_name() in process.info["name"]:
                return True
        return False

    async def wait_for_vtube(self):
        """Listener to keep checking if VTube Studio starts running."""
        while not self.is_vtube_running():
            print("VTube is loading wait a bit...")
            await asyncio.sleep(5)

    def set_audio_level(self, level):
        global VOICE_LEVEL
        VOICE_LEVEL = level
        # Debug output
        if level > 0.1:  # Only print significant values
            print(f"[Audio Level] {level:.2f}", end="\r")

    async def get_available_parameters(self):
        """Fetch and print all available parameters from the current VTube Studio model."""
        try:
            response = await VTS.request(VTS.vts_request.requestTrackingParameterList())

            print("\n=== Available VTube Studio Parameters ===")
            if hasattr(response, "data") and "parameters" in response.data:
                for param in response.data["parameters"]:
                    print(
                        f"  - {param['name']}: {param['value']} (min: {param['min']}, max: {param['max']})"
                    )
            else:
                print("No parameters found or unexpected response format")
                print(f"Response: {response}")
            print("=========================================\n")
            return response
        except Exception as e:
            print(f"Error fetching parameters: {e}")
            return None

    async def listen_voice_level(self):
        """Listener to adjust voice level in real-time."""
        global VOICE_LEVEL
        current_voice_level = 0

        # Print available parameters when starting
        if showModelMethods:
            await self.get_available_parameters()

        try:
            while True:
                if VOICE_LEVEL != current_voice_level:
                    print(f"[VTS] Setting {VOICE_PARAMETER} to {VOICE_LEVEL:.2f}")
                    await VTS.request(
                        VTS.vts_request.requestSetParameterValue(
                            parameter=VOICE_PARAMETER, value=VOICE_LEVEL
                        )
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
            vtube_path = os.getenv("VTUBE_PATH")
            if vtube_path:

                if current_os == "Windows":
                    # Windows: use start command
                    subprocess.Popen(
                        ["cmd", "/c", "start", "", vtube_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif current_os == "Linux":
                    # Linux/Steam: launch via Steam protocol
                    vtube_gameid = os.getenv("VTUBE_GAMEID")
                    subprocess.Popen(
                        ["steam", f"steam://rungameid/{vtube_gameid}"],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                elif current_os == "Darwin":
                    # macOS: use open command
                    subprocess.Popen(
                        ["open", vtube_path],
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                else:
                    print(f"Unsupported OS: {current_os}")
                    return
            else:
                print("VTUBE_PATH not set in environment variables!")
                return
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
            await self.wait_for_vtube()
        else:
            print("VTube Studio is already running.")

        await asyncio.sleep(8)

        print(f"Connecting to VTube Studio!")
        while True:
            try:
                if not self.is_connected:
                    await VTS.connect()
                    print(f"Authentication request sent to VTube Studio, click allow.")
                    self.is_connected = True
                await VTS.request_authenticate_token()
                await VTS.request_authenticate()
                break
            except Exception as e:
                print(f"Connection error: {e}")
                await asyncio.sleep(5)

        print(f"VTube Studio connected!")


async def main():
    """Main function to run VTube service for testing."""
    load_dotenv()
    await SileroSpeech.prepare()
    service = VTubeService()

    # Start VTube Studio and connect
    await service.start()

    # Wait a bit
    await asyncio.sleep(2)
    print("Activando oidos")

    # Start the voice level listener in the background
    listener_task = asyncio.create_task(service.listen_voice_level())

    # Wait for listener to initialize
    await asyncio.sleep(1)

    print("Testing TTS with lip sync...")
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(
        None,
        SileroSpeech.save_and_play,
        "Hi my name is sam, this is a testing model i repeat a testing model, i have an opinion about the three body problem, i feel thtat this lecture is a bit different from others the autor has been extremely descriptive in this oddisey",
        "testing/test.mp3",
        service.set_audio_level,
    )

    print("TTS finished, keeping listener running...")
    # Keep listener running
    await listener_task


if __name__ == "__main__":
    asyncio.run(main())
