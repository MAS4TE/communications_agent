import json
import paho.mqtt.client as mqtt
import logging
from paho.mqtt.enums import CallbackAPIVersion

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
        self.topic_response = f"mas4te/battery-storage/{self.agent_id}"  # reply uses agent_id

        self.client = mqtt.Client(
            callback_api_version=CallbackAPIVersion(2),
            client_id=f"agent{agent_id}_battery"
        )
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        if username and password:
            self.client.username_pw_set(username, password)

    def start(self, tls=True):
        if tls:
            self.client.tls_set()
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        logger.info(f"[Battery] MQTT agent {self.agent_id} connected to broker")

    def on_connect(self, client, userdata, flags, rc, properties):
        if rc == 0:
            logger.info("[Battery] Connected successfully!")
            logger.info(f"[Battery] Subscribing to {self.topic_response}")
            client.subscribe(self.topic_response)
        else:
            logger.error(f"[Battery] Connection failed with rc={rc}")

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            print(f"\n--- [Battery] Response on {msg.topic} ---")
            print(json.dumps(payload, indent=2))
            print("-------------------------------------------\n")
        except json.JSONDecodeError:
            payload = msg.payload.decode()
            print(f"\n--- [Battery] Response on {msg.topic} ---")
            print(payload)
            print("-------------------------------------------\n")

        logger.info(f"[Battery] Response received on {msg.topic}: {payload}")

    def send_power_request_to_battery(self, power_request: dict):
        power_request["request_id"] = self.agent_id  # inject request_id
        self.client.publish(self.topic_power_request, json.dumps(power_request))
        logger.info(f"[Battery] Agent {self.agent_id} sent power request to {self.topic_power_request}")