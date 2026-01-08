# core/pipeline/steps.py
from core.llm.tools.registry import tool_registry

async def step1(data):
    data["step1"] = "done"
    print("STEPS : Step 1 completed")
    return data

async def time_tool_step(data):
    # Print tools for debugging
    print("Tools in registry:")
    for t in tool_registry.tools:
        print("-", t.__name__)
    
    # Find the time tool
    tool = next(t for t in tool_registry.tools if t.__name__ == "get_current_time")
    result = tool()
    data["current_time"] = result["current_time"]
    return data

async def step2(data):
    print("Step 2 sees current_time:", data.get("current_time"))
    data["step2"] = "done"
    print("STEPS : Step 2 completed")
    return data

async def step3(data):
    data["step3"] = "done"
    print("STEPS : Step 3 completed")
    return data


# List of all steps in order
STEPS = [step1, time_tool_step, step2, step3]
