import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import time
import datetime
import socket
import json
import argparse

N = 100
stats_fname = "qos-stats.txt"
hostname = "ec2-18-118-33-83.us-east-2.compute.amazonaws.com"
port = 1883
keepalive = 60


# The callback for when the client receives a CONNACK response from the server.
def on_connect(client, userdata, flags, reason, rc):
    print("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("test", qos=qos)


# The callback for when a PUBLISH message is received from the server.
def on_message(client, userdata, msg):
    rcv_time = time.time_ns() // (10 ** 6)
    print(f"{msg.topic} {msg.payload} {msg.mid} {time.time_ns()}")
    if msg.topic == "test":
        content = msg.payload.decode()
        seq_num, send_time = content.split(" ")
        pkt_data = {
            "seq_num": seq_num,
            "send_time": int(send_time),
            "rcv_time": rcv_time,
            "time_diff": (rcv_time - int(send_time)),
            "qos": msg.qos,
        }
        userdata.append(pkt_data)


def on_disconnect(client, userdata, rc):
    print("Disconnected")


def on_log(client, userdata, level, buf):
    print(f"[{level}] {buf}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        prog="sub-client",
        usage="Usage: python sub-client.py <qos> <network-cond>\nDefault: qos=0, network_cond=good",
    )
    parser.add_argument("--qos", action="store", type=int, default=0, required=False)
    parser.add_argument(
        "--net_cond", action="store", type=str, default="good", required=False
    )
    args = parser.parse_args()

    qos = args.qos
    net_cond = args.net_cond

    try:
        data = []
        client = mqtt.Client(
            client_id="test-sub", userdata=data, protocol=mqtt.MQTTv5, transport="tcp"
        )
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_log = on_log

        connected = False
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 30
        while not connected:
            try:
                client.connect(
                    hostname,
                    port,
                    keepalive,
                    clean_start=False,
                    properties=properties,
                )
                connected = True
            except socket.timeout:
                pass
    except KeyboardInterrupt:
        data_fname = (
            datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            + "_qos-"
            + str(qos)
            + f"_netcond-{net_cond}"
            + ".json"
        )
        with open(data_fname, "w") as data_f:
            json.dump(data, data_f)
        total_diff = 0
        for pkt in data:
            total_diff += pkt["time_diff"]

        with open(stats_fname, "a") as stats_f:
            stats_f.write("Subscriber\n")
            stats_f.write("----------\n")
            stats_f.write(f"Network conditions: {net_cond}\n")
            stats_f.write(f"QoS level: {qos}\n")
            stats_f.write(f"Data file: {data_fname}\n")
            stats_f.write(f"Number of packets sent: {N}\n")
            stats_f.write(f"Average end-to-end delay: {total_diff/len(data)}ms\n")
            stats_f.write(f"Packet loss: {N-len(data)/N*100}%\n")
            stats_f.write("\n\n")
