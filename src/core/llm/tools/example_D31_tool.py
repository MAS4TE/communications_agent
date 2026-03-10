from core.llm.tools.decorators import tool, trace_tool

@tool(
    schema={
        "name": "example_D31_tool",
        "description": "Provides onboarding information for new MAS4TE users about virtual energy storage trading. Use when users ask 'I'm new', 'how does this work', 'what is MAS4TE', 'getting started', or need an introduction.",
        "parameters": {}
    }
)
@trace_tool
def example_D31_tool():
    """Tool that returns onboarding information for new MAS4TE users"""
    return """Welcome to MAS4TE! I'm here to help you participate in virtual energy storage trading.

What is virtual storage trading?
When you buy virtual storage bundles, you're renting space on someone else's physical battery. You can store your excess solar energy there when you produce more than you need, and retrieve it later when you need it - like a virtual energy bank account.

Anonymous community market:
You trade on a local community market where all transactions are anonymous. You can buy storage capacity from battery owners in your community without knowing who they are, and they don't know who you are either.

Optimize your energy costs:
Buy storage bundles when you need a place to store excess energy, and retrieve that energy later when you need it. This lets you use your own solar energy at night or on cloudy days without needing to buy an expensive physical battery yourself.

I can help you with:
- Finding available storage capacity to rent
- Understanding storage prices and your current storage usage
- Tracking how much energy you've stored and retrieved
- Optimizing when to store and when to retrieve energy

What would you like to explore first?"""