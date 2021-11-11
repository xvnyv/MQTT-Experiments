import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties
import time
import datetime
import socket
import json
import argparse
import random
import threading
import os

N = 10
stats_fname = "qos-stats.txt"
hostname = "ec2-3-145-35-37.us-east-2.compute.amazonaws.com"
port = 1883
keepalive = 60


def periodic_disconnect(client, userdata):
    """Periodically disconnects the client based on the specified disconnect_perc. Ends on KeyboardInterrupt."""
    while not userdata["disconnect_event"].is_set():
        time.sleep(5)
        n = random.uniform(0, 1)
        if n <= userdata["disconnect_perc"]:
            client.disconnect()


def on_connect(client, userdata, flags, reason, rc):
    """Callback for when client receives a CONNACK response from broker"""
    print("Connected with result code " + str(rc))

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe("test", qos=qos)
    
    # Create and start disconnect thread only if:
    #   We want disconnections to happen (ie. disconnect_perc > 0) 
    #   Thread has not already been created and started
    if userdata["disconnect_thread"] is None and userdata["disconnect_perc"] > 0:
        userdata["disconnect_thread"] = threading.Thread(target=periodic_disconnect, args=[client, userdata])
        userdata["disconnect_thread"].start()


def on_message(client, userdata, msg):
    """Callback for when a PUBLISH message is received from the server"""
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
        userdata["data"].append(pkt_data)


def on_log(client, userdata, level, buf):
    """Logs messages sent and received by client"""
    print(f"[{level}] {buf}")


if __name__ == "__main__":
    # Process arguments
    parser = argparse.ArgumentParser(
        prog="sub-client",
        usage="Usage: python sub-client.py <qos> <net_cond> <disconnect_perc>\nDefault: qos=0, net_cond=good, disconnect_perc=0",
    )
    parser.add_argument("--qos", action="store", type=int, default=0, required=False)
    parser.add_argument(
        "--net_cond", action="store", type=str, default="good", required=False
    )
    parser.add_argument("--disconnect_perc", action="store", type=float, default=0, required=False)
    args = parser.parse_args()

    qos = args.qos
    net_cond = args.net_cond
    disconnect_perc = args.disconnect_perc

    try:
        # Initialise userdata to be passed to client callbacks
        userdata = {}
        data = []
        userdata["data"] = data
        userdata["disconnect_perc"] = disconnect_perc
        userdata["disconnect_event"] = threading.Event()
        userdata["disconnect_thread"] = None
        
        # Initialise client and callbacks
        client = mqtt.Client(
            client_id="test-sub", userdata=userdata, protocol=mqtt.MQTTv5, transport="tcp"
        )
        client.on_connect = on_connect
        client.on_message = on_message
        client.on_log = on_log

        # Initial connect
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
            
        # Loop forever with periodic disconnects and reconnects
        while True:
            print(f"Active threads: {threading.enumerate()}")
            client.loop_forever()
            # client disconnects and loop stops
            connected = False
            while not connected:
                try:
                    client.reconnect()
                    connected = True
                except socket.timeout:
                    pass
    except KeyboardInterrupt:
        # Write collected data to file
            # Can delete if we don't need to collect all the generated data
            # Just collecting for now in case we want to do further analysis later on
        data_folder = "data/"
        data_fname = (
            data_folder 
            + datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            + "_qos-"
            + str(qos)
            + f"_netcond-{net_cond}"
            + ".json"
        )
        if not os.path.isdir(data_folder):
            os.mkdir(data_folder)
        with open(data_fname, "w") as data_f:
            json.dump(data, data_f)
        
        # Stop disconnect thread, blocks until disconnect thread has been stopped
        if userdata["disconnect_thread"] is not None:
            print("Cancelling timer...")
            userdata["disconnect_event"].set()
            userdata["disconnect_thread"].join()
            
        # Process collected data
        if data:
            print("Calculating statistics...")
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
        
        print("Subscriber closed successfully")
