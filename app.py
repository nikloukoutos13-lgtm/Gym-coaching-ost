import os
import json
import math
import random
import requests
import base64
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st
import matplotlib.pyplot as plt

from data_manager import (
    load_all_app_data, 
    save_profile_file, 
    save_settings_file, 
    save_custom_foods_file, 
    save_custom_exercises_file,
    load_json
)

from science_engine import (
    load_strength_standards,
    analyze_fractional_emg_and_profiles,
    evaluate_strength_standards
)

from coaching_engine import (
    load_coaching_rules,
    calc_double_progression,
    calc_weekly_fatigue_and_deload,
    calc_hyrox_splits,
    calc_running_pace_zones
)

STRENGTH_STANDARDS = load_strength_standards()
COACHING_RULES = load_coaching_rules()

# ------------------------------------------------------------------------------
# 1. PAGE CONFIG & STYLING
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Gym Coaching OS",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .main { padding: 0rem 1rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef; }
    div[data-testid="stExpander"] { border: 1px solid #ced4da; border-radius: 8px; }
    .badge-card { background-color: #fff9db; border: 1px solid #f59f00; padding: 4px 10px; border-radius: 12px; margin-right: 5px; font-size: 13px; display: inline-block; }
    .report-card { background-color: #ffffff; color: #111111; border: 2px solid #2b8a3e; padding: 15px; border-radius: 10px; margin-top: 10px; }
    .overload-card { background-color: #e7f5ff; border: 1px solid #339af0; padding: 12px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }
    .zone-badge { padding: 4px 10px; border-radius: 8px; font-weight: bold; color: white; display: inline-block; }
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# LANGUAGE HELPER & DYNAMIC SMART QUIPS
# ------------------------------------------------------------------------------
if "lang" not in st.session_state:
    st.session_state["lang"] = "Ελληνικά"

def t(el_text, en_text):
    return en_text if st.session_state.get("lang") == "English" else el_text

DAYS_EL = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]
DAYS_EN = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]

DAY_MAP_TO_EN = dict(zip(DAYS_EL, DAYS_EN))
DAY_MAP_TO_EL = dict(zip(DAYS_EN, DAYS_EL))

QUIPS_DATA = load_json(os.path.join("data", "quips.json"), {})

def get_smart_workout_quip(ex_summary, total_tonnage, total_cardio_km, total_cardio_mins, user_db):
    """
    Αναλύει τη συνεδρία και επιλέγει τυχαίο σχόλιο με βάση το τι κυριάρχησε:
    1. HYROX / Functional Dominant
    2. Running / Cardio Dominant
    3. Heavy Weightlifting Dominant (Tonnage)
    """
    lang_key_t = "tonnage_en" if st.session_state.get("lang") == "English" else "tonnage_el"
    lang_key_c = "cardio_en" if st.session_state.get("lang") == "English" else "cardio_el"
    
    tonnage_quips = QUIPS_DATA.get(lang_key_t, [])
    cardio_quips = QUIPS_DATA.get(lang_key_c, [])
    
    def pick(val):
        if isinstance(val, list):
            return random.choice(val)
        return val

    hyrox_count = 0
    weight_sets = 0
    main_hyrox_ex = ""
    
    for ex_name, ex_data in ex_summary.items():
        if "(HYROX)" in ex_name:
            hyrox_count += 1
            main_hyrox_ex = ex_name
        
        ex_info = user_db.get(ex_name, {})
        if ex_info.get("type") == "weight":
            weight_sets += ex_data.get("sets", 0)

    # 1. Κυριαρχία HYROX / Functional
    if hyrox_count >= 2 or (hyrox_count == 1 and weight_sets < 6):
        if "Sled Push" in main_hyrox_ex and len(cardio_quips) > 9: return pick(cardio_quips[9][1])
        if "Sled Pull" in main_hyrox_ex and len(cardio_quips) > 10: return pick(cardio_quips[10][1])
        if ("SkiErg" in main_hyrox_ex or "RowErg" in main_hyrox_ex) and len(cardio_quips) > 11: return pick(cardio_quips[11][1])
        if "Burpee" in main_hyrox_ex and len(cardio_quips) > 12: return pick(cardio_quips[12][1])
        if "Wall Balls" in main_hyrox_ex and len(cardio_quips) > 13: return pick(cardio_quips[13][1])
        if "Sandbag" in main_hyrox_ex and len(cardio_quips) > 14: return pick(cardio_quips[14][1])
        if "Farmers" in main_hyrox_ex and len(cardio_quips) > 15: return pick(cardio_quips[15][1])

    # 2. Κυριαρχία Cardio / Τρεξίματος
    if total_cardio_km >= 3.0 or (total_cardio_mins >= 20 and total_tonnage < 2000):
        for limit, text in cardio_quips:
            if total_cardio_km <= limit and limit <= 42: return pick(text)
        return pick(cardio_quips[8][1]) if len(cardio_quips) > 8 else ""

    # 3. Κυριαρχία Βαρών (Tonnage Focus)
    if tonnage_quips:
        for limit, text in tonnage_quips:
            if total_tonnage <= limit: return pick(text)
        return pick(tonnage_quips[-1][1])
        
    return ""

# ------------------------------------------------------------------------------
# 2. PERSISTENCE & USER DATA
# ------------------------------------------------------------------------------
def load_user_data():
    if "user_data" not in st.session_state:
        st.session_state["user_data"] = load_all_app_data()

load_user_data()
user_data = st.session_state["user_data"]

def save_user_data():
    if "user_data" in st.session_state:
        ud = st.session_state["user_data"]
        act_name = ud.get("active_profile", "")
        
        if act_name and act_name in ud.get("profiles", {}):
            save_profile_file(act_name, ud["profiles"][act_name])
            
        save_settings_file(act_name)
        save_custom_foods_file(ud.get("food_db", {}))
        save_custom_exercises_file(ud.get("exercise_database", {}))

        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets and act_name:
            try:
                import re
                token = st.secrets["GITHUB_TOKEN"]
                repo = st.secrets["GITHUB_REPO"]
                
                clean_fname = re.sub(r'[^a-zA-Z0-9_-]', '_', act_name.lower())
                clean_fname = re.sub(r'_+', '_', clean_fname).strip('_')
                file_path = f"user_data/profiles/{clean_fname}.json"
                
                url = f"https://api.github.com/repos/{repo}/contents/{file_path}"
                headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3+json"}
                get_res = requests.get(url, headers=headers, timeout=3)
                sha = get_res.json().get("sha", "") if get_res.status_code == 200 else ""
                
                content_json = json.dumps(ud["profiles"][act_name], ensure_ascii=False, indent=2)
                content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")
                
                payload = {
                    "message": f"🤖 Auto-save profile {act_name}",
                    "content": content_b64,
                    "sha": sha
                }
                requests.put(url, headers=headers, json=payload, timeout=3)
            except Exception:
                pass

active_profile_name = user_data["active_profile"]
active_p = user_data["profiles"].get(active_profile_name, {})

# ------------------------------------------------------------------------------
# 3. HELPER CALCULATORS & STREAKS
# ------------------------------------------------------------------------------
def req_xp_for_level(lvl):
    return int(500 * (lvl ** 1.6))

def get_level_title(lvl):
    titles_el = {
        1: "Gym Novice (Πρωτάρης)", 2: "Iron Enthusiast (Σιδερένιος)", 3: "Hypertrophy Apprentice (Μαθητευόμενος)",
        4: "Bench Press Specialist (Παγκίτης)", 5: "Iron Warrior (Πολεμιστής)", 6: "Volume Monster (Τέρας Όγκου)",
        7: "Local Gym Legend (Θρύλος του Gym)", 8: "Hypertrophy Master (Master Υπερτροφίας)", 9: "Iron God (Θεός του Σιδήρου)", 10: "Titan of Muscle (Τιτάνας)"
    }
    titles_en = {
        1: "Gym Novice", 2: "Iron Enthusiast", 3: "Hypertrophy Apprentice", 4: "Bench Press Specialist",
        5: "Iron Warrior", 6: "Volume Monster", 7: "Local Gym Legend", 8: "Hypertrophy Master", 9: "Iron God", 10: "Titan of Muscle"
    }
    return t(titles_el.get(lvl, f"Overlord Level {lvl}"), titles_en.get(lvl, f"Overlord Level {lvl}"))

def calculate_streak(log_dates_strs):
    if not log_dates_strs: return 0, False
    unique_dates = set()
    for d_str in log_dates_strs:
        try:
            d_part = d_str.split()[0]
            dt = datetime.strptime(d_part, "%d/%m/%Y").date()
            unique_dates.add(dt)
        except Exception:
            pass
    if not unique_dates: return 0, False
    
    sorted_dates = sorted(list(unique_dates), reverse=True)
    today = datetime.now().date()
    yesterday = today - timedelta(days=1)
    
    if sorted_dates[0] != today and sorted_dates[0] != yesterday:
        return 0, False
        
    streak = 0
    curr = sorted_dates[0]
    for d in sorted_dates:
        if d == curr:
            streak += 1
            curr = curr - timedelta(days=1)
        elif d < curr:
            break
    return streak, (sorted_dates[0] == today)

def calc_hr_zone(hr_bpm, age=26):
    max_hr = 211 - (0.64 * age)
    pct = (hr_bpm / max_hr) * 100.0 if max_hr > 0 else 0
    if pct < 60: return t("Zone 1: Active Recovery (50-60%)", "Zone 1: Active Recovery (50-60%)"), "#339af0"
    elif pct < 70: return t("Zone 2: Aerobic Endurance (60-70%)", "Zone 2: Aerobic Endurance (60-70%)"), "#51cf66"
    elif pct < 80: return t("Zone 3: Tempo / Aerobic Capacity (70-80%)", "Zone 3: Tempo / Aerobic Capacity (70-80%)"), "#fcc419"
    elif pct < 90: return t("Zone 4: Threshold / Lactate (80-90%)", "Zone 4: Threshold / Lactate (80-90%)"), "#ff922b"
    else: return t("Zone 5: Anaerobic Max Sprint (90-100%)", "Zone 5: Anaerobic Max Sprint (90-100%)"), "#ff6b6b"

def calc_progressive_overload(ex_name, history, ex_db):
    if not history: return None
    last_perf = None
    for session in reversed(history):
        if "exercises" in session and ex_name in session["exercises"]:
            last_perf = session["exercises"][ex_name]
            break
    if not last_perf or last_perf.get("type") != "weight": return None
    
    max_w = last_perf.get("max_weight", 0.0)
    avg_rir = sum(last_perf.get("rirs", [2])) / max(1, len(last_perf.get("rirs", [2])))
    sets = last_perf.get("sets", 3)
    reps = int(last_perf.get("total_reps_or_min", 36) / max(1, sets))
    is_db = ex_db.get(ex_name, {}).get("is_db", False)
    
    if avg_rir >= 3.0:
        inc = 1.0 if is_db else 2.5
        msg = t(f"🚀 **Υψηλό RIR ({avg_rir:.1f}):** Αύξηση φορτίου κατά +{inc} kg!", f"🚀 **High RIR ({avg_rir:.1f}):** Increase load by +{inc} kg!")
        return {"w": max_w + inc, "r": reps, "msg": msg}
    elif avg_rir >= 1.5:
        inc = 0.5 if is_db else 1.25
        msg = t(f"🎯 **Ιδανικό RIR ({avg_rir:.1f}):** Σταδιακή αύξηση +{inc} kg.", f"🎯 **Optimal RIR ({avg_rir:.1f}):** Increase load by +{inc} kg.")
        return {"w": max_w + inc, "r": reps, "msg": msg}
    else:
        msg = t(f"💪 **Κοντά στο Failure (RIR {avg_rir:.1f}):** Διατήρηση {max_w} kg, στόχος {reps+1} reps.", f"💪 **Near Failure (RIR {avg_rir:.1f}):** Keep {max_w} kg, target {reps+1} reps.")
        return {"w": max_w, "r": reps + 1, "msg": msg}

def calc_macros(prof):
    p_wt, p_ht, p_age = prof.get("weight_kg", 70.0), prof.get("height_cm", 175.0), prof.get("age", 25)
    is_male = prof.get("gender") in ["Άνδρας", "Male"]
    bmr = (10 * p_wt) + (6.25 * p_ht) - (5 * p_age) + 5 if is_male else (10 * p_wt) + (6.25 * p_ht) - (5 * p_age) - 161
    tdee = bmr * prof.get("activity_level", 1.55)
    goal = prof.get("goal", "Bulking")
    target_cal = tdee + 350 if goal in ["Bulking", "Όγκος"] else (tdee - 450 if goal in ["Cutting", "Γράμμωση"] else tdee)
    prot_g = p_wt * (2.2 if goal in ["Cutting", "Γράμμωση"] else 2.0)
    fat_g = (target_cal * 0.25) / 9
    carb_g = (target_cal - (prot_g * 4 + fat_g * 9)) / 4
    return round(bmr), round(tdee), round(target_cal), round(prot_g), round(carb_g), round(fat_g)

def calc_1rm(w, r):
    if r <= 1: return w
    elif r <= 10: return round(w * (1 + r / 30.0), 1)
    else: return round((100 * w) / (48.8 + 53.8 * math.exp(-0.075 * r)), 1)

def calc_cardio_calories(speed_kmh, duration_mins, weight_kg):
    met = 1.0 + (0.875 * speed_kmh)
    return round(met * weight_kg * (duration_mins / 60.0), 1)

def calc_projected_vs_real_weight(profile, weight_log):
    logs = []
    for entry in weight_log:
        try:
            d = datetime.strptime(entry["date"], "%d/%m/%Y")
            logs.append({"date_obj": d, "date_str": entry["date"], "weight": float(entry["weight"])})
        except Exception:
            pass
            
    logs.sort(key=lambda x: x["date_obj"])
    if not logs:
        return [], [], [], t("Δεν υπάρχουν ακόμα καταγραφές βάρους.", "No body weight entries yet.")
        
    start_date = logs[0]["date_obj"]
    start_weight = logs[0]["weight"]
    
    real_dates = []
    moving_avgs = []
    
    for i, entry in enumerate(logs):
        real_dates.append(entry["date_str"])
        window = [logs[j]["weight"] for j in range(max(0, i-6), i+1)]
        moving_avgs.append(round(sum(window) / len(window), 2))
        
    goal = profile.get("goal", "Bulking")
    training_age = profile.get("training_age", "Novice (0-1 yr)")
    
    if goal in ["Bulking", "Όγκος"]:
        weekly_rate = 0.0030 if ("Αρχάριος" in training_age or "Novice" in training_age) else (0.0018 if ("Ενδιάμεσος" in training_age or "Intermediate" in training_age) else 0.0009)
    elif goal in ["Cutting", "Γράμμωση"]:
        weekly_rate = -0.0075
    else:
        weekly_rate = 0.0
        
    projected_weights = []
    for entry in logs:
        days_diff = (entry["date_obj"] - start_date).days
        weeks_diff = days_diff / 7.0
        proj_w = start_weight * ((1 + weekly_rate) ** weeks_diff)
        projected_weights.append(round(proj_w, 2))
        
    status_msg = ""
    if len(logs) >= 2:
        actual_gain_kg = moving_avgs[-1] - start_weight
        projected_gain_kg = projected_weights[-1] - start_weight
        
        if goal in ["Bulking", "Όγκος"]:
            if actual_gain_kg <= 0:
                status_msg = t("⚠️ <b>Υποσιτισμός / Στασιμότητα:</b> Το βάρος δεν αυξάνεται. Προτείνεται αύξηση +200 kcal/ημέρα!", "⚠️ <b>Undereating / Plateau:</b> Weight is not increasing. Consider adding +200 kcal/day!")
            elif actual_gain_kg > (projected_gain_kg * 1.8 + 0.5):
                status_msg = t("🚨 <b>Πολύ γρήγορη αύξηση:</b> Κίνδυνος αυξημένου λίπους. Μειώστε τις θερμίδες κατά -150 kcal/ημέρα.", "🚨 <b>Gaining too fast:</b> Risk of excess fat mass. Lower intake by -150 kcal/day.")
            else:
                status_msg = t("🟢 <b>Ιδανικός Ρυθμός Καθαρής Υπερτροφίας:</b> Το βάρος αυξάνεται σύμφωνα με το μοντέλο!", "🟢 <b>Optimal Lean Hypertrophy Rate:</b> Weight gain matches target curve!")
        elif goal in ["Cutting", "Γράμμωση"]:
            if actual_gain_kg >= 0:
                status_msg = t("⚠️ <b>Στασιμότητα:</b> Δεν παρατηρείται απώλεια. Μειώστε τις θερμίδες κατά -200 kcal/ημέρα.", "⚠️ <b>Plateau:</b> No weight loss observed. Reduce calories by -200 kcal/day.")
            else:
                status_msg = t("🟢 <b>Αποτελεσματική Λιποδιάλυση:</b> Το βάρος μειώνεται σύμφωνα με τον στόχο!", "🟢 <b>Effective Fat Loss:</b> Weight is dropping according to target!")
        else:
            status_msg = t("🟢 <b>Σταθερή Συντήρηση:</b> Το σωματικό βάρος διατηρείται σταθερό.", "🟢 <b>Stable Maintenance:</b> Body weight remains consistent.")
            
    return real_dates, moving_avgs, projected_weights, status_msg

def check_and_unlock_achievements(total_tonnage):
    unlocked = []
    current_achs = active_p.get("achievements", [])
    
    pr_name = t("🏆 First Blood (Πρώτο PR)", "🏆 First Blood (First PR)")
    if active_p.get("prs") and pr_name not in current_achs:
        unlocked.append(t("🏆 First Blood (Έσπασες το πρώτο σου ατομικό ρεκόρ!)", "🏆 First Blood (Broke your first personal record!)"))
        current_achs.append(pr_name)
        
    ton10_name = "🏋️ 10 Ton Club"
    if total_tonnage >= 10000 and ton10_name not in current_achs:
        unlocked.append(t("🏋️ 10 Ton Club (Σήκωσες πάνω από 10.000 kg σε μία συνεδρία!)", "🏋️ 10 Ton Club (Lifted over 10,000 kg in a single workout!)"))
        current_achs.append(ton10_name)

    ton25_name = "🐘 25 Ton Titan"
    if total_tonnage >= 25000 and ton25_name not in current_achs:
        unlocked.append(t("🐘 25 Ton Titan (Ξεπέρασες τα 25.000 kg σε μία προπόνηση!)", "🐘 25 Ton Titan (Crossed 25,000 kg in one session!)"))
        current_achs.append(ton25_name)

    scale_name = "⚖️ Scale Master"
    if len(active_p.get("weight_log", [])) >= 7 and scale_name not in current_achs:
        unlocked.append(t("⚖️ Scale Master (Κατέγραψες το βάρος σου για 7+ ημέρες!)", "⚖️ Scale Master (Logged body weight for 7+ days!)"))
        current_achs.append(scale_name)

    active_p["achievements"] = current_achs
    return unlocked

def generate_post_workout_quiz(logged_exercises, exercise_db, trivia_db):
    """Δημιουργεί context-aware ερώτηση (Dynamic Session ή Curated Theory Bank)."""
    static_questions = trivia_db.get("questions", [])
    
    valid_session_exs = [
        ex for ex in logged_exercises
        if ex in exercise_db and exercise_db[ex].get("primary") not in (None, "Cardio", "Full Body")
    ]
    
    # 50% πιθανότητα για δυναμική ερώτηση από τις σημερινές ασκήσεις
    if valid_session_exs and (random.random() < 0.5 or not static_questions):
        chosen_ex = random.choice(valid_session_exs)
        ex_info = exercise_db[chosen_ex]
        primary_m = ex_info.get("primary")
        secondary_m = ex_info.get("secondary")
        res_prof = ex_info.get("resistance_profile", "Mid-range")
        
        all_muscles = [
            "Chest", "Upper Back", "Lats", "Quads", "Hamstrings", "Glutes",
            "Front Delts", "Side Delts", "Rear Delts", "Biceps", "Triceps", "Abs", "Lower Back"
        ]
        
        # Επιλογή τύπου δυναμικής ερώτησης: Primary, Secondary (αν υπάρχει) ή Resistance Profile
        q_modes = ["primary"]
        if secondary_m:
            q_modes.append("secondary")
        if res_prof in ("Lengthened-biased", "Shortened-biased", "Mid-range"):
            q_modes.append("profile")
            
        mode = random.choice(q_modes)
        
        if mode == "secondary":
            distractors = [m for m in all_muscles if m not in (primary_m, secondary_m)]
            options = [secondary_m] + random.sample(distractors, 3)
            random.shuffle(options)
            return {
                "category": "🎯 Συνεργιστικοί Μύες (Synergists)",
                "q": f"Στη σημερινή άσκηση **{chosen_ex}**, ποιος μυς λειτουργεί ΔΕΥΤΕΡΕΥΟΝΤΩΣ (Secondary) υποστηρίζοντας τους {primary_m};",
                "options": options,
                "answer": secondary_m,
                "explanation": f"Στην άσκηση **{chosen_ex}**, τον κύριο όγκο αναλαμβάνουν οι **{primary_m}**, ενώ συνεργιστικά συμμετέχουν οι **{secondary_m}**."
            }
        elif mode == "profile":
            profiles = ["Lengthened-biased", "Shortened-biased", "Mid-range", "Isometric"]
            options = profiles.copy()
            random.shuffle(options)
            return {
                "category": "📐 Εμβιομηχανική & Resistance Profile",
                "q": f"Ποιο είναι το προφίλ αντίστασης (Resistance Profile) της άσκησης **{chosen_ex}**;",
                "options": options,
                "answer": res_prof,
                "explanation": f"Η άσκηση **{chosen_ex}** έχει προφίλ αντίστασης **{res_prof}**, δείχνοντας σε ποιο σημείο της τροχιάς κορυφώνεται η μηχανική τάση στους **{primary_m}**."
            }
        else:
            distractors = [m for m in all_muscles if m != primary_m]
            options = [primary_m] + random.sample(distractors, 3)
            random.shuffle(options)
            sec_text = f" ενώ συνεργιστικά δουλεύουν οι **{secondary_m}**" if secondary_m else ""
            return {
                "category": "🎯 Ανάλυση Σημερινής Άσκησης",
                "q": f"Στη σημερινή προπόνηση εκτέλεσες **{chosen_ex}**. Ποιος είναι ο ΚΥΡΙΟΣ (Primary) μυς-στόχος αυτής της άσκησης;",
                "options": options,
                "answer": primary_m,
                "explanation": f"Η άσκηση **{chosen_ex}** στοχεύει πρωτευόντως τους **{primary_m}**{sec_text}. Προφίλ αντίστασης: **{res_prof}**."
            }

    # Static Theory Bank με context-aware προτεραιότητα (HYROX/Running vs Hypertrophy)
    if static_questions:
        is_endurance_session = any(
            "(HYROX)" in ex or exercise_db.get(ex, {}).get("type") == "cardio"
            for ex in logged_exercises
        )
        target_tags = {"hyrox", "running"} if is_endurance_session else {"hypertrophy", "anatomy", "biomechanics"}
        matched = [q for q in static_questions if target_tags.intersection(set(q.get("tags", [])))]
        
        pool = matched if (matched and random.random() < 0.75) else static_questions
        chosen_q = dict(random.choice(pool))
        opts = list(chosen_q["options"])
        random.shuffle(opts)
        chosen_q["options"] = opts
        return chosen_q
        
    return None
# ------------------------------------------------------------------------------
# 4. SIDEBAR MANAGEMENT
# ------------------------------------------------------------------------------
with st.sidebar:
    st.subheader(t("🌐 Γλώσσα / Language", "🌐 Language / Γλώσσα"))
    lang_choice = st.selectbox(
        "Select Language:",
        ["Ελληνικά", "English"],
        index=0 if st.session_state["lang"] == "Ελληνικά" else 1,
        label_visibility="collapsed"
    )
    if lang_choice != st.session_state["lang"]:
        st.session_state["lang"] = lang_choice
        st.rerun()

    st.divider()
    st.subheader(t("👤 Διαχείριση Προφίλ", "👤 Profile Management"))
    
    profile_list = list(user_data["profiles"].keys())
    curr_index = profile_list.index(active_profile_name) if active_profile_name in profile_list else 0
    
    selected_prof = st.selectbox(t("Επιλογή Ενεργού Προφίλ:", "Select Active Profile:"), profile_list, index=curr_index)
    if selected_prof != active_profile_name:
        user_data["active_profile"] = selected_prof
        save_user_data()
        st.rerun()

    history_dates = [h.get("date", "") for h in active_p.get("history", [])] + [w.get("date", "") for w in active_p.get("weight_log", [])]
    streak_days, logged_today = calculate_streak(history_dates)
    
    st.markdown(f"### 🔥 Streak: **{streak_days} {t('Ημέρες', 'Days')}**")
    if logged_today:
        st.success(t("✅ Κατέγραψες δεδομένα σήμερα!", "✅ Data logged today!"))
    else:
        st.warning(t("⚠️ Κατέγραψε βάρος/προπόνηση για να κρατήσεις το streak!", "⚠️ Log weight or workout to maintain streak!"))

    st.divider()
    with st.expander(t("➕ Προσθήκη Νέου Προφίλ", "➕ Add New Profile")):
        new_prof_name = st.text_input(t("Όνομα νέου προφίλ:", "New profile name:"))
        new_prof_type = st.selectbox(t("Τύπος Προγράμματος:", "Program Type:"), ["Gym & Hypertrophy", "HYROX & Running"])
        if st.button(t("Δημιουργία Προφίλ", "Create Profile")):
            if new_prof_name.strip() and new_prof_name.strip() not in user_data["profiles"]:
                new_template = {
                    "profile": {
                        "gender": t("Άνδρας", "Male"), "age": 25, "weight_kg": 70.0, "height_cm": 175.0,
                        "activity_level": 1.55, "goal": "Cutting" if "HYROX" in new_prof_type else "Bulking",
                        "training_age": t("Αρχάριος (0-1 έτος)", "Novice (0-1 yr)"), "xp": 0, "level": 1
                    },
                    "daily_logs": [],
                    "weight_log": [{"date": datetime.now().strftime("%d/%m/%Y"), "weight": 70.0}],
                    "templates": {day: [] for day in DAYS_EL},
                    "prs": {}, "achievements": [], "history": []
                }
                user_data["profiles"][new_prof_name.strip()] = new_template
                user_data["active_profile"] = new_prof_name.strip()
                save_user_data()
                st.success(t(f"Το προφίλ '{new_prof_name}' δημιουργήθηκε!", f"Profile '{new_prof_name}' created successfully!"))
                st.rerun()
            else:
                st.warning(t("Παρακαλώ δώσε μοναδικό όνομα.", "Please enter a unique name."))

    st.divider()
    st.subheader(t("⚙️ Διαχείριση Δεδομένων & Backup", "⚙️ Data & Backup Management"))
    json_str = json.dumps(active_p, ensure_ascii=False, indent=2)
    st.download_button(f"📥 Download {active_profile_name}.json", data=json_str, file_name=f"{active_profile_name}.json", mime="application/json")
    
    uploaded_json = st.file_uploader(t("📤 Restore Προφίλ JSON", "📤 Restore Profile JSON"), type=["json"])
    if uploaded_json is not None:
        try:
            data = json.load(uploaded_json)
            if "profile" in data:
                user_data["profiles"][active_profile_name] = data
                save_user_data()
                st.success(t("✅ Restore επιτυχές!", "✅ Restore successful!"))
                st.rerun()
        except Exception:
            st.error(t("❌ Σφάλμα αρχείου JSON.", "❌ JSON file error."))

# ------------------------------------------------------------------------------
# 5. MAIN UI & TABS
# ------------------------------------------------------------------------------
st.title("🏋️ GYM & HYROX COACHING OS")
st.caption(f"{t('Ενεργό Προφίλ', 'Active Profile')}: **{active_profile_name}**")

tab1, tab_tracker, tab2, tab3 = st.tabs([
    t("🎮 Dashboard & Βάρος", "🎮 Dashboard & Weight"), 
    t("🥗 Daily Nutrition Tracker", "🥗 Daily Nutrition Tracker"), 
    t("🏋️ Schedule & Workout Tracker", "🏋️ Schedule & Workout Tracker"), 
    t("📊 Visual Analytics & HR Zones", "📊 Visual Analytics & HR Zones")
])

# ==============================================================================
# TAB 1: DASHBOARD & BODY WEIGHT
# ==============================================================================
with tab1:
    prof = active_p.get("profile", {})
    lvl = prof.get("level", 1)
    title = get_level_title(lvl)
    req_xp = req_xp_for_level(lvl)
    curr_xp = prof.get("xp", 0)
    
    st.markdown(f"### 🎮 Level {lvl} — {title}")
    st.progress(min(1.0, curr_xp / req_xp if req_xp > 0 else 0.0))
    st.caption(f"Progress: {curr_xp} / {req_xp} XP (Stricter Exponential Scaling Active)")
    
    achs = active_p.get("achievements", [])
    if achs:
        badge_html = "".join([f"<span class='badge-card'>{a}</span>" for a in achs])
        st.markdown(f"**🎖️ {t('Παράσημα', 'Badges')} ({len(achs)}):** {badge_html}", unsafe_allow_html=True)
        
    st.divider()
    
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        st.subheader(t("⚖️ Πρωινό Ζύγισμα (Νηστικός)", "⚖️ Morning Weigh-in (Fasted)"))
        today_val = st.number_input(t("Σημερινό Βάρος (kg):", "Today's Weight (kg):"), value=float(prof.get("weight_kg", 70.0)), step=0.1, key=f"daily_w_in_{active_profile_name}")
        if st.button(t("⚖️ Καταγραφή Βάρους", "⚖️ Log Weight"), key=f"btn_w_log_{active_profile_name}"):
            today_str = datetime.now().strftime("%d/%m/%Y")
            logs = active_p.get("weight_log", [])
            found = False
            for entry in logs:
                if entry["date"] == today_str:
                    entry["weight"] = today_val
                    found = True
                    break
            if not found:
                logs.append({"date": today_str, "weight": today_val})
            active_p["weight_log"] = logs
            active_p["profile"]["weight_kg"] = today_val
            
            active_p["profile"]["xp"] += 15
            save_user_data()
            st.success(t(f"✅ Καταγράφηκε: {today_val} kg για τις {today_str}!", f"✅ Logged: {today_val} kg for {today_str}!"))
            st.rerun()

    _, _, _, status_msg = calc_projected_vs_real_weight(prof, active_p.get("weight_log", []))
    if status_msg:
        st.info(status_msg, icon="📊")

    st.divider()
    st.subheader(t("⚙️ Προσωπικά Στοιχεία & Στόχοι", "⚙️ Personal Info & Goals"))
    
    with st.form(key=f"profile_form_{active_profile_name}"):
        c1, c2 = st.columns(2)
        with c1:
            g_options = [t("Άνδρας", "Male"), t("Γυναίκα", "Female")]
            g_idx = 0 if prof.get("gender") in ["Άνδρας", "Male"] else 1
            gender = st.selectbox(t("Φύλο", "Gender"), g_options, index=g_idx)
            age = st.number_input(t("Ηλικία", "Age"), value=int(prof.get("age", 25)), step=1)
            height = st.number_input(t("Ύψος (cm)", "Height (cm)"), value=float(prof.get("height_cm", 175.0)), step=0.5)
            weight = st.number_input(t("Βάρος (kg)", "Weight (kg)"), value=float(prof.get("weight_kg", 70.0)), step=0.1)
        with c2:
            goal_opts = [t("Bulking", "Bulking"), t("Cutting", "Cutting"), t("Συντήρηση", "Maintenance")]
            curr_goal = prof.get("goal", "Bulking")
            goal_idx = 0 if curr_goal in ["Bulking", "Όγκος"] else (1 if curr_goal in ["Cutting", "Γράμμωση"] else 2)
            goal = st.selectbox(t("Στόχος", "Goal"), goal_opts, index=goal_idx)
            
            train_opts = [t("Αρχάριος (0-1 έτος)", "Novice (0-1 yr)"), t("Ενδιάμεσος (1-3 έτη)", "Intermediate (1-3 yrs)"), t("Προχωρημένος (3+ έτη)", "Advanced (3+ yrs)")]
            curr_t_age = prof.get("training_age", "")
            t_idx = 0 if "Αρχάριος" in curr_t_age or "Novice" in curr_t_age else (1 if "Ενδιάμεσος" in curr_t_age or "Intermediate" in curr_t_age else 2)
            train_age = st.selectbox(t("Επίπεδο", "Experience Level"), train_opts, index=t_idx)
            
            act_level_val = prof.get("activity_level", 1.55)
            act_idx = [1.2, 1.375, 1.55, 1.725].index(act_level_val) if act_level_val in [1.2, 1.375, 1.55, 1.725] else 2
            act_opts = [
                (t("Καθιστική (1.2)", "Sedentary (1.2)"), 1.2),
                (t("Ελαφριά (1.375)", "Lightly Active (1.375)"), 1.375),
                (t("Μέτρια (1.55)", "Moderately Active (1.55)"), 1.55),
                (t("Υψηλή (1.725)", "Very Active (1.725)"), 1.725)
            ]
            act_level = st.selectbox(t("Δραστηριότητα", "Activity Level"), act_opts, index=act_idx, format_func=lambda x: x[0])[1]
            
        btn_save_p = st.form_submit_button(t("💾 Αποθήκευση Προφίλ", "💾 Save Profile"))
        if btn_save_p:
            prof["gender"] = gender
            prof["age"] = age
            prof["height_cm"] = height
            prof["weight_kg"] = weight
            prof["goal"] = goal
            prof["training_age"] = train_age
            prof["activity_level"] = act_level
            save_user_data()
            st.success(t("✅ Το προφίλ ενημερώθηκε επιτυχώς!", "✅ Profile updated successfully!"))
            st.rerun()

    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(prof)
    st.markdown(t("#### 📊 Στόχοι Μεταβολισμού (Mifflin-St Jeor):", "#### 📊 Metabolism Targets (Mifflin-St Jeor):"))
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("BMR", f"{bmr} kcal")
    m2.metric("TDEE", f"{tdee} kcal")
    m3.metric(t("Στόχος Calories", "Target Calories"), f"{target_cal} kcal", f"{prof.get('goal')}")
    m4.metric("Macros (P/C/F)", f"{prot_g}g / {carb_g}g / {fat_g}g")

# ==============================================================================
# TAB 2: DAILY NUTRITION TRACKER
# ==============================================================================
with tab_tracker:
    st.title(t("🥗 Daily Nutrition & Protein Tracker", "🥗 Daily Nutrition & Protein Tracker"))
    st.caption(f"{t('Διατροφή για', 'Nutrition for')} **{active_profile_name}**")

    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(active_p.get("profile", {}))

    totals = {"cal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
    for log in active_p.get("daily_logs", []):
        totals["cal"] += log.get("cal", 0.0)
        totals["p"] += log.get("p", 0.0)
        totals["c"] += log.get("c", 0.0)
        totals["f"] += log.get("f", 0.0)

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        p_rem = max(0.0, prot_g - totals["p"])
        st.metric(f"{t('Πρωτεΐνη', 'Protein')} ({t('Στόχος', 'Target')}: {prot_g}g)", f"{totals['p']:.1f}g", f"{t('Λείπουν', 'Remaining')} {p_rem:.1f}g", delta_color="inverse" if p_rem > 0 else "normal")
        st.progress(min(1.0, totals["p"] / prot_g if prot_g > 0 else 0.0))

    with col2:
        cal_rem = max(0.0, target_cal - totals["cal"])
        st.metric(f"{t('Θερμίδες', 'Calories')} ({t('Στόχος', 'Target')}: {target_cal}kcal)", f"{int(totals['cal'])} kcal", f"{t('Λείπουν', 'Remaining')} {int(cal_rem)} kcal")
        st.progress(min(1.0, totals["cal"] / target_cal if target_cal > 0 else 0.0))

    with col3:
        c_rem = max(0.0, carb_g - totals["c"])
        st.metric(f"{t('Υδατάνθρακες', 'Carbs')} ({t('Στόχος', 'Target')}: {carb_g}g)", f"{totals['c']:.1f}g", f"{t('Λείπουν', 'Remaining')} {c_rem:.1f}g")
        st.progress(min(1.0, totals["c"] / carb_g if carb_g > 0 else 0.0))

    with col4:
        f_rem = max(0.0, fat_g - totals["f"])
        st.metric(f"{t('Λιπαρά', 'Fats')} ({t('Στόχος', 'Target')}: {fat_g}g)", f"{totals['f']:.1f}g", f"{t('Λείπουν', 'Remaining')} {f_rem:.1f}g")
        st.progress(min(1.0, totals["f"] / fat_g if fat_g > 0 else 0.0))

    if totals["p"] >= prot_g and prot_g > 0:
        st.success(t(f"🎉 Συγχαρητήρια! Κάλυψες τον ημερήσιο στόχο πρωτεΐνης ({prot_g}g)!", f"🎉 Congratulations! You reached your daily protein goal ({prot_g}g)!"))

    st.markdown("---")

    st.subheader(t("➕ Καταγραφή Γεύματος", "➕ Log Meal"))
    c_select, c_qty, c_btn = st.columns([3, 1.5, 1])
    food_db = user_data["food_db"]

    with c_select:
        selected_name = st.selectbox(t("Επίλεξε Τρόφιμο:", "Select Food Item:"), list(food_db.keys()), key=f"f_select_{active_profile_name}")
        food_info = food_db.get(selected_name, {"unit": "100g", "cal": 100, "p": 10, "c": 10, "f": 2})

    with c_qty:
        if food_info["unit"] == "100g":
            qty = st.number_input(t("Γραμμάρια (g):", "Grams (g):"), min_value=10, max_value=1000, value=150, step=10, key=f"qty_g_{active_profile_name}")
            factor = qty / 100.0
            unit_str = f"{qty}g"
        else:
            qty = st.number_input(t("Τεμάχια / Μερίδες:", "Servings / Items:"), min_value=0.5, max_value=10.0, value=1.0, step=0.5, key=f"qty_p_{active_profile_name}")
            factor = qty
            unit_str = f"{qty} {t('τεμάχιο/α', 'item(s)')}"

    with c_btn:
        st.write("")
        st.write("")
        if st.button(t("Προσθήκη ➕", "Add ➕"), key=f"btn_add_food_{active_profile_name}"):
            calc_item = {
                "name": selected_name,
                "portion": unit_str,
                "cal": food_info["cal"] * factor,
                "p": food_info["p"] * factor,
                "c": food_info["c"] * factor,
                "f": food_info["f"] * factor,
            }
            active_p["daily_logs"].append(calc_item)
            save_user_data()
            st.rerun()

    with st.expander(t("✨ Πρόσθεσε Νέο Τρόφιμο στη Βάση Δεδομένων (Custom Food Creator)", "✨ Add Custom Food to Database")):
        c_n, c_u = st.columns([3, 1])
        new_name = c_n.text_input(t("Όνομα Προϊόντος (π.χ. Tesco High Protein Pudding):", "Food Item Name (e.g., High Protein Yoghurt):"), key="cf_name")
        new_unit = c_u.selectbox(t("Μονάδα μέτρησης:", "Serving Unit:"), ["100g", "piece"], key="cf_unit")
        
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        new_cal = col_c1.number_input(t("Θερμίδες (kcal):", "Calories (kcal):"), min_value=0.0, value=100.0, key="cf_cal")
        new_p = col_c2.number_input(t("Πρωτεΐνη (g):", "Protein (g):"), min_value=0.0, value=10.0, key="cf_p")
        new_c = col_c3.number_input(t("Υδατάνθρακες (g):", "Carbs (g):"), min_value=0.0, value=10.0, key="cf_c")
        new_f = col_c4.number_input(t("Λιπαρά (g):", "Fats (g):"), min_value=0.0, value=2.0, key="cf_f")
        
        if st.button(t("💾 Αποθήκευση στη Βάση", "💾 Save to Database"), key="btn_save_custom_food"):
            if new_name.strip():
                user_data["food_db"][new_name.strip()] = {
                    "unit": new_unit, "cal": new_cal, "p": new_p, "c": new_c, "f": new_f
                }
                save_user_data()
                st.success(t(f"Το '{new_name}' προστέθηκε επιτυχώς στη βάση δεδομένων!", f"'{new_name}' added to food database!"))
                st.rerun()
            else:
                st.warning(t("Παρακαλώ δώσε ένα όνομα στο νέο προϊόν.", "Please give a name to the food item."))

    st.markdown("---")
    st.subheader(t("📋 Τι κατέγραψες σήμερα:", "📋 Today's Logged Meals:"))

    if active_p.get("daily_logs"):
        rows_to_del_food = []
        for idx, item in enumerate(active_p["daily_logs"]):
            c_desc, c_del = st.columns([5, 1])
            with c_desc:
                st.write(
                    f"• **{item['name']}** ({item['portion']}) -> **{item.get('p', 0.0):.1f}g P** | {int(item.get('cal', 0.0))} kcal | {item.get('c', 0.0):.1f}g C | {item.get('f', 0.0):.1f}g F"
                )
            with c_del:
                if st.button("🗑️", key=f"del_food_{active_profile_name}_{idx}"):
                    rows_to_del_food.append(idx)
        
        if rows_to_del_food:
            for i in sorted(rows_to_del_food, reverse=True):
                active_p["daily_logs"].pop(i)
            save_user_data()
            st.rerun()
    else:
        st.info(t("Δεν έχεις καταγράψει ακόμα κάποιο γεύμα σήμερα.", "No meals logged yet today."))

    st.write("")
    if st.button(t("🔄 Επαναφορά (Μηδενισμός Νέας Ημέρας)", "🔄 Reset Day (Clear Meals)"), key=f"btn_reset_day_{active_profile_name}"):
        active_p["daily_logs"] = []
        save_user_data()
        st.rerun()

# ==============================================================================
# TAB 3: WORKOUT TRACKER & AUTO OVERLOAD
# ==============================================================================
with tab2:
    st.subheader(t("🏋️ Καταγραφή Προπόνησης (Πλήρες 7-Ημερο Schedule)", "🏋️ Workout Tracker (7-Day Schedule)"))
    
    day_options = DAYS_EN if st.session_state.get("lang") == "English" else DAYS_EL
    day_selected_label = st.selectbox(t("📅 Επιλογή Ημέρας:", "📅 Select Day:"), day_options, key=f"day_select_{active_profile_name}")
    
    if st.session_state.get("lang") == "English":
        day_selected = DAY_MAP_TO_EL.get(day_selected_label, "Δευτέρα")
    else:
        day_selected = day_selected_label
    
    if "templates" not in active_p:
        active_p["templates"] = {}
    if day_selected not in active_p["templates"]:
        active_p["templates"][day_selected] = []
        
    current_list = active_p["templates"][day_selected]
    
    st.markdown(f"##### {t('📋 Ασκήσεις Ημέρας:', '📋 Day Exercises:')}")
    ex_options = list(user_data["exercise_database"].keys())
    
    rows_to_delete = []

    # --- SYSTEMIC FATIGUE & 1-CLICK DELOAD ENGINE ---
    fatigue_info = calc_weekly_fatigue_and_deload(active_p.get("history", []), user_data["exercise_database"], COACHING_RULES)
    f_col1, f_col2 = st.columns([3, 1])
    with f_col1:
        st.markdown(
            f"<div style='padding:10px 14px; border-left:4px solid {fatigue_info['color']}; background:rgba(255,255,255,0.04); border-radius:6px; margin-bottom:10px;'>"
            f"<b>🧠 7-Day Fatigue Index:</b> {fatigue_info['score']} pts (Axial/CNS: {fatigue_info['axial_score']} pts | {fatigue_info['sets_7d']} σετ)<br>"
            f"<span style='color:{fatigue_info['color']}; font-weight:600;'>{fatigue_info['status']}</span>"
            f"</div>",
            unsafe_allow_html=True
        )
    with f_col2:
        if st.button("🔋 Deload (-40% Σετ)", key=f"deload_btn_{active_profile_name}_{day_selected}", use_container_width=True):
            mult = fatigue_info.get("deload_mult", 0.6)
            for ex_it in current_list:
                ex_it["s"] = max(1, int(round(ex_it.get("s", 3) * mult)))
            save_user_data()
            st.toast("✅ Εφαρμόστηκε Deload (-40% σετ) στο σημερινό πρόγραμμα!")
            st.rerun()
    
    for idx, item in enumerate(current_list):
        prof_key_id = active_profile_name.replace(" ", "_").replace("(", "").replace(")", "")
        ex_name = item["ex"]
        ex_info = user_data["exercise_database"].get(ex_name, {})
        ex_type = ex_info.get("type", "weight")
        
        overload_info = calc_double_progression(ex_name, item, active_p.get("history", []), user_data["exercise_database"], COACHING_RULES)
        
        with st.expander(f"🔹 #{idx+1} {ex_name}", expanded=True):
            if overload_info:
                st.markdown(f"<div class='overload-card'>⚡ <b>{t('Auto Progressive Overload Πρόταση:', 'Auto Progressive Overload Suggestion:')}</b><br>{overload_info['msg']}<br>{t('Στόχος Επόμενης Προπόνησης:', 'Target for next workout:')} <b>{overload_info['w']} kg x {overload_info['r']} reps</b></div>", unsafe_allow_html=True)
                if st.button(f"⚡ {t('Εφαρμογή Target', 'Apply Overload Target')} ({overload_info['w']}kg)", key=f"ov_btn_{prof_key_id}_{day_selected}_{idx}"):
                    item["w"] = overload_info["w"]
                    item["r"] = overload_info["r"]
                    save_user_data()
                    st.rerun()

            col_ex, col_s, col_w, col_r, col_rir, col_del = st.columns([4, 1, 1, 1, 1, 1])
            
            with col_ex:
                if ex_options:
                    all_muscles = ["Όλες οι κατηγορίες"] + sorted(list(set(
                        info.get("muscle", "Άλλο") 
                        for info in user_data["exercise_database"].values() 
                        if info.get("muscle")
                    )))
                    
                    curr_muscle = ex_info.get("muscle", "Όλες οι κατηγορίες")
                    default_cat_idx = all_muscles.index(curr_muscle) if curr_muscle in all_muscles else 0
                    
                    c_cat, c_ex = st.columns(2)
                    
                    with c_cat:
                        sel_cat = st.selectbox(
                            t("Μυϊκή Ομάδα", "Category"),
                            options=all_muscles,
                            index=default_cat_idx,
                            key=f"cat_{prof_key_id}_{day_selected}_{idx}"
                        )
                    
                    if sel_cat == "Όλες οι κατηγορίες":
                        filtered_exs = sorted(list(user_data["exercise_database"].keys()))
                    else:
                        filtered_exs = sorted([
                            k for k, v in user_data["exercise_database"].items()
                            if v.get("muscle") == sel_cat or v.get("primary") == sel_cat
                        ])
                    
                    if not filtered_exs:
                        filtered_exs = sorted(list(user_data["exercise_database"].keys()))
                        
                    curr_ex_val = ex_name if ex_name in filtered_exs else filtered_exs[0]
                    ex_idx = filtered_exs.index(curr_ex_val)
                    
                    with c_ex:
                        new_ex = st.selectbox(
                            t("Άσκηση", "Exercise"), 
                            options=filtered_exs, 
                            index=ex_idx, 
                            key=f"ex_{prof_key_id}_{day_selected}_{idx}"
                        )
                        item["ex"] = new_ex
                else:
                    st.warning(t("⚠️ Κενή βάση ασκήσεων", "⚠️ Empty exercise database"))
                    item["ex"] = ex_name
                
            with col_s:
                item["s"] = st.number_input("Sets", value=int(item.get("s", 3)), min_value=1, max_value=20, key=f"s_{prof_key_id}_{day_selected}_{idx}")
            
            with col_w:
                if ex_type == "cardio":
                    item["w"] = st.number_input(t("Απόσταση (Km)", "Distance (Km)"), value=float(item.get("w", 5.0)), step=0.5, key=f"w_{prof_key_id}_{day_selected}_{idx}")
                elif "bodyweight" in ex_type:
                    st.number_input("Kg", value=0.0, disabled=True, key=f"w_{prof_key_id}_{day_selected}_{idx}")
                    item["w"] = 0.0
                else:
                    item["w"] = st.number_input("Kg", value=float(item.get("w", 20.0)), step=0.5, key=f"w_{prof_key_id}_{day_selected}_{idx}")
                    
            with col_r:
                if ex_type == "bodyweight_time":
                    item["r"] = st.number_input("Sec", value=int(item.get("r", 60)), step=5, key=f"r_{prof_key_id}_{day_selected}_{idx}")
                elif ex_type == "cardio":
                    item["r"] = st.number_input(t("Διάρκεια (Min)", "Duration (Min)"), value=int(item.get("r", 25)), step=1, key=f"r_{prof_key_id}_{day_selected}_{idx}")
                else:
                    item["r"] = st.number_input("Reps", value=int(item.get("r", 12)), step=1, key=f"r_{prof_key_id}_{day_selected}_{idx}")
                    
            with col_rir:
                if ex_type == "cardio":
                    item["hr"] = st.number_input(t("Μέσοι Παλμοί (HR)", "Avg HR (bpm)"), value=int(item.get("hr", 145)), min_value=60, max_value=220, key=f"hr_{prof_key_id}_{day_selected}_{idx}")
                else:
                    item["rir"] = st.number_input("RIR", value=int(item.get("rir", 2)), min_value=0, max_value=5, key=f"rir_{prof_key_id}_{day_selected}_{idx}")
                
            with col_del:
                st.write("")
                st.write("")
                if st.button("❌", key=f"del_{prof_key_id}_{day_selected}_{idx}"):
                    rows_to_delete.append(idx)

            if ex_type == "cardio" and item.get("w", 0) > 0 and item.get("r", 0) > 0:
                dist = item["w"]
                mins = item["r"]
                pace_dec = mins / dist
                pace_m = int(pace_dec)
                pace_s = int((pace_dec - pace_m) * 60)
                z_name, z_color = calc_hr_zone(item.get("hr", 145), active_p.get("profile", {}).get("age", 25))
                
                st.info(f"🏃 **Pace:** {pace_m}:{pace_s:02d} min/km | **Speed:** {60/pace_dec:.1f} km/h | **HR Zone:** <span style='color:{z_color}; font-weight:bold;'>{z_name}</span>", icon="⚡")

    if rows_to_delete:
        for i in sorted(rows_to_delete, reverse=True):
            current_list.pop(i)
        save_user_data()
        st.rerun()

    c_btn1, c_btn2, c_btn3 = st.columns(3)
    with c_btn1:
        if st.button(t("➕ Προσθήκη Extra Άσκησης", "➕ Add Extra Exercise")):
            if ex_options:
                current_list.append({"ex": ex_options[0], "s": 3, "w": 20.0, "r": 12, "rir": 2})
                save_user_data()
                st.rerun()
            else:
                st.error(t("⚠️ Δεν υπάρχουν διαθέσιμες ασκήσεις στη βάση δεδομένων!", "⚠️ No exercises available in database!"))

    with c_btn2:
        if st.button(t("💾 Αποθήκευση Αλλαγών Προγράμματος", "💾 Save Workout Schedule")):
            save_user_data()
            st.success(t("✅ Οι αλλαγές στο πρόγραμμα αποθηκεύτηκαν επιτυχώς!", "✅ Workout schedule changes saved!"))

    with c_btn3:
        btn_digest = st.button(t("🔥 Ολοκλήρωση & Αποθήκευση", "🔥 Complete & Log Workout"), type="primary")

    if btn_digest:
        if not current_list:
            st.error(t("⚠️ Η λίστα ασκήσεων είναι κενή!", "⚠️ Exercise list is empty!"))
        else:
            total_tonnage = 0
            total_cardio_cal = 0
            total_cardio_km = 0.0
            total_cardio_mins = 0
            ex_summary = {}
            pr_alerts = []
            effective_sets = 0
            bonus_pr_xp = 0
            
            for item in current_list:
                ex = item["ex"]
                s = item["s"]
                w = item["w"]
                r = item["r"]
                rir = item.get("rir", 2)
                
                if rir <= 3: effective_sets += s
                ex_info = user_data["exercise_database"].get(ex, {})
                ex_type = ex_info.get("type", "weight")
                is_db = ex_info.get("is_db", False)
                muscle = ex_info.get("muscle", "General")
                
                cardio_cal = 0
                e1rm = 0
                
                if ex_type == "cardio":
                    total_cardio_km += w
                    total_cardio_mins += r
                    cardio_cal = calc_cardio_calories(60.0 / (r / max(0.1, w)) if w > 0 else 9.0, r, active_p.get("profile", {}).get("weight_kg", 70.0))
                    total_cardio_cal += cardio_cal
                elif ex_type == "weight":
                    eff_w = w * 2 if is_db else w
                    total_tonnage += s * eff_w * r
                    e1rm = calc_1rm(eff_w, r)
                    
                if ex not in ex_summary:
                    ex_summary[ex] = {"sets": 0, "max_1rm": 0, "max_weight": w, "rirs": [], "total_reps_or_min": 0, "type": ex_type, "muscle": muscle, "cal": 0}
                    
                ex_summary[ex]["sets"] += s
                ex_summary[ex]["total_reps_or_min"] += r
                ex_summary[ex]["rirs"].append(rir)
                ex_summary[ex]["cal"] += cardio_cal
                if w > ex_summary[ex]["max_weight"]: ex_summary[ex]["max_weight"] = w
                if e1rm > ex_summary[ex]["max_1rm"]: ex_summary[ex]["max_1rm"] = e1rm

            quip_msg = get_smart_workout_quip(
                ex_summary=ex_summary, 
                total_tonnage=total_tonnage, 
                total_cardio_km=total_cardio_km, 
                total_cardio_mins=total_cardio_mins,
                user_db=user_data["exercise_database"]
            )

            if "prs" not in active_p: active_p["prs"] = {}
            for ex_name, ex_data in ex_summary.items():
                if ex_data["type"] == "weight":
                    c_1rm = ex_data["max_1rm"]
                    p_pr = active_p["prs"].get(ex_name, 0)
                    if c_1rm > p_pr:
                        active_p["prs"][ex_name] = c_1rm
                        pr_alerts.append(f"🏆 **NEW PR!** {ex_name}: {c_1rm} kg (Prev: {p_pr} kg)")
                        bonus_pr_xp += 150

            active_p["templates"][day_selected] = current_list
            unlocked_achs = check_and_unlock_achievements(total_tonnage)
            bonus_ach_xp = len(unlocked_achs) * 200
            
            if "history" not in active_p: active_p["history"] = []
            active_p["history"].append({
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "day": day_selected,
                "tonnage": total_tonnage,
                "cardio_cal": total_cardio_cal,
                "exercises": ex_summary
            })
            
            earned_xp = 35 + (effective_sets * 5) + bonus_pr_xp + bonus_ach_xp
            active_p["profile"]["xp"] += earned_xp
            
            req_xp = req_xp_for_level(active_p["profile"]["level"])
            if active_p["profile"]["xp"] >= req_xp:
                active_p["profile"]["level"] += 1
                st.balloons()
                st.success(f"🎉 **LEVEL UP! Level {active_p['profile']['level']}!**")
                
            save_user_data()
            
            st.markdown(f"""
            <div class='report-card'>
                <h3 style='color:#2b8a3e; margin-top:0;'>📊 {t('REPORT ΠΡΟΠΟΝΗΣΗΣ', 'WORKOUT REPORT')} ({DAY_MAP_TO_EN.get(day_selected, day_selected)}) - {active_profile_name}</h3>
                <p>• <b>{t('Συνολικός Όγκος (Tonnage):', 'Total Tonnage:')}</b> <span style='font-size:20px; color:#2b8a3e;'><b>{total_tonnage:,} kg</b></span></p>
                <p>• 🎈 <i>{quip_msg}</i></p>
                <p>• 🎮 <b>XP Earned:</b> +{earned_xp} XP</p>
            </div>
            """, unsafe_allow_html=True)
            
            if pr_alerts:
                st.warning("\n".join(pr_alerts))
            if unlocked_achs:
                st.success("🎖️ **UNLOCKED ACHIEVEMENTS:**\n" + "\n".join(unlocked_achs))

            # --- ΕΚΚΙΝΗΣΗ POST-WORKOUT QUIZ ---
            logged_ex_names = [row["ex"] for row in current_list]
            st.session_state[f"pw_quiz_{active_profile_name}"] = generate_post_workout_quiz(
                logged_ex_names,
                user_data.get("exercise_database", {}),
                user_data.get("trivia_db", {})
            )
            st.session_state[f"pw_quiz_answered_{active_profile_name}"] = False
            st.session_state[f"pw_quiz_choice_{active_profile_name}"] = None

    # --- ΕΜΦΑΝΙΣΗ ΚΑΡΤΑΣ QUIZ (ΕΞΩ ΑΠΟ ΤΟ if btn_digest ΓΙΑ ΝΑ ΜΗΝ ΧΑΝΕΤΑΙ ΣΤΟ RERUN) ---
    quiz_key = f"pw_quiz_{active_profile_name}"
    ans_key = f"pw_quiz_answered_{active_profile_name}"
    choice_key = f"pw_quiz_choice_{active_profile_name}"

    if st.session_state.get(quiz_key):
        quiz = st.session_state[quiz_key]
        st.divider()
        st.markdown(f"### 🧠 Post-Workout Fitness & Anatomy Quiz ({quiz.get('category', 'Trivia')})")
        st.caption(t("Κλείδωσε τη θεωρία πίσω από την προπόνηση και κέρδισε **+25 XP**!", "Lock in the theory behind your workout and earn **+25 XP**!"))

        user_choice = st.radio(
            quiz["q"],
            quiz["options"],
            key=f"pw_quiz_radio_{active_profile_name}",
            disabled=st.session_state.get(ans_key, False)
        )

        if not st.session_state.get(ans_key, False):
            if st.button(t("✅ Υποβολή Απάντησης (+25 XP)", "✅ Submit Answer (+25 XP)"), key=f"pw_quiz_submit_{active_profile_name}"):
                st.session_state[ans_key] = True
                st.session_state[choice_key] = user_choice

                if user_choice == quiz["answer"]:
                    active_p["profile"]["xp"] = active_p["profile"].get("xp", 0) + 25
                    active_p["profile"]["quizzes_solved"] = active_p["profile"].get("quizzes_solved", 0) + 1
                    
                    req_xp = req_xp_for_level(active_p["profile"].get("level", 1))
                    if active_p["profile"]["xp"] >= req_xp:
                        active_p["profile"]["level"] += 1
                    save_user_data()
                st.rerun()
        else:
            chosen = st.session_state.get(choice_key)
            if chosen == quiz["answer"]:
                solved_cnt = active_p["profile"].get("quizzes_solved", 1)
                st.success(t(
                    f"🎉 **Σωστά! +25 XP!** (Σύνολο λυμένων Quiz: {solved_cnt})",
                    f"🎉 **Correct! +25 XP!** (Total Quizzes Solved: {solved_cnt})"
                ))
            else:
                st.error(t(
                    f"❌ **Λάθος!** Η σωστή απάντηση είναι: **{quiz['answer']}**",
                    f"❌ **Wrong!** The correct answer is: **{quiz['answer']}**"
                ))

            st.info(f"📚 **{t('Θεωρητική Ανάλυση', 'Theory Breakdown')}:** {quiz.get('explanation', '')}")

            if st.button(t("🔄 Επόμενη Ερώτηση Θεωρίας", "🔄 Next Theory Question"), key=f"pw_quiz_next_{active_profile_name}"):
                st.session_state[quiz_key] = generate_post_workout_quiz(
                    [row["ex"] for row in current_list],
                    user_data.get("exercise_database", {}),
                    user_data.get("trivia_db", {})
                )
                st.session_state[ans_key] = False
                st.session_state[choice_key] = None
                st.rerun()

    st.markdown("---")
    with st.expander(t("✨ Προσθήκη Νέας Άσκησης στη Βάση (Custom Exercise Creator)", "✨ Add Custom Exercise to Database")):
        ce_name = st.text_input(t("Όνομα Άσκησης (π.χ. Bulgarian Split Squat):", "Exercise Name (e.g., Bulgarian Split Squat):"), key="ce_name")
        col_e1, col_e2, col_e3 = st.columns(3)
        
        with col_e1:
            ce_type_desc = st.selectbox(
                t("Τύπος Άσκησης:", "Exercise Type:"), 
                ["Weight (Kg + Reps)", "Dumbbell (Dumbbells x2)", "Bodyweight (Reps)", "Bodyweight Timed (Sec)", "Cardio / Running (Km/Min)"],
                key="ce_type_desc"
            )
        with col_e2:
            ce_primary = st.selectbox(
                t("Κύρια Μυϊκή Ομάδα:", "Primary Muscle:"),
                ["Quads", "Hamstrings", "Glutes", "Lower Back", "Chest", "Upper Chest", "Lats", "Upper Back", "Front Delts", "Side Delts", "Rear Delts", "Biceps", "Triceps", "Abs", "Core", "Cardio", "Full Body"],
                key="ce_primary"
            )
        with col_e3:
            ce_secondary = st.selectbox(
                t("Δευτερεύουσα Μυϊκή Ομάδα:", "Secondary Muscle:"),
                ["None", "Quads", "Hamstrings", "Glutes", "Lower Back", "Chest", "Lats", "Upper Back", "Front Delts", "Side Delts", "Rear Delts", "Biceps", "Triceps", "Abs", "Core", "Cardio"],
                key="ce_secondary"
            )

        if st.button(t("💾 Αποθήκευση Άσκησης στη Βάση", "💾 Save Exercise to Database"), key="btn_save_custom_ex"):
            if ce_name.strip():
                if "Dumbbell" in ce_type_desc:
                    ex_type = "weight"
                    is_db = True
                elif "Bodyweight (Reps)" in ce_type_desc:
                    ex_type = "bodyweight"
                    is_db = False
                elif "Bodyweight Timed" in ce_type_desc:
                    ex_type = "bodyweight_time"
                    is_db = False
                elif "Cardio" in ce_type_desc:
                    ex_type = "cardio"
                    is_db = False
                else:
                    ex_type = "weight"
                    is_db = False

                sec_val = None if ce_secondary == "None" else ce_secondary

                user_data["exercise_database"][ce_name.strip()] = {
                    "muscle": ce_primary,
                    "type": ex_type,
                    "is_db": is_db,
                    "primary": ce_primary,
                    "secondary": sec_val
                }
                save_user_data()
                st.success(t(f"Η άσκηση '{ce_name.strip()}' προστέθηκε επιτυχώς στη βάση δεδομένων!", f"Exercise '{ce_name.strip()}' added to database!"))
                st.rerun()
            else:
                st.warning(t("Παρακαλώ δώσε ένα όνομα στην άσκηση.", "Please enter an exercise name."))

# ==============================================================================
# TAB 4: VISUAL ANALYTICS
# ==============================================================================
with tab3:
    st.subheader(f"📊 {t('Visual Analytics & Performance', 'Visual Analytics & Performance')} — {active_profile_name}")
    
    history = active_p.get("history", [])
    
    if not history:
        st.info(t("💡 Καταγράψτε την πρώτη σας προπόνηση στο Tab 3 για να εμφανιστούν τα αναλυτικά διαγράμματα!", "💡 Log your first workout in Tab 3 to see performance analytics!"))
    else:
        # ----------------------------------------------------------------------
        # 1. CONTROLS: Χρονικό Παράθυρο & Φίλτρο RIR
        # ----------------------------------------------------------------------
        c_filt1, c_filt2 = st.columns([2, 1])
        with c_filt1:
            period_opts = [
                t("Τελευταίες 7 ημέρες (7D)", "Last 7 Days (7D)"),
                t("Τελευταίες 30 ημέρες (30D)", "Last 30 Days (30D)"),
                t("Όλο το Ιστορικό (All Time)", "All Time History")
            ]
            selected_period = st.selectbox(
                t("📅 Χρονικό Παράθυρο Ανάλυσης:", "📅 Analysis Time Window:"),
                period_opts,
                index=0,
                key=f"analytics_period_{active_profile_name}"
            )
        with c_filt2:
            st.write("")
            st.write("")
            only_effective = st.checkbox(
                t("🎯 Μόνο Effective Sets (RIR ≤ 3)", "🎯 Effective Sets Only (RIR ≤ 3)"),
                value=True,
                key=f"analytics_rir_filt_{active_profile_name}"
            )

        now_dt = datetime.now()
        filtered_history = []
        for h in history:
            d_raw = h.get("date", "").split()[0]
            try:
                h_dt = datetime.strptime(d_raw, "%d/%m/%Y")
            except Exception:
                h_dt = now_dt
            days_ago = (now_dt - h_dt).days
            if "7D" in selected_period and days_ago <= 7:
                filtered_history.append(h)
            elif "30D" in selected_period and days_ago <= 30:
                filtered_history.append(h)
            elif "All Time" in selected_period or "Όλο" in selected_period:
                filtered_history.append(h)

        if not filtered_history:
            st.warning(t(
                "⚠️ Δεν βρέθηκαν προπονήσεις σε αυτό το χρονικό παράθυρο. Επίλεξε 'Τελευταίες 30 ημέρες' ή 'Όλο το Ιστορικό'.",
                "⚠️ No workouts found in this time window. Select 'Last 30 Days' or 'All Time History'."
            ))
        else:
            # ------------------------------------------------------------------
            # 2. ΥΠΟΛΟΓΙΣΜΟΣ ΜΕΤΡΙΚΩΝ (EMG Volume, Resistance Profile, Cardio)
            # ------------------------------------------------------------------
            tracked_muscles = [
                "Chest", "Upper Back", "Lats", "Quads", "Hamstrings", "Glutes",
                "Lower Back", "Front Delts", "Side Delts", "Rear Delts",
                "Biceps", "Triceps", "Abs", "Core", "Calves", "Traps", "Forearms"
            ]
            emg_volume = {m: 0.0 for m in tracked_muscles}
            profile_breakdown = {
                m: {"Lengthened": 0.0, "Full-range": 0.0, "Mid-range": 0.0, "Shortened": 0.0}
                for m in tracked_muscles
            }

            total_eff_sets = 0
            total_period_tonnage = 0.0
            total_period_km = 0.0
            total_period_cardio_mins = 0
            lengthened_sets_sum = 0.0
            total_profiled_sets = 0.0

            if "7D" in selected_period:
                weeks_divisor = 1.0
            elif "30D" in selected_period:
                weeks_divisor = 4.3
            else:
                parsed_dates = []
                for h in filtered_history:
                    try:
                        parsed_dates.append(datetime.strptime(h.get("date", "").split()[0], "%d/%m/%Y"))
                    except Exception:
                        pass
                if len(parsed_dates) >= 2:
                    span_days = max(7, (max(parsed_dates) - min(parsed_dates)).days)
                    weeks_divisor = max(1.0, span_days / 7.0)
                else:
                    weeks_divisor = 1.0

            for h in filtered_history:
                total_period_tonnage += h.get("tonnage", 0.0)
                exs = h.get("exercises", {})
                for ex_name, ex_data in exs.items():
                    s = ex_data.get("sets", 0)
                    ex_type = ex_data.get("type", "weight")
                    db_info = user_data["exercise_database"].get(ex_name, {})

                    if ex_type == "cardio":
                        total_period_km += ex_data.get("max_weight", 0.0)
                        total_period_cardio_mins += ex_data.get("total_reps_or_min", 0)
                        continue

                    rirs = ex_data.get("rirs") or [2]
                    avg_rir = sum(rirs) / len(rirs)
                    if only_effective and avg_rir > 3.0:
                        continue

                    total_eff_sets += s

                    raw_rp = db_info.get("resistance_profile", "Mid-range")
                    if "Lengthened" in raw_rp:
                        rp_bucket = "Lengthened"
                    elif "Full-range" in raw_rp:
                        rp_bucket = "Full-range"
                    elif "Mid-range" in raw_rp:
                        rp_bucket = "Mid-range"
                    else:
                        rp_bucket = "Shortened"

                    total_profiled_sets += s
                    if rp_bucket in ["Lengthened", "Full-range"]:
                        lengthened_sets_sum += s

                    emg_map = db_info.get("emg_weights")
                    if not isinstance(emg_map, dict) or not emg_map:
                        emg_map = {}
                        prim = db_info.get("primary", db_info.get("muscle"))
                        sec = db_info.get("secondary")
                        if prim:
                            emg_map[prim] = 1.0
                        if sec:
                            emg_map[sec] = 0.5

                    for m_key, weight_factor in emg_map.items():
                        if m_key in emg_volume:
                            weighted_s = s * float(weight_factor)
                            emg_volume[m_key] += weighted_s
                            profile_breakdown[m_key][rp_bucket] += weighted_s

            weekly_emg_volume = {m: round(v / weeks_divisor, 1) for m, v in emg_volume.items()}
            active_muscles = [
                m for m in tracked_muscles
                if weekly_emg_volume[m] > 0 or m in ["Chest", "Lats", "Upper Back", "Quads", "Hamstrings", "Glutes", "Side Delts", "Biceps", "Triceps"]
            ]

            top_muscle = max(weekly_emg_volume, key=weekly_emg_volume.get)
            top_muscle_val = weekly_emg_volume[top_muscle]
            stretch_pct = round((lengthened_sets_sum / total_profiled_sets) * 100, 1) if total_profiled_sets > 0 else 0.0

            # ------------------------------------------------------------------
            # 3. TOP 4 KPI CARDS
            # ------------------------------------------------------------------
            k1, k2, k3, k4 = st.columns(4)
            k1.metric(t("🔥 Effective Sets", "🔥 Effective Sets"), f"{total_eff_sets} sets", f"{len(filtered_history)} {t('προπονήσεις', 'sessions')}")
            k2.metric(t("🏆 Top Μυϊκή Ομάδα", "🏆 Top Muscle Group"), top_muscle, f"{top_muscle_val} sets/{t('εβδ.', 'wk')}")
            k3.metric(t("📐 Stretch / Full-Range", "📐 Stretch / Full-Range"), f"{stretch_pct}%", t("Στόχος: >35%", "Target: >35%"))
            if total_period_tonnage >= 500 or total_period_km == 0:
                k4.metric(t("🏋️ Συνολικό Tonnage", "🏋️ Total Tonnage"), f"{int(total_period_tonnage):,} kg")
            else:
                k4.metric(t("🏃 Απόσταση Cardio", "🏃 Cardio Distance"), f"{total_period_km:.1f} km", f"{total_period_cardio_mins} min")

            st.write("")

            # ------------------------------------------------------------------
            # 4. SUB-TABS ΓΙΑ ΚΑΘΑΡΗ ΠΡΟΒΟΛΗ ΣΕ DESKTOP & MOBILE
            # ------------------------------------------------------------------
            sub_tab1, sub_tab2 = st.tabs([
                t("💪 Μυϊκός Όγκος & Biomechanics", "💪 Muscle Volume & Biomechanics"),
                t("📈 Πρόοδος, Βάρος & Cardio/HYROX", "📈 Progress, Weight & Cardio/HYROX")
            ])

            # ==================================================================
            # SUB-TAB 1: EMG VOLUME, RESISTANCE PROFILE & BENCHMARKS
            # ==================================================================
            with sub_tab1:
                days_win = 7 if "7D" in selected_period else (30 if "30D" in selected_period else 0)
                frac_sets, prof_break, biomech_alerts, _ = analyze_fractional_emg_and_profiles(
                    history, user_data["exercise_database"], STRENGTH_STANDARDS, days_window=days_win
                )
                landmarks = STRENGTH_STANDARDS.get("volume_landmarks", {})
                norm_div = 1.0 if days_win == 7 else (4.3 if days_win == 30 else weeks_divisor)
                wk_frac = {m: round(v / norm_div, 1) for m, v in frac_sets.items() if v > 0 or m in landmarks}

                fig1, (ax_vol, ax_rp) = plt.subplots(2, 1, figsize=(11, 10))

                # --- 1. Fractional EMG Volume vs MEV / MAV / MRV ---
                m_labels = list(wk_frac.keys())[::-1]
                m_vals = [wk_frac[m] for m in m_labels]
                bar_colors = []
                for m, v in zip(m_labels, m_vals):
                    lm = landmarks.get(m, {"mev": 6, "mav": 14, "mrv": 20})
                    mev_val = lm.get("mev", 6)
                    mav_raw = lm.get("mav", 14)
                    mav_top = mav_raw[-1] if isinstance(mav_raw, (list, tuple)) else mav_raw
                    mrv_val = lm.get("mrv", mav_top)
                    if v < mev_val:
                        bar_colors.append("#fcc419")
                    elif v <= mrv_val:
                        bar_colors.append("#2b8a3e")
                    else:
                        bar_colors.append("#ff6b6b")

                bars = ax_vol.barh(m_labels, m_vals, color=bar_colors, edgecolor="#343a40", alpha=0.9)
                ax_vol.axvline(x=6, color="#f59f00", linestyle="--", linewidth=1.5, label="MEV (~6 sets/wk)")
                ax_vol.axvline(x=10, color="#2b8a3e", linestyle="-.", linewidth=1.5, label="MAV Start (~10 sets/wk)")
                ax_vol.axvline(x=20, color="#e03131", linestyle=":", linewidth=1.5, label="MRV Limit (~20+ sets/wk)")
                ax_vol.set_title(t("🧬 Fractional EMG Εβδομαδιαίος Όγκος (sets/εβδ.)", "🧬 Fractional EMG Weekly Volume (sets/wk)"), fontweight="bold")
                ax_vol.set_xlabel(t("Σταθμισμένα Σετ / Εβδομάδα", "Weighted Sets / Week"))
                ax_vol.grid(axis="x", linestyle="--", alpha=0.4)
                ax_vol.legend(loc="lower right")
                for bar in bars:
                    w_val = bar.get_width()
                    if w_val > 0:
                        ax_vol.text(w_val + 0.3, bar.get_y() + bar.get_height() / 2, f"{w_val:.1f}", va="center", fontsize=9, fontweight="bold")

                # --- 2. Resistance Profile Analyzer (%) ---
                trained_m = [m for m in m_labels if sum(prof_break.get(m, {}).values()) > 0]
                if trained_m:
                    leng_p, full_p, mid_p, short_p = [], [], [], []
                    for m in trained_m:
                        pb = prof_break[m]
                        tot_m = max(0.01, sum(pb.values()))
                        leng_p.append((pb.get("Lengthened-biased", 0.0) / tot_m) * 100)
                        full_p.append((pb.get("Full-range", 0.0) / tot_m) * 100)
                        mid_p.append((pb.get("Mid-range", 0.0) / tot_m) * 100)
                        short_p.append((pb.get("Shortened-biased", 0.0) / tot_m) * 100)

                    ax_rp.barh(trained_m, leng_p, color="#2b8a3e", label="Lengthened-biased (Stretch)")
                    ax_rp.barh(trained_m, full_p, left=leng_p, color="#20c997", label="Full-range")
                    l_mid = [a + b for a, b in zip(leng_p, full_p)]
                    ax_rp.barh(trained_m, mid_p, left=l_mid, color="#339af0", label="Mid-range")
                    l_sh = [a + b for a, b in zip(l_mid, mid_p)]
                    ax_rp.barh(trained_m, short_p, left=l_sh, color="#adb5bd", label="Shortened-biased")
                    ax_rp.set_xlim(0, 100)
                    ax_rp.set_title(t("📐 Resistance Profile Balance ανά Μυϊκή Ομάδα (%)", "📐 Resistance Profile Balance per Muscle (%)"), fontweight="bold")
                    ax_rp.legend(loc="lower right", ncol=2, fontsize=8)

                plt.tight_layout()
                st.pyplot(fig1)
                plt.close(fig1)

                for alert in biomech_alerts:
                    st.info(f"💡 **Stretch-Mediated Hypertrophy Alert:** {alert}")

                # --- 3. Scientific Strength Standards, Relative Strength & DOTS Score ---
                st.divider()
                st.markdown(f"#### 🏆 {t('Scientific Strength Standards, Relative Strength & DOTS Score', 'Scientific Strength Standards, Relative Strength & DOTS Score')}")
                std_results, dots_score, sbd_total = evaluate_strength_standards(active_p, user_data["exercise_database"], STRENGTH_STANDARDS)

                dc1, dc2 = st.columns(2)
                dc1.metric("🏅 DOTS Score (Relative Strength)", f"{dots_score} pts")
                dc2.metric("🏋️ Estimated SBD Total", f"{sbd_total} kg")

                if std_results:
                    for res in std_results:
                        sc1, sc2 = st.columns([2, 3])
                        with sc1:
                            st.markdown(f"**{res['exercise']}** — `{res['e1rm']} kg` ({res['bw_ratio']}× BW)")
                            st.caption(f"Tier: **{res['current_tier']}** → Next: **{res['next_tier']}** (+{res['kg_to_next']} kg)")
                        with sc2:
                            st.progress(res["progress_pct"] / 100.0)
                else:
                    st.info(t(
                        "Κατάγραψε σετ σε βασικές ασκήσεις (π.χ. Squat, Bench Press, RDL, Lat Pulldown) για να υπολογιστεί η κατάταξη δύναμης.",
                        "Log sets in main lifts (e.g., Squat, Bench Press, RDL, Lat Pulldown) to unlock strength benchmarks."
                    ))

            # ==================================================================
            # SUB-TAB 2: ΠΡΟΟΔΟΣ 1RM, ΒΑΡΟΣ (SWEET ZONE) & CARDIO / HYROX
            # ==================================================================
            with sub_tab2:
                c_ex1, c_ex2 = st.columns([2, 1])
                performed_exs = sorted(list({ex_k for h in history for ex_k in h.get("exercises", {}).keys()}))
                all_db_exs = sorted(list(user_data["exercise_database"].keys()))
                selectable_exs = performed_exs if performed_exs else all_db_exs

                with c_ex1:
                    selected_ex = st.selectbox(
                        t("🏋️ Επιλογή Άσκησης για Ανάλυση Προόδου:", "🏋️ Select Exercise for Progress Analysis:"),
                        selectable_exs,
                        key=f"ex_graph_v2_{active_profile_name}"
                    ) if selectable_exs else None
                with c_ex2:
                    st.write("")
                    st.write("")
                    show_rir_1rm = st.checkbox(
                        t("⚡ RIR-Adjusted 1RM", "⚡ RIR-Adjusted 1RM"),
                        value=True,
                        key=f"rir_1rm_toggle_{active_profile_name}"
                    )

                fig2, (ax_ton, ax_prog) = plt.subplots(1, 2, figsize=(12, 4.5))

                # --- Γράφημα 1: Tonnage ή Cardio Distance ανά Συνεδρία ---
                s_dates = [
                    f"{DAY_MAP_TO_EN.get(h.get('day',''), h.get('day','')) if st.session_state.get('lang') == 'English' else h.get('day','')}\n{h.get('date','').split()[0]}"
                    for h in filtered_history
                ]
                s_tonnages = [h.get("tonnage", 0) for h in filtered_history]
                s_kms = [
                    sum(v.get("max_weight", 0.0) for v in h.get("exercises", {}).values() if v.get("type") == "cardio")
                    for h in filtered_history
                ]

                if sum(s_tonnages) > 0:
                    ax_ton.plot(s_dates, s_tonnages, marker="o", color="#2b8a3e", linewidth=2.5, label="Tonnage (kg)")
                    ax_ton.set_title(t("📈 Εξέλιξη Όγκου (Tonnage kg)", "📈 Total Tonnage Progress (kg)"), fontweight="bold")
                    ax_ton.set_ylabel("Kg")
                else:
                    ax_ton.plot(s_dates, s_kms, marker="o", color="#1971c2", linewidth=2.5, label="Distance (km)")
                    ax_ton.set_title(t("🏃 Εξέλιξη Απόστασης Cardio (km)", "🏃 Cardio Distance Progress (km)"), fontweight="bold")
                    ax_ton.set_ylabel("Km")
                ax_ton.grid(True, linestyle="--", alpha=0.5)
                ax_ton.tick_params(axis="x", rotation=30)

                # --- Γράφημα 2: Estimated 1RM & RIR-Adjusted 1RM (ή Cardio Pace) ---
                ex_dates, base_1rms, adj_1rms, cardio_paces = [], [], [], []
                is_cardio_sel = user_data["exercise_database"].get(selected_ex, {}).get("type") == "cardio" if selected_ex else False

                for h in history:
                    exs = h.get("exercises", {})
                    if selected_ex and selected_ex in exs:
                        ex_dates.append(f"{h.get('date','').split()[0]}")
                        ex_d = exs[selected_ex]
                        if ex_d.get("type") == "weight":
                            b_1rm = ex_d.get("max_1rm", 0.0)
                            base_1rms.append(b_1rm)
                            n_ent = max(1, len(ex_d.get("rirs") or [1]))
                            avg_r = ex_d.get("total_reps_or_min", 10) / n_ent
                            avg_rir_ex = sum(ex_d.get("rirs") or [2]) / n_ent
                            if b_1rm > 0 and avg_r > 0:
                                eff_w_est = b_1rm / (1.0 + avg_r / 30.0) if avg_r <= 10 else b_1rm * (48.8 + 53.8 * math.exp(-0.075 * avg_r)) / 100.0
                                adj_1rms.append(calc_1rm(eff_w_est, avg_r + avg_rir_ex))
                            else:
                                adj_1rms.append(b_1rm)
                        elif ex_d.get("type") == "cardio":
                            dist_v = ex_d.get("max_weight", 0.0)
                            mins_v = ex_d.get("total_reps_or_min", 0.0)
                            cardio_paces.append(round(mins_v / dist_v, 2) if dist_v > 0 else 0.0)
                        else:
                            base_1rms.append(ex_d.get("total_reps_or_min", 0))
                            adj_1rms.append(ex_d.get("total_reps_or_min", 0))

                if is_cardio_sel and cardio_paces:
                    ax_prog.plot(ex_dates, cardio_paces, marker="s", color="#e8590c", linewidth=2.5, label="Pace (min/km)")
                    ax_prog.invert_yaxis()
                    ax_prog.set_title(f"🏃 Pace (min/km): {selected_ex}", fontweight="bold")
                    ax_prog.grid(True, linestyle="--", alpha=0.5)
                    ax_prog.legend()
                elif base_1rms:
                    ax_prog.plot(ex_dates, base_1rms, marker="s", color="#1971c2", linewidth=2.5, label="Est. 1RM (kg)")
                    if show_rir_1rm and adj_1rms != base_1rms:
                        ax_prog.plot(ex_dates, adj_1rms, marker="^", linestyle="--", color="#2b8a3e", linewidth=2, label="RIR-Adjusted 1RM (kg)")
                    ax_prog.set_title(f"📊 {t('Πρόοδος Δύναμης (1RM)', 'Strength Progress (1RM)')}: {selected_ex}", fontweight="bold")
                    ax_prog.set_ylabel("Kg")
                    ax_prog.grid(True, linestyle="--", alpha=0.5)
                    ax_prog.legend()
                else:
                    ax_prog.text(0.5, 0.5, f"{t('Δεν υπάρχουν ακόμα δεδομένα για:', 'No data yet for:')}\n{selected_ex}", ha="center", va="center")

                ax_prog.tick_params(axis="x", rotation=30)
                plt.tight_layout()
                st.pyplot(fig2)
                plt.close(fig2)

                # --- Γράφημα 3: Body Weight Trend + Sweet Zone & Hypertrophy Efficiency ---
                w_dates, w_mov_avg, w_proj, _ = calc_projected_vs_real_weight(active_p.get("profile", {}), active_p.get("weight_log", []))
                if w_dates:
                    fig3, ax_w = plt.subplots(figsize=(11, 4))
                    x_w = list(range(len(w_dates)))
                    sweet_low = [p - 0.5 for p in w_proj]
                    sweet_high = [p + 0.5 for p in w_proj]

                    ax_w.fill_between(x_w, sweet_low, sweet_high, color="#51cf66", alpha=0.2, label=t("Sweet Zone (±0.5 kg)", "Sweet Zone (±0.5 kg)"))
                    ax_w.plot(x_w, w_proj, color="#f59f00", linestyle="--", linewidth=2, label=t("Projected Target Curve", "Projected Target Curve"))
                    ax_w.plot(x_w, w_mov_avg, color="#2b8a3e", marker="o", linewidth=3, label=t("Real Weight Trend (7d Moving Avg)", "Real Weight Trend (7d Moving Avg)"))
                    ax_w.set_xticks(x_w)
                    ax_w.set_xticklabels(w_dates, rotation=30)
                    ax_w.set_ylabel("Kg")
                    ax_w.set_title(t("⚖️ Target Curve, Sweet Zone & Real Weight Trend", "⚖️ Target Curve, Sweet Zone & Real Weight Trend"), fontweight="bold")
                    ax_w.legend()
                    ax_w.grid(True, linestyle="--", alpha=0.5)
                    plt.tight_layout()
                    st.pyplot(fig3)
                    plt.close(fig3)

                    if len(w_mov_avg) >= 2 and w_mov_avg[0] > 0 and len(history) >= 2:
                        pct_w_gain = ((w_mov_avg[-1] - w_mov_avg[0]) / w_mov_avg[0]) * 100.0
                        first_exs = history[0].get("exercises", {})
                        last_exs = history[-1].get("exercises", {})
                        common_w_exs = [
                            k for k in first_exs
                            if k in last_exs and first_exs[k].get("max_1rm", 0) > 0 and last_exs[k].get("max_1rm", 0) > 0
                        ]
                        if common_w_exs and pct_w_gain > 0.2:
                            pct_1rm_gains = [
                                ((last_exs[k]["max_1rm"] - first_exs[k]["max_1rm"]) / first_exs[k]["max_1rm"]) * 100.0
                                for k in common_w_exs
                            ]
                            avg_1rm_gain = sum(pct_1rm_gains) / len(pct_1rm_gains)
                            eff_idx = avg_1rm_gain / pct_w_gain
                            if eff_idx >= 1.5:
                                st.success(t(
                                    f"🟢 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — Καθαρή μυϊκή υπερτροφή! Η δύναμη ανέβηκε +{avg_1rm_gain:.1f}% έναντι +{pct_w_gain:.1f}% σωματικού βάρους.",
                                    f"🟢 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — High quality muscle gain! Strength rose +{avg_1rm_gain:.1f}% vs +{pct_w_gain:.1f}% body weight."
                                ))
                            elif eff_idx >= 0.8:
                                st.info(t(
                                    f"🟡 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — Ισορροπημένο Bulking (δύναμη +{avg_1rm_gain:.1f}%, βάρος +{pct_w_gain:.1f}%).",
                                    f"🟡 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — Optimal bulking ratio (strength +{avg_1rm_gain:.1f}%, weight +{pct_w_gain:.1f}%)."
                                ))
                            else:
                                st.warning(t(
                                    f"🔴 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — Το βάρος ανεβαίνει ταχύτερα από τη δύναμη (+{pct_w_gain:.1f}% βάρος vs +{avg_1rm_gain:.1f}% 1RM). Έλεγξε το θερμιδικό πλεόνασμα.",
                                    f"🔴 **Hypertrophy Efficiency Index: {eff_idx:.2f}** — Weight rising faster than strength (+{pct_w_gain:.1f}% weight vs +{avg_1rm_gain:.1f}% 1RM). Consider trimming surplus."
                                ))

                # --- Γράφημα 4: Cardio HR Zones (όταν υπάρχουν καταγραφές Cardio) ---
                if total_period_cardio_mins > 0:
                    zone_mins = {"Zone 1": 0, "Zone 2": 0, "Zone 3": 0, "Zone 4": 0, "Zone 5": 0}
                    user_age = active_p.get("profile", {}).get("age", 26)
                    for h in filtered_history:
                        for ex_k, ex_v in h.get("exercises", {}).items():
                            if ex_v.get("type") == "cardio":
                                c_mins = ex_v.get("total_reps_or_min", 0)
                                c_dist = ex_v.get("max_weight", 0)
                                est_hr = ex_v.get("avg_hr")
                                if not est_hr:
                                    spd = (60.0 / (c_mins / c_dist)) if (c_dist > 0 and c_mins > 0) else 9.0
                                    est_hr = min(195, int(115 + spd * 4.5))
                                z_label, _ = calc_hr_zone(est_hr, user_age)
                                for zk in zone_mins:
                                    if zk in z_label:
                                        zone_mins[zk] += c_mins
                                        break

                    fig4, ax_hr = plt.subplots(figsize=(10, 3.5))
                    z_keys = list(zone_mins.keys())
                    z_vals = list(zone_mins.values())
                    z_colors = ["#339af0", "#51cf66", "#fcc419", "#ff922b", "#ff6b6b"]
                    ax_hr.bar(z_keys, z_vals, color=z_colors, edgecolor="#343a40")
                    ax_hr.set_ylabel(t("Λεπτά (Min)", "Minutes (Min)"))
                    ax_hr.set_title(t("❤️ Κατανομή Χρόνου ανά Heart Rate Zone", "❤️ Time Distribution per Heart Rate Zone"), fontweight="bold")
                    ax_hr.grid(axis="y", linestyle="--", alpha=0.4)
                    plt.tight_layout()
                    st.pyplot(fig4)
                    plt.close(fig4)

    # ==========================================================================
    # HYROX SPLIT PLANNER & RUNNING PACE ENGINE (RIEGEL + ZONE 2 / LT2)
    # ==========================================================================
    st.divider()
    st.subheader(t("🏎️ HYROX Split Planner & Running Pace Engine", "🏎️ HYROX Split Planner & Running Pace Engine"))

    tab_hyrox, tab_run = st.tabs([
        t("🏁 HYROX Race Split Simulator", "🏁 HYROX Race Split Simulator"),
        t("🏃 Riegel Predictor & Zone 2 / LT2 Paces", "🏃 Riegel Predictor & Zone 2 / LT2 Paces")
    ])

    with tab_hyrox:
        hc1, hc2 = st.columns(2)
        with hc1:
            target_hyrox_min = st.number_input(
                t("Στόχος Τερματισμού HYROX (Λεπτά):", "HYROX Target Finish Time (Minutes):"),
                min_value=50, max_value=150, value=75, step=1,
                key=f"hyrox_target_{active_profile_name}"
            )
        with hc2:
            hyrox_div = st.selectbox(
                t("Κατηγορία Αγώνα:", "Race Division:"),
                ["Open", "Pro"],
                key=f"hyrox_div_{active_profile_name}"
            )

        splits_data = calc_hyrox_splits(target_hyrox_min, hyrox_div, COACHING_RULES)
        hm1, hm2, hm3 = st.columns(3)
        hm1.metric("🏃 Target Pace (8 × 1km)", splits_data["per_1km_pace"])
        hm2.metric("⏱️ Συνολικό Τρέξιμο (8km)", splits_data["total_run_time"])
        hm3.metric("🔄 Roxzone (Μεταβάσεις)", splits_data["roxzone_total"])

        if splits_data["stations"]:
            st.dataframe(pd.DataFrame(splits_data["stations"]), use_container_width=True, hide_index=True)

    with tab_run:
        rc1, rc2 = st.columns(2)
        with rc1:
            ref_dist = st.number_input(
                t("Πρόσφατη Απόσταση Αναφοράς (km):", "Recent Benchmark Distance (km):"),
                min_value=1.0, max_value=42.2, value=5.0, step=0.5,
                key=f"run_ref_d_{active_profile_name}"
            )
        with rc2:
            ref_mins = st.number_input(
                t("Χρόνος Επίδοσης (Λεπτά):", "Benchmark Time (Minutes):"),
                min_value=3.0, max_value=360.0, value=24.0, step=0.5,
                key=f"run_ref_t_{active_profile_name}"
            )

        preds_list, zones_list = calc_running_pace_zones(ref_dist, ref_mins, COACHING_RULES)
        if preds_list:
            st.markdown(f"**📈 {t('Προβλέψεις Αγώνων (Riegel Formula)', 'Race Time Predictions (Riegel Formula)')}:**")
            st.dataframe(pd.DataFrame(preds_list), use_container_width=True, hide_index=True)

        if zones_list:
            st.markdown(f"**🎯 {t('Εξατομικευμένες Ζώνες Ρυθμού (min/km)', 'Personalized Pace Zones (min/km)')}:**")
            st.dataframe(pd.DataFrame(zones_list), use_container_width=True, hide_index=True)
