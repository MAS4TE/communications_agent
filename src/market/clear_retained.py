import paho.mqtt.client as mqtt

topics = [
    "mas4te/market/status_agentB_01",
    "mas4te/market/status_agentB_02",
    "mas4te/market/status_agentB_03",
    "mas4te/market/status_agentB_04",
    "mas4te/market/status_agentB_05",
    "mas4te/market/status_agentB_06",
    "mas4te/market/status_agentB_07",
    "mas4te/market/status_agentS_01",
    "mas4te/market/status_agentS_02",
    "mas4te/market/status_agentS_03",
]

client = mqtt.Client()
client.connect("localhost", 1883, 60)
client.loop_start()

for topic in topics:
    info = client.publish(topic, payload=None, qos=1, retain=True)
    info.wait_for_publish()
    print(f"Cleared retained message on {topic}")

client.loop_stop()
client.disconnect()
