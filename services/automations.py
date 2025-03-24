import asyncio
from core.constants.main import ENGLISH_TUTOR_ROL, INTERVIEW_MODE_ROL, CHAT_ANALYSIST_SPECIALIST, AWS_SOLUTIONS_ARCHITECT_SPECIALIST, INTERVIEW_MODE_ROL_ALPHA
from services.automation_service import SeleniumAutomation
from core.constants.automationDic import AutomationDictionary

seleniumAuto = SeleniumAutomation()

class NeumaAutomationService:
    
    async def process_automations(self, text, neumaLLM):
        
        # Ensure text is lowercased for consistent matching
        text = text.lower()
        
        if AutomationDictionary.GOODBYE.value.lower() in text:
            print('Neuma is shutting down')
            # Cancel all tasks
            for task in asyncio.all_tasks():
                task.cancel()
            
            # Wait for all tasks to gracefully exit
            return await asyncio.gather(*asyncio.all_tasks(), return_exceptions=True)
        
        if AutomationDictionary.OPEN_BRAVE.value.lower() in text:
            seleniumAuto.open_browser()
            
        if AutomationDictionary.INTERVIEW_MODE.value.lower() in text:
            neumaLLM.personalityUpdate(INTERVIEW_MODE_ROL_ALPHA)
            
        if AutomationDictionary.ENGLISH_MODE.value.lower() in text:
            neumaLLM.personalityUpdate(ENGLISH_TUTOR_ROL)
            
        if AutomationDictionary.CHAT_ANALYSIST_MODE.value.lower() in text:
            neumaLLM.personalityUpdate(CHAT_ANALYSIST_SPECIALIST)
            
        if AutomationDictionary.AWS_ARCHITECT_MODE.value.lower() in text:
            neumaLLM.personalityUpdate(AWS_SOLUTIONS_ARCHITECT_SPECIALIST)
