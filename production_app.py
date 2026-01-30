import streamlit as st
import pandas as pd
import plotly.express as px
from graphviz import Digraph
from math import ceil

st.set_page_config(page_title="Smart Production AI System", layout="wide")
st.title("🏭 Smart Production Time Study, Line Balancing & Capacity AI")

# ================= SIDEBAR =================
st.sidebar.header("⏳ Production Schedule")
hours_per_day = st.sidebar.number_input("Work Hours per Day", value=8)
days_per_week = st.sidebar.number_input("Days per Week", value=5)
weeks_per_year = st.sidebar.number_input("Weeks per Year", value=50)

st.sidebar.header("⚙ OEE Breakdown")
availability = st.sidebar.slider("Availability %", 50, 100, 90) / 100
performance = st.sidebar.slider("Performance %", 50, 100, 95) / 100
quality = st.sidebar.slider("Quality %", 50, 100, 98) / 100
oee = availability * performance * quality
available_time_day = hours_per_day * 3600 * oee

st.sidebar.header("📦 Demand & Sales")
daily_demand = st.sidebar.number_input("Customer Demand (units/day)", value=200)
selling_price = st.sidebar.number_input("Selling Price per Unit ($)", value=150.0)
material_cost = st.sidebar.number_input("Material Cost per Unit ($)", value=50.0)

# ================= INPUT =================
st.header("🛠 Operation Time Study")
num_tasks = st.number_input("Number of Operations", 1, 20, 4)
batch_size = st.number_input("Batch Size", 1, 10000, 20)

tasks = []

for i in range(num_tasks):
    st.subheader(f"Operation {i+1}")
    c1, c2, c3 = st.columns(3)

    name = c1.text_input("Operation Name", value=f"Op {i+1}", key=f"name{i}")
    setup = c1.number_input("Setup Time (s)", 0, 10000, 60, key=f"setup{i}")

    cycle = c2.number_input("Cycle Time (s)", 1, 10000, 30, key=f"cycle{i}")

    # Optional Soak / Cure
    add_soak = c2.checkbox("Add Soak / Cure", key=f"soak_chk{i}")
    if add_soak:
        soak_value = c2.number_input("Soak Time", min_value=0.0, value=0.0, key=f"soak_val{i}")
        soak_unit = c2.selectbox("Soak Unit", ["seconds", "minutes", "hours", "days"], key=f"soak_unit{i}")
        if soak_unit == "minutes":
            soak_sec = soak_value * 60
        elif soak_unit == "hours":
            soak_sec = soak_value * 3600
        elif soak_unit == "days":
            soak_sec = soak_value * 3600 * 24
        else:
            soak_sec = soak_value
    else:
        soak_sec = 0

    operators = c2.number_input("Operators", 1, 20, 1, key=f"op{i}")
    setup_rate = c3.number_input("Setup Labor Rate ($/hr)", 1, 200, 25, key=f"sr{i}")
    cycle_rate = c3.number_input("Cycle Labor Rate ($/hr)", 1, 200, 25, key=f"cr{i}")

    tasks.append({
        "Operation": name,
        "Setup Time": setup,
        "Cycle Time": cycle,
        "Soak Time": soak_sec,
        "Operators": operators,
        "Setup Rate": setup_rate,
        "Cycle Rate": cycle_rate
    })

df = pd.DataFrame(tasks)
df_sim = df.copy()  # for simulations

# ================= CALCULATIONS =================
df["Setup per Unit"] = df["Setup Time"] / batch_size
df["Effective Cycle"] = df["Cycle Time"] / df["Operators"]
df["Unit Time"] = df["Effective Cycle"] + df["Setup per Unit"] + df["Soak Time"]

df["Cycle Cost/Unit"] = df["Effective Cycle"] * (df["Cycle Rate"] / 3600)
df["Setup Cost/Unit"] = df["Setup per Unit"] * (df["Setup Rate"] / 3600)
df["Labor Cost/Unit"] = df["Cycle Cost/Unit"] + df["Setup Cost/Unit"]
df["Material Cost/Unit"] = material_cost
df["Total Cost/Unit"] = df["Labor Cost/Unit"] + df["Material Cost/Unit"]

# ================= MULTIPLE BOTTLENECKS =================
top_n_bottlenecks = 3
bottlenecks_df = df.sort_values("Unit Time", ascending=False).head(top_n_bottlenecks)
bottleneck_ops = bottlenecks_df["Operation"].tolist()
bottleneck_times = bottlenecks_df["Unit Time"].tolist()

df["Utilization %"] = df["Unit Time"] / bottleneck_times[0] * 100

# Throughput & Takt
throughput_hr = 3600 / bottleneck_times[0]
takt_time = available_time_day / daily_demand
current_ops = df["Operators"].sum()
st.metric("👷 Current Operators", current_ops)

# Capacity
daily_capacity = available_time_day / bottleneck_times[0]
weekly_capacity = daily_capacity * days_per_week
monthly_capacity = weekly_capacity * 4.33
yearly_capacity = weekly_capacity * weeks_per_year

