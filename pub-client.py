# import paho.mqtt.client as mqtt
import argparse
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import time
import socket

N = 100
stats_fname = "qos-stats.txt"
hostname = "ec2-3-145-35-37.us-east-2.compute.amazonaws.com"
port = 1883
keepalive = 60


def on_connect(client, userdata, flags, reason, rc):
    print("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    userdata["connected"] = True


def on_publish(client, userdata, mid):
    """QoS 0: called when message has left the publisher
    QoS 1 & 2: called when handshakes have completed"""
    p_time = time.time_ns() // (10 ** 6)
    userdata["published_time"][mid] = p_time


def on_log(client, userdata, level, buf):
    print(f"[{level}] {buf}")


if __name__ == "__main__":
    # get args
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

    # initialise
    sent = [False] * N
    published_time = {}
    userdata = {"connected": False, "published_time": published_time}
    client = mqtt.Client(
        client_id="test-pub",
        userdata=userdata,
        protocol=mqtt.MQTTv5,
        transport="tcp",
    )
    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_log = on_log

    data = []

    # connect to host
    connected = False
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 30
    while not connected:
        try:
            client.connect(hostname, port, keepalive, clean_start=False, properties=properties)
            connected = True
        except socket.timeout:
            print("connection socket timeout, retrying...")

    # start looping to read from and write to broker
    client.loop_start()

    # wait for connection to be established before publishing
    while not userdata["connected"]:
        pass

    # publish N messages
    for seq_num in range(1, N + 1):
        while not sent[seq_num - 1]:
            try:
                # switch to using threading.Timer to send at an interval
                cur_time = time.time_ns() // (10 ** 6)
                msg = client.publish("test", f"{seq_num} {cur_time}", qos)
                time.sleep(1)
                # msg.wait_for_publish()

                while msg.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"Error publishing message with seq_num {seq_num}: {msg.rc}")
                    print("Retrying...")

                    cur_time = time.time_ns() // (10 ** 6)
                    msg = client.publish("test", f"{seq_num} {cur_time}", qos)
                    time.sleep(1)
                    # msg.wait_for_publish()

                print(f"Message {msg.mid} with seq num {seq_num} is published")
                sent[seq_num - 1] = True

                cur_data = {
                    "publishing_time": cur_time,
                    "published_time": published_time[msg.mid],
                    "time_diff": published_time[msg.mid] - cur_time,
                    "seq_num": seq_num,
                    "qos": qos,
                }
                data.append(cur_data)
            except ValueError:
                time.sleep(1)

    total_diff = 0
    for pkt in data:
        total_diff += pkt["time_diff"]

    with open(stats_fname, "a") as stats_f:
        stats_f.write("Publisher\n")
        stats_f.write("----------\n")
        stats_f.write(f"Network conditions: {net_cond}\n")
        stats_f.write(f"QoS level: {qos}\n")
        stats_f.write(f"Number of packets sent: {N}\n")
        stats_f.write(f"Average publishing delay: {total_diff/len(data)}ms\n")
        stats_f.write("\n\n")
