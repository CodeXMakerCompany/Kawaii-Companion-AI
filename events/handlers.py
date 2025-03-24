from core.automation.mic.main import MicrophoneManager
from services.automations import NeumaAutomationService
from utils.logger import LoggerUtil

# App state
automationInstance = NeumaAutomationService()
loggerInstance = LoggerUtil()
micManagerInstance = MicrophoneManager()

def logger_handler(data):
    """Handles styled loggers."""
    # DO THIS DYNAMIC
    if 'agent' in data:
        loggerInstance.agent(data['message'])
    if 'user' in data:
        loggerInstance.user(data['message'])  
    if 'error' in data:
        loggerInstance.user(data['message'])  
    if 'is Listening....' in data:
        loggerInstance.agent(data['message'])            
        
def open_brave_handler(data):
    """Handles 'open brave' command."""
    print("Opened Brave Browser.")
    
async def neuma_automations_handler(data):
    await automationInstance.process_automations(data['text'], data['assitantLLM'])

def mute(data):
    micManagerInstance.mute()

def unmute(data):
    micManagerInstance.unmute()

def getMicStatus(data):
    return micManagerInstance.getMicStatus()        

def goodbye_handler(data):
    """Handles exit command."""
    print("Goodbye!")
    exit(0)
