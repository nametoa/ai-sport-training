#!/usr/bin/env python3
"""COROS Training Dashboard – Streamlit app."""
from __future__ import annotations

import json
import math
from datetime import datetime, timedelta, date
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ──────────────────────────────────────────────
# Paths & constants
# ──────────────────────────────────────────────
DATA_DIR = Path(__file__).parent / "data"
PLANS_DIR = Path(__file__).parent / "training_plans"

SPORT_TYPE_MAP = {
    100: ("🏃", "跑步"),
    102: ("🏔️", "越野跑"),
    200: ("🚴", "骑行"),
    402: ("🏋️", "力量训练"),
    401: ("🏋️", "力量训练"),
    300: ("🏊", "游泳"),
    10100: ("🚶", "健步"),
    10300: ("🧘", "瑜伽"),
}

PACE_ZONE_LABELS = ["E 轻松", "M 马拉松", "T 乳酸阈", "I 间歇", "R 重复", "其他跑", "其他运动"]
HR_ZONE_LABELS = ["Zone 1", "Zone 2", "Zone 3", "Zone 4", "Zone 5"]

PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font_color="#fafafa",
    margin=dict(l=40, r=20, t=30, b=30),
    legend=dict(orientation="h", y=-0.15),
)


# ──────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────
@st.cache_data(ttl=60)
def load_json(name: str):
    p = DATA_DIR / name
    if not p.exists():
        return None
    with open(p, "r", encoding="utf-8") as f:
        return json.load(f)


def fmt_pace(seconds_per_km: float) -> str:
    if not seconds_per_km or seconds_per_km <= 0:
        return "--"
    m = int(seconds_per_km) // 60
    s = int(seconds_per_km) % 60
    return f"{m}'{s:02d}\""


def fmt_duration(seconds: int) -> str:
    if not seconds or seconds <= 0:
        return "--"
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


def fmt_distance(meters: float) -> str:
    if not meters or meters <= 0:
        return "--"
    km = meters / 1000
    if km >= 10:
        return f"{km:.1f}km"
    return f"{km:.2f}km"


def fmt_date(d: int) -> str:
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def parse_date(d: int) -> date:
    s = str(d)
    return date(int(s[:4]), int(s[4:6]), int(s[6:]))


def sport_icon(sport_type: int) -> str:
    return SPORT_TYPE_MAP.get(sport_type, ("🏅", "其他"))[0]


def sport_name(sport_type: int) -> str:
    return SPORT_TYPE_MAP.get(sport_type, ("🏅", "其他"))[1]


def tl_ratio_state_text(state: int) -> tuple[str, str]:
    mapping = {
        1: ("严重不足", "🔴"),
        2: ("不足", "🟠"),
        3: ("维持", "🟡"),
        4: ("高效", "🟢"),
        5: ("过度", "🔴"),
    }
    return mapping.get(state, ("未知", "⚪"))


def fatigue_state_text(state: int) -> tuple[str, str]:
    mapping = {
        1: ("非常轻松", "🟢"),
        2: ("轻松", "🟢"),
        3: ("适中", "🟡"),
        4: ("疲劳", "🟠"),
        5: ("非常疲劳", "🔴"),
    }
    return mapping.get(state, ("未知", "⚪"))


# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(page_title="COROS 训练仪表板", page_icon="🏃", layout="wide")
st.markdown(
    "<style>"
    ".block-container{padding-top:1rem;padding-bottom:0}"
    "div[data-testid='stMetric']{background:#1a1f2e;padding:12px 16px;border-radius:8px}"
    ".stTabs [data-baseweb='tab-list']{gap:8px}"
    "</style>",
    unsafe_allow_html=True,
)

# ──────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────
activities_raw = load_json("activities.json") or []
analyse_raw = load_json("analyse.json") or {}
dashboard_raw = load_json("dashboard.json") or {}

if not activities_raw:
    st.error("未找到数据文件，请先运行 `python fetch_coros_data.py`")
    st.stop()

day_list = analyse_raw.get("dayList", [])
summary_info_analyse = analyse_raw.get("summaryInfo", {})
sport_statistic = analyse_raw.get("sportStatistic", [])
week_list = analyse_raw.get("weekList", [])
tl_intensity = analyse_raw.get("tlIntensity", {})
t7day_list = analyse_raw.get("t7dayList", [])

