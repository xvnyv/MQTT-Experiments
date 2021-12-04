import datetime
import pandas as pd
import plotly.graph_objects as go
import os
import json

# EDIT THESE VALUES
test_var = "bandwidth"  # stability, loss, bandwidth
metric = "e2e_delay"  # pub_delay, e2e_delay
plot_type = "multi"  # indiv, multi
VAR = "0.01KB"  # optional to specify var, only if label field is not used else set to None

# DO NOT EDIT FROM HERE ONWARDS
cur_date = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
html_dir = "data-html"
data_dir = "data-0.2KB"
params = {
    "pub_delay": {
        "title": "Publishing Delay (ms)",
        "html_filename": f"{html_dir}/{test_var}_pub_",
        "directory": f"{data_dir}/pub",
    },
    "e2e_delay": {
        "title": "End-to-End Delay (ms)",
        "html_filename": f"{html_dir}/{test_var}_sub_",
        "directory": f"{data_dir}/sub",
    },
    "pub_conn_delay": {
        "title": "Publisher Connecting Delay (ms)",
        "html_filename": f"{html_dir}/{test_var}_pub-conn_",
        "directory": f"{data_dir}/pub-conn",
    },
    "sub_conn_delay": {
        "title": "Subscriber Connecting Delay (ms)",
        "html_filename": f"{html_dir}/{test_var}_sub-conn_",
        "directory": f"{data_dir}/sub-conn",
    },
}
x_axis_title = "Seq Num"
plotly_colors = [
    "#1f77b4",  # muted blue
    "#ff7f0e",  # safety orange
    "#2ca02c",  # cooked asparagus green
    "#d62728",  # brick red
    "#9467bd",  # muted purple
    "#8c564b",  # chestnut brown
    "#e377c2",  # raspberry yogurt pink
    "#7f7f7f",  # middle gray
    "#bcbd22",  # curry yellow-green
    "#17becf",  # blue-teal
]
plots = {}


def parse_label(label):
    qos = label[: len("qos0")]
    tls = "tls" if label[-len("tls") :] == "tls" else "no_tls"
    var = label[len("qos0_") :].rstrip("_tls")

    return tls, qos, var


def create_multi_plots(var, entries):
    fig = go.Figure().set_subplots(
        rows=3,
        cols=6,
        specs=[
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
    fig.update_layout(title=f"{params[metric]['title']}: {var}")
    # fig.update_layout(height=1500)
    fig.update_xaxes(title_text=x_axis_title)

    row_col = [(1, 1), (1, 4), (2, 1), (2, 4), (3, 1)]

    for i, entry in enumerate(entries):
        for line in entry:
            fig.add_trace(
                go.Scatter(
                    x=line["x"],
                    y=line["y"],
                    mode="lines+markers",
                    name=f"Test {i+1}: {line['tls']} {line['qos']}",
                ),
                row=row_col[i][0],
                col=row_col[i][1],
            )
    fig.write_html(params[metric]["html_filename"] + var + ".html")


def create_indiv_plots(var, entries):
    for i, entry in enumerate(entries):
        fig = go.Figure()
        fig.update_layout(title=f"{params[metric]['title']}: {var}")
        fig.update_xaxes(title_text=x_axis_title)
        fig.update_yaxes(title_text=params[metric]["title"])
        for line in entry:
            fig.add_trace(
                go.Scatter(
                    x=line["x"],
                    y=line["y"],
                    mode="lines+markers",
                    name=f"{line['tls']} {line['qos']}",
                )
            )
        fig.write_html(f"{params[metric]['html_filename']}_{var}_indiv{i}.html")


for filename in os.listdir(params[metric]["directory"]):
    f = os.path.join(params[metric]["directory"], filename)
    if os.path.isfile(f):
        with open(f, "r") as fp:
            content = json.load(fp)
        x = []
        y = []

        for msg in content:
            if msg.get("time_diff", None):
                x.append(msg["seq_num"])
                y.append(msg["time_diff"])

        label = f.split("/")[-1][len(cur_date + "_") : -len(".json")]
        tls, qos, var = parse_label(label)
        if VAR is not None:
            var = VAR

        entry = {"x": x, "y": y, "tls": tls, "qos": qos}
        key = f"{var}|{qos}|{tls}"
        if plots.get(key, None) is None:
            plots[key] = [entry]
        else:
            plots[key].append(entry)

sorted_plots = {}
for label, entries in plots.items():
    var = label.split("|")[0]
    if sorted_plots.get(var, None) is None:
        sorted_plots[var] = [[entry] for entry in entries]
    else:
        for i in range(len(sorted_plots[var])):
            sorted_plots[var][i].append(entries[i])

if not os.path.isdir(html_dir):
    os.makedirs(html_dir)

for var, entries in sorted_plots.items():
    if plot_type == "indiv":
        create_indiv_plots(var, entries)
    elif plot_type == "multi":
        create_multi_plots(var, entries)
