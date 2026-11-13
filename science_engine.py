import os
import json
from datetime import datetime, timedelta

STANDARDS_PATH = os.path.join("data", "strength_standards.json")


def load_strength_standards():
    if os.path.exists(STANDARDS_PATH):
        try:
            with open(STANDARDS_PATH, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"volume_landmarks": {}, "dots_coefficients": {}, "bw_multipliers": {}, "tier_labels": []}


def calc_e1rm(weight: float, reps: int, rir: int = 0) -> float:
    """RIR-adjusted Epley 1RM estimation."""
    if weight <= 0:
        return 0.0
    effective_reps = max(1, int(reps) + max(0, int(rir)))
    if effective_reps == 1:
        return round(float(weight), 1)
    return round(float(weight) * (1.0 + effective_reps / 30.0), 1)


def calc_dots(bodyweight_kg: float, total_kg: float, gender: str = "Άνδρας", coeffs_map: dict = None) -> float:
    """IPF/USAPL DOTS relative strength score."""
    if bodyweight_kg <= 0 or total_kg <= 0:
        return 0.0
    coeffs_map = coeffs_map or {}
    c = coeffs_map.get(
        gender,
        [-307.75076, 24.0900756, -0.1918759221, 0.0007391293, -0.000001093]
    )
    bw = max(40.0, min(210.0, float(bodyweight_kg)))
    denom = c[0] + c[1] * bw + c[2] * (bw ** 2) + c[3] * (bw ** 3) + c[4] * (bw ** 4)
    if denom <= 0:
        return 0.0
    return round((500.0 / denom) * float(total_kg), 1)


def _filter_history_by_days(history: list, days_window: int) -> list:
    if not days_window or days_window <= 0:
        return history
    cutoff = datetime.now() - timedelta(days=days_window)
    filtered = []
    for h in history:
        raw_date = str(h.get("date", "")).split()[0]
        try:
            dt = datetime.strptime(raw_date, "%d/%m/%Y")
            if dt >= cutoff:
                filtered.append(h)
        except ValueError:
            # Αν δεν αναγνωριστεί η ημερομηνία, συμπεριλαμβάνεται ώστε να μη χαθεί δεδομένο
            filtered.append(h)
    return filtered


def analyze_fractional_emg_and_profiles(history: list, exercise_db: dict, standards_data: dict, days_window: int = 7):
    """
    Υπολογίζει:
    1. Fractional EMG Sets ανά μυϊκή ομάδα βάσει των emg_weights του exercise_db.
    2. Κατανομή Resistance Profile (Lengthened / Mid-range / Shortened / Full-range) ανά μυϊκή ομάδα.
    3. Προτάσεις βελτιστοποίησης για Stretch-Mediated Hypertrophy & Volume Landmarks.
    """
    filtered_hist = _filter_history_by_days(history, days_window)
    landmarks = standards_data.get("volume_landmarks", {})

    fractional_sets = {m: 0.0 for m in landmarks.keys()}
    profile_breakdown = {
        m: {"Lengthened-biased": 0.0, "Mid-range": 0.0, "Shortened-biased": 0.0, "Full-range": 0.0}
        for m in landmarks.keys()
    }

    for session in filtered_hist:
        exs = session.get("exercises", {})
        for ex_name, ex_data in exs.items():
            sets_count = float(ex_data.get("sets", ex_data.get("s", 0)))
            if sets_count <= 0:
                continue

            db_info = exercise_db.get(ex_name, {})
            if db_info.get("type") == "cardio":
                continue

            emg_map = db_info.get("emg_weights")
            if not emg_map or not isinstance(emg_map, dict):
                # Fallback για custom ασκήσεις χωρίς emg_weights
                emg_map = {}
                prim = db_info.get("primary") or db_info.get("muscle")
                sec = db_info.get("secondary")
                if prim:
                    emg_map[prim] = 1.0
                if sec:
                    emg_map[sec] = 0.5

            res_prof = db_info.get("resistance_profile", "Mid-range")

            for muscle, coeff in emg_map.items():
                if muscle == "Cardio":
                    continue
                if muscle not in fractional_sets:
                    fractional_sets[muscle] = 0.0
                    profile_breakdown[muscle] = {
                        "Lengthened-biased": 0.0, "Mid-range": 0.0, "Shortened-biased": 0.0, "Full-range": 0.0
                    }
                weighted_s = sets_count * float(coeff)
                fractional_sets[muscle] += weighted_s
                if res_prof in profile_breakdown[muscle]:
                    profile_breakdown[muscle][res_prof] += weighted_s

    # Στρογγυλοποίηση
    fractional_sets = {k: round(v, 1) for k, v in fractional_sets.items()}

    # Εντοπισμός ελλείψεων σε Lengthened-biased stimulus (Stretch-Mediated Hypertrophy)
    biomech_alerts = []
    for muscle, profs in profile_breakdown.items():
        total_m = fractional_sets.get(muscle, 0.0)
        lengthened = profs.get("Lengthened-biased", 0.0)
        shortened = profs.get("Shortened-biased", 0.0)
        if total_m >= 4.0 and lengthened == 0.0 and shortened > 0.0:
            biomech_alerts.append(
                f"**{muscle}**: {total_m:.1f} σετ χωρίς καμία **Lengthened-biased** άσκηση "
                f"(μόνο Shortened/Mid-range). Πρόσθεσε κίνηση με φόρτιση στη διάταση!"
            )

    return fractional_sets, profile_breakdown, biomech_alerts, len(filtered_hist)