dash_summary = dashboard_raw.get("summaryInfo", {})
dash_current_week = dashboard_raw.get("currentWeekRecord", {})
dash_sport_data = dashboard_raw.get("sportDataList", [])
dash_detail_list = dashboard_raw.get("detailList", [])
dash_target_list = dashboard_raw.get("targetList", [])


# ──────────────────────────────────────────────
# Tabs
# ──────────────────────────────────────────────
tab_dashboard, tab_analysis, tab_activities, tab_plan = st.tabs(
    ["📊 仪表板", "📈 数据分析", "📋 活动列表", "📅 训练计划"]
)

# ═══════════════════════════════════════════════
# TAB 1 – Dashboard
# ═══════════════════════════════════════════════
with tab_dashboard:
    # Row 1: headline metrics
    latest_day = day_list[-1] if day_list else {}
    vo2max = latest_day.get("vo2max") or 0
    for d in reversed(day_list):
        if d.get("vo2max"):
            vo2max = d["vo2max"]
            break
    stamina = latest_day.get("staminaLevel") or 0
    for d in reversed(day_list):
        if d.get("staminaLevel"):
            stamina = d["staminaLevel"]
            break
    lthr = 0
    ltsp = 0
    for d in reversed(day_list):
        if d.get("lthr"):
            lthr = d["lthr"]
            ltsp = d.get("ltsp", 0)
            break

    tl_ratio = dash_summary.get("trainingLoadRatio", 0)
    tl_ratio_st = dash_summary.get("trainingLoadRatioState", 0)
    tl_text, tl_emoji = tl_ratio_state_text(tl_ratio_st)
    tired_state = dash_summary.get("tiredRateNewState", 0)
    tired_text, tired_emoji = fatigue_state_text(tired_state)

    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("VO2max", f"{vo2max}")
    c2.metric("跑步能力", f"{stamina}")
    c3.metric("训练负荷比", f"{tl_ratio*100:.0f}%", f"{tl_emoji} {tl_text}")
    c4.metric("疲劳状态", f"{tired_text}", f"ATI {dash_summary.get('ati','--')} / CTI {dash_summary.get('cti','--')}")
    c5.metric("乳酸阈心率", f"{lthr} bpm")
    c6.metric("乳酸阈配速", fmt_pace(ltsp))

    st.divider()

    # Row 2: 7-day load chart + recent activities + this week summary
    col_load, col_recent, col_week = st.columns([1.2, 2, 1.2])

    with col_load:
        st.subheader("7 天训练负荷")
        if dash_detail_list:
            df_detail = pd.DataFrame(dash_detail_list)
            df_detail["date_str"] = df_detail["happenDay"].apply(fmt_date)
            fig = go.Figure()
            fig.add_bar(
                x=df_detail["date_str"],
                y=df_detail["trainingLoad"],
                marker_color="#00d4aa",
                name="训练负荷",
            )
            if "trainingLoadTarget" in df_detail.columns:
                fig.add_scatter(
                    x=df_detail["date_str"],
                    y=df_detail["trainingLoadTarget"],
                    mode="lines+markers",
                    line=dict(color="#ff6b6b", dash="dash"),
                    name="目标",
                )
            fig.update_layout(**PLOTLY_LAYOUT, height=250, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

    with col_recent:
        st.subheader("最近运动")
        recent = dash_sport_data[:7] if dash_sport_data else activities_raw[:7]
        rows = []
        for a in recent:
            rows.append({
                "日期": fmt_date(a.get("happenDay", a.get("date", 0))),
                "类型": sport_icon(a.get("sportType", 0)),
                "名称": a.get("name", sport_name(a.get("sportType", 0))),
                "距离": fmt_distance(a.get("distance", 0)),
                "时间": fmt_duration(a.get("duration", a.get("totalTime", 0))),
                "心率": a.get("avgHeartRate", a.get("avgHr", "--")),
                "负荷": a.get("trainingLoad", "--"),
            })
        if rows:
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True, height=290)

    with col_week:
        st.subheader("本周汇总")
        dist_rec = dash_current_week.get("distanceRecord", {})
        dur_rec = dash_current_week.get("durationRecord", {})
        tl_rec = dash_current_week.get("tlRecord", {})
        st.metric("距离", fmt_distance(dist_rec.get("totalValue", 0)),
                  f"目标 {fmt_distance(dist_rec.get('totalTarget', 0))}  ({dist_rec.get('percentage', 0):.0f}%)")
        st.metric("时间", fmt_duration(int(dur_rec.get("totalValue", 0))),
                  f"目标 {fmt_duration(int(dur_rec.get('totalTarget', 0)))}  ({dur_rec.get('percentage', 0):.0f}%)")
        st.metric("训练负荷", tl_rec.get("totalValue", 0),
                  f"目标 {tl_rec.get('totalTarget', 0)}  ({tl_rec.get('percentage', 0):.0f}%)")

    st.divider()

    # Row 3: HRV + Resting HR + Personal records
    col_hrv, col_rhr, col_records = st.columns(3)

    with col_hrv:
        st.subheader("HRV 评估")
        hrv_vals = [d.get("avgSleepHrv") for d in day_list if d.get("avgSleepHrv")]
        if hrv_vals:
            latest_hrv = hrv_vals[-1]
            base_hrv = [d.get("sleepHrvBase") for d in day_list if d.get("sleepHrvBase")]
            base = base_hrv[-1] if base_hrv else 0
            st.metric("最近 HRV", f"{latest_hrv} ms", f"基线 {base} ms")
            df_hrv = pd.DataFrame([
                {"日期": fmt_date(d["happenDay"]), "HRV": d["avgSleepHrv"]}
                for d in day_list if d.get("avgSleepHrv")
            ])
            fig = px.line(df_hrv, x="日期", y="HRV", height=200)
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_traces(line_color="#a78bfa")
            st.plotly_chart(fig, use_container_width=True)

    with col_rhr:
        st.subheader("静息心率")
        rhr_vals = [(d["happenDay"], d["rhr"]) for d in day_list if d.get("rhr")]
        if rhr_vals:
            latest_rhr = rhr_vals[-1][1]
            min_rhr = min(v for _, v in rhr_vals)
            st.metric("最近 RHR", f"{latest_rhr} bpm", f"最低 {min_rhr} bpm")
            df_rhr = pd.DataFrame([
                {"日期": fmt_date(hd), "RHR": rhr} for hd, rhr in rhr_vals
            ])
            fig = px.line(df_rhr, x="日期", y="RHR", height=200)
            fig.update_layout(**PLOTLY_LAYOUT)
            fig.update_traces(line_color="#f87171")
            st.plotly_chart(fig, use_container_width=True)

    with col_records:
        st.subheader("运动类型统计")
        if sport_statistic:
            rows = []
            for s in sport_statistic:
                st_type = s.get("sportType", 0)
                if st_type == 65535:
                    continue
                rows.append({
                    "类型": sport_name(st_type),
                    "次数": s.get("count", 0),
                    "距离": fmt_distance(s.get("distance", 0)),
                    "时间": fmt_duration(s.get("duration", 0)),
                    "负荷": s.get("trainingLoad", 0),
                })
            if rows:
                st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)


