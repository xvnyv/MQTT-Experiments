import json
import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
from paho.mqtt.reasoncodes import ReasonCodes
import time
import datetime
import socket
import argparse
import random
import threading
import os
from typing import Any, List, Dict

from util import (
    dump_data,
    calc_stats,
    get_time,
    record_connect,
    connect_to_broker,
    transport,
    parse_yaml,
)


def periodic_disconnect(client: mqtt.Client, userdata: Dict[str, Any]):
    """Periodically disconnects the client based on the specified disconnect_perc. Ends on KeyboardInterrupt."""
    while not userdata["disconnect_event"].is_set():
        time.sleep(userdata["disconnect_interval"])
        n: float = random.uniform(0, 1)
        if n <= userdata["disconnect_perc"]:
            client.disconnect()
            userdata["e2e_data"].append(
                {
                    "seq_num": -1,
                    "last_seq_num": userdata["e2e_data"][-1]["seq_num"]
                    if len(userdata["e2e_data"]) > 0
                    else -1,
                    "disconnect_time": get_time(),
                    "reconnect_time": -1,
                }
            )
            # wait for reconnect before starting next interval
            time.sleep(userdata["disconnect_duration"])


def on_connect(
    client: mqtt.Client,
    userdata: Dict[str, Any],
    flags: Dict[str, Any],
    reason: ReasonCodes,
    properties: Properties,
):
    """Callback for when client receives a CONNACK response from broker"""
    record_connect(userdata)
    print("Connected with reason code " + reason.getName())

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("test", qos=userdata["qos"])

    # Create and start disconnect thread only if:
    #   We want disconnections to happen (ie. disconnect_perc > 0)
    #   Thread has not already been created and started
    if userdata["disconnect_thread"] is None and userdata["disconnect_perc"] > 0:
        userdata["disconnect_event"] = threading.Event()
        userdata["disconnect_thread"] = threading.Thread(
            target=periodic_disconnect, args=[client, userdata]
        )
        userdata["disconnect_thread"].start()


def on_message(client: mqtt.Client, userdata: Dict[str, Any], msg: mqtt.MQTTMessage):
    """Callback for when a PUBLISH message is received from the server"""
    rcv_time: float = get_time()
    print(f"{msg.topic} {msg.payload} {msg.mid}")
    if msg.topic == "test":
        content: str = msg.payload.decode()
        seq_num, send_time = content.split(" ")
        pkt_data: Dict[str, Any] = {
            "seq_num": int(seq_num),
            "send_time": float(send_time),
            "rcv_time": rcv_time,
            "time_diff": (rcv_time - float(send_time)),
            "qos": msg.qos,
        }
        userdata["e2e_data"].append(pkt_data)


def on_log(client, userdata, level, buf):
    """Logs messages sent and received by client"""
    print(f"[{level}] {buf}")


if __name__ == "__main__":
    # Process arguments
    parser = argparse.ArgumentParser(
        prog="sub-client",
        usage="Usage: python sub-client.py -f <input-file-path>",
    )

    parser.add_argument(
        "-f",
        "--file",
        help="Path to file with input variables",
        required=False,
        default="",
    )
    args = parser.parse_args()

    # Initialise userdata to be passed to client callbacks
    e2e_data: List[Dict[str, Any]] = []
    conn_data: List[Dict[str, Any]] = []
    userdata: Dict[str, Any] = {  # default values
        "qos": 0,
        "label": "normal",
        "tls": False,
        "total_packets": 50,
        "e2e_data": e2e_data,
        "conn_time": -1,
        "conn_tries": 0,
        "conn_data": conn_data,
        "disconnect_perc": 0,
        "disconnect_interval": 10,
        "disconnect_duration": 10,
        "disconnect_event": None,  # Optional[threading.Event]
        "disconnect_thread": None,  # Optional[threading.Thread]
    }
    userdata = parse_yaml(args.file, userdata, "subscriber")
    print(f"userdata: {userdata}")

    try:
        # Initialise client and callbacks
        client = mqtt.Client(
            client_id="test-sub",
            userdata=userdata,
            protocol=mqtt.MQTTv5,
            transport=transport,
        )
        client.username_pw_set("test", "test")
        if userdata["tls"]:
            client.tls_set()

        client.on_connect = on_connect
        client.on_message = on_message
        client.on_log = on_log

        # Initial connect
        properties = Properties(PacketTypes.CONNECT)
        properties.SessionExpiryInterval = 30
        connect_to_broker(client, userdata, properties)

        start_time = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        # Loop forever with periodic disconnects and reconnects
        while True:
            client.loop_forever()
            # client disconnects and loop stops --> initiate reconnect after disconnect_duration
            time.sleep(userdata["disconnect_duration"])
            connected = False
            while not connected:
                try:
                    client.reconnect()
                    connected = True
                    userdata["e2e_data"][-1]["reconnect_time"] = get_time()
                except socket.timeout:
                    pass
    except KeyboardInterrupt:
        cur_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        if conn_data:
            conn_data_fname = dump_data("sub-conn", conn_data, cur_date, userdata)
            conn_delay_stats = calc_stats(conn_data)
            conn_tries_stats = calc_stats(conn_data, "tries")
        if e2e_data:
            # Write collected data to file
            #   Can delete if we don't need to collect all the generated data
            #   Just collecting for now in case we want to do further analysis later on
            data_fname = dump_data("sub", e2e_data, cur_date, userdata)

            # Process collected data
            print("Calculating statistics...")
            e2e_stats = calc_stats(e2e_data)

            stats_folder = "summary/"
            stats_fname = stats_folder + userdata["label"] + ".json"

            if not os.path.isdir(stats_folder):
                os.mkdir(stats_folder)

            with open(stats_fname, "r+") as stats_f:
                cur_data = json.load(stats_f)
                summary_data = {
                    "start_time": start_time,
                    "label": userdata["label"],
                    "e2e_data_file": data_fname,
                    "tls": userdata["tls"],
                    "qos": userdata["qos"],
                    "pkt_sent": userdata["total_packets"],
                    "pkt_recv": e2e_stats["count"],
                    "pkt_loss": (userdata["total_packets"] - e2e_stats["count"])
                    / userdata["total_packets"],
                    "e2e_delay": e2e_stats,
                }
                if conn_data:
                    summary_data["conn_delay"] = conn_delay_stats
                    summary_data["conn_tries"] = conn_tries_stats
                    summary_data["conn_data_file"] = conn_data_fname

                stats_f.seek(0)
                json.dump({**cur_data, "subscriber": summary_data}, stats_f)

            os.rename(
                stats_fname,
                stats_folder + cur_date + "_" + userdata["label"] + ".json",
            )

        # Stop disconnect thread, blocks until disconnect thread has been stopped
        if userdata["disconnect_thread"] is not None:
            print("Cancelling timer...")
            userdata["disconnect_event"].set()
            userdata["disconnect_thread"].join()

        print("Subscriber closed successfully")