def evaluate_strength_standards(active_p: dict, exercise_db: dict, standards_data: dict):
    """
    Υπολογίζει RIR-adjusted e1RM, BW ratio, Tier κατάταξη και επόμενο στόχο (+kg),
    καθώς και το συνολικό DOTS Score.
    """
    prof = active_p.get("profile", {})
    gender = prof.get("gender", "Άνδρας")
    bw = float(prof.get("weight_kg", 75.0))
    multipliers_by_ex = standards_data.get("bw_multipliers", {}).get(gender, {})
    tier_labels = standards_data.get("tier_labels", ["Untrained", "Novice", "Intermediate", "Advanced", "Elite"])

    # Βρίσκουμε το καλύτερο e1RM ανά άσκηση από history + prs
    best_e1rm = {}
    for ex_name, pr_val in active_p.get("prs", {}).items():
        if float(pr_val) > 0:
            best_e1rm[ex_name] = float(pr_val)

    for session in active_p.get("history", []):
        for ex_name, ex_data in session.get("exercises", {}).items():
            if ex_data.get("type") == "weight":
                w = float(ex_data.get("max_weight", ex_data.get("w", 0)))
                # Αν είναι αλτήρες και έχει καταγραφεί βάρος ενός αλτήρα vs ζεύγους, χρησιμοποιούμε το logged βάρος
                r = int(ex_data.get("reps", ex_data.get("r", 1)))
                rir = int(ex_data.get("rir", 1))
                est = calc_e1rm(w, r, rir)
                if est > best_e1rm.get(ex_name, 0.0):
                    best_e1rm[ex_name] = est

    results = []
    for ex_name, mults in multipliers_by_ex.items():
        if ex_name not in best_e1rm:
            continue
        user_1rm = best_e1rm[ex_name]
        bw_ratio = round(user_1rm / bw, 2) if bw > 0 else 0.0

        # Εύρεση τρέχοντος επιπέδου & επόμενου milestone
        current_tier = "Beginner (<Untrained)"
        next_tier = tier_labels[0]
        next_target_kg = round(mults[0] * bw, 1)
        progress_pct = min(100, int((user_1rm / max(1.0, next_target_kg)) * 100))

        for idx, m in enumerate(mults):
            threshold_kg = m * bw
            if user_1rm >= threshold_kg:
                current_tier = tier_labels[idx]
                if idx + 1 < len(mults):
                    next_tier = tier_labels[idx + 1]
                    next_target_kg = round(mults[idx + 1] * bw, 1)
                    span = max(1.0, next_target_kg - threshold_kg)
                    progress_pct = min(100, max(0, int(((user_1rm - threshold_kg) / span) * 100)))
                else:
                    next_tier = "Max Tier (Elite)"
                    next_target_kg = round(threshold_kg, 1)
                    progress_pct = 100

        kg_to_next = max(0.0, round(next_target_kg - user_1rm, 1))
        results.append({
            "exercise": ex_name,
            "e1rm": user_1rm,
            "bw_ratio": bw_ratio,
            "current_tier": current_tier,
            "next_tier": next_tier,
            "next_target_kg": next_target_kg,
            "kg_to_next": kg_to_next,
            "progress_pct": progress_pct
        })

    # Υπολογισμός DOTS Score (από Squat + Bench + Deadlift ή τα αντίστοιχα βασικά lifts)
    squat_max = max(
        best_e1rm.get("Barbell Back Squat", 0.0),
        best_e1rm.get("Barbell Front Squat", 0.0),
        best_e1rm.get("Hack Squat Machine", 0.0),
        best_e1rm.get("Leg Press", 0.0) * 0.65
    )
    bench_max = max(
        best_e1rm.get("Flat Barbell Bench Press", 0.0),
        best_e1rm.get("Flat Dumbbell Chest Press", 0.0) * 1.15,
        best_e1rm.get("Incline DB Bench Press", 0.0) * 1.25
    )
    deadlift_max = max(
        best_e1rm.get("Barbell Deadlift", 0.0),
        best_e1rm.get("Barbell RDL", 0.0) * 1.20,
        best_e1rm.get("Romanian Deadlift (RDL)", 0.0) * 1.30
    )
    sbd_total = round(squat_max + bench_max + deadlift_max, 1)
    dots_score = calc_dots(bw, sbd_total, gender, standards_data.get("dots_coefficients", {}))

    return results, dots_score, sbd_total
