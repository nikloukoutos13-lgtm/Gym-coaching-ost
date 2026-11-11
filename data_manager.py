import os
import json
import re

DATA_DIR = "data"
USER_DATA_DIR = "user_data"
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
        except Exception:
            pass
    return default_val

def save_json(filepath, data):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def migrate_legacy_data():
    """Αυτόματο σπάσιμο του μονολιθικού gym_data.json σε υπο-αρχεία JSON."""
    legacy_file = "gym_data.json"
    if os.path.exists(legacy_file):
        try:
            with open(legacy_file, "r", encoding="utf-8") as f:
                legacy = json.load(f)
            
            if "active_profile" in legacy:
                save_json(os.path.join(USER_DATA_DIR, "settings.json"), {"active_profile": legacy["active_profile"]})
            if "food_db" in legacy:
                save_json(os.path.join(USER_DATA_DIR, "custom_foods.json"), legacy["food_db"])
            if "exercise_database" in legacy:
                save_json(os.path.join(USER_DATA_DIR, "custom_exercises.json"), legacy["exercise_database"])
                
            if "profiles" in legacy and isinstance(legacy["profiles"], dict):
                for p_name, p_data in legacy["profiles"].items():
                    p_data["profile_name"] = p_name
                    fname = f"{sanitize_filename(p_name)}.json"
                    save_json(os.path.join(PROFILES_DIR, fname), p_data)
            
            os.rename(legacy_file, "gym_data.json.bak")
        except Exception as e:
            print(f"Migration error: {e}")

def load_all_app_data():
    ensure_directories()
    migrate_legacy_data()
    
    settings = load_json(os.path.join(USER_DATA_DIR, "settings.json"), {"active_profile": ""})
    
    # 1. Φόρτωση Στατικών Βάσεων Δεδομένων
    base_foods = load_json(os.path.join(DATA_DIR, "base_foods.json"), {})
    base_exercises = load_json(os.path.join(DATA_DIR, "base_exercises.json"), {})
    
    # 2. Φόρτωση Δυναμικών / Custom Βάσεων Δεδομένων
    custom_foods = load_json(os.path.join(USER_DATA_DIR, "custom_foods.json"), {})
    custom_exercises = load_json(os.path.join(USER_DATA_DIR, "custom_exercises.json"), {})
    
    # 3. Συγχώνευση (Τα custom υπερισχύουν σε περίπτωσή διπλότυπων)
    merged_foods = {**base_foods, **custom_foods}
    merged_exercises = {**base_exercises, **custom_exercises}
    
    # 4. Φόρτωση όλων των Προφίλ από το user_data/profiles/
    profiles = {}
    if os.path.exists(PROFILES_DIR):
        for fname in os.listdir(PROFILES_DIR):
            if fname.endswith(".json"):
                p_data = load_json(os.path.join(PROFILES_DIR, fname), None)
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
    ensure_directories()
    profile_data["profile_name"] = profile_name
    fname = f"{sanitize_filename(profile_name)}.json"
    save_json(os.path.join(PROFILES_DIR, fname), profile_data)

def save_settings_file(active_profile_name):
    ensure_directories()
    save_json(os.path.join(USER_DATA_DIR, "settings.json"), {"active_profile": active_profile_name})

def save_custom_foods_file(food_db):
    ensure_directories()
    save_json(os.path.join(USER_DATA_DIR, "custom_foods.json"), food_db)

def save_custom_exercises_file(exercise_db):
    ensure_directories()
    save_json(os.path.join(USER_DATA_DIR, "custom_exercises.json"), exercise_db)
