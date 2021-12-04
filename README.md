# Networks Project

Raw data and plots for final experiments can be found here: https://drive.google.com/drive/folders/1guFbEUKBr7Eck9_k3m2HmrLUqBEW8p2g?usp=sharing

## Setup Description

Mosuqitto broker deployed on EC2. Scripts for Paho clients are included in this repo.

Both broker and clients are using MQTT v5. Clients connect to the broker with the clean start flag set to 0 and session expiry interval set to 30s. This ensures that when using QoS 1 or 2, the session state will be restored for a client who disconnects and reconnects with the same client ID within 30s (ie. client will receive all the messages that were published during the time that it was disconnected).

Initial experiment was run with the broker deployed on EC2 and both publisher and subscriber client scripts were run locally from my Ubuntu VM. Simulated packet loss using `tc` was done on the Ubuntu VM, which means only outgoing packets from the publisher were affected. We might want to change where we simulate packet loss/low bandwidth to the host running NGINX so that packets from all 3 parties (ie. publisher, subscriber, broker) will be subjected to these conditions.

## Running Clients: w/o Docker

Run `pip install -r requirements.txt` if `paho-mqtt` is not yet installed.

If Mosquitto broker was stopped and re-started, update the `hostname` variable with the new EC2 public DNS hostname before running either scripts.

`N` specifies the number of packets to be sent.

The publisher will send `N` messages to the specified topic immediately after connecting. Hence, to test communications between publisher and subscriber, run the subscriber first.

```
python sub-client.py -f <input-file-path>
```

Once the subscriber is connected to the broker, run the publisher with:

```
python pub-client.py -f <input-file-path>
```

**Input File Format**

Input arguments can be specified using a YAML file. The available parameters and default values are:

```yaml
shared:
  qos: 0
  net_cond: normal
  total_packets: 50
  tls: False
publisher:
subscriber:
  disconnect_perc: 0
  disconnect_duration: 10
  disconnect_interval: 10
```

Valid options:

- `qos=0,1,2`
- `net_cond` acts as a label in qos-stats.txt so that you can identify which test scenario that data was for
- `total_packets` is the total number of messages to be sent from publisher to subscriber
- `tls` is used to indicate whether or not both publisher and subscriber should use TLS
- `0 <= disconnect_perc <= 1` represents the chance for subscriber to get disconnected
- `disconnect_duration` represents the duration before client initiates reconnect after disconnecting in seconds
- `disconnect_interval` represents the minimum interval before next disconnect will be called after initiating reconnect in seconds

The publisher script will end immediately after all `N` messages have been sent. Some stats about publishing delay will be written to the file `qos-stats.txt` just before the script ends. The subscriber script will continue running indefinitely. Hence, once all messages are received, terminate the script wtih ctrl-c. The stats regarding end-to-end delay and packet loss will be recorded in the same `qos-stats.txt` file.

Note: Connecting to the broker might take a while. The socket will sometimes time out so I set both clients to retry until they manage to connect.

## Running Clients: Docker

`run.sh` builds and runs the clients in Docker containers that will be removed upon ending the program.

To run the publisher:

```
./run.sh pub -f <input-file-path>
```

To run the subscriber:

```
./run.sh sub -f <input-file-path>
```

Note that only 1 publisher and 1 subscriber can be run at the same time. If you wish to run multiple subscribers/publishers at the same time, edit `run.sh` to change the way the containers are named.
