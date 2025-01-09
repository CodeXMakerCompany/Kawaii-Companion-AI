from services.automations import NeumaAutomationService
from utils.logger import LoggerUtil

neumaAutomationInstance = NeumaAutomationService()
loggerInstance = LoggerUtil()

def logger_handler(data):
    """Handles styled loggers."""
    # DO THIS DYNAMIC
    if 'agent' in data:
        loggerInstance.agent(data['message'])
    if 'user' in data:
        loggerInstance.user(data['message'])  
    if 'error' in data:
        loggerInstance.user(data['message'])        
        
def open_brave_handler(data):
    """Handles 'open brave' command."""
    print("Opened Brave Browser.")
    
async def neuma_automations_handler(data):
    await neumaAutomationInstance.process_automations(data['text'], data['assitantLLM'])   

def goodbye_handler(data):
    """Handles exit command."""
    print("Goodbye!")
    exit(0)
