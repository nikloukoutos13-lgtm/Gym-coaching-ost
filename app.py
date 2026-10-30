import os
import json
import math
import requests
import base64
from datetime import datetime, timedelta
import streamlit as st
import matplotlib.pyplot as plt

# ------------------------------------------------------------------------------
# 1. PAGE CONFIG & STYLING
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Gym Coaching OS",
    page_icon="🏋️",
    layout="wide",
    initial_sidebar_state="expanded"
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
    .overload-card { background-color: #e7f5ff; border: 1px solid #339af0; padding: 12px; border-radius: 8px; margin-bottom: 10px; font-size: 14px; }
    .zone-badge { padding: 4px 10px; border-radius: 8px; font-weight: bold; color: white; display: inline-block; }
</style>
""", unsafe_allow_html=True)

DATA_FILE = "gym_data.json"
DAYS = ["Δευτέρα", "Τρίτη", "Τετάρτη", "Πέμπτη", "Παρασκευή", "Σάββατο", "Κυριακή"]

# ------------------------------------------------------------------------------
# 2. DEFAULT FOOD & EXERCISE DATABASES & 30+ QUIPS
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

default_exercise_db = {
    # Traditional Gym Exercises
    "Stationary Bike (Ποδήλατο)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": None},
    "Treadmill (Διάδρομος)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": None},
    "Running (Εξωτερικό Τρέξιμο)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": None},
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
    "Plank": {"muscle": "Core", "type": "bodyweight_time", "primary": "Abs", "secondary": None},

    # HYROX Specific Movements
    "SkiErg (HYROX)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": "Lats"},
    "Sled Push (HYROX)": {"muscle": "Quads", "type": "weight", "is_db": False, "primary": "Quads", "secondary": "Glutes"},
    "Sled Pull (HYROX)": {"muscle": "Hamstrings", "type": "weight", "is_db": False, "primary": "Hamstrings", "secondary": "Upper Back"},
    "Burpee Broad Jumps (HYROX)": {"muscle": "Full Body", "type": "bodyweight", "primary": "Quads", "secondary": "Cardio"},
    "RowErg / Κωπηλατικό (HYROX)": {"muscle": "Cardio", "type": "cardio", "primary": "Cardio", "secondary": "Upper Back"},
    "Farmers Carry (HYROX)": {"muscle": "Upper Back", "type": "weight", "is_db": True, "primary": "Upper Back", "secondary": "Abs"},
    "Sandbag Lunges (HYROX)": {"muscle": "Quads", "type": "weight", "is_db": False, "primary": "Quads", "secondary": "Glutes"},
    "Wall Balls (HYROX)": {"muscle": "Full Body", "type": "weight", "is_db": False, "primary": "Quads", "secondary": "Front Delts"}
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

CARDIO_RUNNING_QUIPS = [
    (1, "🐢 Πρώτο χιλιόμετρο! Ξεπέρασες τη χελώνα του Αισώπου!"),
    (2, "🏃 Τρέχεις ήδη πιο γρήγορα από το 80% των ανθρώπων στον καναπέ!"),
    (3, "🐕 Έτρεξες όσο ένας δραστήριος σκύλος Golden Retriever στο πάρκο!"),
    (4, "🐈 Προσπέρασες μια γάτα που κυνηγάει ποντίκι!"),
    (5, "🐇 5km! Ξεπέρασες ένα κουνέλι σε πλήρη ταχύτητα!"),
    (6, "🦔 Κινείσαι πιο γρήγορα κι από τον Sonic the Hedgehog!"),
    (8, "🐺 8km! Κάλυψες την ημερήσια περιοδεία μιας αγέλης λύκων!"),
    (10, "🐎 10km! Τρέχεις με το σθένος και την αντοχή ενός καθαρόαιμου αλόγου!"),
    (12, "🦘 Κάλυψες απόσταση μεγαλύτερη από 1.000 άλματα καγκουρό!"),
    (15, "🐆 15km! Σήμερα προσπέρασες έναν γατόπαρδο (Cheetah) σε αντοχή!"),
    (18, "🦅 Έτρεξες όσο πετάει ένας αετός σε μια πρωινή περιπολία!"),
    (21, "🏅 21km Ημιμαραθώνιος! Είσαι επίσημα μηχανή αντοχής!"),
    (25, "🦁 Έτρεξες περισσότερο από όσο διανύει ένα λιοντάρι στη σαβάνα!"),
    (30, "🐬 Κάλυψες την απόσταση που κολυμπάει ένα δελφίνι στον ωκεανό!"),
    (35, "🐫 Διασχίζεις αποστάσεις σαν καμήλα στη Σαχάρα χωρίς να σταματάς!"),
    (42, "🏆 42.2km ΜΑΡΑΘΩΝΙΟΣ! Γράφεις ιστορία σαν τον Φειδιππίδη!"),
    (50, "🚀 50km Ultramarathon! Προσπέρασες τα σύνορα της πόλης!"),
    (100, "🛸 100km! Είσαι πλέον υπεράνθρωπος, εκτός γήινου συναγωνισμού!"),
    (101, "🛷 Sled Push: Σπρώξατε βάρος μεγαλύτερο από έναν ενήλικο Γορίλα!"),
    (102, "🐻 Sled Pull: Τραβήξατε το βάρος μιας επιθετικής Πολικής Αρκούδας!"),
    (103, "🚣 SkiErg / RowErg: Κωπηλατήσατε τη διαδρομή μιας ολόκληρης λίμνης!"),
    (104, "☄️ Burpee Broad Jumps: Εξερράγης σαν πύραυλος SpaceX σε κάθε άλμα!"),
    (105, "🧱 Wall Balls: Εκτοξεύσατε τη μπάλα πιο ψηλά κι από τον τοίχο!"),
    (106, "🎒 Sandbag Lunges: Κουβαλήσατε το βάρος ενός πολεμιστή Spartan Race!"),
    (107, "🏋️ Farmers Carry: Σφίξατε τη λαβή σας σαν μέγγενη από τιτάνιο!"),
    (108, "🔥 HYROX Workout Complete: Κάψατε θερμίδες για ένα μικρό χωριό!"),
    (109, "⚡ Roxzone Master: Μεταβάσεις πιο γρήγορες κι από pit stop Formula 1!"),
    (110, "👑 HYROX Queen: Ένταση προπόνησης επιπέδου World Championship!"),
    (111, "💣 Cardio Explosion: Η καρδιά σου δουλεύει σαν ελβετικό ρολόι!"),
    (112, "🛡️ Unstoppable Endurance: Η αντοχή σου λυγίζει ακόμα και σίδερα!")
]

default_nikos_profile = {
    "profile": {
        "gender": "Άνδρας", "age": 28, "weight_kg": 72.0, "height_cm": 177.0,
        "activity_level": 1.55, "goal": "Bulking", "training_age": "Αρχάριος (0-1 έτος)",
        "xp": 0, "level": 1
    },
    "daily_logs": [],
    "weight_log": [{"date": datetime.now().strftime("%d/%m/%Y"), "weight": 72.0}],
    "templates": {
        "Δευτέρα": [
            {"ex": "Stationary Bike (Ποδήλατο)", "s": 1, "w": 6.0, "r": 5, "rir": 0},
            {"ex": "Leg Press", "s": 3, "w": 105.0, "r": 12, "rir": 2},
            {"ex": "Flat Dumbbell Chest Press", "s": 3, "w": 17.5, "r": 12, "rir": 2},
            {"ex": "Pull-ups (Έλξεις στο Ζυγό)", "s": 3, "w": 0.0, "r": 8, "rir": 2},
            {"ex": "Chest-Supported DB Row (30°)", "s": 3, "w": 10.0, "r": 12, "rir": 2},
            {"ex": "Triceps Rope Pushdown", "s": 3, "w": 15.0, "r": 12, "rir": 2}
        ],
        "Τρίτη": [],
        "Τετάρτη": [
            {"ex": "Treadmill (Διάδρομος)", "s": 1, "w": 12.0, "r": 5, "rir": 0},
            {"ex": "Romanian Deadlift (RDL)", "s": 3, "w": 16.0, "r": 10, "rir": 2},
            {"ex": "Chin-ups (Υπτιάστιες Έλξεις)", "s": 3, "w": 0.0, "r": 8, "rir": 2},
            {"ex": "Incline DB Bench Press", "s": 3, "w": 12.5, "r": 10, "rir": 2},
            {"ex": "Dumbbell Shoulder Press", "s": 3, "w": 12.5, "r": 8, "rir": 2}
        ],
        "Πέμπτη": [],
        "Παρασκευή": [
            {"ex": "Stationary Bike (Ποδήλατο)", "s": 1, "w": 6.0, "r": 5, "rir": 0},
            {"ex": "Leg Extension Machine", "s": 3, "w": 45.0, "r": 12, "rir": 2},
            {"ex": "Seated Leg Curl Machine", "s": 3, "w": 40.0, "r": 12, "rir": 2},
            {"ex": "Seated Cable Row (Κωπηλατική Τροχαλία)", "s": 3, "w": 45.0, "r": 12, "rir": 2},
            {"ex": "Cable Bicep Curls", "s": 3, "w": 12.5, "r": 12, "rir": 2}
        ],
        "Σάββατο": [],
        "Κυριακή": []
    },
    "prs": {},
    "achievements": [],
    "history": []
}

default_marilena_profile = {
    "profile": {
        "gender": "Γυναίκα", "age": 26, "weight_kg": 60.0, "height_cm": 165.0,
        "activity_level": 1.725, "goal": "Συντήρηση", "training_age": "Ενδιάμεσος (1-3 έτη)",
        "xp": 0, "level": 1
    },
    "daily_logs": [],
    "weight_log": [{"date": datetime.now().strftime("%d/%m/%Y"), "weight": 60.0}],
    "templates": {
        "Δευτέρα": [
            {"ex": "Running (Εξωτερικό Τρέξιμο)", "s": 1, "w": 5.0, "r": 28, "rir": 0, "hr": 145},
            {"ex": "SkiErg (HYROX)", "s": 3, "w": 0.0, "r": 10, "rir": 1},
            {"ex": "Sled Push (HYROX)", "s": 4, "w": 75.0, "r": 15, "rir": 2}
        ],
        "Τρίτη": [],
        "Τετάρτη": [
            {"ex": "Running (Εξωτερικό Τρέξιμο)", "s": 1, "w": 6.0, "r": 33, "rir": 0, "hr": 152},
            {"ex": "RowErg / Κωπηλατικό (HYROX)", "s": 3, "w": 0.0, "r": 10, "rir": 1},
            {"ex": "Wall Balls (HYROX)", "s": 4, "w": 6.0, "r": 20, "rir": 1}
        ],
        "Πέμπτη": [],
        "Παρασκευή": [
            {"ex": "Running (Εξωτερικό Τρέξιμο)", "s": 1, "w": 8.0, "r": 45, "rir": 0, "hr": 158},
            {"ex": "Sled Pull (HYROX)", "s": 4, "w": 50.0, "r": 15, "rir": 2},
            {"ex": "Farmers Carry (HYROX)", "s": 3, "w": 16.0, "r": 50, "rir": 2}
        ],
        "Σάββατο": [],
        "Κυριακή": []
    },
    "prs": {},
    "achievements": [],
    "history": []
}

# ------------------------------------------------------------------------------
# 3. PROFILE MIGRATION & PERSISTENCE
# ------------------------------------------------------------------------------
def load_user_data():
    if "user_data" not in st.session_state:
        data = None
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                data = None
        
        if not data: data = {}

        if "food_db" not in data: data["food_db"] = default_food_db.copy()
        if "exercise_database" not in data: data["exercise_database"] = default_exercise_db.copy()
        else:
            for k, v in default_exercise_db.items():
                if k not in data["exercise_database"]: data["exercise_database"][k] = v

        # Convert/Migrate Profiles if needed
        if "profiles" not in data or not isinstance(data.get("profiles"), dict):
            data["profiles"] = {
                "NIKOS (Gym & Hypertrophy)": json.loads(json.dumps(default_nikos_profile)),
                "MARILENA (HYROX & Run)": json.loads(json.dumps(default_marilena_profile))
            }
            data["active_profile"] = "NIKOS (Gym & Hypertrophy)"

        if "active_profile" not in data or data["active_profile"] not in data["profiles"]:
            data["active_profile"] = list(data["profiles"].keys())[0]

        st.session_state["user_data"] = data

load_user_data()
user_data = st.session_state["user_data"]

def save_user_data():
    if "user_data" in st.session_state:
        try:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(st.session_state["user_data"], f, ensure_ascii=False, indent=2)
        except Exception:
            pass

        if "GITHUB_TOKEN" in st.secrets and "GITHUB_REPO" in st.secrets:
            try:
                token = st.secrets["GITHUB_TOKEN"]
                repo = st.secrets["GITHUB_REPO"]
                url = f"https://api.github.com/repos/{repo}/contents/{DATA_FILE}"
                headers = {
                    "Authorization": f"token {token}",
                    "Accept": "application/vnd.github.v3+json"
                }
                get_res = requests.get(url, headers=headers)
                sha = get_res.json().get("sha", "") if get_res.status_code == 200 else ""
                
                content_json = json.dumps(st.session_state["user_data"], ensure_ascii=False, indent=2)
                content_b64 = base64.b64encode(content_json.encode("utf-8")).decode("utf-8")
                
                payload = {
                    "message": "🤖 Auto-save multi-profile gym data",
                    "content": content_b64,
                    "sha": sha
                }
                requests.put(url, headers=headers, json=payload)
            except Exception:
                pass

active_profile_name = user_data["active_profile"]
active_p = user_data["profiles"][active_profile_name]

# ------------------------------------------------------------------------------
# 4. HELPER CALCULATORS & STREAK / GAMIFICATION ENGINE
# ------------------------------------------------------------------------------
def req_xp_for_level(lvl):
    return int(500 * (lvl ** 1.6))

def get_level_title(lvl):
    titles = {
        1: "Novice (Πρωτάρης)", 2: "Enthusiast (Σιδερένιος)", 3: "Apprentice (Μαθητευόμενος)",
        4: "Specialist (Ειδικός)", 5: "Warrior (Πολεμιστής)", 6: "Volume Monster (Τέρας)",
        7: "Gym Legend (Θρύλος)", 8: "Master Υπερτροφίας", 9: "Iron God (Θεός)", 10: "Titan (Τιτάνας)"
    }
    return titles.get(lvl, f"Level {lvl} Master")

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

def get_cardio_quip(dist_km, ex_name=""):
    if "Sled Push" in ex_name: return CARDIO_RUNNING_QUIPS[18][1]
    if "Sled Pull" in ex_name: return CARDIO_RUNNING_QUIPS[19][1]
    if "SkiErg" in ex_name or "RowErg" in ex_name: return CARDIO_RUNNING_QUIPS[20][1]
    if "Burpee" in ex_name: return CARDIO_RUNNING_QUIPS[21][1]
    if "Wall Balls" in ex_name: return CARDIO_RUNNING_QUIPS[22][1]
    if "Sandbag" in ex_name: return CARDIO_RUNNING_QUIPS[23][1]
    
    for limit, text in CARDIO_RUNNING_QUIPS:
        if dist_km <= limit and limit <= 100: return text
    return CARDIO_RUNNING_QUIPS[17][1]

def calc_hr_zone(hr_bpm, age=26):
    max_hr = 211 - (0.64 * age)
    pct = (hr_bpm / max_hr) * 100.0 if max_hr > 0 else 0
    if pct < 60: return "Zone 1: Active Recovery (50-60%)", "#339af0"
    elif pct < 70: return "Zone 2: Aerobic Endurance (60-70%)", "#51cf66"
    elif pct < 80: return "Zone 3: Tempo / Aerobic Capacity (70-80%)", "#fcc419"
    elif pct < 90: return "Zone 4: Threshold / Lactate (80-90%)", "#ff922b"
    else: return "Zone 5: Anaerobic Max Sprint (90-100%)", "#ff6b6b"

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
        return {"w": max_w + inc, "r": reps, "msg": f"🚀 **High RIR ({avg_rir:.1f}):** Increase load by +{inc} kg!"}
    elif avg_rir >= 1.5:
        inc = 0.5 if is_db else 1.25
        return {"w": max_w + inc, "r": reps, "msg": f"🎯 **Optimal RIR ({avg_rir:.1f}):** Moderate overload +{inc} kg."}
    else:
        return {"w": max_w, "r": reps + 1, "msg": f"💪 **Near Failure (RIR {avg_rir:.1f}):** Keep weight at {max_w} kg, target {reps+1} reps."}

def calc_macros(prof):
    p_wt, p_ht, p_age = prof["weight_kg"], prof["height_cm"], prof["age"]
    bmr = (10 * p_wt) + (6.25 * p_ht) - (5 * p_age) + (5 if prof["gender"] == "Άνδρας" else -161)
    tdee = bmr * prof["activity_level"]
    target_cal = tdee + 350 if prof["goal"] == "Bulking" else (tdee - 450 if prof["goal"] == "Cutting" else tdee)
    prot_g = p_wt * (2.2 if prof["goal"] == "Cutting" else 2.0)
    fat_g = (target_cal * 0.25) / 9
    carb_g = (target_cal - (prot_g * 4 + fat_g * 9)) / 4
    return round(bmr), round(tdee), round(target_cal), round(prot_g), round(carb_g), round(fat_g)

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
    
    real_dates, moving_avgs = [], []
    for i, entry in enumerate(logs):
        real_dates.append(entry["date_str"])
        window = [logs[j]["weight"] for j in range(max(0, i-6), i+1)]
        moving_avgs.append(round(sum(window) / len(window), 2))
        
    goal = profile.get("goal", "Bulking")
    training_age = profile.get("training_age", "Αρχάριος (0-1 έτος)")
    weekly_rate = 0.0030 if goal == "Bulking" and "Αρχάριος" in training_age else (-0.0075 if goal == "Cutting" else 0.0)
        
    projected_weights = []
    for entry in logs:
        days_diff = (entry["date_obj"] - start_date).days
        proj_w = start_weight * ((1 + weekly_rate) ** (days_diff / 7.0))
        projected_weights.append(round(proj_w, 2))
        
    status_msg = "🟢 **Σταθερή Πορεία:** Το βάρος εξελίσσεται ομαλά!" if len(logs) >= 2 else ""
    return real_dates, moving_avgs, projected_weights, status_msg

# ------------------------------------------------------------------------------
# 5. SIDEBAR: PROFILE SWITCHER & STREAKS
# ------------------------------------------------------------------------------
with st.sidebar:
    st.subheader("👤 Profile Selector")
    profile_list = list(user_data["profiles"].keys())
    curr_idx = profile_list.index(active_profile_name) if active_profile_name in profile_list else 0
    
    selected_prof = st.selectbox("Active Profile:", profile_list, index=curr_idx)
    if selected_prof != active_profile_name:
        user_data["active_profile"] = selected_prof
        save_user_data()
        st.rerun()

    # Calculate Streak
    history_dates = [h.get("date", "") for h in active_p.get("history", [])] + [w.get("date", "") for w in active_p.get("weight_log", [])]
    streak_days, logged_today = calculate_streak(history_dates)
    
    st.markdown(f"### 🔥 Streak: **{streak_days} Days**")
    if logged_today:
        st.success("✅ Logged today!")
    else:
        st.warning("⚠️ Log a workout/weight to maintain streak!")

    st.divider()
    with st.expander("➕ Create New Profile"):
        new_p_name = st.text_input("Name:")
        new_p_type = st.selectbox("Type:", ["Gym & Hypertrophy", "HYROX & Running"])
        if st.button("Create Profile"):
            if new_p_name.strip() and new_p_name.strip() not in user_data["profiles"]:
                tpl = default_marilena_profile if "HYROX" in new_p_type else default_nikos_profile
                user_data["profiles"][new_p_name.strip()] = json.loads(json.dumps(tpl))
                user_data["active_profile"] = new_p_name.strip()
                save_user_data()
                st.rerun()

    st.divider()
    st.subheader("⚙️ Data Management")
    json_str = json.dumps(user_data, ensure_ascii=False, indent=2)
    st.download_button("📥 Backup JSON", data=json_str, file_name="gym_data.json", mime="application/json")
    
    uploaded_json = st.file_uploader("📤 Restore JSON", type=["json"])
    if uploaded_json is not None:
        try:
            data = json.load(uploaded_json)
            st.session_state["user_data"] = data
            save_user_data()
            st.success("✅ Restore successful!")
            st.rerun()
        except Exception:
            st.error("❌ Invalid JSON file.")

# ------------------------------------------------------------------------------
# 6. APP TABS
# ------------------------------------------------------------------------------
st.title("🏋️ GYM & HYROX COACHING OS")
st.caption(f"Active Profile: **{active_profile_name}**")

tab1, tab_tracker, tab2, tab3 = st.tabs([
    "🎮 Dashboard & Weight", 
    "🥗 Daily Nutrition", 
    "🏋️ Schedule & Workout Tracker", 
    "📊 Analytics & HR Zones"
])

# ==============================================================================
# TAB 1: DASHBOARD
# ==============================================================================
with tab1:
    prof = active_p["profile"]
    lvl = prof["level"]
    title = get_level_title(lvl)
    req_xp = req_xp_for_level(lvl)
    curr_xp = prof["xp"]
    
    st.markdown(f"### 🎮 Level {lvl} — {title}")
    st.progress(min(1.0, curr_xp / req_xp))
    st.caption(f"XP Progress: {curr_xp} / {req_xp} XP (Stricter Exponential Scaling)")
    
    achs = active_p.get("achievements", [])
    if achs:
        badge_html = "".join([f"<span class='badge-card'>{a}</span>" for a in achs])
        st.markdown(f"**🎖️ Badges ({len(achs)}):** {badge_html}", unsafe_allow_html=True)
        
    st.divider()
    c_w1, c_w2 = st.columns([2, 1])
    with c_w1:
        st.subheader("⚖️ Morning Weight Log")
        today_val = st.number_input("Today's Weight (kg):", value=float(prof["weight_kg"]), step=0.1, key=f"w_in_{active_profile_name}")
        if st.button("⚖️ Save Weight", key=f"btn_w_{active_profile_name}"):
            today_str = datetime.now().strftime("%d/%m/%Y")
            logs = active_p.get("weight_log", [])
            logs.append({"date": today_str, "weight": today_val})
            active_p["weight_log"] = logs
            active_p["profile"]["weight_kg"] = today_val
            
            # Streak bonus XP
            active_p["profile"]["xp"] += 15
            save_user_data()
            st.success(f"✅ Saved {today_val} kg!")
            st.rerun()

    # Profile Edit Form
    st.divider()
    st.subheader("⚙️ Profile Parameters")
    with st.form(key=f"p_form_{active_profile_name}"):
        fc1, fc2 = st.columns(2)
        with fc1:
            gender = st.selectbox("Gender", ["Άνδρας", "Γυναίκα"], index=0 if prof["gender"]=="Άνδρας" else 1)
            age = st.number_input("Age", value=int(prof["age"]), step=1)
            height = st.number_input("Height (cm)", value=float(prof["height_cm"]), step=0.5)
            weight = st.number_input("Weight (kg)", value=float(prof["weight_kg"]), step=0.1)
        with fc2:
            goal = st.selectbox("Goal", ["Bulking", "Cutting", "Συντήρηση"], index=["Bulking", "Cutting", "Συντήρηση"].index(prof.get("goal","Bulking")))
            train_age = st.selectbox("Training Level", ["Αρχάριος (0-1 έτος)", "Ενδιάμεσος (1-3 έτη)", "Προχωρημένος (3+ έτη)"], index=["Αρχάριος (0-1 έτος)", "Ενδιάμεσος (1-3 έτη)", "Προχωρημένος (3+ έτη)"].index(prof.get("training_age","Αρχάριος (0-1 έτος)")))
            act_idx = [1.2, 1.375, 1.55, 1.725].index(prof.get("activity_level", 1.55))
            act_level = st.selectbox("Activity Level", [("Sedentary (1.2)", 1.2), ("Light (1.375)", 1.375), ("Moderate (1.55)", 1.55), ("High (1.725)", 1.725)], index=act_idx, format_func=lambda x: x[0])[1]
            
        if st.form_submit_button("💾 Save Profile Settings"):
            prof.update({"gender": gender, "age": age, "height_cm": height, "weight_kg": weight, "goal": goal, "training_age": train_age, "activity_level": act_level})
            save_user_data()
            st.success("✅ Profile Updated!")
            st.rerun()

    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(prof)
    st.markdown("#### 📊 Target Daily Macros (Mifflin-St Jeor):")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("BMR", f"{bmr} kcal")
    m2.metric("TDEE", f"{tdee} kcal")
    m3.metric("Calorie Goal", f"{target_cal} kcal")
    m4.metric("Macros (P/C/F)", f"{prot_g}g / {carb_g}g / {fat_g}g")

# ==============================================================================
# TAB 2: NUTRITION
# ==============================================================================
with tab_tracker:
    st.subheader("🥗 Daily Food & Protein Tracker")
    bmr, tdee, target_cal, prot_g, carb_g, fat_g = calc_macros(active_p["profile"])
    
    totals = {"cal": 0.0, "p": 0.0, "c": 0.0, "f": 0.0}
    for log in active_p.get("daily_logs", []):
        totals["cal"] += log.get("cal", 0.0)
        totals["p"] += log.get("p", 0.0)
        totals["c"] += log.get("c", 0.0)
        totals["f"] += log.get("f", 0.0)

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Protein", f"{totals['p']:.1f}g", f"Goal: {prot_g}g")
    col2.metric("Calories", f"{int(totals['cal'])} kcal", f"Goal: {target_cal} kcal")
    col3.metric("Carbs", f"{totals['c']:.1f}g", f"Goal: {carb_g}g")
    col4.metric("Fats", f"{totals['f']:.1f}g", f"Goal: {fat_g}g")

    st.markdown("---")
    st.subheader("➕ Log Meal")
    food_db = user_data["food_db"]
    c_sel, c_qty, c_btn = st.columns([3, 1.5, 1])
    with c_sel:
        selected_food = st.selectbox("Select Food Item:", list(food_db.keys()), key=f"food_s_{active_profile_name}")
        f_info = food_db[selected_food]
    with c_qty:
        qty = st.number_input("Amount (g or pieces):", value=150.0 if f_info["unit"]=="100g" else 1.0, step=10.0 if f_info["unit"]=="100g" else 0.5, key=f"food_q_{active_profile_name}")
        factor = (qty / 100.0) if f_info["unit"] == "100g" else qty
    with c_btn:
        st.write("")
        st.write("")
        if st.button("Add ➕", key=f"btn_food_add_{active_profile_name}"):
            active_p["daily_logs"].append({
                "name": selected_food, "portion": f"{qty}{'g' if f_info['unit']=='100g' else ' pc'}",
                "cal": f_info["cal"] * factor, "p": f_info["p"] * factor,
                "c": f_info["c"] * factor, "f": f_info["f"] * factor
            })
            save_user_data()
            st.rerun()

    # Custom Food Creator
    with st.expander("✨ Add Custom Item to Food Database"):
        cf_n = st.text_input("Name:", key="cf_n")
        cf_u = st.selectbox("Unit:", ["100g", "piece"], key="cf_u")
        c1, c2, c3, c4 = st.columns(4)
        cf_cal = c1.number_input("Calories", value=100.0, key="cf_cal")
        cf_p = c2.number_input("Protein (g)", value=10.0, key="cf_p")
        cf_c = c3.number_input("Carbs (g)", value=10.0, key="cf_c")
        cf_f = c4.number_input("Fats (g)", value=2.0, key="cf_f")
        if st.button("Save Custom Food", key="btn_cf"):
            if cf_n.strip():
                user_data["food_db"][cf_n.strip()] = {"unit": cf_u, "cal": cf_cal, "p": cf_p, "c": cf_c, "f": cf_f}
                save_user_data()
                st.success("Food added!")
                st.rerun()

    st.markdown("---")
    st.subheader("📋 Today's Meals:")
    if active_p.get("daily_logs"):
        for idx, item in enumerate(active_p["daily_logs"]):
            cd1, cd2 = st.columns([5, 1])
            cd1.write(f"• **{item['name']}** ({item['portion']}) $\rightarrow$ **{item['p']:.1f}g P** | {int(item['cal'])} kcal")
            if cd2.button("🗑️", key=f"del_meal_{active_profile_name}_{idx}"):
                active_p["daily_logs"].pop(idx)
                save_user_data()
                st.rerun()

# ==============================================================================
# TAB 3: WORKOUT TRACKER & AUTO OVERLOAD
# ==============================================================================
with tab2:
    st.subheader("🏋️ Weekly Schedule (Monday – Sunday)")
    day_selected = st.selectbox("📅 Choose Day:", DAYS, key=f"day_sel_{active_profile_name}")
    
    if "templates" not in active_p: active_p["templates"] = {}
    if day_selected not in active_p["templates"]: active_p["templates"][day_selected] = []
    
    current_list = active_p["templates"][day_selected]
    ex_options = list(user_data["exercise_database"].keys())
    
    rows_to_delete = []
    
    for idx, item in enumerate(current_list):
        p_key = active_profile_name.replace(" ", "_")
        ex_name = item["ex"]
        ex_info = user_data["exercise_database"].get(ex_name, {})
        ex_type = ex_info.get("type", "weight")
        
        # Check Auto Progressive Overload for Nikos / Weight Exercises
        overload_info = calc_progressive_overload(ex_name, active_p.get("history", []), user_data["exercise_database"])
        
        with st.expander(f"🔹 #{idx+1} {ex_name}", expanded=True):
            if overload_info and "NIKOS" in active_profile_name:
                st.markdown(f"<div class='overload-card'>⚡ <b>Auto Progressive Overload Suggestion:</b><br>{overload_info['msg']}<br>Target: <b>{overload_info['w']} kg x {overload_info['r']} reps</b></div>", unsafe_allow_html=True)
                if st.button(f"⚡ Apply Overload Target ({overload_info['w']}kg)", key=f"ov_btn_{p_key}_{day_selected}_{idx}"):
                    item["w"] = overload_info["w"]
                    item["r"] = overload_info["r"]
                    save_user_data()
                    st.rerun()

            c_ex, c_s, c_w, c_r, c_rir, c_del = st.columns([3, 1, 1, 1, 1, 0.5])
            with c_ex:
                curr_idx = ex_options.index(ex_name) if ex_name in ex_options else 0
                item["ex"] = st.selectbox("Exercise", ex_options, index=curr_idx, key=f"ex_{p_key}_{day_selected}_{idx}")
            with c_s:
                item["s"] = st.number_input("Sets", value=int(item.get("s", 3)), min_value=1, key=f"s_{p_key}_{day_selected}_{idx}")
            with c_w:
                if ex_type == "cardio":
                    item["w"] = st.number_input("Dist (km)", value=float(item.get("w", 5.0)), step=0.5, key=f"w_{p_key}_{day_selected}_{idx}")
                else:
                    item["w"] = st.number_input("Kg", value=float(item.get("w", 20.0)), step=0.5, key=f"w_{p_key}_{day_selected}_{idx}")
            with c_r:
                if ex_type == "cardio":
                    item["r"] = st.number_input("Time (Min)", value=int(item.get("r", 25)), step=1, key=f"r_{p_key}_{day_selected}_{idx}")
                else:
                    item["r"] = st.number_input("Reps", value=int(item.get("r", 12)), step=1, key=f"r_{p_key}_{day_selected}_{idx}")
            with c_rir:
                if ex_type == "cardio":
                    item["hr"] = st.number_input("Avg HR", value=int(item.get("hr", 145)), min_value=60, max_value=220, key=f"hr_{p_key}_{day_selected}_{idx}")
                else:
                    item["rir"] = st.number_input("RIR", value=int(item.get("rir", 2)), min_value=0, max_value=5, key=f"rir_{p_key}_{day_selected}_{idx}")
            with c_del:
                st.write("")
                if st.button("❌", key=f"del_{p_key}_{day_selected}_{idx}"):
                    rows_to_delete.append(idx)

            # Display Running Pace & HR Zone if Cardio (Marilena Specialized)
            if ex_type == "cardio" and item.get("w", 0) > 0 and item.get("r", 0) > 0:
                dist = item["w"]
                mins = item["r"]
                pace_dec = mins / dist
                pace_m = int(pace_dec)
                pace_s = int((pace_dec - pace_m) * 60)
                z_name, z_color = calc_hr_zone(item.get("hr", 145), active_p["profile"]["age"])
                
                st.info(f"🏃 **Pace:** {pace_m}:{pace_s:02d} min/km | **Speed:** {60/pace_dec:.1f} km/h | **HR Zone:** {z_name}", icon="⚡")

    if rows_to_delete:
        for i in sorted(rows_to_delete, reverse=True): current_list.pop(i)
        save_user_data()
        st.rerun()

    c_b1, c_b2, c_b3 = st.columns(3)
    with c_b1:
        if st.button("➕ Add Exercise to Routine"):
            current_list.append({"ex": ex_options[0], "s": 3, "w": 10.0, "r": 12, "rir": 2})
            save_user_data()
            st.rerun()
    with c_b2:
        if st.button("💾 Save Schedule Changes"):
            save_user_data()
            st.success("✅ Schedule saved successfully!")
    with c_b3:
        if st.button("🔥 Complete & Log Workout", type="primary"):
            if not current_list:
                st.error("Routine is empty!")
            else:
                total_tonnage = 0
                ex_summary = {}
                quip_msg = ""
                
                for item in current_list:
                    ex = item["ex"]
                    s, w, r = item["s"], item["w"], item["r"]
                    ex_info = user_data["exercise_database"].get(ex, {})
                    ex_type = ex_info.get("type", "weight")
                    
                    if ex_type == "weight":
                        total_tonnage += s * w * r
                    elif ex_type == "cardio":
                        quip_msg = get_cardio_quip(w, ex)

                    ex_summary[ex] = {"sets": s, "max_weight": w, "total_reps_or_min": r, "type": ex_type}

                active_p["history"].append({
                    "date": datetime.now().strftime("%d/%m/%Y %H:%M"),
                    "day": day_selected,
                    "tonnage": total_tonnage,
                    "exercises": ex_summary
                })
                
                # Stricter XP reward
                earned_xp = 35 + (len(current_list) * 5)
                active_p["profile"]["xp"] += earned_xp
                
                if active_p["profile"]["xp"] >= req_xp_for_level(active_p["profile"]["level"]):
                    active_p["profile"]["level"] += 1
                    st.balloons()
                    st.success(f"🎉 LEVEL UP! Reached Level {active_p['profile']['level']}!")

                save_user_data()
                st.success(f"Workout logged! Earned +{earned_xp} XP.")
                if quip_msg: st.info(f"🎈 **Achievement Quip:** {quip_msg}")

    # Custom Exercise Creator
    st.markdown("---")
    with st.expander("✨ Add Custom Exercise to Master Database"):
        ce_name = st.text_input("Exercise Name:", key="ce_n")
        ce_col1, ce_col2 = st.columns(2)
        ce_type = ce_col1.selectbox("Type:", ["Weight (Barbell/Machine)", "Dumbbell", "Bodyweight", "Cardio / Running"], key="ce_t")
        ce_muscle = ce_col2.selectbox("Target Muscle:", ["Quads", "Hamstrings", "Chest", "Lats", "Upper Back", "Front Delts", "Side Delts", "Rear Delts", "Biceps", "Triceps", "Abs", "Cardio"], key="ce_m")
        if st.button("Save Exercise to Database", key="btn_ce"):
            if ce_name.strip():
                user_data["exercise_database"][ce_name.strip()] = {
                    "muscle": ce_muscle,
                    "type": "cardio" if "Cardio" in ce_type else "weight",
                    "is_db": True if "Dumbbell" in ce_type else False,
                    "primary": ce_muscle,
                    "secondary": None
                }
                save_user_data()
                st.success(f"Exercise '{ce_name}' saved!")
                st.rerun()

# ==============================================================================
# TAB 4: VISUAL ANALYTICS & HR ZONES
# ==============================================================================
with tab3:
    st.subheader(f"📊 Visual Analytics & Performance — {active_profile_name}")
    history = active_p.get("history", [])
    
    if not history:
        st.info("Log your first workout in Tab 3 to generate visual charts!")
    else:
        fig = plt.figure(figsize=(12, 10))
        gs = fig.add_gridspec(2, 2)
        
        ax1 = fig.add_subplot(gs[0, 0])
        ax2 = fig.add_subplot(gs[0, 1])
        ax3 = fig.add_subplot(gs[1, 0])
        ax4 = fig.add_subplot(gs[1, 1])
        
        # 1. Tonnage Graph
        dates = [f"{h.get('day','')}\n{h.get('date','').split()[0]}" for h in history[-8:]]
        tonnages = [h.get("tonnage", 0) for h in history[-8:]]
        ax1.plot(dates, tonnages, marker='o', color='#2b8a3e', linewidth=2)
        ax1.set_title("📈 Tonnage Progress (kg)")
        ax1.grid(True, linestyle='--', alpha=0.5)
        
        # 2. Exercise Specific Progression
        selected_ex = st.selectbox("Select Exercise for Chart:", list(user_data["exercise_database"].keys()), key=f"chart_ex_{active_profile_name}")
        ex_dates, ex_vals = [], []
        for h in history:
            exs = h.get("exercises", {})
            if selected_ex in exs:
                ex_dates.append(f"{h.get('day','')}\n{h.get('date','').split()[0]}")
                ex_vals.append(exs[selected_ex].get("max_weight", 0) if exs[selected_ex].get("type") == "weight" else exs[selected_ex].get("total_reps_or_min", 0))
                
        if ex_vals:
            ax2.plot(ex_dates, ex_vals, marker='s', color='#1971c2', linewidth=2)
            ax2.set_title(f"📊 Progress: {selected_ex}")
            ax2.grid(True, linestyle='--', alpha=0.5)
        else:
            ax2.text(0.5, 0.5, f"No history yet for:\n{selected_ex}", ha='center', va='center')

        # 3. Target Muscle Volume Distribution
        m_counts = {"Quads": 0, "Chest": 0, "Lats": 0, "Upper Back": 0, "Side Delts": 0, "Biceps": 0, "Triceps": 0, "Cardio": 0}
        for h in history:
            for ex_n, ex_d in h.get("exercises", {}).items():
                m = user_data["exercise_database"].get(ex_n, {}).get("primary", "Cardio")
                if m in m_counts: m_counts[m] += ex_d.get("sets", 1)
                
        ax3.bar(list(m_counts.keys()), list(m_counts.values()), color='#20c997')
        ax3.axhline(y=10, color='#2b8a3e', linestyle='--', label='MAV (10 sets)')
        ax3.set_title("🏋️ Weekly Volume per Muscle Target")
        ax3.tick_params(axis='x', rotation=45)
        ax3.legend()

        # 4. Projected vs Real Weight Trend
        w_dates, w_mov_avg, w_proj, _ = calc_projected_vs_real_weight(active_p["profile"], active_p.get("weight_log", []))
        if w_dates:
            ax4.plot(w_dates, w_proj, color='#f59f00', linestyle='--', label='Projected Target')
            ax4.plot(w_dates, w_mov_avg, color='#2b8a3e', marker='o', label='Real Weight Trend')
            ax4.set_title("⚖️ Target vs Real Weight")
            ax4.legend()
            ax4.grid(True, linestyle='--', alpha=0.5)

        plt.tight_layout()
        st.pyplot(fig)
        plt.close(fig)
