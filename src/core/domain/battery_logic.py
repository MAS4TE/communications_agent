# domain/battery_logic.py
import psutil

def get_battery_metrics() -> dict:
    """Core battery logic, independent of API or agent."""
    battery = psutil.sensors_battery()
    if battery is None:
        raise RuntimeError("No battery found")

    status = "charging" if battery.power_plugged else "discharging"
    return {
        "percent": battery.percent,
        "power_plugged": battery.power_plugged,
        "secsleft": getattr(battery, "secsleft", None),
        "status": status,
    }