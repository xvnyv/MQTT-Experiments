# Networks Project

Mosuqitto broker deployed on EC2. Scripts for Paho clients are included in this repo.

Both broker and clients are using MQTT v5. Clients connect to the broker with the clean start flag set to 0 and session expiry interval set to 30s. This ensures that when using QoS 1 or 2, the session state will be restored for a client who disconnects and reconnects with the same client ID within 30s (ie. client will receive all the messages that were published during the time that it was disconnected).

Initial experiment was run with the broker deployed on EC2 and both publisher and subscriber client scripts were run locally from my Ubuntu VM. Simulated packet loss using `tc` was done on the Ubuntu VM, which means only outgoing packets from the publisher were affected. We might want to change where we simulate packet loss/low bandwidth to the host running NGINX so that packets from all 3 parties (ie. publisher, subscriber, broker) will be subjected to these conditions.

## Running Clients
If Mosquitto broker was stopped and re-started, update the `hostname` variable with the new EC2 public DNS hostname before running either scripts.

`N` specifies the number of packets to be sent.

The publisher will send `N` messages to the specified topic immediately after connecting. Hence, to test communications between publisher and subscriber, run the subscriber first.
```
python sub-client.py --qos=<qos> --net_cond=<net_cond>
```
Once the subscriber is connected to the broker, run the publisher with:
```
python pub-client.py <qos> <net_cond>
```
Valid options are `qos=0,1,2` and `net_cond=good,poor` (`net_cond` is just a metadata recorded in the output file -- does not affect communications)

Default options are: `--qos=0 --net_cond=good`

The publisher script will end immediately after all `N` messages have been sent. Some stats about publishing delay will be written to the file `qos-stats.txt` just before the script ends. The subscriber script will continue running indefinitely. Hence, once all messages are received, terminate the script wtih ctrl-c. The stats regarding end-to-end delay and packet loss will be recorded in the same `qos-stats.txt` file.

Note: Connecting to the broker might take a while. The socket will sometimes time out so I set both clients to retry until they manage to connect.
