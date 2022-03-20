# MQTT QoS and TLS Research

As part of the 50.012 module in Fall 2021, my team chose to examine how the performance of the MQTT protocol is affected by the 3 levels of QoS and the addition of TLS under different network conditions. 

## Background
Theory suggests that lower QoS levels are typically used under stable network conditions, and higher QoS levels are used under unstable network conditions with the aim of minimizing packet loss. However, in practice, there is a trade-off between the performance and reliability of data transfer. As such, the team is interested in finding out the relationship between performance and reliability, and the extent to which performance is sacrificed to achieve reliability.

Messages sent via MQTT are unencrypted and in plaintext. Since MQTT uses TCP/IP, the messages will pass through many infrastructure components like routers and Internet Exchange Points (IXPs) before reaching the target (The HiveHQ Team, 2015). As such, it is good practice to use Transport Layer Security (TLS) to provide a secure communication channel between the clients and server, especially if sensitive information is being transmitted. However, the usage of TLS would also impose additional overhead. Therefore, the team is interested in finding out how much overhead the addition of TLS will impose, and to what extent would the overhead affect the performance of MQTT across the different QoS levels and network conditions.

## Experiment Setup

### Broker and Clients
A Mosquitto broker and 2 Paho clients were used to simulate publishing and subscribing.

Both broker and clients used MQTT v5. Clients connected to the broker with the clean start flag set to 0 and session expiry interval set to 30s. This ensured that when using QoS 1 or 2, the session state will be restored for a client who disconnects and reconnects with the same client ID within 30s (ie. client will receive all the messages that were published during the time that it was disconnected).

Both publisher and subscriber clients were run locally on the same device.

### Nginx and TLS
Nginx’s default behaviour blocks access to all ports that it is not monitoring. Since mosquitto runs on port 1883, it was necessary to create a passthrough from port 80 to port 1883. However, nginx did not accept external traffic since it does not support the MQTT protocol. Hence, the broker was set up to use the websockets protocol on port 8082. When a request was received by the nginx server, it would upgrade the protocol from HTTP to websockets and pass it on to the broker. The nginx proxy timeout was also set to 5min to prevent nginx from closing connections between the broker and clients prematurely.

Let’s Encrypt was used to generate a TLS certificate. The above configuration was extended to listen to port 443 using the generated certificate.

## Experiment Details

To investigate the performance of MQTT across the different QoS levels and with the addition of TLS, my team decided to create 3 different scenarios under which we would vary QoS levels and the usage of TLS.
- Network Stability (measured in terms of subscriber disconnect frequency)
- Packet Loss
- Bandwidth

To evaluate the performance of MQTT, my team looked at the following metrics:
- Publishing Delay
  - The time taken for a publisher to complete its publishing process and discard the published message after calling the publish method provided by Paho. This means that publishing delay will take into account all publishing-related control packets.
- End-to-End Delay
  - The time taken from when the publisher publishes a message until the subscriber successfully receives it.
- Packet Loss Percentage
  - the percentage of packets that were published by the publisher but not received by the subscriber.
- Connecting Delay
  - The time taken for the client to successfully connect to the broker.

For more information about our experiment setup, methods and results, please visit the following links.
- Report with details on our experiment methods and results can be found here: https://docs.google.com/document/d/1tTaTM5_rO4brFeQDLGxC4GMX1-WoC86r6TfwUJg9GPY/edit?usp=sharing 
- Raw data and plots for final experiments can be found here: https://drive.google.com/drive/folders/1guFbEUKBr7Eck9_k3m2HmrLUqBEW8p2g?usp=sharing

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
