"""Clear retained market_open messages from the broker.

The ASSUME market publishes each agent's status with the retain flag set, so a
freshly started agent immediately receives the *last* market_open message and
bids for a window that is already over. Run this between simulation runs to wipe
those retained messages:

    python -m market.clear_retained            # the agents from agents.yml
    python -m market.clear_retained B_01 S_01  # or an explicit list
"""
import sys

from paho.mqtt.client import CallbackAPIVersion, Client

from config import MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT


def clear(agent_ids: list[str]) -> None:
    # paho 2.x requires an explicit callback API version; the bare Client()
    # of paho 1.x raises ValueError here.
    client = Client(CallbackAPIVersion.VERSION2, client_id="clear_retained")
    client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
    client.loop_start()

    for agent_id in agent_ids:
        topic = f"mas4te/market/status_agent{agent_id}"
        info = client.publish(topic, payload=None, qos=1, retain=True)
        info.wait_for_publish()
        print(f"Cleared retained message on {topic}")

    client.loop_stop()
    client.disconnect()


def main() -> None:
    agent_ids = sys.argv[1:]
    if not agent_ids:
        from agents_config import load_agents

        agent_ids = [agent.agent_id for agent in load_agents()]
    clear(agent_ids)


if __name__ == "__main__":
    main()
