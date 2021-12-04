from typing import Any, Dict, List
from statistics import mean
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

import os
import json

# EDIT THESE VALUES
# directory = "summaries"
# x_data = [0, 15, 30, 45, 60]
# x_title = "Packet Loss (%)"
# labels = ["loss_0", "loss15", "loss30", "loss45", "loss60"]
directory = "summary"
x_data = [0, 2, 3.33, 10, 20]
x_title = "Disconnect Frequency (%)"
labels = [
    "disconnect_never",
    "disconnect_1_in_50",
    "disconnect_1_in_30",
    "disconnect_1_in_10",
    "disconnect_1_in_5",
]

# DO NOT EDIT FROM HERE ONWARDS
test_repetitions = 5
default_figure_parameters = {
    "title": "Default Title",
    "y_axis_title": "Y Axis",
    "x_axis_title": "X Axis",
    "filename": "figure",
}
pub_delay = {}
e2e_delay = {}
pub_conn_delay = {}
sub_conn_delay = {}
loss = {}
test_metrics = [
    {
        "data": pub_delay,
        "figure_parameters": {
            "title": "Publishing Delay (ms)",
            "y_axis_title": "Publishing Delay (ms)",
            "x_axis_title": x_title,
            "indiv_filename": "mean-publishing-delay",
            "agg_filename": "agg-publishing-delay",
        },
    },
    {
        "data": e2e_delay,
        "figure_parameters": {
            "title": "End-to-End Delay (ms)",
            "y_axis_title": "End-to-End Delay (ms)",
            "x_axis_title": x_title,
            "indiv_filename": "mean-e2e-delay",
            "agg_filename": "agg-e2e-delay",
        },
    },
    {
        "data": sub_conn_delay,
        "figure_parameters": {
            "title": "Subscriber Connecting Delay (ms)",
            "y_axis_title": "Connecting Delay (ms)",
            "x_axis_title": x_title,
            "indiv_filename": "mean-sub-conn-delay",
            "agg_filename": "agg-sub-conn-delay",
        },
    },
    {
        "data": pub_conn_delay,
        "figure_parameters": {
            "title": "Publisher Connecting Delay (ms)",
            "y_axis_title": "Connecting Delay (ms)",
            "x_axis_title": x_title,
            "indiv_filename": "mean-pub-conn-delay",
            "agg_filename": "agg-pub-conn-delay",
        },
    },
    {
        "data": loss,
        "figure_parameters": {
            "title": "Packet Loss (%)",
            "y_axis_title": "Packet Loss (%)",
            "x_axis_title": x_title,
            "indiv_filename": "loss",
            "agg_filename": "agg-loss",
        },
    },
]


def get_dict(label, val):
    d = {}
    add_to_dict_array(d, label, val)
    return d


def add_to_dict_array(d: dict, key: str, val: Any):
    if d.get(key, None) is None:
        d[key] = [val]
    else:
        d[key].append(val)


def add_to_dict_dict(
    d: Dict[str, Dict[str, List[float]]], key: str, val: Dict[str, List[float]]
):
    if d.get(key, None) is None:
        d[key] = val
    else:
        for k, v in val.items():
            add_to_dict_array(d[key], k, v[0])


def unpack_figure_parameters(figure_params):
    if figure_params is not None:
        return {**default_figure_parameters, **figure_params}
    else:
        return default_figure_parameters


