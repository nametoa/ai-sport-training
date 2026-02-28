#!/usr/bin/env python3
"""
将 COROS 全量数据导出为 Open WebUI 知识库友好的 Markdown 文件。
运行: python3 export_knowledge.py
输出: knowledge/ 目录下的若干 .md 文件，直接上传到 Open WebUI 知识库即可。
"""
from __future__ import annotations

import json
import os
from datetime import datetime, date
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path(__file__).parent / "data"
OUTPUT_DIR = Path(__file__).parent / "knowledge"

SPORT_TYPE_MAP = {
    100: "跑步", 102: "越野跑", 200: "骑行",
    402: "力量训练", 401: "力量训练", 300: "游泳",
    10100: "健步", 10300: "瑜伽",
}


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
        return f"{h}h{m:02d}m{s:02d}s"
    return f"{m}m{s:02d}s"


def fmt_date(d: int) -> str:
    s = str(d)
    return f"{s[:4]}-{s[4:6]}-{s[6:]}"


def fmt_distance(meters: float) -> str:
    if not meters or meters <= 0:
        return "--"
    km = meters / 1000
    return f"{km:.2f}km"


def export_activities_summary():
    """导出活动记录摘要（按月分组，含关键指标）。"""
    acts = load_json("activities.json")
    if not acts:
        return

    # 按月分组
    monthly = defaultdict(list)
    for a in acts:
        d = a.get("date", 0)
        month_key = str(d)[:6]  # YYYYMM
        monthly[month_key].append(a)

    lines = [
        "# COROS 训练活动记录",
        "",
        f"> 数据导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 总活动数: {len(acts)}",
        "",
    ]

    # 总体统计
    sport_counts = defaultdict(int)
    sport_dist = defaultdict(float)
    sport_dur = defaultdict(int)
    for a in acts:
        st = a.get("sportType", 0)
        name = SPORT_TYPE_MAP.get(st, f"其他({st})")
        sport_counts[name] += 1
        sport_dist[name] += a.get("distance", 0)
        sport_dur[name] += a.get("totalTime", 0)

    lines.append("## 全量运动统计")
    lines.append("")
    lines.append("| 运动类型 | 次数 | 总距离 | 总时长 |")
    lines.append("|---------|------|--------|--------|")
    for name in sorted(sport_counts, key=lambda x: sport_counts[x], reverse=True):
        lines.append(
            f"| {name} | {sport_counts[name]} | "
            f"{fmt_distance(sport_dist[name])} | {fmt_duration(sport_dur[name])} |"
        )
    lines.append("")

    # 按月详情
    for month_key in sorted(monthly.keys(), reverse=True):
        month_acts = monthly[month_key]
        year, mon = month_key[:4], month_key[4:]
        lines.append(f"## {year}年{mon}月 ({len(month_acts)}次活动)")
        lines.append("")
        lines.append("| 日期 | 类型 | 距离 | 时长 | 均配速 | 均心率 | 训练负荷 |")
        lines.append("|------|------|------|------|--------|--------|---------|")

        for a in sorted(month_acts, key=lambda x: x.get("date", 0), reverse=True):
            d = fmt_date(a.get("date", 0))
            st = SPORT_TYPE_MAP.get(a.get("sportType", 0), "其他")
            dist = fmt_distance(a.get("distance", 0))
            dur = fmt_duration(a.get("totalTime", 0))
            pace = fmt_pace(a.get("adjustedPace", 0)) if a.get("adjustedPace") else "--"
            hr = a.get("avgHr", 0)
            hr_str = f"{hr} bpm" if hr else "--"
            tl = a.get("trainingLoad", 0)
            tl_str = str(tl) if tl else "--"
            lines.append(f"| {d} | {st} | {dist} | {dur} | {pace} | {hr_str} | {tl_str} |")
        lines.append("")

    out = OUTPUT_DIR / "01_训练活动记录.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {out.name} ({len(acts)} 条活动)")


