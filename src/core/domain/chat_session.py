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
        from api.services.prosumer.prosumer_service import ProsumerService
        service = ProsumerService()
        prefs = service.get_preferences()
        profile = service.get_profile()

        if profile.get("home_battery"):
            role_context = (
                f"This prosumer is a seller (they own a {profile.get('battery_capacity_kwh', 'unknown')} kWh battery and can rent out capacity). "
                f"They have set a maximum of {prefs['battery_tradeable_pct']}% of their battery capacity as tradeable. "
                f"The actual amount offered to the market may be less, as the system decides the optimal bid based on forecasts and economics."
            )
        else:
            role_context = (
                "This prosumer is a buyer (they rent battery capacity from others). "
                "They do not own a battery. Never mention battery_tradeable_pct or battery scheduling to them — these are irrelevant for buyers."
            )

        fresh_context = {
            "role": "system",
            "content": (
                f"IMPORTANT: The prosumer's current preferences RIGHT NOW are: "
                f"trading_preference={prefs['trading_preference']}, expertise={prefs['expertise']}. "
                f"These are the latest values — ignore any previous preference values mentioned in this conversation. "
                f"{role_context}"
            )
        }

        self.messages.append({"role": "user", "content": user_message})
        messages_with_context = self.messages[:-1] + [fresh_context, self.messages[-1]]
        reply = self.llm.invoke(messages_with_context)
        self.messages.append({"role": "assistant", "content": reply})
        return reply