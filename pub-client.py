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

stats_fname = "qos-stats.txt"
hostname = "m.shohamc1.com"
port = 80
keepalive = 60


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


def on_log(client: mqtt.Client, userdata: Dict[str, Any], level: int, buf: str):
    print(f"[{level}] {buf}")


if __name__ == "__main__":
    # get args
    parser = argparse.ArgumentParser(
        prog="sub-client",
        usage="Usage: python sub-client.py <qos> <network-cond>\nDefault: qos=0, network_cond=good",
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
        "net_cond": "good",
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
        transport="websockets",
    )
    client.username_pw_set("test", "test")

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
        except socket.timeout:
            print("connection socket timeout, retrying...")

    # start looping to read from and write to broker
    client.loop_start()

    # wait for connection to be established before publishing
    while not userdata["connected"]:
        pass

    # publish N messages
    for seq_num in range(1, userdata["total_packets"] + 1):
        while not sent[seq_num - 1]:
            try:
                # switch to using threading.Timer to send at an interval
                cur_time: int = time.time_ns() // (10 ** 6)
                msg: mqtt.MQTTMessageInfo = client.publish(
                    "test", f"{seq_num} {cur_time}", userdata["qos"]
                )
                time.sleep(1)
                # msg.wait_for_publish()

                while msg.rc != mqtt.MQTT_ERR_SUCCESS:
                    print(f"Error publishing message with seq_num {seq_num}: {msg.rc}")
                    print("Retrying...")

                    cur_time = time.time_ns() // (10 ** 6)
                    msg = client.publish(
                        "test", f"{seq_num} {cur_time}", userdata["qos"]
                    )
                    time.sleep(1)
                    # msg.wait_for_publish()

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
                    data[msg.mid]["time_diff"] = (
                        data[msg.mid]["published_time"] - cur_time
                    )

                print(f"Message {msg.mid} with seq num {seq_num} is published")
                sent[seq_num - 1] = True
            except ValueError:
                time.sleep(1)

    total_diff: int = 0
    for mid, pkt in data.items():
        total_diff += pkt["time_diff"]

    with open(stats_fname, "a") as stats_f:
        stats_f.write("Publisher\n")
        stats_f.write("----------\n")
        stats_f.write(f"Network conditions: {userdata['net_cond']}\n")
        stats_f.write(f"QoS level: {userdata['qos']}\n")
        stats_f.write(f"Number of packets sent: {userdata['total_packets']}\n")
        stats_f.write(f"Average publishing delay: {total_diff/len(data)}ms\n")
        stats_f.write("\n\n")
