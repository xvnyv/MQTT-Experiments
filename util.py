import os
import json
import statistics
import time
import yaml
import socket
import paho.mqtt.client as mqtt


hostname = "m.shohamc1.com"
port = 80
transport = "websockets"
# hostname = "ec2-3-137-165-98.us-east-2.compute.amazonaws.com"
# port = 1883
# transport = "tcp"
keepalive = 60


def parse_yaml(fname, userdata, caller):
    if fname:
        if not os.path.exists(fname):
            print(f"{fname} is not a valid path. Using default values.")
        else:
            with open(fname, "r") as input_f:
                input_values = yaml.safe_load(input_f)
                if input_values.get(caller, None) is not None:
                    userdata = {**userdata, **input_values[caller]}
                if input_values.get("shared", None) is not None:
                    userdata = {**userdata, **input_values["shared"]}
    global port
    if userdata["tls"]:
        port = 443
    return userdata


def dump_data(subfolder, data_dump, cur_date, userdata):
    data_folder = f"data/{subfolder}/"
    data_fname = (
        data_folder
        + cur_date
        + "_qos-"
        + str(userdata["qos"])
        + f"_netcond-{userdata['label']}"
        + ".json"
    )
    if not os.path.isdir(data_folder):
        os.makedirs(data_folder)
    with open(data_fname, "w") as data_f:
        json.dump(data_dump, data_f)
    return data_fname


def calc_stats(dataset, parameter="time_diff"):
    total_diff = 0
    data_points = []
    for pkt in dataset:
        if (pkt.get("seq_num", None) and pkt["seq_num"] != -1) or pkt.get(
            "seq_num", None
        ) is None:
            total_diff += pkt[parameter]
            data_points.append(pkt[parameter])

    count = len(dataset)
    std_deviation = statistics.stdev(data_points) if count > 1 else 0
    max_point = max(data_points)
    min_point = min(data_points)
    median = statistics.median(data_points)
    mean = total_diff / count

    return {
        "count": count,
        "min": min_point,
        "max": max_point,
        "mean": mean,
        "std_dev": std_deviation,
        "median": median,
    }


def get_time():
    return time.time_ns() // (10 ** 3) / (10 ** 3)


def connect_to_broker(client, userdata, properties=None):
    connected = False
    userdata["conn_time"] = get_time()
    while not connected:
        userdata["conn_tries"] += 1
        try:
            client.connect(
                hostname,
                port,
                keepalive,
                clean_start=False,
                properties=properties,
            )
            connected = True
        except (socket.timeout, mqtt.WebsocketConnectionError):
            print("connection error, retrying...")


def record_connect(userdata):
    if userdata["conn_time"] != -1 and userdata["conn_tries"] > 0:
        connected_time = get_time()
        userdata["conn_data"].append(
            {
                "connect_time": userdata["conn_time"],
                "connected_time": connected_time,
                "time_diff": connected_time - userdata["conn_time"],
                "tries": userdata["conn_tries"],
            }
        )
        userdata["conn_time"] = -1
        userdata["conn_tries"] = 0
