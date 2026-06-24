from core.domain.chat_session import SolarChatSession

class ChatService:
    def __init__(self, llm, prompt: str = "You are a solar battery assistant."):
        self.llm = llm
        self.session = SolarChatSession(llm, prompt=prompt)

    def process_message(self, message: str, preferences: dict = None) -> str:
        return self.session.process_message(message, preferences)