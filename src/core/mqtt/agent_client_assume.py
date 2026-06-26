

# core/mqtt/agent_client.py
import json
import asyncio
import paho.mqtt.client as mqtt

# from core.pipeline.manager import PipelineManager

class MqttAgentAssume:
    def __init__(self, broker, port, agent_id, pipeline_manager, loop): #username and password optional
        self.broker = broker
        self.port = port
        self.agent_id = agent_id
        self.pipeline_manager = pipeline_manager
        self.loop = loop

        self.topic_market_status = f"mas4te/market/status_agent{agent_id}"
        self.topic_bids = f"mas4te/bids/agent{agent_id}"
        self.topic_market_clearing = f"mas4te/results/agent{agent_id}"

        self.client = mqtt.Client(client_id=f"agent{agent_id}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message


    def start(self):
        self.client.connect(self.broker, self.port, 60)
        self.client.loop_start()
        print(f"MQTT agent {self.agent_id} connected")

    def on_connect(self, client, userdata, flags, rc):
        print(f"MQTT connected with rc={rc}")
        client.subscribe(self.topic_market_status)
        client.subscribe(self.topic_market_clearing)

    def on_message(self, client, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
        except json.JSONDecodeError:
            print("MQTT: Invalid JSON received")
            return
        
        job = None
        
        if msg.topic == self.topic_market_status and payload.get("status") == "market_open":
            job = {
                "type": "market_open",
                "market_data": payload,
            }
            print("MQTT: Market opened -> enqueue job")
            
        elif msg.topic == self.topic_market_clearing:
            if payload.get("msg") == "market result":
                job = {
                    "type": "market_clearing",
                    "market_data": payload,
                }
                print(f"MQTT: Market cleared -> enqueue job. Data: {payload}")
            else:
                print(f"MQTT: Ignored message on clearing topic: {payload.get('ack', 'unknown')}")
        
        if job:
            print('creating job for pipeline manager')
            asyncio.run_coroutine_threadsafe(
                self.pipeline_manager.enqueue(job),
                self.loop
            )
    



    def send_orderbook_to_market(self, orderbook):
        """
        Sends an orderbook to the given MQTT topic
        """

        self.client.publish(self.topic_bids, json.dumps(orderbook))
        print(f"Agent {self.agent_id} sent orderbook: {orderbook} to topic {self.topic_bids}")

