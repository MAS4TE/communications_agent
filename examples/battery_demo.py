from communication_agent.mcp_server.battery import get_battery_status

if __name__ == "__main__":
    result = get_battery_status()
    print("Battery status:", result)