# Lead time & WIP
wip_multiplier = st.sidebar.slider("WIP Multiplier (Queue effect)", 1.0, 5.0, 1.5)
lead_time = df["Unit Time"].sum() * wip_multiplier
wip = daily_capacity * (lead_time / available_time_day)
lead_time_days = wip / daily_capacity if daily_capacity > 0 else 0
st.metric("⏳ Lead Time (Days)", f"{lead_time_days:.2f}")

# Line Balance Efficiency
total_work_content = df["Unit Time"].sum()
theoretical_min_ops = ceil(total_work_content / takt_time)
balance_efficiency = total_work_content / (current_ops * bottleneck_times[0]) * 100

# Profit
total_cost_per_unit = df["Total Cost/Unit"].mean()
profit_per_unit = max(0, selling_price - total_cost_per_unit)
actual_output = min(daily_capacity, daily_demand)
daily_profit = profit_per_unit * actual_output
weekly_profit = daily_profit * days_per_week
monthly_profit = daily_profit * days_per_week * 4.33
yearly_profit = daily_profit * days_per_week * weeks_per_year

daily_labor_cost = (
    (df["Cycle Rate"] * df["Operators"] * hours_per_day).sum()
    + (df["Setup Rate"] * df["Setup Time"] * (daily_capacity / batch_size) / 3600).sum()
)
st.metric("💵 Daily Labor Cost", f"${daily_labor_cost:,.0f}")

# ================= KPI =================
st.header("📊 Production KPIs")
st.metric("⚖ Line Balance Efficiency", f"{balance_efficiency:.1f}%")
k1, k2, k3, k4 = st.columns(4)
k1.metric("Bottlenecks", ", ".join(bottleneck_ops))
k2.metric("Throughput", f"{throughput_hr:.1f} units/hr")
k3.metric("Takt Time", f"{takt_time:.1f}s/unit")
k4.metric("Lead Time", f"{lead_time:.1f}s")
st.metric("💰 Daily Profit", f"${daily_profit:,.0f}")
util = (actual_output/daily_capacity*100) if daily_capacity > 0 else 0
st.metric("📈 Capacity Utilization", f"{util:.1f}%")

st.subheader("👥 Operator Utilization")
st.dataframe(df[["Operation", "Operators", "Unit Time", "Utilization %"]])

# ================= CAPACITY =================
st.header("🏭 Production Capacity")
c1, c2, c3, c4 = st.columns(4)
c1.metric("Daily", f"{daily_capacity:,.0f}")
c2.metric("Weekly", f"{weekly_capacity:,.0f}")
c3.metric("Monthly", f"{monthly_capacity:,.0f}")
c4.metric("Yearly", f"{yearly_capacity:,.0f}")
st.metric("💰 Weekly Profit", f"${weekly_profit:,.0f}")
st.metric("💰 Monthly Profit", f"${monthly_profit:,.0f}")
st.metric("💰 Yearly Profit", f"${yearly_profit:,.0f}")

# ================= FLOW CHART =================
st.header("🔄 Process Flow")
dot = Digraph()
for _, r in df.iterrows():
    if r["Operation"] in bottleneck_ops:
        color = "mistyrose"
    elif r["Soak Time"] > 0:
        color = "lightgreen"
    else:
        color = "white"
    label = f"{r['Operation']}\nUnit Time: {r['Unit Time']:.1f}s\nOperators: {r['Operators']}"
    dot.node(r["Operation"], label, style="filled", fillcolor=color)
for i in range(len(df)-1):
    dot.edge(df["Operation"][i], df["Operation"][i+1])
st.graphviz_chart(dot)

# ================= VSM =================
st.header("📊 Value Stream Map")
colors = ["crimson" if r["Operation"] in bottleneck_ops else "lightgreen" if r["Soak Time"]>0 else "lightskyblue" for _, r in df.iterrows()]
fig = px.bar(df, x="Operation", y="Unit Time", text="Unit Time", color=df["Operation"], color_discrete_sequence=colors, labels={"Unit Time": "Time per Unit (s)"})
fig.update_layout(title_text="Value Stream Map per Operation", title_x=0.5, showlegend=False)
st.plotly_chart(fig, use_container_width=True)

# ================= PARETO =================
st.header("📉 Pareto Loss")
pareto_df = df.sort_values("Unit Time", ascending=False)
colors_pareto = ["crimson" if r["Operation"] in bottleneck_ops else "lightgreen" if r["Soak Time"]>0 else "lightskyblue" for _, r in pareto_df.iterrows()]
fig2 = px.bar(pareto_df, x="Operation", y="Unit Time", text="Unit Time", color=pareto_df["Operation"], color_discrete_sequence=colors_pareto, labels={"Unit Time": "Time per Unit (s)"})
fig2.update_layout(title_text="Pareto: Time Loss by Operation", title_x=0.5, showlegend=False)
st.plotly_chart(fig2, use_container_width=True)

