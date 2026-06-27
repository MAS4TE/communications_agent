"""MQTT clients: the agent's link to the market and the battery.

Two thin wrappers around paho-mqtt:

  - MarketClient talks to the ASSUME market simulation. It listens for
    "market_open" and "market result" messages and, when one arrives, schedules
    the matching pipeline on the agent's event loop. It also publishes the
    agent's orderbook.
  - BatteryClient talks to the physical battery (or its simulation). It sends
    power requests and logs whatever the battery replies.

The MQTT callbacks run on paho's own thread, so they hand work back to the
asyncio loop with ``run_coroutine_threadsafe``. The agent's lock then makes sure
two pipeline runs never overlap.
"""
import asyncio
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
        self.client.on_message = self._on_message

    def start(self):
        self.client.connect(MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT, 60)
        self.client.loop_start()
        print(f"MQTT: market client for {self.agent.agent_id} connected")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(self.topic_status)
        client.subscribe(self.topic_results)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
        except json.JSONDecodeError:
            print("MQTT: ignoring non-JSON message")
            return

        if message.topic == self.topic_status and payload.get("status") == "market_open":
            print("MQTT: market opened -> run bidding")
            coroutine = self.agent.handle_market_open(payload)
        elif message.topic == self.topic_results and payload.get("msg") == "market result":
            print("MQTT: market cleared -> run clearing")
            coroutine = self.agent.handle_market_clearing(payload)
        else:
            return

        asyncio.run_coroutine_threadsafe(coroutine, self.agent.loop)

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
        self.client.connect(broker, port, 60)
        self.client.loop_start()
        print(f"MQTT: battery client for {self.agent.agent_id} connected")

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        client.subscribe(self.topic_response)

    def _on_message(self, client, userdata, message):
        print(f"MQTT [battery] response on {message.topic}: {message.payload.decode()}")

    def send_power_request(self, power_request: dict):
        power_request["request_id"] = self.agent.agent_id
        self.client.publish(self.topic_power_request, json.dumps(power_request))
        print(f"MQTT: {self.agent.agent_id} sent power request to {self.topic_power_request}")
