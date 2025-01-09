
import asyncio
from core.constants.main import ENGLISH_TUTOR_ROL, INTERVIEW_MODE_ROL
from services.automation_service import SeleniumAutomation


seleniumAuto = SeleniumAutomation()

class NeumaAutomationService:
    
    async def process_automations(self, text, neumaLLM):
            
        if  'goodbye' in text:
            print('Neuma is shutting down')
             # Cancel all tasks
            for task in asyncio.all_tasks():
                task.cancel()
                
            # Wait for all tasks to gracefully exit
            return await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)
            
        if 'open brave' in text:
            seleniumAuto.open_browser()
                
        if 'interview mode' in text:
            neumaLLM.personalityUpdate(INTERVIEW_MODE_ROL)
            
        if 'english mode' in text:
            neumaLLM.personalityUpdate(ENGLISH_TUTOR_ROL)
        
            
            
    