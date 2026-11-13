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


def calc_double_progression(ex_name: str, current_item: dict, history: list, exercise_db: dict, rules: dict):
    """
    Επιστημονικός αλγόριθμος Double Progression:
    1. Αν έπιασες το πάνω όριο επαναλήψεων με RIR >= target_rir -> Αύξηση κιλών (+2.5kg ή +1kg DB) & επαναφορά reps στο κάτω όριο.
    2. Αν είσαι εντός rep range με RIR >= 1 -> Διατήρηση κιλών & +1 επανάληψη.
    3. Αν ήσουν στο RIR 0 -> Σταθεροποίηση φορτίου μέχρι να βγει με RIR 1-2.
    """
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

    # Εύρεση τελευταίας εκτέλεσης της άσκησης στο ιστορικό
    last_exec = None
    for session in reversed(history):
        exs = session.get("exercises", {})
        if ex_name in exs:
            last_exec = exs[ex_name]
            break

    if not last_exec:
        return None

    last_w = float(last_exec.get("max_weight", current_item.get("w", 0)))
    # Αν στο history αποθηκεύτηκε συνολικό volume ή reps, υπολογίζουμε μέσο όρο reps ανά σετ
    last_sets = max(1, int(last_exec.get("sets", current_item.get("s", 3))))
    raw_reps = last_exec.get("reps", None)
    if raw_reps is None:
        tot_r = int(last_exec.get("total_reps_or_min", 0))
        last_r = max(1, round(tot_r / last_sets)) if tot_r > 0 else int(current_item.get("r", min_r))
    else:
        last_r = int(raw_reps)

    last_rir = int(last_exec.get("rir", 2))

    # Κανόνας 1: Έτοιμος για αύξηση βάρους (Double Progression Top-Out)
    if last_r >= max_r and last_rir >= target_rir:
        new_w = round(last_w + step_kg, 2)
        db_note = " (ανά αλτήρα)" if is_db else ""
        return {
            "w": new_w,
            "r": min_r,
            "msg": f"Έπιασες {last_w}kg × {last_r} reps με RIR {last_rir} (άνω όριο {max_r} reps). Ανέβασε +{step_kg}kg{db_note} και ξεκίνα ξανά από {min_r} reps!"
        }

    # Κανόνας 2: Αύξηση επαναλήψεων εντός του εύρους
    if last_r < max_r and last_rir >= 1:
        new_r = last_r + 1
        return {
            "w": last_w,
            "r": new_r,
            "msg": f"Προηγούμενο: {last_w}kg × {last_r} reps (RIR {last_rir}). Κράτα τα ίδια κιλά και στόχευσε +1 rep ({new_r}/{max_r} reps)."
        }

    # Κανόνας 3: Υψηλή κόπωση (RIR 0) — Εδραίωση
    return {
        "w": last_w,
        "r": last_r,
        "msg": f"Στην τελευταία συνεδρία έφτασες RIR {last_rir} στα {last_w}kg × {last_r}. Εδραίωσε το ίδιο φορτίο μέχρι να βγει με RIR {target_rir}."
    }


def calc_weekly_fatigue_and_deload(history: list, exercise_db: dict, rules: dict):
    """
    Υπολογίζει το 7-Day Systemic & Axial Fatigue Score βάσει:
    - RIR proximity-to-failure multiplier (RIR 0 = 1.65x κόπωση)
    - Axial / CNS load multiplier (Deadlift, Squat, RDL, Sleds)
    """
    f_cfg = rules.get("fatigue_model", {})
    rir_mults = f_cfg.get("rir_multipliers", {"0": 1.65, "1": 1.3, "2": 1.0, "3": 0.75, "4": 0.55, "5": 0.4})
    axial_map = f_cfg.get("axial_heavy_exercises", {})
    thresholds = f_cfg.get("weekly_thresholds", {"optimal_max": 65.0, "high_warning": 85.0, "deload_trigger": 100.0})

    cutoff_7d = datetime.now() - timedelta(days=7)
    weekly_score = 0.0
    axial_score = 0.0
    total_sets_7d = 0

    for session in history:
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
            rir_key = str(int(ex_data.get("rir", 2)))
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
        status = "🔴 Κρίσιμη Κόπωση ΚΝΣ — Προτείνεται Deload Week"
        color = "#ff6b6b"
        needs_deload = True
    elif weekly_score >= high_warn:
        status = "🟠 Υψηλή Συσσώρευση Κόπωσης (Overreaching)"
        color = "#ffa94d"
        needs_deload = True
    elif weekly_score >= opt_max * 0.5:
        status = "🟢 Βέλτιστη Παραγωγική Ζώνη (Productive Overload)"
        color = "#20c997"
        needs_deload = False
    else:
        status = "🔵 Χαμηλή Κόπωση / Φρέσκο Νευρικό Σύστημα"
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
    """Υπολογίζει τα splits για 8x1km Runs, Roxzone και τα 8 stations του HYROX."""
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


def calc_running_pace_zones(ref_dist_km: float, ref_time_min: float, rules: dict = None):
    """
    Υπολογίζει προβλέψεις αποστάσεων μέσω τύπου Riegel: T2 = T1 * (D2 / D1)^1.06
    και εξάγει τις 5 ζώνες προπόνησης σε min/km βάσει LT2.
    """
    r_cfg = (rules or {}).get("running_engine", {})
    exp = float(r_cfg.get("riegel_exponent", 1.06))
    zones_cfg = r_cfg.get("pace_zones_vs_lt2", [])

    if ref_dist_km <= 0 or ref_time_min <= 0:
        return [], []

    # Προβλέψεις αποστάσεων Riegel
    targets = [("5 km", 5.0), ("10 km", 10.0), ("Ημιμαραθώνιος (21.1 km)", 21.0975), ("Μαραθώνιος (42.2 km)", 42.195)]
    predictions = []
    lt2_pace_min_km = (ref_time_min * ((10.0 / ref_dist_km) ** exp)) / 10.0  # Εκτίμηση LT2 από 10K pace

    for label, d_km in targets:
        pred_min = ref_time_min * ((d_km / ref_dist_km) ** exp)
        pace_min = pred_min / d_km
        hrs = int(pred_min // 60)
        rem_m = pred_min - (hrs * 60)
        time_str = f"{hrs}h {format_mmss(rem_m)}" if hrs > 0 else format_mmss(pred_min)
        predictions.append({
            "Απόσταση": label,
            "Προβλεπόμενος Χρόνος": time_str,
            "Μέσος Ρυθμός": f"{format_mmss(pace_min)} /km"
        })

    # Ζώνες ρυθμού (min/km)
    zones = []
    for z in zones_cfg:
        fast_p = lt2_pace_min_km * float(z.get("min_mult", 1.0))
        slow_p = lt2_pace_min_km * float(z.get("max_mult", 1.1))
        zones.append({
            "Ζώνη": z.get("zone", ""),
            "Ρυθμός (min/km)": f"{format_mmss(fast_p)} – {format_mmss(slow_p)} /km",
            "Στόχος": z.get("desc", "")
        })

    return predictions, zones
