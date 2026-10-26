import os
import json
import math
import random
import requests
import base64
from datetime import datetime
import streamlit as st
import matplotlib.pyplot as plt
import pandas as pd

# ------------------------------------------------------------------------------
# 1. PAGE CONFIG & STYLING
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Gym Coaching OS",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Custom Mobile-Friendly CSS
st.markdown("""
<style>
    .main { padding: 0rem 1rem; }
    .stButton>button { width: 100%; border-radius: 8px; height: 3em; font-weight: bold; }
    .stMetric { background-color: #f8f9fa; padding: 10px; border-radius: 8px; border: 1px solid #e9ecef; }
    div[data-testid="stExpander"] { border: 1px solid #ced4da; border-radius: 8px; }
    .badge-card { background-color: #fff9db; border: 1px solid #f59f00; padding: 4px 10px; border-radius: 12px; margin-right: 5px; font-size: 13px; display: inline-block; }
    .report-card { background-color: #ffffff; color: #111111; border: 2px solid #2b8a3e; padding: 15px; border-radius: 10px; margin-top: 10px; }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "gym_data.json"

# ------------------------------------------------------------------------------
# 2. DEFAULT DATA & FOOD DATABASE
# ------------------------------------------------------------------------------
default_food_db = {
    # 🍗 ΚΡΕΑΤΑ & ΨΑΡΙΑ (ανά 100g ή ανά τεμάχιο)
    "🍗 Κοτόπουλο Στήθος (ψητό/μαγειρεμένο)": {"unit": "100g", "cal": 165, "p": 31.0, "c": 0.0, "f": 3.6},
    "🍗 Κοτόπουλο Μπούτι (χωρίς δέρμα)": {"unit": "100g", "cal": 180, "p": 24.0, "c": 0.0, "f": 9.0},
    "🍗 Κοτόπουλο Φτερούγες (με δέρμα)": {"unit": "100g", "cal": 203, "p": 18.0, "c": 0.0, "f": 14.0},
    "🐟 Κονσέρβα Τόνου σε νερό (drained)": {"unit": "100g", "cal": 110, "p": 25.0, "c": 0.0, "f": 0.6},
    "🦐 King Prawns (Γαρίδες Tesco)": {"unit": "100g", "cal": 85, "p": 18.5, "c": 0.5, "f": 0.9},
    "🥩 Tesco Basted Pork": {"unit": "100g", "cal": 145, "p": 21.0, "c": 1.0, "f": 6.0},
    "🌭 Tesco Finest Irish Pork & Apple Sausage": {"unit": "piece", "cal": 137, "p": 8.0, "c": 3.4, "f": 9.7},
    "🌯 Burrito (Μοσχαρίσιος κιμάς, φασόλια, ρύζι)": {"unit": "100g", "cal": 170, "p": 8.5, "c": 20.0, "f": 6.0},
    
    # 🥛 ΠΡΩΤΕΙΝΙΚΑ & ΓΑΛΑΚΤΟΚΟΜΙΚΑ
    "🥤 Myprotein Impact Whey Protein (1 scoop 30g)": {"unit": "piece", "cal": 114, "p": 23.0, "c": 1.8, "f": 1.9},
    "🥚 Αυγό Ολόκληρο (1 μέτριο/μεγάλο)": {"unit": "piece", "cal": 72, "p": 6.0, "c": 0.4, "f": 4.8},
    "🥛 GetPRO / GoPRO Protein Yoghurt (160g)": {"unit": "piece", "cal": 104, "p": 15.0, "c": 7.2, "f": 0.3},
    "🥣 Tesco Plain Skyr / Quark": {"unit": "100g", "cal": 65, "p": 11.0, "c": 4.0, "f": 0.2},
    "🍨 Ελληνικό Γιαούρτι 2%": {"unit": "100g", "cal": 73, "p": 10.0, "c": 3.8, "f": 2.0},
    "🍫 Nature Valley Extra Protein Bar": {"unit": "piece", "cal": 198, "p": 10.0, "c": 15.0, "f": 11.0},
    
    # 🥔 ΣΥΝΟΔΕΥΤΙΚΑ, ΦΡΟΥΤΑ & ΛΙΠΗ
    "🥔 Tesco Country Potatoes (κατεψυγμένες)": {"unit": "100g", "cal": 135, "p": 2.5, "c": 22.0, "f": 3.8},
    "🍌 Μπανάνα (1 μέτρια ~120g)": {"unit": "piece", "cal": 105, "p": 1.3, "c": 27.0, "f": 0.3},
    "🍎 Μήλο (1 μέτριο ~150g)": {"unit": "piece", "cal": 78, "p": 0.5, "c": 21.0, "f": 0.3},
    "🥜 Φυστικοβούτυρο 100%": {"unit": "100g", "cal": 590, "p": 25.0, "c": 12.0, "f": 49.0},
    "🍚 Ρύζι βρασμένο": {"unit": "100g", "cal": 130, "p": 2.7, "c": 28.0, "f": 0.3},
    "🍝 Μακαρόνια βρασμένα": {"unit": "100g", "cal": 158, "p": 5.8, "c": 31.0, "f": 0.9},
    "🍲 Φακές βρασμένες / Σούπα": {"unit": "100g", "cal": 116, "p": 9.0, "c": 20.0, "f": 0.4},
}

TONNAGE_QUIPS = [
    (100, "🦆 Σήκωσες το βάρος από 40 πάπιες!"),
    (250, "🦭 Σήκωσες το βάρος από 1 ενήλικη φώκια!"),
    (500, "🎹 Σήκωσες 1 πιάνο με ουρά Konzertflügel!"),
    (1200, "🚗 Σήκωσες 1 Fiat 500 / Mini Cooper!"),
    (2500, "🦏 Σήκωσες έναν αρσενικό Λευκό Ρινόκερο!"),
    (6000, "🐘 Σήκωσες έναν ενήλικο Αφρικανικό Ελέφαντα!"),
    (12000, "🦖 Σήκωσες έναν πλήρως αναπτυγμένο Tyrannosaurus Rex!"),
    (22000, "🚌 Σήκωσες 2 διώροφα κόκκινα λεωφορεία του Λονδίνου!"),
    (55000, "✈️ Σήκωσες ένα άδειο επιβατικό Boeing 737-800!"),
    (100000, "🚂 Σήκωσες μια ατμομηχανή τρένου Orient Express!")
]

default_data = {
    "profile": {
        "gender": "Άνδρας",
        "age": 28,
        "weight_kg": 72.0,
        "height_cm": 177.0,
        "activity_level": 1.55,
        "goal": "Bulking",
        "training_age": "Αρχάριος (0-1 έτος)",
        "xp": 0,
        "level": 1,
        "quizzes_solved": 0
    },
    "food_db": default_food_db,
    "daily_logs": [],
    "weight_log": [],
    "exercise_database": {
        "Stationary Bike (Ποδήλατο)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": None},
        "Treadmill (Διάδρομος)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": None},
        "Leg Press": {"muscle": "Quads", "type": "weight", "is_db": False, "primary": "Quads", "secondary": "Glutes"},
        "Leg Extension Machine": {"muscle": "Quads", "type": "weight", "is_db": False, "primary": "Quads", "secondary": None},
        "Seated Leg Curl Machine": {"muscle": "Hamstrings", "type": "weight", "is_db": False, "primary": "Hamstrings", "secondary": None},
        "Romanian Deadlift (RDL)": {"muscle": "Hamstrings", "type": "weight", "is_db": True, "primary": "Hamstrings", "secondary": "Glutes"},
        "Roman Chair Hyperextensions (Ρωμαϊκή Έδρα)": {"muscle": "Lower Back", "type": "bodyweight", "primary": "Hamstrings", "secondary": "Glutes"},
        "Pull-ups (Έλξεις στο Ζυγό)": {"muscle": "Lats", "type": "bodyweight", "primary": "Lats", "secondary": "Biceps"},
        "Chin-ups (Υπτιάστιες Έλξεις)": {"muscle": "Lats", "type": "bodyweight", "primary": "Lats", "secondary": "Biceps"},
        "Lat Pulldown (Τροχαλία)": {"muscle": "Lats", "type": "weight", "is_db": False, "primary": "Lats", "secondary": "Biceps"},
        "Seated Cable Row (Κωπηλατική Τροχαλία)": {"muscle": "Upper Back", "type": "weight", "is_db": False, "primary": "Upper Back", "secondary": "Biceps"},
        "Chest-Supported DB Row (30°)": {"muscle": "Upper Back", "type": "weight", "is_db": True, "primary": "Upper Back", "secondary": "Rear Delts"},
        "Flat Dumbbell Chest Press": {"muscle": "Chest", "type": "weight", "is_db": True, "primary": "Chest", "secondary": "Triceps"},
        "Incline DB Bench Press": {"muscle": "Upper Chest", "type": "weight", "is_db": True, "primary": "Chest", "secondary": "Front Delts"},
        "Cable Chest Flyes (Τροχαλία)": {"muscle": "Chest", "type": "weight", "is_db": False, "primary": "Chest", "secondary": None},
        "Dumbbell Shoulder Press": {"muscle": "Shoulders", "type": "weight", "is_db": True, "primary": "Front Delts", "secondary": "Triceps"},
        "Cable Lateral Raises (Τροχαλία)": {"muscle": "Side Delts", "type": "weight", "is_db": False, "primary": "Side Delts", "secondary": None},
        "Lateral Raises (Αλτήρες)": {"muscle": "Side Delts", "type": "weight", "is_db": True, "primary": "Side Delts", "secondary": None},
        "Cable Face Pulls": {"muscle": "Rear Delts", "type": "weight", "is_db": False, "primary": "Rear Delts", "secondary": "Upper Back"},
        "Cable Bicep Curls": {"muscle": "Biceps", "type": "weight", "is_db": False, "primary": "Biceps", "secondary": None},
        "Dumbbell Bicep Curls": {"muscle": "Biceps", "type": "weight", "is_db": True, "primary": "Biceps", "secondary": None},
        "Triceps Rope Pushdown": {"muscle": "Triceps", "type": "weight", "is_db": False, "primary": "Triceps", "secondary": None},
        "Overhead Cable Triceps Extension": {"muscle": "Triceps", "type": "weight", "is_db": False, "primary": "Triceps", "secondary": None},
        "Crunches": {"muscle": "Abs", "type": "bodyweight", "primary": "Abs", "secondary": None},
        "Plank": {"muscle": "Core", "type": "bodyweight_time", "primary": "Abs", "secondary": None}
    },
    "templates": {
        "Δευτέρα": [
            {"ex": "Stationary Bike (Ποδήλατο)", "s": 1, "w": 6.0, "r": 5, "rir": 0},
            {"ex": "Leg Press", "s": 3, "w": 105.0, "r": 12, "rir": 2},
            {"ex": "Flat Dumbbell Chest Press", "s": 3, "w": 17.5, "r": 12, "rir": 2},
            {"ex": "Pull-ups (Έλξεις στο Ζυγό)", "s": 3, "w": 0.0, "r": 8, "rir": 2},
            {"ex": "Chest-Supported DB Row (30°)", "s": 3, "w": 10.0, "r": 12, "rir": 2},
            {"ex": "Roman Chair Hyperextensions (Ρωμαϊκή Έδρα)", "s": 3, "w": 0.0, "r": 12, "rir": 2},
            {"ex": "Triceps Rope Pushdown", "s": 3, "w": 15.0, "r": 12, "rir": 2},
            {"ex": "Crunches", "s": 2, "w": 0.0, "r": 20, "rir": 1}
        ],
        "Τετάρτη": [
            {"ex": "Treadmill (Διάδρομος)", "s": 1, "w": 12.0, "r": 5, "rir": 0},
            {"ex": "Romanian Deadlift (RDL)", "s": 3, "w": 16.0, "r": 10, "rir": 2},
            {"ex": "Chin-ups (Υπτιάστιες Έλξεις)", "s": 3, "w": 0.0, "r": 8, "rir": 2},
            {"ex": "Incline DB Bench Press", "s": 3, "w": 12.5, "r": 10, "rir": 2},
            {"ex": "Dumbbell Shoulder Press", "s": 3, "w": 12.5, "r": 8, "rir": 2},
            {"ex": "Cable Lateral Raises (Τροχαλία)", "s": 3, "w": 5.0, "r": 12, "rir": 2},
            {"ex": "Cable Face Pulls", "s": 3, "w": 12.5, "r": 15, "rir": 2},
            {"ex": "Plank", "s": 2, "w": 0.0, "r": 60, "rir": 1}
        ],
        "Παρασκευή": [
            {"ex": "Stationary Bike (Ποδήλατο)", "s": 1, "w": 6.0, "r": 5, "rir": 0},
            {"ex": "Leg Extension Machine", "s": 3, "w": 45.0, "r": 12, "rir": 2},
            {"ex": "Seated Leg Curl Machine", "s": 3, "w": 40.0, "r": 12, "rir": 2},
            {"ex": "Seated Cable Row (Κωπηλατική Τροχαλία)", "s": 3, "w": 45.0, "r": 12, "rir": 2},
            {"ex": "Lateral Raises (Αλτήρες)", "s": 3, "w": 5.0, "r": 12, "rir": 2},
            {"ex": "Cable Bicep Curls", "s": 3, "w": 12.5, "r": 12, "rir": 2},
            {"ex": "Overhead Cable Triceps Extension", "s": 3, "w": 15.0, "r": 12, "rir": 2},
            {"ex": "Crunches", "s": 2, "w": 0.0, "r": 20, "rir": 1}
        ]
    },
    "prs": {},
    "achievements": [],
    "history": []
}

# Load / Save Helpers
def load_user_data():
    if "user_data" not in st.session_state:
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for k in default_data:
                        if k not in data:
                            data[k] = default_data[k]
                    st.session_state["user_data"] = data
            except Exception:
                st.session_state["user_data"] = json.loads(json.dumps(default_data))
        else:
            st.session_state["user_data"] = json.loads(json.dumps(default_data))
            
    # Ensure weight log has initial entry
    if not st.session_state["user_data"].get("weight_log"):
        today_str = datetime.now().strftime("%d/%m/%Y")
        st.session_state["user_data"]["weight_log"] = [{"date": today_str, "weight": st.session_state["user_data"]["profile"]["weight_kg"]}]

    # Ensure food_db & daily_logs exist
    if "food_db" not in st.session_state["user_data"]:
        st.session_state["user_data"]["food_db"] = default_food_db.copy()
    if "daily_logs" not in st.session_state["user_data"]:
        st.session_state["user_data"]["daily_logs"] = []

def save_user_data():
    if "user_data" in st.session_state:
        # 1. Τοπική αποθήκευση στο session
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state["user_data"], f, ensure_ascii=False, indent=2)
        except Exception:
            pass
            
        # 2. Αυτόματο Sync στο GitHub (αν έχουν οριστεί Secrets)
        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
            try:
                token = st.secrets["GITHUB_TOKEN"]
                repo = st.secrets["GITHUB_REPO"]
                url = f"https://api.github.com/repos/{repo}/contents/{DATA_FILE}"
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                
                # Λήψη SHA του υπάρχοντος αρχείου στο GitHub
                get_res = requests.get(url, headers=headers)
                sha = get_res.json().get("sha", "") if get_res.status_code == 200 else ""
                
                # Προετοιμασία περιεχομένου σε base64
                content_json = json.dumps(st.session_state["user_data"], ensure_ascii=False, indent=2)
                content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")
                
                payload = {
                    "message": "🤖 Auto-save user gym data",
                    "content": content_b64,
                    "sha": sha
                }
                
                # Push στο GitHub
                requests.put(url, headers=headers, json=payload)
            except Exception:
                pass

load_user_data()
user_data = st.session_state["user_data"]

# ------------------------------------------------------------------------------
# 3. HELPER FUNCTIONS
# ------------------------------------------------------------------------------
def get_level_title(lvl):
    titles = {
        1: "Gym Novice (Πρωτάρης)",
        2: "Iron Enthusiast (Σιδερένιος)",
        3: "Hypertrophy Apprentice (Μαθητευόμενος)",
        4: "Bench Press Specialist (Παγκίτης)",
        5: "Iron Warrior (Πολεμιστής)",
        6: "Volume Monster (Τέρας Όγκου)",
        7: "Local Gym Legend (Θρύλος του Gym)",
        8: "Hypertrophy Master (Master Υπερτροφίας)",
        9: "Iron God (Θεός του Σιδήρου)",
        10: "Titan of Muscle (Τιτάνας)"
    }
    return titles.get(lvl, f"Overlord Level {lvl}")

def get_tonnage_quips(tonnage_kg):
    for limit, text in TONNAGE_QUIPS:
        if tonnage_kg <= limit: return text
    return TONNAGE_QUIPS[-1][1]

def calc_macros(prof):
    p_wt, p_ht, p_age = prof["weight_kg"], prof["height_cm"], prof["age"]
    bmr = (10 * p_wt) + (6.25 * p_ht) - (5 * p_age) + 5 if prof["gender"] == "Άνδρας" else (10 * p_wt) + (6.25 * p_ht) - (5 * p_age) - 161
    tdee = bmr * prof["activity_level"]
    target_cal = tdee + 350 if prof["goal"] == "Bulking" else (tdee - 450 if prof["goal"] == "Cutting" else tdee)
    prot_g = p_wt * (2.2 if prof["goal"] == "Cutting" else 2.0) # 2.0g/kg για Bulking/Maintenance
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
        return [], [], [], "Δεν υπάρχουν ακόμα καταγραφές βάρους."
        
    start_date = logs[0]["date_obj"]
    start_weight = logs[0]["weight"]
    
    real_dates = []
    moving_avgs = []
    
    for i, entry in enumerate(logs):
        real_dates.append(entry["date_str"])
        window = [logs[j]["weight"] for j in range(max(0, i-6), i+1)]
        moving_avgs.append(round(sum(window) / len(window), 2))
        
    goal = profile.get("goal", "Bulking")
    training_age = profile.get("training_age", "Αρχάριος (0-1 έτος)")
    
    if goal == "Bulking":
        weekly_rate = 0.0030 if "Αρχάριος" in training_age else (0.0018 if "Ενδιάμεσος" in training_age else 0.0009)
    elif goal == "Cutting":
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
        
        if goal == "Bulking":
            if actual_gain_kg <= 0:
                status_msg = "⚠️ <b>Υποσιτισμός / Στασιμότητα:</b> Το βάρος δεν αυξάνεται. Προτείνεται αύξηση +200 kcal/ημέρα!"
            elif actual_gain_kg > (projected_gain_kg * 1.8 + 0.5):
                status_msg = "🚨 <b>Πολύ γρήγορη αύξηση:</b> Κίνδυνος αυξημένου λίπους. Μειώστε τις θερμίδες κατά -150 kcal/ημέρα."
            else:
                status_msg = "🟢 <b>Ιδανικός Ρυθμός Καθαρής Υπερτροφίας:</b> Το βάρος αυξάνεται σύμφωνα με το επιστημονικό μοντέλο!"
        elif goal == "Cutting":
            if actual_gain_kg >= 0:
                status_msg = "⚠️ <b>Στασιμότητα:</b> Δεν παρατηρείται απώλεια. Μειώστε τις θερμίδες κατά -200 kcal/ημέρα."
            else:
                status_msg = "🟢 <b>Αποτελεσματική Λιποδιάλυση:</b> Το βάρος μειώνεται σύμφωνα με τον στόχο!"
        else:
            status_msg = "🟢 <b>Σταθερή Συντήρηση:</b> Το σωματικό βάρος διατηρείται σταθερό."
            
    return real_dates, moving_avgs, projected_weights, status_msg

def check_and_unlock_achievements(total_tonnage):
    unlocked = []
    current_achs = user_data.get("achievements", [])
    
    if user_data.get("prs") and "🏆 First Blood (Πρώτο PR)" not in current_achs:
        unlocked.append("🏆 First Blood (Έσπασες το πρώτο σου ατομικό ρεκόρ!)")
        current_achs.append("🏆 First Blood (Πρώτο PR)")
        
    if total_tonnage >= 10000 and "🏋️ 10 Ton Club" not in current_achs:
        unlocked.append("🏋️ 10 Ton Club (Σήκωσες πάνω από 10.000 kg σε μία συνεδρία!)")
        current_achs.append("🏋️ 10 Ton Club")

    if total_tonnage >= 25000 and "🐘 25 Ton Titan" not in current_achs:
        unlocked.append("🐘 25 Ton Titan (Ξεπέρασες τα 25.000 kg σε μία προπόνηση!)")
        current_achs.append("🐘 25 Ton Titan")

    if len(user_data.get("weight_log", [])) >= 7 and "⚖️ Scale Master" not in current_achs:
        unlocked.append("⚖️ Scale Master (Κατέγραψες το βάρος σου για 7+ ημέρες!)")
        current_achs.append("⚖️ Scale Master")

    user_data["achievements"] = current_achs
    return unlocked

# ------------------------------------------------------------------------------
# 4. APP NAVIGATION & UI
# ------------------------------------------------------------------------------
st.title("🏋️ GYM COACHING OS")
st.caption("Interactive Fitness, Nutrition & Body Composition Tracker")

tab1, tab_tracker, tab2, tab3 = st.tabs([
    "🎮 Dashboard & Βάρος", 
    "🥗 Daily Nutrition Tracker", 
    "🏋️ Fitness Tracker (MWF)", 
    "📊 Visual Analytics"
])

# ==============================================================================
# TAB 1: DASHBOARD & BODY WEIGHT
# ==============================================================================
with tab1:
    prof = user_data["profile"]
    lvl = prof["level"]
    title = get_level_title(lvl)
    req_xp = lvl * 200
    curr_xp = prof["xp"]
    
    # Header Gamification Banner
    st.markdown(f"### 🎮 Level {lvl} — {title}")
    st.progress(min(1.0, curr_xp / req_xp))
    st.caption(f"Progress: {curr_xp} / {req_xp} XP")
    
    # Badges
    achs = user_data.get("achievements", [])
    if achs:
        badge_html = "".join([f"<span class='badge-card'>{a}</span>" for a in achs])
        st.markdown(f"**🎖️ Parashmas ({len(achs)}):** {badge_html}", unsafe_allow_html=True)
        
    st.divider()
    
    col_w1, col_w2 = st.columns([2, 1])
    with col_w1:
        st.subheader("⚖️ Πρωινό Ζύγισμα (Νηστικός)")
        today_val = st.number_input("Σημερινό Βάρος (kg):", value=float(prof["weight_kg"]), step=0.1, key="daily_w_in")
        if st.button("⚖️ Καταγραφή Βάρους"):
            today_str = datetime.now().strftime("%d/%m/%Y")
            logs = user_data.get("weight_log", [])
            found = False
            for entry in logs:
                if entry["date"] == today_str:
                    entry["weight"] = today_val
                    found = True
                    break
            if not found:
                logs.append({"date": today_str, "weight": today_val})
            user_data["weight_log"] = logs
            user_data["profile"]["weight_kg"] = today_val
            save_user_data()
            st.success(f"✅ Καταγράφηκε: {today_val} kg για τις {today_str}!")
            st.rerun()

    # Projected vs Real Status
    _, _, _, status_msg = calc_projected_vs_real_weight(prof, user_data.get("weight_log", []))
    if status_msg:
        st.info(status_msg, icon="📊")

    st.divider()
    st.subheader("⚙️ Προσωπικά Στοιχεία & Στόχοι")
    
    with st.form("profile_form"):
        c1, c2 = st.columns(2)
        with c1:
            gender = st.selectbox("Φύλο", ["Άνδρας", "Γυναίκα"], index=0 if prof["gender"]=="Άνδρας" else 1)
            age = st.number_input("Ηλικία", value=int(prof["age"]), step=1)
            height = st.number_input("Ύψος (cm)", value=float(prof["height_cm"]), step=0.5)
            weight = st.number_input("Βάρος (kg)", value=float(prof["weight_kg"]), step=0.1)
        with c2:
            goal = st.selectbox("Στόχος", ["Bulking", "Cutting", "Συντήρηση"], index=["Bulking", "Cutting", "Συντήρηση"].index(prof.get("goal","Bulking")))
            train_age = st.selectbox("Επίπεδο", ["Αρχάριος (0-1 έτος)", "Ενδιάμεσος (1-3 έτη)", "Προχωρημένος (3+ έτη)"], index=["Αρχάριος (0-1 έτος)", "Ενδιάμεσος (1-3 έτη)", "Προχωρημένος (3+ έτη)"].index(prof.get("training_age","Αρχάριος (0-1 έτος)")))
            act_idx = [1.2, 1.375, 1.55, 1.725].index(prof.get("activity_level", 1.55))
            act_level = st.selectbox("Δραστηριότητα", [("Καθιστική (1.2)", 1.2), ("Ελαφριά (1.375)", 1.375), ("Μέτρια (1.55)", 1.55), ("Υψηλή (1.725)", 1.725)], index=act_idx, format_func=lambda x: x[0])[1]
            
        btn_save_p = st.form_submit_button("💾 Αποθήκευση Προφίλ")
        if btn_save_p:
            prof["gender"] = gender
            prof["age"] = age
            prof["height_cm"] = height
            prof["weight_kg"] = weight
            prof["goal"] = goal
            prof["training_age"] = train_age
            prof["activity_level"] = act_level
            save_user_data()
            st.success("✅ Το προφίλ ενημερώθηκε επιτυχώς!")
            st.rerun()

    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(prof)
    st.markdown("#### 📊 Στόχοι Μεταβολισμού (Mifflin-St Jeor):")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("BMR", f"{bmr} kcal")
    m2.metric("TDEE", f"{tdee} kcal")
    m3.metric("Στόχος Calories", f"{target_cal} kcal", f"{prof.get('goal')}")
    m4.metric("Macros (P/C/F)", f"{prot_g}g / {carb_g}g / {fat_g}g")

# ==============================================================================
# TAB 2: 🥗 DAILY NUTRITION TRACKER (Δυναμικά Συνδεδεμένο)
# ==============================================================================
with tab_tracker:
    st.title("🥗 Daily Nutrition & Protein Tracker")
    st.caption("Δυναμικά Συνδεδεμένο με τους Στόχους του Προφίλ σου")

    # Υπολογισμός Δυναμικών Στόχων από το Προφίλ
    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(user_data["profile"])

    # Υπολογισμός Συνόλων Ημέρας από τα daily_logs
    totals = {"cal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
    for log in user_data["daily_logs"]:
        totals["cal"] += log["cal"]
        totals["p"] += log["p"]
        totals["c"] += log["c"]
        totals["f"] += log["f"]

    # KPIs DASHBOARD
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        p_rem = max(0.0, prot_g - totals["p"])
        st.metric(f"Πρωτεΐνη (Στόχος: {prot_g}g)", f"{totals['p']:.1f}g", f"Λείπουν {p_rem:.1f}g", delta_color="inverse" if p_rem > 0 else "normal")
        st.progress(min(1.0, totals["p"] / prot_g if prot_g > 0 else 0.0))

    with col2:
        cal_rem = max(0.0, target_cal - totals["cal"])
        st.metric(f"Θερμίδες (Στόχος: {target_cal}kcal)", f"{int(totals['cal'])} kcal", f"Λείπουν {int(cal_rem)} kcal")
        st.progress(min(1.0, totals["cal"] / target_cal if target_cal > 0 else 0.0))

    with col3:
        c_rem = max(0.0, carb_g - totals["c"])
        st.metric(f"Υδατάνθρακες (Στόχος: {carb_g}g)", f"{totals['c']:.1f}g", f"Λείπουν {c_rem:.1f}g")
        st.progress(min(1.0, totals["c"] / carb_g if carb_g > 0 else 0.0))

    with col4:
        f_rem = max(0.0, fat_g - totals["f"])
        st.metric(f"Λιπαρά (Στόχος: {fat_g}g)", f"{totals['f']:.1f}g", f"Λείπουν {f_rem:.1f}g")
        st.progress(min(1.0, totals["fat"] / fat_g if fat_g > 0 else 0.0))

    if totals["p"] >= prot_g:
        st.success(f"🎉 Συγχαρητήρια! Κάλυψες τον ημερήσιο στόχο πρωτεΐνης ({prot_g}g)!")

    st.markdown("---")

    # ΚΑΤΑΓΡΑΦΗ ΓΕΥΜΑΤΟΣ
    st.subheader("➕ Καταγραφή Γεύματος")

    c_select, c_qty, c_btn = st.columns([3, 1.5, 1])

    food_db = user_data["food_db"]

    with c_select:
        selected_name = st.selectbox("Επίλεξε Τρόφιμο:", list(food_db.keys()))
        food_info = food_db[selected_name]

    with c_qty:
        if food_info["unit"] == "100g":
            qty = st.number_input("Γραμμάρια (g):", min_value=10, max_value=1000, value=150, step=10, key="qty_g")
            factor = qty / 100.0
            unit_str = f"{qty}g"
        else:
            qty = st.number_input("Τεμάχια / Μερίδες:", min_value=0.5, max_value=10.0, value=1.0, step=0.5, key="qty_p")
            factor = qty
            unit_str = f"{qty} τεμάχιο/α"

    with c_btn:
        st.write("")
        st.write("")
        if st.button("Προσθήκη ➕", key="btn_add_food"):
            calc_item = {
                "name": selected_name,
                "portion": unit_str,
                "cal": food_info["cal"] * factor,
                "p": food_info["p"] * factor,
                "c": food_info["c"] * factor,
                "f": food_info["f"] * factor,
            }
            user_data["daily_logs"].append(calc_item)
            save_user_data()
            st.rerun()

    # ΠΡΟΣΘΗΚΗ ΝΕΟΥ CUSTOM ΤΡΟΦΙΜΟΥ ΣΤΗ ΒΑΣΗ
    with st.expander("✨ Πρόσθεσε Νέο Τρόφιμο στη Βάση Δεδομένων (Custom Food Creator)"):
        st.write("Αν αγοράσεις κάποιο νέο προϊόν, πρόσθεσέ το εδώ για να αποθηκευτεί στη λιστα σου!")
        c_n, c_u = st.columns([3, 1])
        new_name = c_n.text_input("Όνομα Προϊόντος (π.χ. Tesco High Protein Pudding):")
        new_unit = c_u.selectbox("Μονάδα μέτρησης:", ["100g", "piece"])
        
        col_c1, col_c2, col_c3, col_c4 = st.columns(4)
        new_cal = col_c1.number_input("Θερμίδες (kcal):", min_value=0.0, value=100.0)
        new_p = col_c2.number_input("Πρωτεΐνη (g):", min_value=0.0, value=10.0)
        new_c = col_c3.number_input("Υδατάνθρακες (g):", min_value=0.0, value=10.0)
        new_f = col_c4.number_input("Λιπαρά (g):", min_value=0.0, value=2.0)
        
        if st.button("💾 Αποθήκευση στη Βάση", key="btn_save_custom"):
            if new_name.strip():
                user_data["food_db"][new_name.strip()] = {
                    "unit": new_unit,
                    "cal": new_cal,
                    "p": new_p,
                    "c": new_c,
                    "f": new_f
                }
                save_user_data()
                st.success(f"Το '{new_name}' προστέθηκε επιτυχώς στη βάση δεδομένων!")
                st.rerun()
            else:
                st.warning("Παρακαλώ δώσε ένα όνομα στο νέο προϊόν.")

    # ΙΣΤΟΡΙΚΟ ΗΜΕΡΑΣ & DELETE/RESET
    st.markdown("---")
    st.subheader("📋 Τι κατέγραψες σήμερα:")

    if user_data["daily_logs"]:
        rows_to_del_food = []
        for idx, item in enumerate(user_data["daily_logs"]):
            c_desc, c_del = st.columns([5, 1])
            with c_desc:
                st.write(
                    f"• **{item['name']}** ({item['portion']}) $\rightarrow$ "
                    f"**{item['p']:.1f}g P** | {int(item['cal'])} kcal | {item['c']:.1f}g C | {item['f']:.1f}g F"
                )
            with c_del:
                if st.button("🗑️", key=f"del_food_{idx}"):
                    rows_to_del_food.append(idx)
        
        if rows_to_del_food:
            for i in sorted(rows_to_del_food, reverse=True):
                user_data["daily_logs"].pop(i)
            save_user_data()
            st.rerun()
    else:
        st.info("Δεν έχεις καταγράψει ακόμα κάποιο γεύμα σήμερα.")

    st.write("")
    if st.button("🔄 Επαναφορά (Μηδενισμός Νέας Ημέρας)", key="btn_reset_day"):
        user_data["daily_logs"] = []
        save_user_data()
        st.rerun()

# ==============================================================================
# TAB 3: WORKOUT TRACKER (MWF)
# ==============================================================================
with tab2:
    st.subheader("🏋️ Καταγραφή Προπόνησης ανά Ημέρα")
    day_selected = st.selectbox("📅 Επιλογή Ημέρας:", ["Δευτέρα", "Τετάρτη", "Παρασκευή"])
    
    # Load default session template if state not set
    session_key = f"current_session_{day_selected}"
    if session_key not in st.session_state:
        st.session_state[session_key] = json.loads(json.dumps(user_data["templates"].get(day_selected, [])))
        
    current_list = st.session_state[session_key]
    
    st.markdown("##### 📋 Ασκήσεις Ημέρας:")
    ex_options = list(user_data["exercise_database"].keys())
    
    rows_to_delete = []
    
    for idx, item in enumerate(current_list):
        with st.expander(f"🔹 #{idx+1} {item['ex']}", expanded=True):
            col_ex, col_s, col_w, col_r, col_rir, col_del = st.columns([3, 1, 1, 1, 1, 1])
            with col_ex:
                item["ex"] = st.selectbox("Άσκηση", ex_options, index=ex_options.index(item["ex"]) if item["ex"] in ex_options else 0, key=f"ex_{day_selected}_{idx}")
            with col_s:
                item["s"] = st.number_input("Sets", value=int(item.get("s", 3)), min_value=1, max_value=20, key=f"s_{day_selected}_{idx}")
            
            ex_info = user_data["exercise_database"].get(item["ex"], {})
            ex_type = ex_info.get("type", "weight")
            
            with col_w:
                if ex_type == "cardio":
                    item["w"] = st.number_input("Lvl/Km", value=float(item.get("w", 12.0)), step=0.5, key=f"w_{day_selected}_{idx}")
                elif "bodyweight" in ex_type:
                    st.number_input("Kg", value=0.0, disabled=True, key=f"w_{day_selected}_{idx}")
                    item["w"] = 0.0
                else:
                    item["w"] = st.number_input("Kg", value=float(item.get("w", 20.0)), step=0.5, key=f"w_{day_selected}_{idx}")
            with col_r:
                if ex_type == "bodyweight_time":
                    item["r"] = st.number_input("Sec", value=int(item.get("r", 60)), step=5, key=f"r_{day_selected}_{idx}")
                elif ex_type == "cardio":
                    item["r"] = st.number_input("Min", value=int(item.get("r", 5)), step=1, key=f"r_{day_selected}_{idx}")
                else:
                    item["r"] = st.number_input("Reps", value=int(item.get("r", 12)), step=1, key=f"r_{day_selected}_{idx}")
            with col_rir:
                item["rir"] = st.number_input("RIR", value=int(item.get("rir", 2)), min_value=0, max_value=5, key=f"rir_{day_selected}_{idx}")
            with col_del:
                st.write("")
                st.write("")
                if st.button("❌", key=f"del_{day_selected}_{idx}"):
                    rows_to_delete.append(idx)

    if rows_to_delete:
        for i in sorted(rows_to_delete, reverse=True):
            current_list.pop(i)
        st.rerun()

    c_btn1, c_btn2 = st.columns(2)
    with c_btn1:
        if st.button("➕ Προσθήκη Extra Άσκησης"):
            current_list.append({"ex": "Leg Press", "s": 3, "w": 50.0, "r": 12, "rir": 2})
            st.rerun()
            
    with c_btn2:
        btn_digest = st.button("🔥 Ολοκλήρωση & Αποθήκευση", type="primary")

    if btn_digest:
        if not current_list:
            st.error("⚠️ Η λίστα ασκήσεων είναι κενή!")
        else:
            total_tonnage = 0
            total_cardio_cal = 0
            ex_summary = {}
            pr_alerts = []
            effective_sets = 0
            bonus_pr_xp = 0
            
            for item in current_list:
                ex = item["ex"]
                s = item["s"]
                w = item["w"]
                r = item["r"]
                rir = item["rir"]
                
                if rir <= 3: effective_sets += s
                ex_info = user_data["exercise_database"].get(ex, {})
                ex_type = ex_info.get("type", "weight")
                is_db = ex_info.get("is_db", False)
                muscle = ex_info.get("muscle", "General")
                primary = ex_info.get("primary", muscle)
                secondary = ex_info.get("secondary", None)
                
                cardio_cal = 0
                e1rm = 0
                
                if ex_type == "cardio":
                    cardio_cal = calc_cardio_calories(w, r, user_data["profile"]["weight_kg"])
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

            # PR Check
            if "prs" not in user_data: user_data["prs"] = {}
            for ex_name, ex_data in ex_summary.items():
                if ex_data["type"] == "weight":
                    c_1rm = ex_data["max_1rm"]
                    p_pr = user_data["prs"].get(ex_name, 0)
                    if c_1rm > p_pr:
                        user_data["prs"][ex_name] = c_1rm
                        pr_alerts.append(f"🏆 **ΝΕΟ PR!** {ex_name}: {c_1rm} kg (Προηγούμενο: {p_pr} kg)")
                        bonus_pr_xp += 150

            user_data["templates"][day_selected] = current_list
            unlocked_achs = check_and_unlock_achievements(total_tonnage)
            bonus_ach_xp = len(unlocked_achs) * 200
            
            user_data["history"].append({
                "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                "day": day_selected,
                "tonnage": total_tonnage,
                "cardio_cal": total_cardio_cal,
                "exercises": ex_summary
            })
            
            earned_xp = 100 + (effective_sets * 10) + bonus_pr_xp + bonus_ach_xp
            user_data["profile"]["xp"] += earned_xp
            
            req_xp = user_data["profile"]["level"] * 200
            if user_data["profile"]["xp"] >= req_xp:
                user_data["profile"]["level"] += 1
                st.balloons()
                st.success(f"🎉 **LEVEL UP! Έφτασες στο Level {user_data['profile']['level']}!**")
                
            save_user_data()
            
            st.markdown(f"""
            <div class='report-card'>
                <h3 style='color:#2b8a3e; margin-top:0;'>📊 REPORT ΠΡΟΠΟΝΗΣΗΣ ({day_selected})</h3>
                <p>• <b>Συνολικός Όγκος (Tonnage):</b> <span style='font-size:20px; color:#2b8a3e;'><b>{total_tonnage:,} kg</b></span></p>
                <p>• 🎈 <i>{get_tonnage_quips(total_tonnage)}</i></p>
                <p>• 🎮 <b>XP Earned:</b> +{earned_xp} XP</p>
            </div>
            """, unsafe_allow_html=True)
            
            if pr_alerts:
                st.warning("\n".join(pr_alerts))
            if unlocked_achs:
                st.success("🎖️ **UNLOCKED ACHIEVEMENTS:**\n" + "\n".join(unlocked_achs))

# ==============================================================================
# TAB 4: VISUAL ANALYTICS
# ==============================================================================
with tab3:
    st.subheader("📊 Visual Analytics & Body Composition")
    
    history = user_data.get("history", [])
    
    if not history:
        st.info("💡 Καταγράψτε την πρώτη σας προπόνηση στο Tab 3 για να εμφανιστούν τα αναλυτικά διαγράμματα!")
    else:
        fig = plt.figure(figsize=(12, 12))
        gs = fig.add_gridspec(3, 2)
        
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1])
        ax3 = fig.add_subplot(gs[1, 0])
        ax4 = fig.add_subplot(gs[1, 1])
        ax5 = fig.add_subplot(gs[2, :])
        
        # 1. Tonnage Graph
        dates = [f"{h.get('day','')}\n{h.get('date','').split()[0]}" for h in history]
        tonnages = [h.get("tonnage", 0) for h in history]
        ax1.plot(dates, tonnages, marker='o', color='#2b8a3e', linewidth=2)
        ax1.set_title("📈 Εξέλιξη Συνολικού Όγκου (Tonnage kg)")
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # 2. Selected Exercise Progress
        selected_ex = st.selectbox("🏋️ Επιλογή Άσκησης για Γράφημα:", list(user_data["exercise_database"].keys()))
        ex_dates, ex_vals = [], []
        for h in history:
            exs = h.get("exercises", {})
            if selected_ex in exs:
                ex_dates.append(f"{h.get('day','')}\n{h.get('date','').split()[0]}")
                ex_data = exs[selected_ex]
                if ex_data.get("type") == "weight":
                    ex_vals.append(ex_data.get("max_weight", 0))
                else:
                    ex_vals.append(ex_data.get("total_reps_or_min", 0))
                    
        if ex_vals:
            ax2.plot(ex_dates, ex_vals, marker='s', color='#1971c2', linewidth=2)
            ax2.set_title(f"📊 Πρόοδος: {selected_ex}")
            ax2.grid(True, linestyle='--', alpha=0.5)
        else:
            ax2.text(0.5, 0.5, f"Δεν υπάρχουν ακόμα δεδομένα για:\n{selected_ex}", ha='center', va='center')
            
        # 3. Muscle Volume Bar Chart
        muscle_volume = {"Quads": 0.0, "Hamstrings": 0.0, "Chest": 0.0, "Lats": 0.0, "Upper Back": 0.0, "Front Delts": 0.0, "Side Delts": 0.0, "Biceps": 0.0, "Triceps": 0.0, "Abs": 0.0}
        for h in history:
            exs = h.get("exercises", {})
            for ex_name, ex_data in exs.items():
                s = ex_data.get("sets", 0)
                db_info = user_data["exercise_database"].get(ex_name, {})
                prim = db_info.get("primary", db_info.get("muscle", None))
                sec = db_info.get("secondary", None)
                if prim in muscle_volume: muscle_volume[prim] += s * 1.0
                if sec in muscle_volume: muscle_volume[sec] += s * 0.5

        muscles = list(muscle_volume.keys())
        volumes = list(muscle_volume.values())
        colors = ['#20c997' if v >= 6 else '#ff6b6b' for v in volumes]
        ax3.bar(muscles, volumes, color=colors)
        ax3.axhline(y=10, color='#2b8a3e', linestyle='--', label='MAV (10 sets)')
        ax3.set_title("🏋️ Εβδομαδιαίος Όγκος Σετ ανά Μυϊκή Ομάδα")
        ax3.tick_params(axis='x', rotation=45)
        ax3.legend()
        
        # 4. Strength Benchmarks
        bw = user_data["profile"]["weight_kg"]
        my_bench = user_data.get("prs", {}).get("Flat Dumbbell Chest Press", bw * 0.7)
        my_legpress = user_data.get("prs", {}).get("Leg Press", bw * 1.5)
        my_lat = user_data.get("prs", {}).get("Lat Pulldown (Τροχαλία)", bw * 0.7)
        
        cats = ['Chest Press', 'Leg Press', 'Lat Pulldown']
        user_scores = [my_bench, my_legpress, my_lat]
        avg_novice = [bw * 0.8, bw * 1.6, bw * 0.75]
        
        x = range(len(cats))
        width = 0.35
        ax4.bar([p - width/2 for p in x], avg_novice, width=width, label='Μέσος Novice', color='#adb5bd')
        ax4.bar([p + width/2 for p in x], user_scores, width=width, label='Εσύ (1RM)', color='#2b8a3e')
        ax4.set_xticks(x)
        ax4.set_xticklabels(cats)
        ax4.set_title("🥊 Σύγκριση Δύναμης vs Μέσος Όρος")
        ax4.legend()
        
        # 5. Projected Target Curve vs Real Weight
        w_dates, w_mov_avg, w_proj, _ = calc_projected_vs_real_weight(user_data["profile"], user_data.get("weight_log", []))
        if w_dates:
            ax5.plot(w_dates, w_proj, color='#f59f00', linestyle='--', linewidth=2, label='Projected Target Curve')
            ax5.plot(w_dates, w_mov_avg, color='#2b8a3e', marker='o', linewidth=3, label='Real Weight Trend (Moving Avg)')
            ax5.set_title("⚖️ Projected Target vs Real Weight Trend")
            ax5.legend()
            ax5.grid(True, linestyle='--', alpha=0.5)

        plt.tight_layout()
        st.pyplot(fig)

# ------------------------------------------------------------------------------
# SIDEBAR / RESET
# ------------------------------------------------------------------------------
with st.sidebar:
    st.subheader("⚙️ Διαχείριση Δεδομένων")
    
    # Download JSON Backup
    json_str = json.dumps(user_data, ensure_ascii=False, indent=2)
    st.download_button(
        label="📥 Download gym_data.json",
        data=json_str,
        file_name="gym_data.json",
        mime="application/json"
    )
    
    # Upload JSON Restore
    uploaded_json = st.file_uploader("📤 Restore gym_data.json", type=["json"])
    if uploaded_json is not None:
        try:
            data = json.load(uploaded_json)
            st.session_state["user_data"] = data
            save_user_data()
            st.success("✅ Restore επιτυχές!")
            st.rerun()
        except Exception as e:
            st.error("❌ Σφάλμα αρχείου JSON.")

    st.divider()
    if st.button("🗑️ Επαναφορά στο Level 1 (Reset All)", type="secondary"):
        st.session_state["user_data"] = json.loads(json.dumps(default_data))
        if os.path.exists(DATA_FILE):
            try: os.remove(DATA_FILE)
            except Exception: pass
        save_user_data()
        st.warning("🗑️ Τα πάντα μηδενίστηκαν!")
        st.rerun()