# ================= OPERATOR OPTIMIZATION =================
st.header("🤖 Operator Optimization")
for bn_op in bottleneck_ops:
    bn_row = df[df["Operation"] == bn_op].iloc[0]
    setup_u = bn_row["Setup per Unit"]
    cycle = bn_row["Cycle Time"]
    if takt_time > setup_u:
        required_unit_time = takt_time
        needed_ops = ceil(cycle / (required_unit_time - setup_u))
        if needed_ops > bn_row["Operators"]:
            st.error(f"Add operators at bottleneck {bn_op} → Needed: {needed_ops}")
        else:
            st.success(f"Current operators at bottleneck {bn_op} are sufficient")
    else:
        st.warning(f"⚠ Setup time too high at {bn_op} — reduce setup first (SMED).")

st.subheader("Remove Operators to Save Labor")
for _, r in df.iterrows():
    if r["Operation"] not in bottleneck_ops and r["Operators"] > 1:
        new_unit_time = r["Cycle Time"] / (r["Operators"]-1) + r["Setup per Unit"]
        if new_unit_time <= bottleneck_times[0]:
            st.info(f"Can remove 1 operator from {r['Operation']} without affecting output")

# ================= IMPROVEMENT RECOMMENDATIONS =================
st.header("💡 Improvement Recommendations")
for bn_op in bottleneck_ops:
    if df[df["Operation"]==bn_op]["Unit Time"].values[0] > takt_time:
        st.warning(f"Bottleneck {bn_op} slower than takt → demand not met")
st.info("🔧 Reduce setup time on high-setup operations (SMED)")
st.info("⚖ Balance operations so each cycle time is near takt time")
st.info("📈 Increase OEE to boost total capacity")
st.info("👥 Add parallel station at bottleneck if possible")
st.info("📦 Control WIP to reduce lead time and improve flow")

# ================= IMPROVEMENT SIMULATION =================
st.header("🚀 Improvement Simulation Engine")
setup_reduction = st.slider("Setup Time Reduction %", 0, 80, 0)
oee_gain = st.slider("OEE Improvement %", 0, 20, 0)
extra_shift = st.checkbox("Add Second Shift")
add_operator_bn = st.number_input("Add Operators at Bottleneck", 0, 10, 0)

df_sim = df.copy()
df_sim["Setup Time"] = df_sim["Setup Time"] * (1 - setup_reduction/100)
df_sim["Setup per Unit"] = df_sim["Setup Time"] / batch_size
for bn_op in bottleneck_ops:
    df_sim.loc[df_sim["Operation"]==bn_op, "Operators"] += add_operator_bn
df_sim["Effective Cycle"] = df_sim["Cycle Time"] / df_sim["Operators"]
df_sim["Unit Time"] = df_sim["Effective Cycle"] + df_sim["Setup per Unit"] + df_sim["Soak Time"]

new_bottleneck_time = df_sim["Unit Time"].max()
new_available_time = hours_per_day * 3600 * min(oee + oee_gain/100, 1)
new_daily_capacity = new_available_time / new_bottleneck_time
if extra_shift:
    new_daily_capacity *= 2
capacity_gain = new_daily_capacity - daily_capacity

st.write(f"📈 Capacity Gain from Improvements: **{capacity_gain:,.0f} units/day**")
new_actual_output = min(new_daily_capacity, daily_demand)
new_profit = new_actual_output * profit_per_unit
profit_gain = new_profit - daily_profit
st.write(f"💰 New Daily Profit: **${new_profit:,.0f}**")
st.write(f"📊 Profit Increase: **${profit_gain:,.0f} per day**")

# ================= DOWNLOAD SUMMARY =================
st.header("💾 Download Complete Summary")
df_summary = df.copy()
df_summary["Line Balance Efficiency %"] = balance_efficiency
df_summary["Utilization %"] = df["Utilization %"]
df_summary["Theoretical Min Operators"] = theoretical_min_ops
df_summary["Current Operators"] = current_ops
df_summary["Lead Time (Days)"] = lead_time_days
df_summary["Daily Labor Cost"] = daily_labor_cost
df_summary["OEE"] = oee
df_summary["Daily Capacity"] = daily_capacity
df_summary["Weekly Capacity"] = weekly_capacity
df_summary["Monthly Capacity"] = monthly_capacity
df_summary["Yearly Capacity"] = yearly_capacity
df_summary["Profit per Unit"] = profit_per_unit
df_summary["Daily Profit"] = daily_profit
df_summary["Weekly Profit"] = weekly_profit
df_summary["Monthly Profit"] = monthly_profit
df_summary["Yearly Profit"] = yearly_profit
df_summary["Bottlenecks"] = ", ".join(bottleneck_ops)
df_summary["Bottleneck Time"] = bottleneck_times[0]
df_summary["Total Cost/Unit"] = total_cost_per_unit
df_summary["Material Cost/Unit"] = material_cost

lost_capacity = max(0, daily_demand - daily_capacity)
lost_profit = lost_capacity * profit_per_unit
st.metric("🚨 Profit Lost Due to Bottleneck", f"${lost_profit:,.0f} / day")
labor_util = (actual_output / daily_capacity * 100) if daily_capacity > 0 else 0
st.metric("👷 Labor Utilization", f"{labor_util:.1f}%")

csv = df_summary.to_csv(index=False).encode('utf-8')
st.download_button("Download CSV Summary", csv, "production_summary.csv", "text/csv")
