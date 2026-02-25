#!/usr/bin/env python3
"""COROS Training Dashboard – Streamlit app."""
from __future__ import annotations

import json
import math
import os
import sys
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
st.markdown('<meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0">', unsafe_allow_html=True)
st.markdown("""<style>
    .block-container { padding-top: 2.5rem; padding-bottom: 0; }
    header[data-testid="stHeader"] { background: #0e1117; }
    div[data-testid='stMetric'] {
        background: #1a1f2e; padding: 14px 18px; border-radius: 10px;
    }
    div[data-testid='stMetricLabel'] > div > div > p {
        font-size: 1rem !important; color: #e2e8f0 !important;
    }
    div[data-testid='stMetricValue'] > div {
        font-size: 1.8rem !important; font-weight: 700 !important;
    }
    div[data-testid='stMetricDelta'] > div {
        font-size: 0.85rem !important;
    }

    /* Tabs — cover all Streamlit versions */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0; background: #111827; border-radius: 10px; padding: 4px;
    }
    .stTabs [data-baseweb="tab-list"] button,
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"] {
        font-size: 1.05rem !important; font-weight: 600 !important;
        padding: 12px 28px !important; border-radius: 8px !important;
        color: #94a3b8 !important; border: none !important;
        background: transparent !important;
    }
    .stTabs [data-baseweb="tab-list"] button[aria-selected="true"],
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"][aria-selected="true"] {
        color: #00d4aa !important;
        background: rgba(0,212,170,0.12) !important;
    }
    .stTabs [data-baseweb="tab-list"] button:hover,
    .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"]:hover {
        color: #f1f5f9 !important;
        background: rgba(255,255,255,0.06) !important;
    }
    /* hide the default underline indicator */
    .stTabs [data-baseweb="tab-highlight"] {
        background-color: #00d4aa !important; height: 3px !important;
    }
    .stTabs [data-baseweb="tab-border"] {
        display: none;
    }

    .todo-done { text-decoration: line-through; color: #6b7280; }

    /* ── Mobile responsive ── */
    @media (max-width: 768px) {
        .block-container {
            padding-top: 1.5rem;
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        /* Stack all columns vertically on mobile */
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: 100% !important;
            flex: 0 0 100% !important;
            min-width: 100% !important;
        }
        /* Smaller metrics */
        div[data-testid='stMetric'] {
            padding: 10px 12px;
        }
        div[data-testid='stMetricValue'] > div {
            font-size: 1.3rem !important;
        }
        div[data-testid='stMetricLabel'] > div > div > p {
            font-size: 0.85rem !important;
        }
        div[data-testid='stMetricDelta'] > div {
            font-size: 0.75rem !important;
        }
        /* Tabs: scroll horizontally, smaller text */
        .stTabs [data-baseweb="tab-list"] {
            overflow-x: auto !important;
            -webkit-overflow-scrolling: touch;
            flex-wrap: nowrap !important;
            padding: 2px;
        }
        .stTabs [data-baseweb="tab-list"] button,
        .stTabs [data-baseweb="tab-list"] [data-baseweb="tab"] {
            font-size: 0.85rem !important;
            padding: 8px 14px !important;
            white-space: nowrap !important;
        }
        /* Tables: horizontal scroll */
        [data-testid="stDataFrame"] {
            overflow-x: auto !important;
        }
        /* Charts: limit overflow */
        .js-plotly-plot, .plotly {
            max-width: 100% !important;
            overflow-x: hidden !important;
        }
    }

    /* Slightly wider phones / small tablets */
    @media (min-width: 769px) and (max-width: 1024px) {
        [data-testid="stHorizontalBlock"] {
            flex-wrap: wrap !important;
        }
        [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
            width: 50% !important;
            flex: 0 0 50% !important;
            min-width: 50% !important;
        }
    }
</style>""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Auto-sync on startup (once per session)
# ──────────────────────────────────────────────
if "data_synced" not in st.session_state:
    try:
        coros_secrets = st.secrets.get("coros", {})
        if coros_secrets:
            os.environ.setdefault("COROS_ACCESS_TOKEN", str(coros_secrets.get("access_token", "")))
            os.environ.setdefault("COROS_USER_ID", str(coros_secrets.get("user_id", "")))
            os.environ.setdefault("COROS_COOKIE_WBKFRO", str(coros_secrets.get("cookie_wbkfro", "")))
            os.environ.setdefault("COROS_COOKIE_REGION", str(coros_secrets.get("cookie_region", "2")))
            os.environ.setdefault("COROS_BASE_URL", str(coros_secrets.get("base_url", "https://teamcnapi.coros.com")))
    except Exception:
        pass

    with st.spinner("正在同步 COROS 数据..."):
        try:
            import fetch_coros_data as fcd
            fcd.CONFIG["access_token"] = os.environ.get("COROS_ACCESS_TOKEN", "")
            _tok = fcd.CONFIG["access_token"]
            fcd.CONFIG["cookies"]["_c_WBKFRo"] = os.environ.get("COROS_COOKIE_WBKFRO", "")
            fcd.CONFIG["cookies"]["CPL-coros-token"] = _tok
            fcd.CONFIG["cookies"]["CPL-coros-region"] = os.environ.get("COROS_COOKIE_REGION", "2")
            fcd.CONFIG["user_id"] = os.environ.get("COROS_USER_ID", "")
            fcd.CONFIG["base_url"] = os.environ.get("COROS_BASE_URL", "https://teamcnapi.coros.com")

            if not _tok:
                st.warning("未配置 COROS 凭据，跳过同步")
            else:
                fcd.DATA_DIR.mkdir(parents=True, exist_ok=True)
                fcd.sync_activities()
                fcd.sync_analyse()
                fcd.sync_dashboard()
                fcd._save_meta(fcd._load_meta())
                st.toast("数据同步完成", icon="✅")
        except Exception as e:
            st.warning(f"同步异常: {e}，使用本地缓存")
    st.session_state.data_synced = True

# ──────────────────────────────────────────────
# Load data
# ──────────────────────────────────────────────
activities_raw = load_json("activities.json") or []
analyse_raw = load_json("analyse.json") or {}
dashboard_raw = load_json("dashboard.json") or {}

if not activities_raw:
    st.warning("暂无数据。如首次部署请在 Streamlit Cloud Secrets 中配置 COROS 凭据后刷新页面。")
    st.code("""
# .streamlit/secrets.toml (或 Streamlit Cloud → Settings → Secrets)
[coros]
access_token = "YOUR_COROS_ACCESS_TOKEN"
user_id = "YOUR_COROS_USER_ID"
cookie_wbkfro = "YOUR_COOKIE_VALUE"
cookie_region = "2"
    """.strip(), language="toml")
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
            st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True, height=290)

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
                st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


# ═══════════════════════════════════════════════
# TAB 2 – Data Analysis
# ═══════════════════════════════════════════════
with tab_analysis:
    if not day_list:
        st.warning("无分析数据")
    else:
        df_days = pd.DataFrame(day_list)
        df_days["date_str"] = df_days["happenDay"].apply(fmt_date)

        ncols = st.radio("每行图表数", [2, 3, 4], horizontal=True, index=0, key="analysis_cols")
        chart_h = {2: 320, 3: 280, 4: 240}[ncols]

        def _render_chart(fig):
            st.plotly_chart(fig, use_container_width=True)

        # ── chart builders (lazy list) ──
        def chart_training_load():
            st.markdown("**每日训练负荷**")
            fig = go.Figure()
            fig.add_bar(x=df_days["date_str"], y=df_days["trainingLoad"],
                        marker_color="#00d4aa", name="训练负荷")
            if "recomendTlMax" in df_days.columns:
                fig.add_scatter(x=df_days["date_str"], y=df_days["recomendTlMax"],
                                mode="lines", line=dict(color="rgba(255,107,107,0.4)", dash="dot"), name="建议上限")
                fig.add_scatter(x=df_days["date_str"], y=df_days["recomendTlMin"],
                                mode="lines", line=dict(color="rgba(107,203,119,0.4)", dash="dot"), name="建议下限")
            fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
            _render_chart(fig)

        def chart_vo2max():
            st.markdown("**最大摄氧量 (VO2max)**")
            vo2_data = df_days[df_days["vo2max"] > 0]
            if not vo2_data.empty:
                fig = px.line(vo2_data, x="date_str", y="vo2max", height=chart_h, markers=True)
                fig.update_traces(line_color="#60a5fa")
                fig.update_layout(**PLOTLY_LAYOUT, yaxis_title="VO2max")
                _render_chart(fig)
            else:
                st.info("无 VO2max 数据")

        def chart_rhr():
            st.markdown("**静息心率趋势**")
            rhr_data = df_days[df_days["rhr"] > 0] if "rhr" in df_days.columns else pd.DataFrame()
            if not rhr_data.empty:
                fig = go.Figure()
                fig.add_scatter(x=rhr_data["date_str"], y=rhr_data["rhr"],
                                mode="lines+markers", line_color="#f87171", name="RHR")
                if "testRhr" in rhr_data.columns:
                    test_rhr = rhr_data[rhr_data["testRhr"] > 0]
                    if not test_rhr.empty:
                        fig.add_scatter(x=test_rhr["date_str"], y=test_rhr["testRhr"],
                                        mode="lines", line=dict(color="#fbbf24", dash="dash"), name="测试RHR")
                fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
                _render_chart(fig)

        def chart_7d_28d():
            st.markdown("**7天 / 28天 训练负荷**")
            fig = go.Figure()
            fig.add_scatter(x=df_days["date_str"], y=df_days["t7d"], mode="lines", line_color="#00d4aa", name="7天负荷")
            fig.add_scatter(x=df_days["date_str"], y=df_days["t28d"], mode="lines", line_color="#60a5fa", name="28天负荷")
            fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
            _render_chart(fig)

        def chart_weekly_vol():
            st.markdown("**周训练量**")
            dist_weeks = analyse_raw.get("record", {}).get("distanceRecord", {}).get("detailList", [])
            if dist_weeks:
                df_w = pd.DataFrame(dist_weeks)
                df_w["week_label"] = df_w["firstDayOfWeek"].apply(lambda x: fmt_date(x) if x else "")
                df_w["km"] = df_w["value"] / 1000
                fig = go.Figure()
                fig.add_bar(x=df_w["week_label"], y=df_w["km"], marker_color="#00d4aa", name="距离(km)")
                fig.update_layout(**PLOTLY_LAYOUT, height=chart_h, yaxis_title="km")
                _render_chart(fig)

        def chart_intensity():
            st.markdown("**4 周强度分布**")
            tl_detail = tl_intensity.get("detailList", [])
            if tl_detail:
                df_tl = pd.DataFrame(tl_detail)
                df_tl["period"] = df_tl.apply(
                    lambda r: f"{fmt_date(r['firstDayOfWeek'])}~{fmt_date(r['lastDayInWeek'])}", axis=1)
                fig = go.Figure()
                fig.add_bar(x=df_tl["period"], y=df_tl["periodLowValue"], name="低强度", marker_color="#22c55e")
                fig.add_bar(x=df_tl["period"], y=df_tl["periodMediumValue"], name="中强度", marker_color="#eab308")
                fig.add_bar(x=df_tl["period"], y=df_tl["periodHighValue"], name="高强度", marker_color="#ef4444")
                fig.update_layout(**PLOTLY_LAYOUT, barmode="stack", height=chart_h)
                _render_chart(fig)

        def chart_pace_zone():
            st.markdown("**配速区间分布**")
            dis_area = summary_info_analyse.get("disAreaList", [])
            if dis_area:
                fig = go.Figure(go.Pie(
                    labels=PACE_ZONE_LABELS[:len(dis_area)], values=[a["ratio"] for a in dis_area], hole=0.45,
                    marker_colors=["#22c55e", "#3b82f6", "#eab308", "#f97316", "#ef4444", "#8b5cf6", "#6b7280"]))
                fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
                _render_chart(fig)

        def chart_hr_zone():
            st.markdown("**心率区间分布**")
            hr_area = summary_info_analyse.get("hrDisAreaList", [])
            if hr_area:
                fig = go.Figure(go.Pie(
                    labels=HR_ZONE_LABELS[:len(hr_area)], values=[a["ratio"] for a in hr_area], hole=0.45,
                    marker_colors=["#94a3b8", "#22c55e", "#eab308", "#f97316", "#ef4444"]))
                fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
                _render_chart(fig)

        def chart_fatigue():
            st.markdown("**疲劳趋势 (TIB)**")
            if "tiredRateNew" in df_days.columns:
                fig = go.Figure()
                colors = df_days["tiredRateNew"].apply(
                    lambda v: "#ef4444" if v > 30 else "#eab308" if v > 10 else "#22c55e").tolist()
                fig.add_bar(x=df_days["date_str"], y=df_days["tiredRateNew"], marker_color=colors, name="疲劳指数")
                fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
                fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
                _render_chart(fig)

        def chart_load_ratio():
            st.markdown("**训练负荷比趋势**")
            if "trainingLoadRatio" in df_days.columns:
                ratio_data = df_days[df_days["trainingLoadRatio"] > 0]
                if not ratio_data.empty:
                    fig = go.Figure()
                    fig.add_scatter(x=ratio_data["date_str"], y=ratio_data["trainingLoadRatio"],
                                    mode="lines+markers", line_color="#a78bfa", name="负荷比")
                    fig.add_hline(y=1.0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
                    fig.add_hrect(y0=0.8, y1=1.5, fillcolor="rgba(34,197,94,0.1)", line_width=0, annotation_text="最佳区间")
                    fig.update_layout(**PLOTLY_LAYOUT, height=chart_h)
                    _render_chart(fig)

        all_charts = [
            chart_training_load, chart_vo2max, chart_rhr, chart_7d_28d,
            chart_weekly_vol, chart_intensity, chart_pace_zone, chart_hr_zone,
            chart_fatigue, chart_load_ratio,
        ]

        for row_start in range(0, len(all_charts), ncols):
            row_charts = all_charts[row_start : row_start + ncols]
            cols = st.columns(ncols)
            for col, fn in zip(cols, row_charts):
                with col:
                    fn()


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
            width="stretch",
            hide_index=True,
            height=min(len(rows) * 38 + 40, 900),
        )
    st.caption(f"第 {page_num}/{total_pages} 页 · 共 {len(filtered)} 条")


# ═══════════════════════════════════════════════
# TAB 4 – Training Plan (Concurrent Training)
# ═══════════════════════════════════════════════
with tab_plan:
    PLANS_DIR.mkdir(parents=True, exist_ok=True)
    TODO_FILE = DATA_DIR / "plan_todo_state.json"

    def load_todo_state() -> dict:
        if TODO_FILE.exists():
            with open(TODO_FILE, "r") as f:
                return json.load(f)
        return {}

    def save_todo_state(state: dict):
        with open(TODO_FILE, "w") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)

    if "todo_state" not in st.session_state:
        st.session_state.todo_state = load_todo_state()

    # Auto-complete days that have actual COROS activity data
    act_dates_with_data = set()
    for a in activities_raw:
        d = a.get("date", 0)
        if d:
            act_dates_with_data.add(parse_date(d).isoformat())

    def auto_sync_todo(phases):
        changed = False
        for phase in phases:
            for week in phase["weeks"]:
                for day in week["days"]:
                    dd = day["date"]
                    if dd in act_dates_with_data and not st.session_state.todo_state.get(dd, False):
                        st.session_state.todo_state[dd] = True
                        changed = True
        if changed:
            save_todo_state(st.session_state.todo_state)

    # ── Concrete concurrent training plan ──
    RACE_A = {"name": "九华山南北穿越", "date": "2026-03-08", "dist": "40km", "elev": "4000m"}
    RACE_B = {"name": "无锡马拉松", "date": "2026-03-22", "dist": "全马", "goal": "Sub-3"}

    PLAN_PHASES = [
        {
            "name": "九华山赛前减量",
            "tag": "TAPER-A",
            "weeks": [
                {
                    "label": "减量周",
                    "dates": ("2026-02-24", "2026-03-02"),
                    "target_km": "20-25km",
                    "target_tl": "150-200",
                    "days": [
                        {"date": "2026-02-24", "wd": "周一", "am": "", "noon": "力量：硬拉3x3+卧推3x5（减量40%）", "pm": "休息", "tl": 15, "type": "strength"},
                        {"date": "2026-02-25", "wd": "周二", "am": "", "noon": "", "pm": "轻松跑 6km Z2（HR<145）", "tl": 35, "type": "easy_run"},
                        {"date": "2026-02-26", "wd": "周三", "am": "", "noon": "力量：深蹲3x3+腹肌（减量40%）", "pm": "休息/拉伸", "tl": 15, "type": "strength"},
                        {"date": "2026-02-27", "wd": "周四", "am": "", "noon": "", "pm": "坡度跑 8km（含4km爬坡模拟）", "tl": 55, "type": "hill_run"},
                        {"date": "2026-02-28", "wd": "周五", "am": "", "noon": "力量：轻卧推2x8+手臂", "pm": "休息", "tl": 10, "type": "strength"},
                        {"date": "2026-03-01", "wd": "周六", "am": "长距离 12km（含坡度，Z2-Z3）", "noon": "", "pm": "", "tl": 80, "type": "long_run"},
                        {"date": "2026-03-02", "wd": "周日", "am": "", "noon": "", "pm": "完全休息", "tl": 0, "type": "rest"},
                    ],
                },
                {
                    "label": "赛前最后一周",
                    "dates": ("2026-03-03", "2026-03-08"),
                    "target_km": "10-15km",
                    "target_tl": "80-120",
                    "days": [
                        {"date": "2026-03-03", "wd": "周一", "am": "", "noon": "力量：极轻激活（每项1x5）", "pm": "休息", "tl": 5, "type": "strength"},
                        {"date": "2026-03-04", "wd": "周二", "am": "", "noon": "", "pm": "轻松跑 5km Z1-Z2（HR<140）", "tl": 25, "type": "easy_run"},
                        {"date": "2026-03-05", "wd": "周三", "am": "", "noon": "拉伸+泡沫轴", "pm": "休息", "tl": 0, "type": "recovery"},
                        {"date": "2026-03-06", "wd": "周四", "am": "", "noon": "", "pm": "抖腿慢跑 3km（纯激活）", "tl": 10, "type": "easy_run"},
                        {"date": "2026-03-07", "wd": "周五", "am": "", "noon": "", "pm": "完全休息 + 装备检查", "tl": 0, "type": "rest"},
                        {"date": "2026-03-08", "wd": "周六", "am": "🏔️ 九华山南北穿越 40km", "noon": "", "pm": "", "tl": 800, "type": "race"},
                    ],
                },
            ],
        },
        {
            "name": "恢复 + 无锡备赛",
            "tag": "RECOVERY+TAPER-B",
            "weeks": [
                {
                    "label": "恢复周",
                    "dates": ("2026-03-09", "2026-03-15"),
                    "target_km": "15-25km",
                    "target_tl": "100-180",
                    "days": [
                        {"date": "2026-03-09", "wd": "周日", "am": "", "noon": "", "pm": "完全休息（赛后第1天）", "tl": 0, "type": "rest"},
                        {"date": "2026-03-10", "wd": "周一", "am": "", "noon": "", "pm": "步行30min + 拉伸20min", "tl": 5, "type": "recovery"},
                        {"date": "2026-03-11", "wd": "周二", "am": "", "noon": "", "pm": "极轻松跑30min（测试腿部）", "tl": 20, "type": "easy_run"},
                        {"date": "2026-03-12", "wd": "周三", "am": "", "noon": "力量：极轻激活（上肢为主）", "pm": "休息", "tl": 10, "type": "strength"},
                        {"date": "2026-03-13", "wd": "周四", "am": "", "noon": "", "pm": "轻松跑 6km Z2", "tl": 35, "type": "easy_run"},
                        {"date": "2026-03-14", "wd": "周五", "am": "", "noon": "力量：中等（上肢为主，避免深蹲）", "pm": "休息", "tl": 15, "type": "strength"},
                        {"date": "2026-03-15", "wd": "周六", "am": "中距离 12km（含4km@马拉松配速试跑）", "noon": "", "pm": "", "tl": 90, "type": "tempo_run"},
                    ],
                },
                {
                    "label": "无锡赛前减量",
                    "dates": ("2026-03-16", "2026-03-22"),
                    "target_km": "15-20km",
                    "target_tl": "80-150",
                    "days": [
                        {"date": "2026-03-16", "wd": "周一", "am": "", "noon": "力量：轻量维持", "pm": "休息", "tl": 10, "type": "strength"},
                        {"date": "2026-03-17", "wd": "周二", "am": "", "noon": "", "pm": "质量跑 8km：含4x1km@T配速（3'46\"）", "tl": 80, "type": "interval"},
                        {"date": "2026-03-18", "wd": "周三", "am": "", "noon": "拉伸+泡沫轴", "pm": "休息", "tl": 0, "type": "recovery"},
                        {"date": "2026-03-19", "wd": "周四", "am": "", "noon": "", "pm": "轻松跑 5km Z2", "tl": 25, "type": "easy_run"},
                        {"date": "2026-03-20", "wd": "周五", "am": "", "noon": "", "pm": "完全休息", "tl": 0, "type": "rest"},
                        {"date": "2026-03-21", "wd": "周六", "am": "抖腿慢跑 3km + 赛前准备", "noon": "", "pm": "", "tl": 10, "type": "easy_run"},
                        {"date": "2026-03-22", "wd": "周日", "am": "🏃 无锡马拉松全马 目标2:55-2:59", "noon": "", "pm": "", "tl": 500, "type": "race"},
                    ],
                },
            ],
        },
        {
            "name": "赛后恢复",
            "tag": "RECOVERY",
            "weeks": [
                {
                    "label": "恢复周",
                    "dates": ("2026-03-23", "2026-03-29"),
                    "target_km": "0-15km",
                    "target_tl": "50-100",
                    "days": [
                        {"date": "2026-03-23", "wd": "周一", "am": "", "noon": "", "pm": "完全休息", "tl": 0, "type": "rest"},
                        {"date": "2026-03-24", "wd": "周二", "am": "", "noon": "", "pm": "步行30min + 拉伸", "tl": 5, "type": "recovery"},
                        {"date": "2026-03-25", "wd": "周三", "am": "", "noon": "", "pm": "极轻松跑20min", "tl": 10, "type": "easy_run"},
                        {"date": "2026-03-26", "wd": "周四", "am": "", "noon": "", "pm": "休息", "tl": 0, "type": "rest"},
                        {"date": "2026-03-27", "wd": "周五", "am": "", "noon": "力量：极轻激活", "pm": "轻松跑30min", "tl": 25, "type": "easy_run"},
                        {"date": "2026-03-28", "wd": "周六", "am": "轻松跑 6km Z2", "noon": "", "pm": "", "tl": 35, "type": "easy_run"},
                        {"date": "2026-03-29", "wd": "周日", "am": "", "noon": "", "pm": "休息/轻松步行", "tl": 0, "type": "rest"},
                    ],
                },
            ],
        },
    ]

    auto_sync_todo(PLAN_PHASES)

    TYPE_COLORS = {
        "race": "#ef4444", "interval": "#f97316", "tempo_run": "#eab308",
        "hill_run": "#a855f7", "long_run": "#3b82f6", "easy_run": "#22c55e",
        "strength": "#06b6d4", "recovery": "#64748b", "rest": "#374151",
    }
    TYPE_LABELS = {
        "race": "比赛", "interval": "间歇", "tempo_run": "节奏跑",
        "hill_run": "坡度跑", "long_run": "长距离", "easy_run": "轻松跑",
        "strength": "力量", "recovery": "恢复", "rest": "休息",
    }

    # ── Header ──
    st.markdown(
        '<h2 style="margin-bottom:0">混合训练计划：九华山 + 无锡马拉松</h2>',
        unsafe_allow_html=True,
    )
    st.markdown(
        f'<p style="color:#94a3b8;margin-top:4px;font-size:0.95rem">'
        f'Concurrent Training · 2026-02-24 — 2026-03-29 (5 weeks)<br>'
        f'A赛 <strong style="color:#ef4444">{RACE_A["date"]}</strong> {RACE_A["name"]} {RACE_A["dist"]}（爬升{RACE_A["elev"]}）&nbsp;&nbsp;|&nbsp;&nbsp;'
        f'B赛 <strong style="color:#3b82f6">{RACE_B["date"]}</strong> {RACE_B["name"]} 目标{RACE_B["goal"]}</p>',
        unsafe_allow_html=True,
    )

    # ── Race countdown ──
    today = date.today()
    days_to_a = (date.fromisoformat(RACE_A["date"]) - today).days
    days_to_b = (date.fromisoformat(RACE_B["date"]) - today).days

    rc1, rc2, rc3, rc4 = st.columns(4)
    a_label = "赛后" if days_to_a < 0 else f"{days_to_a} 天后"
    b_label = "赛后" if days_to_b < 0 else f"{days_to_b} 天后"
    rc1.metric("🏔️ 九华山", a_label, f"{RACE_A['dist']} · {RACE_A['elev']}")
    rc2.metric("🏃 无锡马拉松", b_label, f"目标 {RACE_B['goal']}")

    all_plan_days = [d for p in PLAN_PHASES for w in p["weeks"] for d in w["days"]]
    total_done = sum(1 for d in all_plan_days if st.session_state.todo_state.get(d["date"], False))
    rc3.metric("完成进度", f"{total_done} / {len(all_plan_days)}", f"{total_done/max(len(all_plan_days),1)*100:.0f}%")

    past_days = [d for d in all_plan_days if d["date"] <= today.isoformat()]
    past_done = sum(1 for d in past_days if st.session_state.todo_state.get(d["date"], False))
    behind = len(past_days) - past_done
    rc4.metric("应完成", f"{past_done} / {len(past_days)}", "全部完成" if behind == 0 and past_days else f"差 {behind} 天" if past_days else "未开始")

    # Legend
    legend_html = '<div style="display:flex;flex-wrap:wrap;gap:12px;margin:8px 0 16px">'
    for tp, color in TYPE_COLORS.items():
        legend_html += f'<span style="display:flex;align-items:center;gap:4px"><span style="width:12px;height:12px;border-radius:3px;background:{color};display:inline-block"></span>{TYPE_LABELS[tp]}</span>'
    legend_html += '</div>'
    st.markdown(legend_html, unsafe_allow_html=True)

    # ── Render phases and weeks ──
    today_str = today.isoformat()

    for phase in PLAN_PHASES:
        st.markdown(f"#### {phase['tag']}：{phase['name']}")

        for week in phase["weeks"]:
            w_start = date.fromisoformat(week["dates"][0])
            w_end = date.fromisoformat(week["dates"][1])
            is_current = w_start <= today <= w_end

            border = "border:2px solid #3b82f6;" if is_current else "border:1px solid #2d3748;"
            st.markdown(
                f'<div style="background:#1a1f2e;{border}border-radius:10px;padding:14px;margin-bottom:12px">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">'
                f'<div><strong style="font-size:1.05em">{week["label"]}</strong>'
                f' <span style="color:#94a3b8;font-size:0.85em">{week["dates"][0]} ~ {week["dates"][1]}</span></div>'
                f'<div style="color:#94a3b8;font-size:0.85em">目标: {week["target_km"]} · TL {week["target_tl"]}</div>'
                f'</div></div>',
                unsafe_allow_html=True,
            )

            # Build activity lookup by ISO date
            act_by_date = {}
            for a in activities_raw:
                d = a.get("date", 0)
                if d:
                    ds = parse_date(d).isoformat()
                    act_by_date.setdefault(ds, []).append(a)

            for day in week["days"]:
                d_date = date.fromisoformat(day["date"])
                is_today = day["date"] == today_str
                is_race = day["type"] == "race"

                color = TYPE_COLORS.get(day["type"], "#374151")
                todo_key = day["date"]

                # Planned sessions
                sessions = []
                if day["noon"]:
                    sessions.append(f"🔩 中午: {day['noon']}")
                if day["am"]:
                    sessions.append(f"🌅 上午: {day['am']}")
                if day["pm"]:
                    sessions.append(f"🌙 下午/晚: {day['pm']}")
                session_text = " ｜ ".join(sessions) if sessions else "休息"

                # Actual COROS data for this day
                day_acts = act_by_date.get(day["date"], [])
                actual_parts = []
                actual_tl = 0
                for a in day_acts:
                    name = a.get("name", "")
                    dist = a.get("distance", 0)
                    dur = a.get("totalTime", 0)
                    tl = a.get("trainingLoad", 0)
                    actual_tl += tl
                    desc = name
                    if dist > 0:
                        desc += f" {fmt_distance(dist)}"
                    if dur > 0:
                        desc += f" {fmt_duration(dur)}"
                    if tl > 0:
                        desc += f" TL{tl}"
                    actual_parts.append(desc)
                actual_text = " + ".join(actual_parts) if actual_parts else ""

                col_check, col_info = st.columns([0.08, 0.92])
                with col_check:
                    checked = st.checkbox(
                        "done",
                        value=st.session_state.todo_state.get(todo_key, False),
                        key=f"todo_{todo_key}",
                        label_visibility="collapsed",
                    )
                    if checked != st.session_state.todo_state.get(todo_key, False):
                        st.session_state.todo_state[todo_key] = checked
                        save_todo_state(st.session_state.todo_state)

                with col_info:
                    today_marker = ' style="border-left:3px solid #fff;padding-left:8px"' if is_today else ""
                    done_class = "todo-done" if checked else ""
                    race_badge = f' <span style="background:{color};color:#fff;padding:2px 8px;border-radius:4px;font-weight:bold;font-size:0.8em">{TYPE_LABELS[day["type"]]}</span>' if is_race else f' <span style="color:{color};font-size:0.8em">● {TYPE_LABELS[day["type"]]}</span>'
                    tl_badge = f' <span style="color:#94a3b8;font-size:0.8em">TL≈{day["tl"]}</span>' if day["tl"] > 0 else ""

                    actual_line = ""
                    if actual_text:
                        actual_line = f'<br><span style="color:#22c55e;font-size:0.85em">✅ 实际: {actual_text}</span>'

                    st.markdown(
                        f'<div{today_marker}>'
                        f'<span class="{done_class}">'
                        f'<strong>{day["wd"]} {day["date"][5:]}</strong>{race_badge}{tl_badge}'
                        f'<br><span style="color:#d1d5db;font-size:0.9em">{session_text}</span>'
                        f'{actual_line}'
                        f'</span></div>',
                        unsafe_allow_html=True,
                    )

    # ── Export ──
    st.divider()
    st.subheader("导出训练计划")

    def build_plan_markdown() -> str:
        lines = [
            "# 混合训练计划：九华山 + 无锡马拉松",
            f"",
            f"A赛：{RACE_A['date']} {RACE_A['name']} {RACE_A['dist']}（爬升{RACE_A['elev']}）",
            f"B赛：{RACE_B['date']} {RACE_B['name']} 目标{RACE_B['goal']}",
            f"",
            "---",
            "",
        ]
        for phase in PLAN_PHASES:
            lines.append(f"## {phase['tag']}：{phase['name']}")
            lines.append("")
            for week in phase["weeks"]:
                lines.append(f"### {week['label']}（{week['dates'][0]} ~ {week['dates'][1]}）")
                lines.append(f"目标跑量: {week['target_km']} · 目标负荷: TL {week['target_tl']}")
                lines.append("")
                lines.append("| 日期 | 星期 | 中午训练 | 跑步训练 | 预估TL |")
                lines.append("|------|------|----------|----------|--------|")
                for d in week["days"]:
                    noon = d["noon"] or "—"
                    run = d["am"] or d["pm"] or "休息"
                    lines.append(f"| {d['date']} | {d['wd']} | {noon} | {run} | {d['tl']} |")
                lines.append("")
        lines.append("---")
        lines.append("")
        lines.append("## COROS 手动录入指南")
        lines.append("")
        lines.append("1. 打开 t.coros.com → 日程 tab")
        lines.append("2. 点击对应日期 → 添加训练计划")
        lines.append("3. 按上表内容设置训练类型、时长、心率区间")
        lines.append("4. 对于跑步训练：设置目标心率或配速")
        lines.append("5. 对于力量训练：设置时长和训练类型")
        return "\n".join(lines)

    plan_md = build_plan_markdown()

    ec1, ec2 = st.columns(2)
    with ec1:
        st.download_button(
            "📥 下载训练计划（Markdown）",
            plan_md,
            file_name="concurrent_training_plan_2026.md",
            mime="text/markdown",
        )
    with ec2:
        plan_json_export = json.dumps(
            {"races": [RACE_A, RACE_B], "phases": PLAN_PHASES},
            ensure_ascii=False, indent=2, default=str,
        )
        st.download_button(
            "📥 下载训练计划（JSON）",
            plan_json_export,
            file_name="concurrent_training_plan_2026.json",
            mime="application/json",
        )

    with st.expander("💡 如何导入到 COROS"):
        st.markdown("""
**COROS 目前不支持通过文件直接导入训练计划**，但你可以通过以下方式使用：

1. **COROS Team 日程**：打开 [t.coros.com](https://t.coros.com) → 日程 tab → 逐日添加计划训练
2. **COROS App**：手机 App → 训练计划 → 手动创建每日训练
3. **参考上方 Markdown 文件**：下载后打印或放在手机备忘录中，每天对照执行并在上方打勾

> COROS 支持导入 `.fit` / `.tcx` 格式的**已完成活动**（通过日程页面的"导入"按钮），
> 但训练计划需要手动在平台上创建。
        """)
