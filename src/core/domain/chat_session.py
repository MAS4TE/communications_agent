# chat_session.py
"""Chat session handling for OpenAI interactions.

This module is used by the ChatService to manage OpenAI interactions
and maintain conversation state.
"""



class SolarChatSession:
    """Chat session for handling conversation with OpenAI models.
    
    This class is responsible for maintaining conversation state and 
    calling tools in response to user queries.
    """
    
    def __init__(self, llm, prompt: str):
        self.llm = llm
        self.prompt = prompt
        self.messages = [{"role": "system", "content": self.prompt}]

    def process_message(self, user_message: str):
        self.messages.append({"role": "user", "content": user_message})
        reply = self.llm.invoke(self.messages)
        self.messages.append({"role": "assistant", "content": reply})
        return reply