def export_daily_metrics():
    """导出每日身体指标（HRV、静息心率、VO2max等）。"""
    analyse = load_json("analyse.json")
    if not analyse:
        return

    day_list = analyse.get("dayList", [])

    lines = [
        "# 每日身体指标",
        "",
        f"> 数据导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"> 数据天数: {len(day_list)}",
        "",
        "## 指标说明",
        "- testRhr: COROS 算法评估的静息心率（官方展示值）",
        "- avgSleepHrv: 睡眠期间平均 HRV",
        "- sleepHrvBase: HRV 基线",
        "- vo2max: 最大摄氧量",
        "- staminaLevel: 耐力水平",
        "- trainingLoad: 当日训练负荷",
        "- tiredRateNew: 疲劳指数",
        "",
        "## 每日数据",
        "",
        "| 日期 | 静息心率 | HRV | HRV基线 | VO2max | 耐力 | 训练负荷 | 疲劳指数 |",
        "|------|---------|-----|---------|--------|------|---------|---------|",
    ]

    for d in sorted(day_list, key=lambda x: x["happenDay"], reverse=True):
        hd = fmt_date(d["happenDay"])
        rhr = d.get("testRhr", "--")
        hrv = d.get("avgSleepHrv", "--")
        hrv_base = d.get("sleepHrvBase", "--")
        vo2 = d.get("vo2max", "--")
        stamina = d.get("staminaLevel", "--")
        tl = d.get("trainingLoad", "--")
        tired = d.get("tiredRateNew", "--")
        lines.append(f"| {hd} | {rhr} | {hrv} | {hrv_base} | {vo2} | {stamina} | {tl} | {tired} |")

    lines.append("")

    # 汇总统计
    rhr_vals = [d["testRhr"] for d in day_list if d.get("testRhr")]
    hrv_vals = [d["avgSleepHrv"] for d in day_list if d.get("avgSleepHrv")]
    vo2_vals = [d["vo2max"] for d in day_list if d.get("vo2max")]

    lines.append("## 汇总统计")
    lines.append("")
    if rhr_vals:
        lines.append(f"- 静息心率: 最近 {rhr_vals[-1]} bpm, 最低 {min(rhr_vals)} bpm, 平均 {sum(rhr_vals)/len(rhr_vals):.0f} bpm")
    if hrv_vals:
        lines.append(f"- HRV: 最近 {hrv_vals[-1]} ms, 最高 {max(hrv_vals)} ms, 平均 {sum(hrv_vals)/len(hrv_vals):.0f} ms")
    if vo2_vals:
        lines.append(f"- VO2max: 最近 {vo2_vals[-1]}, 最高 {max(vo2_vals)}, 平均 {sum(vo2_vals)/len(vo2_vals):.1f}")
    lines.append("")

    out = OUTPUT_DIR / "02_每日身体指标.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {out.name} ({len(day_list)} 天)")


def export_weekly_summary():
    """导出周训练统计。"""
    analyse = load_json("analyse.json")
    if not analyse:
        return

    week_list = analyse.get("weekList", [])
    if not week_list:
        return

    lines = [
        "# 周训练统计",
        "",
        f"> 数据导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
        "| 周起始 | 周结束 | 跑量(km) | 时长 | 训练负荷 | 训练次数 |",
        "|--------|--------|----------|------|---------|---------|",
    ]

    for w in sorted(week_list, key=lambda x: x.get("firstDayOfWeek", 0), reverse=True):
        start = fmt_date(w.get("firstDayOfWeek", 0))
        end = fmt_date(w.get("lastDayInWeek", 0))
        dist = fmt_distance(w.get("distance", 0))
        dur = fmt_duration(w.get("duration", 0))
        tl = w.get("trainingLoad", 0) or "--"
        count = w.get("count", 0) or "--"
        lines.append(f"| {start} | {end} | {dist} | {dur} | {tl} | {count} |")

    lines.append("")

    out = OUTPUT_DIR / "03_周训练统计.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"✓ {out.name} ({len(week_list)} 周)")


def export_current_plan():
    """导出当前训练计划。"""
    plan_path = DATA_DIR / "train_exceise.md"
    if plan_path.exists():
        content = plan_path.read_text(encoding="utf-8")
        out = OUTPUT_DIR / "04_当前训练计划.md"
        header = (
            "# 当前训练计划\n\n"
            f"> 数据导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        )
        out.write_text(header + content, encoding="utf-8")
        print(f"✓ {out.name}")

    # save_plan.json
    try:
        plan = load_json("save_plan.json")
    except Exception:
        plan = None
    if plan:
        out = OUTPUT_DIR / "05_COROS训练计划详情.md"
        lines = [
            "# COROS 训练计划详情",
            "",
            f"> 数据导出时间: {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
        ]

        if isinstance(plan, dict):
            plan_data = plan.get("data", plan)
            if isinstance(plan_data, dict):
                for key, val in plan_data.items():
                    lines.append(f"## {key}")
                    lines.append(f"```json\n{json.dumps(val, ensure_ascii=False, indent=2)[:3000]}\n```")
                    lines.append("")

        out.write_text("\n".join(lines), encoding="utf-8")
        print(f"✓ {out.name}")


def export_coach_prompt():
    """复制 AI 教练 Prompt 到知识库。"""
    src = Path(__file__).parent / "ai_coach_prompt.md"
    if src.exists():
        content = src.read_text(encoding="utf-8")
        out = OUTPUT_DIR / "00_AI教练角色设定.md"
        out.write_text(content, encoding="utf-8")
        print(f"✓ {out.name}")


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    print(f"导出目录: {OUTPUT_DIR}\n")

    export_coach_prompt()
    export_activities_summary()
    export_daily_metrics()
    export_weekly_summary()
    export_current_plan()

    print(f"\n✅ 全部导出完成! 文件在 {OUTPUT_DIR}/")
    print("将以上 .md 文件上传到 Open WebUI 知识库即可。")


if __name__ == "__main__":
    main()
