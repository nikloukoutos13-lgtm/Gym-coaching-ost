import os
import json
import re

# Απόλυτη διαδρομή της ρίζας του project (εκεί που βρίσκεται το data_manager.py)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
USER_DATA_DIR = os.path.join(BASE_DIR, "user_data")
PROFILES_DIR = os.path.join(USER_DATA_DIR, "profiles")

def ensure_directories():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(USER_DATA_DIR, exist_ok=True)
    os.makedirs(PROFILES_DIR, exist_ok=True)

def sanitize_filename(name):
    clean = re.sub(r'[^a-zA-Z0-9_-]', '_', name.lower())
    return re.sub(r'_+', '_', clean).strip('_')

def load_json(filepath, default_val):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Σφάλμα κατά την ανάγνωση του {filepath}: {e}")
    return default_val

def save_json(filepath, data):
    ensure_directories()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_all_app_data():
    ensure_directories()
    
    # 1. Φόρτωση settings
    settings = load_json(os.path.join(USER_DATA_DIR, "settings.json"), {"active_profile": ""})
    
    # 2. Φόρτωση Στατικών Βάσεων Δεδομένων από το data/
    base_foods = load_json(os.path.join(DATA_DIR, "base_foods.json"), {})
    base_exercises = load_json(os.path.join(DATA_DIR, "base_exercises.json"), {})
    
    # 3. Φόρτωση Δυναμικών / Custom Βάσεων Δεδομένων από το user_data/
    custom_foods = load_json(os.path.join(USER_DATA_DIR, "custom_foods.json"), {})
    custom_exercises = load_json(os.path.join(USER_DATA_DIR, "custom_exercises.json"), {})
    
    # 4. Συγχώνευση (Τα custom υπερισχύουν σε περίπτωση διπλότυπων)
    merged_foods = {**base_foods, **custom_foods}
    merged_exercises = {**base_exercises, **custom_exercises}
    
    # 5. Φόρτωση όλων των Προφίλ από το user_data/profiles/
    profiles = {}
    if os.path.exists(PROFILES_DIR):
        for fname in os.listdir(PROFILES_DIR):
            if fname.endswith(".json"):
                p_path = os.path.join(PROFILES_DIR, fname)
                p_data = load_json(p_path, None)
                if p_data and isinstance(p_data, dict):
                    p_name = p_data.get("profile_name", fname.replace(".json", ""))
                    profiles[p_name] = p_data

    active_p = settings.get("active_profile", "")
    if not active_p or active_p not in profiles:
        active_p = list(profiles.keys())[0] if profiles else ""

    return {
        "active_profile": active_p,
        "food_db": merged_foods,
        "exercise_database": merged_exercises,
        "profiles": profiles
    }

def save_profile_file(profile_name, profile_data):
    profile_data["profile_name"] = profile_name
    fname = f"{sanitize_filename(profile_name)}.json"
    save_json(os.path.join(PROFILES_DIR, fname), profile_data)

def save_settings_file(active_profile_name):
    save_json(os.path.join(USER_DATA_DIR, "settings.json"), {"active_profile": active_profile_name})

def save_custom_foods_file(food_db):
    base_foods = load_json(os.path.join(DATA_DIR, "base_foods.json"), {})
    only_custom = {k: v for k, v in food_db.items() if k not in base_foods or base_foods[k] != v}
    save_json(os.path.join(USER_DATA_DIR, "custom_foods.json"), only_custom)

def save_custom_exercises_file(exercise_db):
    base_exercises = load_json(os.path.join(DATA_DIR, "base_exercises.json"), {})
    only_custom = {k: v for k, v in exercise_db.items() if k not in base_exercises or base_exercises[k] != v}
    save_json(os.path.join(USER_DATA_DIR, "custom_exercises.json"), only_custom)