# ═══════════════════════════════════════════════
# TAB 2 – Data Analysis
# ═══════════════════════════════════════════════
with tab_analysis:
    if not day_list:
        st.warning("无分析数据")
    else:
        df_days = pd.DataFrame(day_list)
        df_days["date_str"] = df_days["happenDay"].apply(fmt_date)

        # Row 1: Training load trend + VO2max trend
        col_tl, col_vo2 = st.columns(2)

        with col_tl:
            st.subheader("每日训练负荷")
            fig = go.Figure()
            fig.add_bar(x=df_days["date_str"], y=df_days["trainingLoad"],
                        marker_color="#00d4aa", name="训练负荷")
            if "recomendTlMax" in df_days.columns:
                fig.add_scatter(x=df_days["date_str"], y=df_days["recomendTlMax"],
                                mode="lines", line=dict(color="rgba(255,107,107,0.4)", dash="dot"),
                                name="建议上限")
                fig.add_scatter(x=df_days["date_str"], y=df_days["recomendTlMin"],
                                mode="lines", line=dict(color="rgba(107,203,119,0.4)", dash="dot"),
                                name="建议下限")
            fig.update_layout(**PLOTLY_LAYOUT, height=300)
            st.plotly_chart(fig, use_container_width=True)

        with col_vo2:
            st.subheader("最大摄氧量 (VO2max)")
            vo2_data = df_days[df_days["vo2max"] > 0]
            if not vo2_data.empty:
                fig = px.line(vo2_data, x="date_str", y="vo2max", height=300,
                              markers=True)
                fig.update_traces(line_color="#60a5fa")
                fig.update_layout(**PLOTLY_LAYOUT, yaxis_title="VO2max")
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("无 VO2max 数据")

        # Row 2: RHR + 7d/28d load trends
        col_rhr2, col_load2 = st.columns(2)

        with col_rhr2:
            st.subheader("静息心率趋势")
            rhr_data = df_days[df_days["rhr"] > 0] if "rhr" in df_days.columns else pd.DataFrame()
            if not rhr_data.empty:
                fig = go.Figure()
                fig.add_scatter(x=rhr_data["date_str"], y=rhr_data["rhr"],
                                mode="lines+markers", line_color="#f87171", name="RHR")
                if "testRhr" in rhr_data.columns:
                    test_rhr = rhr_data[rhr_data["testRhr"] > 0]
                    if not test_rhr.empty:
                        fig.add_scatter(x=test_rhr["date_str"], y=test_rhr["testRhr"],
                                        mode="lines", line=dict(color="#fbbf24", dash="dash"),
                                        name="测试RHR")
                fig.update_layout(**PLOTLY_LAYOUT, height=300)
                st.plotly_chart(fig, use_container_width=True)

        with col_load2:
            st.subheader("7天 / 28天 训练负荷")
            fig = go.Figure()
            fig.add_scatter(x=df_days["date_str"], y=df_days["t7d"],
                            mode="lines", line_color="#00d4aa", name="7天负荷")
            fig.add_scatter(x=df_days["date_str"], y=df_days["t28d"],
                            mode="lines", line_color="#60a5fa", name="28天负荷")
            fig.update_layout(**PLOTLY_LAYOUT, height=300)
            st.plotly_chart(fig, use_container_width=True)

        # Row 3: Weekly volume + intensity distribution
        col_week_vol, col_intensity = st.columns(2)

        with col_week_vol:
            st.subheader("周训练量")
            analyse_record = analyse_raw.get("record", {})
            dist_record = analyse_record.get("distanceRecord", {})
            dist_weeks = dist_record.get("detailList", [])
            if dist_weeks:
                df_w = pd.DataFrame(dist_weeks)
                df_w["week_label"] = df_w["firstDayOfWeek"].apply(
                    lambda x: fmt_date(x) if x else ""
                )
                df_w["km"] = df_w["value"] / 1000
                fig = go.Figure()
                fig.add_bar(x=df_w["week_label"], y=df_w["km"],
                            marker_color="#00d4aa", name="距离(km)")
                fig.update_layout(**PLOTLY_LAYOUT, height=300, yaxis_title="km")
                st.plotly_chart(fig, use_container_width=True)

        with col_intensity:
            st.subheader("4 周强度分布")
            tl_detail = tl_intensity.get("detailList", [])
            if tl_detail:
                df_tl = pd.DataFrame(tl_detail)
                df_tl["period"] = df_tl.apply(
                    lambda r: f"{fmt_date(r['firstDayOfWeek'])}~{fmt_date(r['lastDayInWeek'])}",
                    axis=1,
                )
                fig = go.Figure()
                fig.add_bar(x=df_tl["period"], y=df_tl["periodLowValue"],
                            name="低强度", marker_color="#22c55e")
                fig.add_bar(x=df_tl["period"], y=df_tl["periodMediumValue"],
                            name="中强度", marker_color="#eab308")
                fig.add_bar(x=df_tl["period"], y=df_tl["periodHighValue"],
                            name="高强度", marker_color="#ef4444")
                fig.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=300)
                st.plotly_chart(fig, use_container_width=True)

        # Row 4: Pace zone + HR zone distribution
        col_pace, col_hr = st.columns(2)

        with col_pace:
            st.subheader("配速区间分布")
            dis_area = summary_info_analyse.get("disAreaList", [])
            if dis_area:
                labels = PACE_ZONE_LABELS[: len(dis_area)]
                values = [a["ratio"] for a in dis_area]
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    hole=0.45,
                    marker_colors=["#22c55e", "#3b82f6", "#eab308", "#f97316", "#ef4444", "#8b5cf6", "#6b7280"],
                ))
                fig.update_layout(**PLOTLY_LAYOUT, height=300)
                st.plotly_chart(fig, use_container_width=True)

        with col_hr:
            st.subheader("心率区间分布")
            hr_area = summary_info_analyse.get("hrDisAreaList", [])
            if hr_area:
                labels = HR_ZONE_LABELS[: len(hr_area)]
                values = [a["ratio"] for a in hr_area]
                fig = go.Figure(go.Pie(
                    labels=labels, values=values,
                    hole=0.45,
                    marker_colors=["#94a3b8", "#22c55e", "#eab308", "#f97316", "#ef4444"],
                ))
                fig.update_layout(**PLOTLY_LAYOUT, height=300)
                st.plotly_chart(fig, use_container_width=True)

        # Row 5: Fatigue rate + Training load ratio
        col_fat, col_ratio = st.columns(2)

        with col_fat:
            st.subheader("疲劳趋势 (TIB)")
            if "tiredRateNew" in df_days.columns:
                fig = go.Figure()
                colors = df_days["tiredRateNew"].apply(
                    lambda v: "#ef4444" if v > 30 else "#eab308" if v > 10 else "#22c55e"
                ).tolist()
                fig.add_bar(x=df_days["date_str"], y=df_days["tiredRateNew"],
                            marker_color=colors, name="疲劳指数")
                fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
                fig.update_layout(**PLOTLY_LAYOUT, height=280)
                st.plotly_chart(fig, use_container_width=True)

        with col_ratio:
            st.subheader("训练负荷比趋势")
            if "trainingLoadRatio" in df_days.columns:
                ratio_data = df_days[df_days["trainingLoadRatio"] > 0]
                if not ratio_data.empty:
                    fig = go.Figure()
                    fig.add_scatter(x=ratio_data["date_str"], y=ratio_data["trainingLoadRatio"],
                                    mode="lines+markers", line_color="#a78bfa", name="负荷比")
                    fig.add_hline(y=1.0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
                    fig.add_hrect(y0=0.8, y1=1.5, fillcolor="rgba(34,197,94,0.1)",
                                  line_width=0, annotation_text="最佳区间")
                    fig.update_layout(**PLOTLY_LAYOUT, height=280)
                    st.plotly_chart(fig, use_container_width=True)


# ═══════════════════════════════════════════════
# TAB 3 – Activity List
# ═══════════════════════════════════════════════
with tab_activities:
    st.subheader(f"活动列表 ({len(activities_raw)} 条记录)")

    # Filters
    fc1, fc2, fc3 = st.columns([1, 1, 2])
    all_sport_types = sorted({a.get("sportType", 0) for a in activities_raw})
    type_options = ["全部"] + [f"{sport_icon(t)} {sport_name(t)}" for t in all_sport_types]
    type_map = {f"{sport_icon(t)} {sport_name(t)}": t for t in all_sport_types}

    with fc1:
        selected_type = st.selectbox("运动类型", type_options)
    with fc2:
        sort_col = st.selectbox("排序", ["日期", "距离", "时间", "心率", "训练负荷"])

    filtered = activities_raw
    if selected_type != "全部":
        target_type = type_map.get(selected_type)
        if target_type is not None:
            filtered = [a for a in filtered if a.get("sportType") == target_type]

    sort_keys = {
        "日期": lambda a: a.get("startTime", 0),
        "距离": lambda a: a.get("distance", 0),
        "时间": lambda a: a.get("totalTime", 0),
        "心率": lambda a: a.get("avgHr", 0),
        "训练负荷": lambda a: a.get("trainingLoad", 0),
    }
    filtered.sort(key=sort_keys.get(sort_col, sort_keys["日期"]), reverse=True)

    # Pagination
    page_size = 30
    total_pages = max(1, math.ceil(len(filtered) / page_size))
    with fc3:
        page_num = st.number_input("页码", 1, total_pages, 1, key="act_page")
    start = (page_num - 1) * page_size
    page_items = filtered[start : start + page_size]

    rows = []
    for a in page_items:
        pace_val = a.get("adjustedPace") or a.get("avgSpeed", 0)
        rows.append({
            "日期": fmt_date(a.get("date", 0)),
            "类型": sport_icon(a.get("sportType", 0)),
            "名称": a.get("name", ""),
            "距离": fmt_distance(a.get("distance", 0)),
            "时间": fmt_duration(a.get("totalTime", 0)),
            "配速": fmt_pace(pace_val) if a.get("sportType", 0) in (100, 102) else "--",
            "平均心率": a.get("avgHr", "--"),
            "训练负荷": a.get("trainingLoad", "--"),
        })
    if rows:
        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
            height=min(len(rows) * 38 + 40, 900),
        )
    st.caption(f"第 {page_num}/{total_pages} 页 · 共 {len(filtered)} 条")


