import json
import asyncio
import paho.mqtt.client as mqtt
import logging

logger = logging.getLogger(__name__)


class MqttAgentBattery:
    def __init__(self, broker, port, agent_id, pipeline_manager, loop, 
                 username=None, password=None, battery_id="mas4te_1"):
        self.broker = broker
        self.port = port
        self.agent_id = agent_id
        self.pipeline_manager = pipeline_manager  # kept for future use
        self.loop = loop
        self.battery_id = battery_id

        self.topic_power_request = "mas4te/battery-storage/power_request"
        self.topic_response = f"mas4te/battery-storage/{self.battery_id}"

        self.client = mqtt.Client(client_id=f"agent{agent_id}_battery")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        if username and password:
            self.username = username
            self.password = password
            self.client.username_pw_set(username, password)

    def start(self, tls=True):
        if tls: 
            self.client.tls_set()  # required for port 8883
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        logger.info(f"[Battery] MQTT agent {self.agent_id} connected to live broker")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("[Battery] Connected successfully!")
            logger.info(f"[Battery] Subscribing to {self.topic_response}")
            client.subscribe(self.topic_response)
        else:
            logger.error(f"[Battery] Connection failed with rc={rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            logger.warning("[Battery] Invalid JSON received")
            return

        logger.info(f"[Battery] Response received on {msg.topic}: {payload}")
        # TODO: enqueue job when pipeline handling is needed

    def send_power_request_to_battery(self, power_request: dict):
        self.client.publish(self.topic_power_request, json.dumps(power_request))
        logger.info(f"[Battery] Agent {self.agent_id} sent power request to {self.topic_power_request}")