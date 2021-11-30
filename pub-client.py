import datetime
import json
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCodes
import argparse
import time
from typing import Dict, Any, List
import os
import yaml
import threading

# from RepeatedTimer import RepeatedTimer
from util import (
    dump_data,
    calc_stats,
    get_time,
    record_connect,
    connect_to_broker,
    transport,
    parse_yaml,
)

send_interval = 1.0


def on_connect(
    client: mqtt.Client,
    userdata: Dict[str, Any],
    flags: Dict[str, Any],
    reason: ReasonCodes,
    properties: Properties,
):
    record_connect(userdata)
    print("Connected with reason code " + reason.getName())

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    userdata["connected"] = True


def on_publish(client: mqtt.Client, userdata: Dict[str, Any], mid: int):
    """QoS 0: called when message has left the publisher
    QoS 1 & 2: called when handshakes have completed"""
    p_time = get_time()

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
        cur_time: float = get_time()
        seq_num = userdata["curr_seq_num"]

        msg: mqtt.MQTTMessageInfo = client.publish(
            "test", f"{seq_num} {cur_time}", userdata["qos"]
        )

        # print(msg.rc)

        while msg.rc != mqtt.MQTT_ERR_SUCCESS:
            print(f"Error publishing message with seq_num {seq_num}: {msg.rc}")
            print("Retrying...")

            cur_time = get_time()
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
    conn_data: List[Dict[str, Any]] = []

    userdata: Dict[str, Any] = {
        "connected": False,
        "data": data,
        "total_packets": 50,
        "qos": 0,
        "tls": False,
        "label": "normal",
        "curr_seq_num": 1,
        "lock": threading.Lock(),
        "published_count": 0,
        "conn_time": -1,
        "conn_tries": 0,
        "conn_data": conn_data,
    }
    sent: List[bool] = [False] * userdata["total_packets"]

    userdata = parse_yaml(args.file, userdata, "publisher")
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

    client.on_connect = on_connect
    client.on_publish = on_publish
    client.on_log = on_log

    # connect to host
    properties = Properties(PacketTypes.CONNECT)
    properties.SessionExpiryInterval = 30
    connect_to_broker(client, userdata, properties)

    start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # start looping to read from and write to broker
    client.loop_start()

    # wait for connection to be established before publishing
    while not userdata["connected"]:
        pass

    send_packets(userdata)

    while userdata["published_count"] < userdata["total_packets"]:
        time.sleep(1)

    cur_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    if conn_data:
        conn_data_fname = dump_data("pub-conn", conn_data, cur_date, userdata)
        conn_delay_stats = calc_stats(conn_data)
        conn_tries_stats = calc_stats(conn_data, "tries")
    if data:
        list_data = list(data.values())
        data_fname = dump_data("pub", list_data, cur_date, userdata)
        pub_delay_stats = calc_stats(list_data)

        stats_folder = "summary/"
        stats_fname = (
            stats_folder 
            + "_qos" 
            + str(userdata["qos"])
            + "_" + userdata['label']
            + ("_tls" if userdata["tls"] else "") 
            + ".json"
            )

        if not os.path.isdir(stats_folder):
            os.mkdir(stats_folder)

        with open(stats_fname, "w") as stats_f:
            summary_data = {
                "start_time": start_time,
                "label": userdata["label"],
                "pub_data_file": data_fname,
                "tls": userdata["tls"],
                "qos": userdata["qos"],
                "pkt_sent": userdata["total_packets"],
                "pub_delay": pub_delay_stats,
            }
            if conn_data:
                summary_data["conn_delay"] = conn_delay_stats
                summary_data["conn_tries"] = conn_tries_stats
                summary_data["conn_data_file"] = conn_data_fname

            json.dump({"publisher": summary_data}, stats_f)
