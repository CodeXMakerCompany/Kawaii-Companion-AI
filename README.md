# **Kawaii Companion AI**

In a world where AI is set to dominate industries, we need a _kawaii_ companion that:

- Helps us deliver quality experiences.
- Deepens our involvement in business processes daily.
- Recognizes requirements and trains our fundamentals and languages.
- Evolves into the ultimate tool for developers.

Welcome to **AI Developer NEXTGEN**—the future of development is in our hands. We are ready to scale to the next era, where every developer is empowered by AI tools that truly understand their needs. Feel free to contribute to this project—let’s build something special together! 💖

---

## **Core Libraries**

### 1. **[Deepgram](https://deepgram.com/)** - Cloud Speech Recognition (Usage billed on demand)

- Create an account and get your token.

### 2. **[VTube Studio](https://denchisoft.com/)** - Visual Interactive Model Talk (Free)

- Download and install.
- **Requirements:** Enable API support (local mode) in the program settings.

### 3. **[Ollama LLM](https://ollama.com/library/llama3.1)**

- Use version 3.1 or set it up as needed.

### 4. **[TTS - Silero](https://github.com/snakers4/silero-models)**

- The best free TTS model for CPU.

### 5. **[Selenium](https://googlechromelabs.github.io/chrome-for-testing/#stable)**

- Web manipulation framework.
- Match your browser version (e.g., Brave).

---

## **Proposed Architectures**

1. **Clean Architecture (Hexagonal or Onion)**
2. **Event-Driven Architecture**
3. **Microservices Approach (Service-Oriented)**
4. **Actor Model (Async Frameworks)**

### **Winner:**

**Event-Driven Architecture** + **Clean Architecture**

---

## **Project Structure**

```plaintext
project_root/
├── .dockerignore
├── .env
├── .git/
├── .gitignore
├── .README
├── adapters/
│   ├── neumaLLM.py
│   └── __pycache__/
├── core/
│   ├── automation/
│   │   └── selenium.py
│   ├── constants/
│   │   └── main.py
│   └── voice/
│       └── main.py
├── drivers/
│   └── chromedriver.exe
├── events/
│   ├── event_bus.py
│   └── handlers.py
├── main.py
├── model.pt
├── requirements.txt
├── services/
│   ├── automations.py
│   ├── automation_service.py
│   ├── speech.py
│   ├── transcription.py
│   └── vtube.py
├── test.wav
├── token.txt
└── utils/
    └── logger.py

## **Sample `.env` File**

- [ ] VTUBE_PATH="steam://rungameid/"  # (Use your Steam run game ID; may vary)
- [ ] VTUBE_API_KEY=""  # Generated after the first project run. Check VTubeService or run it isolated.
- [ ] VTUBE_API_PORT="8001"
- [ ] DEEPGRAM_API_KEY=""

---

## **Previous Requirements**

- [ ] Auto-launch VTube Studio on start.
- [ ] Add browser search data method if a browser is open.
- [ ] Automate daily commands.

---

## **Pending Tasks**

- [ ] Automate VTube Studio launch on project start.
- [ ] Implement browser-based data search methods.
- [ ] Automate repetitive day-to-day commands.
- [ ] Integrate design pattern and software architecture roles.
- [ ] Practice for interviews.
- [ ] Highlight what makes this project unique.
- [ ] Optimize data handling and load balancing strategies.
- [ ] Design scalable architectures and choose the best data structures.

Let's make this project exceptional—one kawaii step at a time! 🌸 with love to the worl by @Codexmaker
```
