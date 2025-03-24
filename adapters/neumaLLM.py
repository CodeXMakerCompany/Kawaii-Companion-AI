import json
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from core.constants.main import BASE_ROL
from core.automation.code.code import CodeInterpreter

# Template with placeholders
template = """
{role}

Here is the conversation history: {context}

Question: {question}

Answer:
"""

class NeumaLLM:
    def __init__(self):
        self.model = OllamaLLM(model='llama3.1')
        self.context = ''  # Can be an empty string or any default value
        self.prompt = ''
        self.chain = ''
        self.rol = BASE_ROL
        self.codeInterpreter = CodeInterpreter()
    
    def init(self):
        self.chain = ChatPromptTemplate.from_template(template) | self.model

    
    def ask(self, question):
        response = self.chain.invoke({
            "role": self.rol,
            "context": self.context,
            "question": question
        })
    
        try:
            # todo fix sometimes the res comes with ``` andrverse tick at end
            if response.strip().startswith("{") and response.strip().endswith("}"):
                parsed_response = json.loads(response)
            # else:
            #     clean_response = response.split("{", 1)[-1].rsplit("}", 1)[0] + "}"
            #     parsed_response = json.loads(clean_response)
            
            # Extract text and code
            aIText = parsed_response.get('text', 'No text available')
            aICode = parsed_response.get('code', None)  # Default to None if no code is present
            
            if aICode:
                CodeInterpreter.open(aICode)

            # Update context with user question and AI response
            self.context += f"\nUser: {question}\nAI: {aIText}\nAICODE: {aICode}"
            
            # Return structured response including text, code, and original parsed response
            return {
                "aIText": aIText,
                "aICode": aICode,
                "response": parsed_response } # Return the full parsed response as well (optional)
            
        except json.JSONDecodeError:
            print('Response is not valid JSON:', response)
            return {
                "aIText": "Error processing response",
                "aICode": None,
                "response": response  # In case the response is not JSON
            } 
    
    def personalityUpdate(self, role):
        """
        Updates the personality and context dynamically and returns the updated response.
        """
        self.context = f"Your personality has been updated to: {role}\n" + self.context
        self.rol = role

        response = self.chain.invoke({
            "role": role,  # Pass the updated personality
            "context": self.context,           # Updated context
            "question": "Confirm this update"  # Example question
        })
        
        return response  