# ═══════════════════════════════════════════════
# TAB 4 – Training Plan
# ═══════════════════════════════════════════════
with tab_plan:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)

    # ── Sidebar-like config in expander ──
    with st.expander("⚙️ 计划配置", expanded=True):
        pc1, pc2, pc3 = st.columns(3)
        with pc1:
            plan_name = st.text_input("计划名称", "RHR 50 → 45 Experiment")
            plan_type = st.selectbox("计划类型", ["Zone 2 + HIIT", "马拉松备赛", "越野备赛", "自定义"])
        with pc2:
            plan_start = st.date_input("开始日期", date(2026, 2, 18))
            plan_weeks = st.number_input("周数", 4, 24, 8)
        with pc3:
            weekly_z2_target = st.number_input("每周 Z2 目标 (分钟)", 60, 600, 200)
            hiit_per_week = st.number_input("每周 HIIT 次数", 0, 5, 1)
            deload_every = st.number_input("每几周减量", 3, 6, 4)

    # ── Generate plan ──
    def generate_plan() -> list[dict]:
        weeks = []
        for w in range(plan_weeks):
            week_start = plan_start + timedelta(weeks=w)
            week_end = week_start + timedelta(days=6)

            is_last = w == plan_weeks - 1
            is_deload = (w + 1) % deload_every == 0 and not is_last
            is_taper = is_last

            progression = 1.0 + (w / plan_weeks) * 0.4
            if is_deload:
                factor = 0.6
                label = "DELOAD"
            elif is_taper:
                factor = 0.5
                label = "TAPER"
            else:
                factor = progression
                label = ""

            target_min = int(weekly_z2_target * factor * 0.9)
            target_max = int(weekly_z2_target * factor * 1.1)
            target_min = max(target_min, 60)

            days = []
            for d_offset in range(7):
                day_date = week_start + timedelta(days=d_offset)
                days.append({
                    "date": day_date.isoformat(),
                    "day_name": ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][day_date.weekday()],
                    "sessions": [],
                    "actual_z2_min": 0,
                    "actual_hiit_min": 0,
                })

            weeks.append({
                "week_num": w + 1,
                "start": week_start.isoformat(),
                "end": week_end.isoformat(),
                "label": label,
                "target_min": target_min,
                "target_max": target_max,
                "hiit_target": hiit_per_week if not is_taper else 0,
                "days": days,
                "actual_z2_total": 0,
                "actual_hiit_count": 0,
            })
        return weeks

    # Match actual activities to plan weeks
    def fill_actual_data(weeks: list[dict]):
        act_by_date = {}
        for a in activities_raw:
            d = a.get("date", 0)
            if d:
                ds = parse_date(d).isoformat()
                act_by_date.setdefault(ds, []).append(a)

        for week in weeks:
            z2_total = 0
            hiit_count = 0
            for day in week["days"]:
                day_acts = act_by_date.get(day["date"], [])
                z2_min = 0
                hiit_min = 0
                for a in day_acts:
                    duration_min = (a.get("totalTime", 0) or 0) / 60
                    avg_hr = a.get("avgHr", 0) or 0
                    sport = a.get("sportType", 0)
                    if sport in (100, 102) and avg_hr > 0:
                        if avg_hr < lthr * 0.85:
                            z2_min += duration_min
                        elif avg_hr > lthr * 0.95:
                            hiit_min += duration_min
                            hiit_count += 1
                        else:
                            z2_min += duration_min * 0.5
                    elif sport == 402:
                        pass
                    elif sport == 200:
                        z2_min += duration_min * 0.7

                day["actual_z2_min"] = round(z2_min)
                day["actual_hiit_min"] = round(hiit_min)
                day["sessions"] = [
                    {"type": a.get("name", ""), "duration": a.get("totalTime", 0)}
                    for a in day_acts
                ]
                z2_total += z2_min

            week["actual_z2_total"] = round(z2_total)
            week["actual_hiit_count"] = hiit_count

    plan_data = generate_plan()
    fill_actual_data(plan_data)

    # ── Summary metrics ──
    total_z2_actual = sum(w["actual_z2_total"] for w in plan_data)
    total_z2_target = sum((w["target_min"] + w["target_max"]) // 2 for w in plan_data)
    weeks_done = sum(1 for w in plan_data if date.fromisoformat(w["end"]) < date.today())
    hiit_weeks_done = sum(1 for w in plan_data
                          if date.fromisoformat(w["end"]) < date.today()
                          and w["actual_hiit_count"] >= w["hiit_target"] > 0)
    current_week_idx = 0
    for i, w in enumerate(plan_data):
        ws = date.fromisoformat(w["start"])
        we = date.fromisoformat(w["end"])
        if ws <= date.today() <= we:
            current_week_idx = i + 1
            break

    st.markdown(f"### {plan_name}")
    st.caption(
        f"{plan_weeks}-week {plan_type} plan · "
        f"{plan_start.strftime('%b %d')} — {(plan_start + timedelta(weeks=plan_weeks) - timedelta(days=1)).strftime('%b %d, %Y')}"
    )

    mc1, mc2, mc3, mc4, mc5 = st.columns(5)
    mc1.metric("TOTAL Z2", f"{total_z2_actual}m")
    mc2.metric("TARGET", f"{total_z2_target}m")
    mc3.metric("WEEKS DONE", f"{weeks_done}/{plan_weeks}")
    mc4.metric("HIIT WEEKS", f"{hiit_weeks_done}/{max(1, weeks_done)}")
    mc5.metric("WEEK", f"{current_week_idx or 1} of {plan_weeks}")

    st.markdown(
        '<div style="display:flex;gap:16px;margin:8px 0">'
        '<span>🟩 Zone 2</span>'
        '<span>🟥 HIIT</span>'
        '<span>⬜ Today</span>'
        '</div>',
        unsafe_allow_html=True,
    )

    # ── Weekly calendar ──
    today_str = date.today().isoformat()

    for week in plan_data:
        w_start = date.fromisoformat(week["start"])
        w_end = date.fromisoformat(week["end"])
        is_current = w_start <= date.today() <= w_end
        is_past = w_end < date.today()

        label_suffix = ""
        if week["label"]:
            label_suffix = f'  <span style="color:#f97316;font-size:0.8em">{week["label"]}</span>'

        border = "border:2px solid #3b82f6;border-radius:8px;" if is_current else ""
        bg = "background:#1a1f2e;" if not is_current else "background:#1e293b;"

        week_html = f'<div style="{bg}{border}padding:12px;margin-bottom:8px;border-radius:8px">'
        week_html += f'<div style="display:flex;align-items:center;justify-content:space-between">'
        week_html += f'<div>'
        week_html += f'<strong>Week {week["week_num"]}</strong>{label_suffix}<br>'
        week_html += f'<span style="color:#94a3b8;font-size:0.8em">{w_start.strftime("%b %d")}–{w_end.strftime("%b %d")}</span>'
        week_html += '</div>'

        # Day cells
        week_html += '<div style="display:flex;gap:4px;flex:1;margin:0 16px">'
        for day in week["days"]:
            d_date = date.fromisoformat(day["date"])
            is_today = day["date"] == today_str
            z2 = day["actual_z2_min"]
            hiit = day["actual_hiit_min"]

            cell_border = "border:2px solid #fff;" if is_today else "border:1px solid #374151;"
            if z2 > 0 and hiit > 0:
                cell_bg = "background:linear-gradient(135deg,#22c55e 50%,#ef4444 50%);"
                cell_text = f"{z2}m"
            elif z2 > 0:
                cell_bg = "background:#22c55e;"
                cell_text = f"{z2}m"
            elif hiit > 0:
                cell_bg = "background:#ef4444;"
                cell_text = f"{hiit}m"
            else:
                cell_bg = "background:#374151;"
                cell_text = day["day_name"][:1]

            week_html += (
                f'<div style="{cell_bg}{cell_border}border-radius:6px;'
                f'width:60px;height:40px;display:flex;align-items:center;'
                f'justify-content:center;font-size:0.75em;color:#fff">'
                f'{cell_text}</div>'
            )
        week_html += '</div>'

        # Right side: actual / target
        actual = week["actual_z2_total"]
        tgt_min = week["target_min"]
        tgt_max = week["target_max"]
        pct = min(actual / ((tgt_min + tgt_max) / 2) * 100, 100) if tgt_min > 0 else 0
        status = "upcoming" if not is_past and not is_current else ""

        week_html += '<div style="text-align:right;min-width:140px">'
        week_html += f'<strong>{actual}m</strong> / {tgt_min}–{tgt_max}m<br>'

        bar_color = "#22c55e" if pct >= 80 else "#3b82f6" if pct > 0 else "#374151"
        week_html += (
            f'<div style="width:100%;background:#374151;border-radius:4px;height:6px;margin-top:4px">'
            f'<div style="width:{pct:.0f}%;background:{bar_color};height:100%;border-radius:4px"></div>'
            f'</div>'
        )

        if not is_past and not is_current:
            week_html += '<span style="color:#94a3b8;font-size:0.75em">upcoming</span>'
        elif is_current:
            z2_left = max(0, tgt_min - actual)
            hint = f"{z2_left}m Z2 left" if z2_left > 0 else "target reached!"
            if week["actual_hiit_count"] < week["hiit_target"]:
                hint += " · need HIIT"
            week_html += f'<span style="color:#3b82f6;font-size:0.75em">{hint}</span>'

        week_html += '</div></div></div>'
        st.markdown(week_html, unsafe_allow_html=True)

    # ── Save / Export ──
    st.divider()
    col_save, col_export = st.columns(2)

    with col_save:
        if st.button("💾 保存计划"):
            plan_file = PLANS_DIR / f"{plan_name.replace(' ', '_')}_{plan_start.isoformat()}.json"
            plan_export = {
                "name": plan_name,
                "type": plan_type,
                "start": plan_start.isoformat(),
                "weeks": plan_weeks,
                "z2_target_per_week": weekly_z2_target,
                "hiit_per_week": hiit_per_week,
                "deload_every": deload_every,
                "plan_data": plan_data,
            }
            with open(plan_file, "w", encoding="utf-8") as f:
                json.dump(plan_export, f, ensure_ascii=False, indent=2, default=str)
            st.success(f"已保存: {plan_file.name}")

    with col_export:
        if st.button("📤 导出 COROS 训练计划"):
            coros_plan = {
                "planName": plan_name,
                "startDate": plan_start.isoformat(),
                "endDate": (plan_start + timedelta(weeks=plan_weeks) - timedelta(days=1)).isoformat(),
                "totalWeeks": plan_weeks,
                "weeks": [],
            }
            for week in plan_data:
                w_entry = {
                    "weekNum": week["week_num"],
                    "label": week["label"],
                    "targetMinutes": f"{week['target_min']}-{week['target_max']}",
                    "sessions": [],
                }
                day_idx = 0
                for day in week["days"]:
                    d_date = date.fromisoformat(day["date"])
                    weekday = d_date.weekday()

                    if plan_type == "Zone 2 + HIIT":
                        if weekday in (1, 3):  # Tue, Thu
                            z2_min = weekly_z2_target // 3
                            factor = 1.0 + (week["week_num"] - 1) / plan_weeks * 0.4
                            if week["label"] == "DELOAD":
                                factor = 0.6
                            elif week["label"] == "TAPER":
                                factor = 0.5
                            z2_min = int(z2_min * factor)
                            w_entry["sessions"].append({
                                "date": day["date"],
                                "dayName": day["day_name"],
                                "type": "Zone 2 有氧跑",
                                "targetMinutes": z2_min,
                                "targetHR": f"{int(lthr*0.65)}-{int(lthr*0.78)} bpm" if lthr else "Z2心率区间",
                                "description": f"轻松有氧跑 {z2_min}分钟，保持Zone 2心率",
                            })
                        elif weekday == 5:  # Sat
                            z2_min = int(weekly_z2_target * 0.4)
                            factor = 1.0 + (week["week_num"] - 1) / plan_weeks * 0.4
                            if week["label"] == "DELOAD":
                                factor = 0.6
                            elif week["label"] == "TAPER":
                                factor = 0.5
                            z2_min = int(z2_min * factor)
                            w_entry["sessions"].append({
                                "date": day["date"],
                                "dayName": day["day_name"],
                                "type": "Zone 2 长距离",
                                "targetMinutes": z2_min,
                                "targetHR": f"{int(lthr*0.65)}-{int(lthr*0.78)} bpm" if lthr else "Z2心率区间",
                                "description": f"长距离有氧 {z2_min}分钟",
                            })
                        elif weekday == 2 and week.get("hiit_target", 0) > 0:  # Wed
                            w_entry["sessions"].append({
                                "date": day["date"],
                                "dayName": day["day_name"],
                                "type": "HIIT 间歇训练",
                                "targetMinutes": 30,
                                "targetHR": f">{int(lthr*0.9)} bpm" if lthr else "Z4-Z5心率",
                                "description": "热身10min + 5x4min快/2min慢 + 冷身5min",
                            })
                    day_idx += 1
                coros_plan["weeks"].append(w_entry)

            plan_json = json.dumps(coros_plan, ensure_ascii=False, indent=2, default=str)
            st.download_button(
                "⬇️ 下载 COROS 训练计划 JSON",
                plan_json,
                file_name=f"coros_plan_{plan_start.isoformat()}.json",
                mime="application/json",
            )
            st.json(coros_plan)
