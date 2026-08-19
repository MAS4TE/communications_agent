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
import logging

from paho.mqtt.client import Client, CallbackAPIVersion

from config import (
    MQTT_ONLINE,
    MQTT_LOCAL_BROKER,
    MQTT_LOCAL_PORT,
    MQTT_BATTERY_BROKER,
    MQTT_BATTERY_PORT,
    mqtt_battery_credentials,
)

log = logging.getLogger("market")


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
        log.info("connecting broker=%s:%s role=market", MQTT_LOCAL_BROKER, MQTT_LOCAL_PORT)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            log.error("broker refused the market client: %s", reason_code)
            return
        client.subscribe(self.topic_status)
        client.subscribe(self.topic_results)
        log.info("connected role=market subscribed=%s,%s", self.topic_status, self.topic_results)

    def _on_disconnect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            log.warning("lost the broker (%s) role=market — retrying", reason_code)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode())
        except json.JSONDecodeError:
            log.warning("receive topic=%s IGNORED (not JSON, %d bytes)",
                        message.topic, len(message.payload))
            return

        # Queue the work and return — see the comment at the top of agent.py.
        if message.topic == self.topic_status and payload.get("status") == "market_open":
            log.info("receive topic=%s status=market_open products=%d -> queue bidding",
                     message.topic, len(payload.get("products", [])))
            self.agent.on_market_open(payload)
        elif message.topic == self.topic_results and payload.get("msg") == "market result":
            log.info("receive topic=%s msg=market_result orders=%d -> queue clearing",
                     message.topic, len(payload.get("orderbook", [])))
            self.agent.on_market_result(payload)
        else:
            log.debug("receive topic=%s ignored keys=%s",
                      message.topic, sorted(payload)[:6])

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def send_orderbook(self, orderbook: list):
        volume = sum(order["volume"] for order in orderbook)
        info = self.client.publish(self.topic_bids, json.dumps(orderbook))
        log.info("publish topic=%s orders=%d volume=%.2fkWh queued=%s",
                 self.topic_bids, len(orderbook), volume, info.rc == 0)


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
        log.info("connecting broker=%s:%s role=battery", broker, port)

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code != 0:
            log.error("broker refused the battery client: %s", reason_code)
            return
        client.subscribe(self.topic_response)
        log.info("connected role=battery subscribed=%s", self.topic_response)

    def _on_message(self, client, userdata, message):
        log.info("receive topic=%s role=battery payload=%s",
                 message.topic, message.payload.decode()[:200])

    def stop(self):
        self.client.loop_stop()
        self.client.disconnect()

    def send_power_request(self, power_request: dict):
        power_request["request_id"] = self.agent.agent_id
        info = self.client.publish(self.topic_power_request, json.dumps(power_request))
        log.info("publish topic=%s role=battery steps=%d queued=%s",
                 self.topic_power_request, len(power_request["time_steps"]), info.rc == 0)
