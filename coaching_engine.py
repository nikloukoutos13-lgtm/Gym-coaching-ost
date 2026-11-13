import os
import json
from datetime import datetime, timedelta

RULES_PATH = os.path.join("data", "coaching_rules.json")


def load_coaching_rules():
    if os.path.exists(RULES_PATH):
        try:
            with open(RULES_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


def _extract_avg_rir(ex_data: dict, default: int = 2) -> int:
    rirs_list = ex_data.get("rirs")
    if isinstance(rirs_list, list) and rirs_list:
        return int(round(sum(rirs_list) / len(rirs_list)))
    return int(ex_data.get("rir", default))


def calc_double_progression(ex_name: str, current_item: dict, history: list, exercise_db: dict, rules: dict, lang: str = "Ελληνικά"):
    is_en = (lang == "English")
    ex_info = exercise_db.get(ex_name, {})
    if ex_info.get("type") != "weight":
        return None

    dp_cfg = rules.get("double_progression", {})
    emg_count = len(ex_info.get("emg_weights", {}))
    is_compound = emg_count >= 2 or ex_info.get("secondary") is not None

    band = dp_cfg.get("compound" if is_compound else "isolation", {"min_reps": 8, "max_reps": 12, "target_rir": 2})
    min_r = int(band.get("min_reps", 8))
    max_r = int(band.get("max_reps", 12))
    target_rir = int(band.get("target_rir", 2))

    is_db = bool(ex_info.get("is_db", False))
    inc_cfg = dp_cfg.get("increments_kg", {})
    step_kg = float(inc_cfg.get("dumbbell_per_hand", 1.0) if is_db else inc_cfg.get("barbell_machine", 2.5))

    last_exec = None
    for session in reversed(history or []):
        exs = session.get("exercises", {})
        if ex_name in exs:
            last_exec = exs[ex_name]
            break

    if not last_exec:
        return None

    last_w = float(last_exec.get("max_weight", current_item.get("w", 0)))
    last_sets = max(1, int(last_exec.get("sets", current_item.get("s", 3))))
    raw_reps = last_exec.get("reps", None)
    if raw_reps is None:
        tot_r = int(last_exec.get("total_reps_or_min", 0))
        last_r = max(1, round(tot_r / last_sets)) if tot_r > 0 else int(current_item.get("r", min_r))
    else:
        last_r = int(raw_reps)

    last_rir = _extract_avg_rir(last_exec, default=2)

    if last_r >= max_r and last_rir >= target_rir:
        new_w = round(last_w + step_kg, 2)
        if is_en:
            db_note = " (per dumbbell)" if is_db else ""
            msg = f"You hit {last_w}kg × {last_r} reps at RIR {last_rir} (top of {max_r}-rep range). Increase load by +{step_kg}kg{db_note} and reset to {min_r} reps!"
        else:
            db_note = " (ανά αλτήρα)" if is_db else ""
            msg = f"Έπιασες {last_w}kg × {last_r} reps με RIR {last_rir} (άνω όριο {max_r} reps). Ανέβασε +{step_kg}kg{db_note} και ξεκίνα ξανά από {min_r} reps!"
        return {"w": new_w, "r": min_r, "msg": msg}

    if last_r < max_r and last_rir >= 1:
        new_r = last_r + 1
        if is_en:
            msg = f"Previous: {last_w}kg × {last_r} reps (RIR {last_rir}). Keep the same load and aim for +1 rep ({new_r}/{max_r} reps)."
        else:
            msg = f"Προηγούμενο: {last_w}kg × {last_r} reps (RIR {last_rir}). Κράτα τα ίδια κιλά και στόχευσε +1 rep ({new_r}/{max_r} reps)."
        return {"w": last_w, "r": new_r, "msg": msg}

    if is_en:
        msg = f"Last session reached RIR {last_rir} at {last_w}kg × {last_r}. Consolidate this load until you hit it with RIR {target_rir}."
    else:
        msg = f"Στην τελευταία συνεδρία έφτασες RIR {last_rir} στα {last_w}kg × {last_r}. Εδραίωσε το ίδιο φορτίο μέχρι να βγει με RIR {target_rir}."
    return {"w": last_w, "r": last_r, "msg": msg}


def calc_weekly_fatigue_and_deload(history: list, exercise_db: dict, rules: dict, lang: str = "Ελληνικά"):
    is_en = (lang == "English")
    f_cfg = rules.get("fatigue_model", {})
    rir_mults = f_cfg.get("rir_multipliers", {"0": 1.65, "1": 1.3, "2": 1.0, "3": 0.75, "4": 0.55, "5": 0.4})
    axial_map = f_cfg.get("axial_heavy_exercises", {})
    thresholds = f_cfg.get("weekly_thresholds", {"optimal_max": 65.0, "high_warning": 85.0, "deload_trigger": 100.0})

    cutoff_7d = datetime.now() - timedelta(days=7)
    weekly_score = 0.0
    axial_score = 0.0
    total_sets_7d = 0

    for session in (history or []):
        raw_date = str(session.get("date", "")).split()[0]
        try:
            dt = datetime.strptime(raw_date, "%d/%m/%Y")
            if dt < cutoff_7d:
                continue
        except ValueError:
            pass

        for ex_name, ex_data in session.get("exercises", {}).items():
            s = float(ex_data.get("sets", 0))
            if s <= 0:
                continue
            rir_key = str(_extract_avg_rir(ex_data, default=2))
            r_mult = float(rir_mults.get(rir_key, 1.0))
            a_mult = float(axial_map.get(ex_name, 1.0))

            set_fatigue = s * r_mult * a_mult
            weekly_score += set_fatigue
            total_sets_7d += int(s)
            if a_mult > 1.0:
                axial_score += set_fatigue

    weekly_score = round(weekly_score, 1)
    axial_score = round(axial_score, 1)

    opt_max = float(thresholds.get("optimal_max", 65.0))
    high_warn = float(thresholds.get("high_warning", 85.0))
    deload_trig = float(thresholds.get("deload_trigger", 100.0))

    if weekly_score >= deload_trig:
        status = "🔴 Critical CNS Fatigue — Deload Week Recommended" if is_en else "🔴 Κρίσιμη Κόπωση ΚΝΣ — Προτείνεται Deload Week"
        color = "#ff6b6b"
        needs_deload = True
    elif weekly_score >= high_warn:
        status = "🟠 High Fatigue Accumulation (Overreaching)" if is_en else "🟠 Υψηλή Συσσώρευση Κόπωσης (Overreaching)"
        color = "#ffa94d"
        needs_deload = True
    elif weekly_score >= opt_max * 0.5:
        status = "🟢 Optimal Productive Zone (Productive Overload)" if is_en else "🟢 Βέλτιστη Παραγωγική Ζώνη (Productive Overload)"
        color = "#20c997"
        needs_deload = False
    else:
        status = "🔵 Low Fatigue / Fresh Nervous System" if is_en else "🔵 Χαμηλή Κόπωση / Φρέσκο Νευρικό Σύστημα"
        color = "#339af0"
        needs_deload = False

    return {
        "score": weekly_score,
        "axial_score": axial_score,
        "sets_7d": total_sets_7d,
        "status": status,
        "color": color,
        "needs_deload": needs_deload,
        "deload_mult": float(f_cfg.get("deload_set_multiplier", 0.6))
    }


def format_mmss(total_minutes: float) -> str:
    total_sec = max(0, int(round(total_minutes * 60)))
    mins = total_sec // 60
    secs = total_sec % 60
    return f"{mins}:{secs:02d}"


def calc_hyrox_splits(target_minutes: float, division: str = "Open", rules: dict = None):
    h_cfg = (rules or {}).get("hyrox_standards", {}).get("divisions", {})
    div_data = h_cfg.get(division, h_cfg.get("Open", {}))

    run_share = float(div_data.get("run_1km_share", 0.51))
    rox_share = float(div_data.get("roxzone_share", 0.07))
    stations_map = div_data.get("stations", {})

    total_run_min = target_minutes * run_share
    per_1km_min = total_run_min / 8.0
    rox_min = target_minutes * rox_share

    station_rows = []
    for st_name, share in stations_map.items():
        st_min = target_minutes * float(share)
        station_rows.append({
            "Station": st_name,
            "Target Split": format_mmss(st_min),
            "Share (%)": f"{share * 100:.1f}%"
        })

    return {
        "per_1km_pace": f"{format_mmss(per_1km_min)} /km",
        "total_run_time": format_mmss(total_run_min),
        "roxzone_total": format_mmss(rox_min),
        "stations": station_rows
    }


def calc_running_pace_zones(ref_dist_km: float, ref_time_min: float, rules: dict = None, lang: str = "Ελληνικά"):
    is_en = (lang == "English")
    r_cfg = (rules or {}).get("running_engine", {})
    exp = float(r_cfg.get("riegel_exponent", 1.06))
    zones_cfg = r_cfg.get("pace_zones_vs_lt2", [])

    if ref_dist_km <= 0 or ref_time_min <= 0:
        return [], []

    targets = [
        ("5 km", 5.0),
        ("10 km", 10.0),
        ("Half Marathon (21.1 km)" if is_en else "Ημιμαραθώνιος (21.1 km)", 21.0975),
        ("Marathon (42.2 km)" if is_en else "Μαραθώνιος (42.2 km)", 42.195)
    ]
    predictions = []
    lt2_pace_min_km = (ref_time_min * ((10.0 / ref_dist_km) ** exp)) / 10.0

    for label, d_km in targets:
        pred_min = ref_time_min * ((d_km / ref_dist_km) ** exp)
        pace_min = pred_min / d_km
        hrs = int(pred_min // 60)
        rem_m = pred_min - (hrs * 60)
        time_str = f"{hrs}h {format_mmss(rem_m)}" if hrs > 0 else format_mmss(pred_min)
        predictions.append({
            "Distance" if is_en else "Απόσταση": label,
            "Predicted Time" if is_en else "Προβλεπόμενος Χρόνος": time_str,
            "Avg Pace" if is_en else "Μέσος Ρυθμός": f"{format_mmss(pace_min)} /km"
        })

    zones = []
    for z in zones_cfg:
        fast_p = lt2_pace_min_km * float(z.get("min_mult", 1.0))
        slow_p = lt2_pace_min_km * float(z.get("max_mult", 1.1))
        desc_text = z.get("desc_en", z.get("desc", "")) if is_en else z.get("desc", "")
        zones.append({
            "Zone" if is_en else "Ζώνη": z.get("zone", ""),
            "Pace (min/km)" if is_en else "Ρυθμός (min/km)": f"{format_mmss(fast_p)} – {format_mmss(slow_p)} /km",
            "Target" if is_en else "Στόχος": desc_text
        })

    return predictions, zones