def create_indiv_figure(data: Dict[str, List], figure_params=None):
    figure_parameters = unpack_figure_parameters(figure_params)

    fig = go.Figure().set_subplots(
        # rows=2,
        rows=3,
        cols=6,
        specs=[
            # [{"colspan": 2}, None, {"colspan": 2}, None, {"colspan": 2}, None],
            # [{"colspan": 3}, None, None, {"colspan": 3}, None, None],
            [{"colspan": 3}, None, None, {"colspan": 3}, None, None],
            [{"colspan": 3}, None, None, {"colspan": 3}, None, None],
            [{"colspan": 6}, None, None, None, None, None],
        ],
        subplot_titles=(
            "Test 1",
            "Test 2",
            "Test 3",
            "Test 4",
            "Test 5",
        ),
    )
    fig.update_layout(title=figure_parameters["title"])
    fig.update_layout(height=1500)
    fig.update_xaxes(title_text=figure_parameters["x_axis_title"])
    # fig.update_yaxes(title_text=figure_parameters["y_axis_title"])

    # row_col = [(1, 1), (1, 3), (1, 5), (2, 1), (2, 4)]
    row_col = [(1, 1), (1, 4), (2, 1), (2, 4), (3, 1)]

    for i in range(test_repetitions):
        for k, v in data.items():
            fig.add_trace(
                go.Scatter(
                    x=x_data,
                    y=v[i],
                    mode="lines+markers",
                    name=f"Test {i+1}: {k}",
                ),
                row=row_col[i][0],
                col=row_col[i][1],
            )
    fig.write_html("html/" + figure_parameters["indiv_filename"] + ".html")


def create_agg_figure(data: Dict[str, List], figure_params=None):
    figure_parameters = unpack_figure_parameters(figure_params)

    fig = go.Figure()
    fig.update_layout(title=figure_parameters["title"])
    fig.update_xaxes(title_text=figure_parameters["x_axis_title"])
    fig.update_yaxes(title_text=figure_parameters["y_axis_title"])

    for k, v in data.items():
        fig.add_trace(
            go.Scatter(
                x=x_data,
                y=v,
                mode="lines+markers",
                name=k,
            )
        )
    fig.write_html("html/" + figure_parameters["agg_filename"] + ".html")


def read_data():
    for filename in os.listdir(directory):
        f = os.path.join(directory, filename)
        # checking if it is a file
        if os.path.isfile(f):
            with open(f, "r") as fp:
                content = json.load(fp)

            e2e_delay_mean = content["subscriber"]["e2e_delay"]["mean"]
            sub_conn_mean = content["subscriber"]["conn_delay"]["mean"]
            pub_delay_mean = content["publisher"]["pub_delay"]["mean"]
            pub_conn_mean = content["publisher"]["conn_delay"]["mean"]
            loss_val = content["subscriber"]["pkt_loss"]

            label = content["publisher"]["label"]
            qos = "qos{}".format(content["publisher"]["qos"])
            tls = "tls" if content["publisher"]["tls"] else "no tls"
            qos_tls = qos + ", " + tls

            add_to_dict_dict(pub_delay, qos_tls, {label: [pub_delay_mean]})
            add_to_dict_dict(e2e_delay, qos_tls, {label: [e2e_delay_mean]})
            add_to_dict_dict(sub_conn_delay, qos_tls, {label: [sub_conn_mean]})
            add_to_dict_dict(pub_conn_delay, qos_tls, {label: [pub_conn_mean]})
            add_to_dict_dict(loss, qos_tls, {label: [loss_val]})


def format_data(d):
    output_d = {}
    for k, v in d.items():
        formatted_data = [[0] * test_repetitions for _ in range(len(x_data))]
        for label, val_arr in v.items():
            for i, val in enumerate(val_arr):
                formatted_data[i][labels.index(label)] = val
        output_d[k] = formatted_data
    return output_d


def aggregate_data(d):
    agg_d = {}
    for k, v in d.items():
        agg_d[k] = list(map(mean, zip(*v)))
    return agg_d


def main():
    read_data()
    if not os.path.isdir("html/"):
        os.makedirs("html/")
    for metric in test_metrics:
        formatted_d = format_data(metric["data"])
        create_indiv_figure(formatted_d, metric["figure_parameters"])

        aggregated_d = aggregate_data(formatted_d)
        create_agg_figure(aggregated_d, metric["figure_parameters"])


if __name__ == "__main__":
    main()
