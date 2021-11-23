import datetime
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCodes
import argparse
import time
import socket
from typing import Dict, Any, List
import os
import yaml
import statistics
import threading
from RepeatedTimer import RepeatedTimer

stats_fname = "qos-stats.txt"
hostname = "m.shohamc1.com"
port = 80
transport = "websockets"
# hostname = "ec2-3-137-165-98.us-east-2.compute.amazonaws.com"
# port = 1883
# transport = "tcp"
keepalive = 60
send_interval = 1.0


def on_connect(
    client: mqtt.Client,
    userdata: Dict[str, Any],
    flags: Dict[str, Any],
    reason: ReasonCodes,
    properties: Properties,
):
    print("Connected with reason code " + reason.getName())

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    userdata["connected"] = True


def on_publish(client: mqtt.Client, userdata: Dict[str, Any], mid: int):
    """QoS 0: called when message has left the publisher
    QoS 1 & 2: called when handshakes have completed"""
    p_time = time.time_ns() // (10 ** 6)

    userdata["lock"].acquire()
    if userdata["data"].get(mid, None) is None:
        # publishing interval not over yet
        userdata["data"][mid] = {
            "publishing_time": -1,
            "published_time": p_time,
            "time_diff": -1,
            "seq_num": -1,
            "qos": -1,
        }
    else:
        # publishing interval over
        userdata["data"][mid]["published_time"] = p_time
        userdata["data"][mid]["time_diff"] = (
            p_time - userdata["data"][mid]["publishing_time"]
        )
    userdata["lock"].release()

    userdata["published_count"] += 1

    # userdata["curr_seq_num"] += 1


def on_log(client: mqtt.Client, userdata: Dict[str, Any], level: int, buf: str):
    print(f"[{level}] {buf}")


def send_packets(userdata):
    while userdata["curr_seq_num"] <= userdata["total_packets"]:
        cur_time: int = time.time_ns() // (10 ** 6)
        seq_num = userdata["curr_seq_num"]

        msg: mqtt.MQTTMessageInfo = client.publish(
            "test", f"{seq_num} {cur_time}", userdata["qos"]
        )

        # print(msg.rc)

        while msg.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Error publishing message with seq_num {seq_num}: {msg.rc}")
            print("Retrying...")

            cur_time = time.time_ns() // (10 ** 6)
            msg = client.publish("test", f"{seq_num} {cur_time}", userdata["qos"])

        userdata["lock"].acquire()
        if data.get(msg.mid, None) is None:
            # on_publish() not called yet
            data[msg.mid] = {
                "publishing_time": cur_time,
                "published_time": -1,
                "time_diff": -1,
                "seq_num": seq_num,
                "qos": userdata["qos"],
            }
        else:
            # on_publish() already called
            data[msg.mid]["publishing_time"] = cur_time
            data[msg.mid]["seq_num"] = seq_num
            data[msg.mid]["qos"] = userdata["qos"]
            data[msg.mid]["time_diff"] = data[msg.mid]["published_time"] - cur_time
        userdata["lock"].release()
        print(f"Message {msg.mid} with seq num {seq_num} is published")
        userdata["curr_seq_num"] += 1
        time.sleep(1)


if __name__ == "__main__":
    # get args
    parser = argparse.ArgumentParser(
        prog="pub-client",
        usage="Usage: python pub-client.py -f <input-file-path>",
    )

    parser.add_argument(
        "-f",
        "--file",
        help="Path to file with input variables",
        required=False,
        default="",
    )
    args = parser.parse_args()

    # initialise data
    data: Dict[int, Dict[str, Any]] = {}
    userdata: Dict[str, Any] = {
        "connected": False,
        "data": data,
        "total_packets": 50,
        "qos": 0,
        "tls": False,
        "net_cond": "normal",
        "curr_seq_num": 1,
        "lock": threading.Lock(),
        "published_count": 0,
    }
    sent: List[bool] = [False] * userdata["total_packets"]

    if args.file:
        if not os.path.exists(args.file):
            print(f"{args.file} is not a valid path. Using default values.")
        else:
            with open(args.file, "r") as input_f:
                input_values = yaml.safe_load(input_f)
                if input_values.get("publisher", None) is not None:
                    userdata = {**userdata, **input_values["publisher"]}
                if input_values.get("shared", None) is not None:
                    userdata = {**userdata, **input_values["shared"]}

    print(f"userdata: {userdata}")

    client = mqtt.Client(
        client_id="test-pub",
        userdata=userdata,
        protocol=mqtt.MQTTv5,
        transport=transport,
    )
    client.username_pw_set("test", "test")
    if userdata["tls"]:
        client.tls_set()
        port = 443

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_log = on_log

    # connect to host
    connected = False
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 30
    while not connected:
        try:
            client.connect(
                hostname, port, keepalive, clean_start=False, properties=properties
            )
            connected = True
        except (socket.timeout, mqtt.WebsocketConnectionError):
            print("connection error, retrying...")
            time.sleep(1)

    start_time = datetime.datetime.now()
    # start looping to read from and write to broker
    client.loop_start()

    # wait for connection to be established before publishing
    while not userdata["connected"]:
        pass

    # rt = RepeatedTimer(send_interval, send_packets, userdata)

    # while True:
    #     if userdata["curr_seq_num"] > userdata["total_packets"]:
    #         rt.stop()
    #         break
    send_packets(userdata)

    while userdata["published_count"] < userdata["total_packets"]:
        time.sleep(1)

    total_diff: int = 0
    data_points: List[int] = []
    for mid, pkt in data.items():
        total_diff += pkt["time_diff"]
        data_points.append(pkt["time_diff"])

    std_deviation = statistics.stdev(data_points)
    max_point = max(data_points)
    min_point = min(data_points)
    median = statistics.median(data_points)

    stats_folder = "summary/"
    stats_fname = stats_folder + userdata["net_cond"] + ".txt"

    if not os.path.isdir(stats_folder):
        os.mkdir(stats_folder)

    with open(stats_fname, "w") as stats_f:
        stats_f.write("Publisher\n")
        stats_f.write("----------\n")
        stats_f.write(f"Start time: {start_time}\n")
        stats_f.write(f"Network conditions: {userdata['net_cond']}\n")
        stats_f.write(f"Used TLS: {userdata['tls']}\n")
        stats_f.write(f"QoS level: {userdata['qos']}\n")
        stats_f.write(f"Number of packets sent: {userdata['total_packets']}\n")
        stats_f.write(f"---Publishing Delay\n")
        stats_f.write(f"Min: {min_point}ms\n")
        stats_f.write(f"Mean: {total_diff/len(data)}ms\n")
        stats_f.write(f"Median: {median}ms\n")
        stats_f.write(f"Max: {max_point}ms\n")
        stats_f.write(f"Standard Deviation: {std_deviation}\n")
        stats_f.write("\n\n")
