import json
import os
import re
import sys
from tkinter import messagebox

from constants import CONFIG_FILE, POWERS_FILE, APP_VERSION


def load_config():
    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception as e:
        messagebox.showerror("Config Error", f"Cannot load config:\n{e}")
        sys.exit(1)


def save_config(cfg):
    try:
        with open(CONFIG_FILE, "w") as f:
            json.dump(cfg, f, indent=2)
    except Exception as e:
        messagebox.showerror("Config Error", f"Cannot save config:\n{e}")


def load_powers():
    try:
        with open(POWERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)["powers"]
    except Exception as e:
        messagebox.showerror("Powers Error", f"Cannot load powers:\n{e}")
        return []


def format_description(text):
    if not text:
        return ""
    text = text.replace("/N", "\n")
    text = text.replace("|+|", "|\n|")
    idx = text.find("|")
    if idx > 0 and text[idx - 1] != "\n":
        text = text[:idx] + "\n" + text[idx:]
    text = re.sub(r"\*\*(.+?)\*\*", lambda m: "\n**" + m.group(1) + "**\n", text)
    return text.strip()


def migrate_char(data):
    """Add fields introduced after 1.0.2. Returns (data, was_migrated)."""
    migrated = False
    if "app_version" not in data:
        data["app_version"] = "1.0.2"
        migrated = True
    if "portrait" not in data:
        data["portrait"] = ""
        migrated = True
    if "body_modifications" not in data:
        data["body_modifications"] = []
        migrated = True
    if isinstance(data.get("aberrations"), str):
        old = data["aberrations"].strip()
        data["aberrations"] = [old] if old else []
        migrated = True
    # Convert old fixed-slot custom_abilities {"ATTR__custom_0": [name, val]} →
    # new list format {"ATTR": [[name, val], ...]}
    custom = data.get("custom_abilities", {})
    if any("__custom_" in k for k in custom):
        new_custom = {}
        for k, v in custom.items():
            if "__custom_" in k:
                attr = k.split("__custom_")[0]
                name = v[0] if v else ""
                val  = v[1] if len(v) > 1 else 0
                if name:
                    new_custom.setdefault(attr, []).append([name, val])
            else:
                new_custom[k] = v
        data["custom_abilities"] = new_custom
        migrated = True
    return data, migrated


def empty_character(cfg):
    """Return a blank character dict matching the config structure."""
    char = {
        "birth_name": "", "nova_name": "", "series": "",
        "eruption": "", "nature": "", "allegiance": "",
        "attributes": {a: 1 for group in [cfg["physical_attributes"],
                                          cfg["mental_attributes"],
                                          cfg["social_attributes"]] for a in group},
        "abilities": {},
        "ability_specialties": {},
        "custom_abilities": {},
        "backgrounds": {},
        "mega_attributes": {ma: 0 for ma in cfg["mega_attributes"]},
        "willpower_perm": 3, "willpower_temp": 3,
        "taint_perm": 0, "taint_temp": 0,
        "aberrations": [],
        "quantum": 1,
        "quantum_pool_max": 20, "quantum_pool_current": 0,
        "attacks": [{"name": "", "acc": "", "dmg": "", "rof": "", "ft": ""} for _ in range(cfg["num_attack_rows"])],
        "armors":  [{"name": "", "b": "", "l": "", "bulk": "", "ft": ""} for _ in range(cfg["num_armor_rows"])],
        "soak_bashing": "", "soak_lethal": "",
        "game_notes": "",
        "portrait": "",
        "body_modifications": [],
        "app_version": APP_VERSION,
    }
    for attr, skills in cfg["abilities"].items():
        for skill in skills:
            char["abilities"][skill] = 3 if skill in ("Endurance", "Resistance") else 0
            char["ability_specialties"][skill] = False
    return char
