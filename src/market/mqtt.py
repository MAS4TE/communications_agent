"""MQTT clients: the agent's link to the market and the battery.

Two thin wrappers around paho-mqtt:

  - MarketClient talks to the ASSUME market simulation. It listens for
    "market_open" and "market result" messages and, when one arrives, schedules
    the matching pipeline on the agent's event loop. It also publishes the
    agent's orderbook.
  - BatteryClient talks to the physical battery (or its simulation). It sends
    power requests and logs whatever the battery replies.

The callbacks run on paho's own thread and must return immediately, so they only
hand the message to the agent, which queues it for its worker thread (agent.py).

Both clients connect asynchronously and keep retrying: an agent must be able to
start before the broker (or the whole ASSUME stack) is up, and rejoin by itself
when the broker restarts.
"""
import json

from paho.mqtt.client import Client, CallbackAPIVersion

from config import (
    MQTT_ONLINE,
    MQTT_LOCAL_BROKER,
    MQTT_LOCAL_PORT,
    MQTT_BATTERY_BROKER,
    MQTT_BATTERY_PORT,
    mqtt_battery_credentials,
)


class MarketClient:
    """Listens to the ASSUME market and publishes orderbooks."""

    def __init__(self, agent):
        self.agent = agent
        self.topic_status = f"mas4te/market/status_agent{agent.agent_id}"
        self.topic_bids = f"mas4te/bids/agent{agent.agent_id}"
        self.topic_results = f"mas4te/results/agent{agent.agent_id}"

        self.client = Client(CallbackAPIVersion.VERSION2, client_id=f"agent{agent.agent_id}")
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

    def start(self):
        # connect_async + loop_start never raises when the broker is down; paho
        # retries in the background and _on_connect re-subscribes each time.
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
        self.client.loop_start()
        print(f"MQTT: market client for {self.agent.agent_id} connecting to "
              f"{MQTT_LOCAL_BROKER}:{MQTT_LOCAL_PORT}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"MQTT: market client for {self.agent.agent_id} refused: {reason_code}")
            return
        client.subscribe(self.topic_status)
        client.subscribe(self.topic_results)
        print(f"MQTT: market client for {self.agent.agent_id} connected, "
              f"subscribed to {self.topic_status} and {self.topic_results}")

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"MQTT: market client for {self.agent.agent_id} lost the broker "
                  f"({reason_code}) — retrying")

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
        except json.JSONDecodeError:
            print("MQTT: ignoring non-JSON message")
            return

        # Queue the work and return — see the comment at the top of agent.py.
        if message.topic == self.topic_status and payload.get("status") == "market_open":
            print("MQTT: market opened -> queue bidding")
            self.agent.on_market_open(payload)
        elif message.topic == self.topic_results and payload.get("msg") == "market result":
            print("MQTT: market cleared -> queue clearing")
            self.agent.on_market_result(payload)

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def send_orderbook(self, orderbook: list):
        self.client.publish(self.topic_bids, json.dumps(orderbook))
        print(f"MQTT: {self.agent.agent_id} sent {len(orderbook)} orders to {self.topic_bids}")


class BatteryClient:
    """Sends power requests to the battery and logs its responses."""

    def __init__(self, agent):
        self.agent = agent
        self.topic_power_request = "mas4te/battery-storage/power_request"
        self.topic_response = f"mas4te/battery-storage/{agent.agent_id}"

        self.client = Client(CallbackAPIVersion.VERSION2, client_id=f"agent{agent.agent_id}_battery")
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message

        username, password = mqtt_battery_credentials()
        if username and password:
            self.client.username_pw_set(username, password)

    def start(self):
        if MQTT_ONLINE:
            self.client.tls_set()
            broker, port = MQTT_BATTERY_BROKER, MQTT_BATTERY_PORT
        else:
            broker, port = MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.client.connect_async(broker, port, 60)
        self.client.loop_start()
        print(f"MQTT: battery client for {self.agent.agent_id} connecting to {broker}:{port}")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            print(f"MQTT: battery client for {self.agent.agent_id} refused: {reason_code}")
            return
        client.subscribe(self.topic_response)
        print(f"MQTT: battery client for {self.agent.agent_id} connected")

    def _on_message(self, client, userdata, message):
        print(f"MQTT [battery] response on {message.topic}: {message.payload.decode()}")

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def send_power_request(self, power_request: dict):
        power_request["request_id"] = self.agent.agent_id
        self.client.publish(self.topic_power_request, json.dumps(power_request))
        print(f"MQTT: {self.agent.agent_id} sent power request to {self.topic_power_request}")
