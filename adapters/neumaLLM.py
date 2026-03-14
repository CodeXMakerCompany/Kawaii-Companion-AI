import json
import os
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from core.constants.main import BASE_ROL
from core.automation.code.code import CodeInterpreter
import infra.sockets_server as _sockets_server

# Output schema: model must return exactly this JSON shape (prompt builder for format compliance)
OUTPUT_FORMAT_INSTRUCTION = """
You must reply with a single JSON object only, no markdown or extra text. Use this exact shape:
{"text": "<your reply text>", "code": null or "<code if any>", "expression": "<one expression key from the list below that matches the emotion of your reply>"}
"""

# Template with placeholders (expressions instruction + format)
template = """
{role}

{output_format}

Here is the conversation history: {context}

Available model expressions (pick one for "expression" that fits the emotion of your reply):
{expressions}

Question: {question}

Reply with only the JSON object, no other text:
"""

class NeumaLLM:
    def __init__(self):
        # When running in Docker, set OLLAMA_BASE_URL=http://host.docker.internal:11434 to reach Ollama on the host
        base_url = os.getenv("OLLAMA_BASE_URL", "").strip() or None
        # Must match "ollama list" (e.g. llama3.1:8b, not just llama3.1)
        model = os.getenv("OLLAMA_MODEL", "llama3.1:8b").strip()
        kwargs = {"model": model}
        if base_url:
            kwargs["base_url"] = base_url
        self.model = OllamaLLM(**kwargs)
        self.context = ''  # Can be an empty string or any default value
        self.prompt = ''
        self.chain = ''
        self.rol = BASE_ROL
        self.codeInterpreter = CodeInterpreter()
    
    def init(self):
        self.chain = ChatPromptTemplate.from_template(template) | self.model

    
    def _expressions_for_prompt(self) -> str:
        """Build expressions list for the prompt from global cache. Read from module so we see updates (from import would stay None)."""
        cache = _sockets_server.model_expressions_cache
        if cache is None:
            return "(none available yet)"
        # Cache can be the list directly (sockets_server stores payload.get("expressions")) or a dict
        if isinstance(cache, (list, tuple)):
            return ", ".join(str(e) for e in cache)
        if isinstance(cache, dict):
            exp = cache.get("expressions", cache)
            if isinstance(exp, (list, tuple)):
                return ", ".join(str(e) for e in exp)
            return ", ".join(exp.keys()) if exp else "(none)"
        return str(cache)

    def ask(self, question):

        response = self.chain.invoke({
            "role": self.rol,
            "context": self.context,
            "question": question,
            "output_format": OUTPUT_FORMAT_INSTRUCTION.strip(),
            "expressions": self._expressions_for_prompt(),
        })

        parsed_response = None
        raw = (response or "").strip()
        # Strip markdown code fence if present (e.g. ```json ... ```)
        if "```" in raw:
            raw = raw.replace("```json", "").replace("```", "").strip()
        try:
            if raw.startswith("{") and raw.endswith("}"):
                parsed_response = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            parsed_response = None

        if parsed_response is not None:
            aIText = parsed_response.get("text", "No text available")
            aICode = parsed_response.get("code", None)
            expression = parsed_response.get("expression", None)
            if aICode:
                CodeInterpreter.open(aICode)
            self.context += f"\nUser: {question}\nAI: {aIText}\nAICODE: {aICode}"
            return {
                "aIText": aIText,
                "aICode": aICode,
                "response": parsed_response,
                "expression": expression,
            }
        # Response was not valid JSON: use full response as text, no expression
        aIText = raw or "No text available"
        self.context += f"\nUser: {question}\nAI: {aIText}\nAICODE: None"
        return {
            "aIText": aIText,
            "aICode": None,
            "response": response,
            "expression": None,
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