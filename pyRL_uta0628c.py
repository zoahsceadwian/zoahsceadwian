#edits to saving into leaderboard to include more

import csv
import os
import sys
import time
import random
import copy

# For non-blocking input on POSIX systems
if os.name == 'posix':
    import tty
    import termios
    import select
    import atexit

# --- Color Constants ---
COLOR_RED = '\033[91m'
COLOR_GREEN = '\033[92m'
COLOR_YELLOW = '\033[93m'
COLOR_CYAN = '\033[96m'
COLOR_RESET = '\033[0m'

# --- Configuration Constants (formerly config.py) ---
REFRESH_RATE = 0.1  # seconds per game tick
ATTRIBUTES = [
    "STA", "STR", "AGI", "DEX", "HIT", "BAL", "WGT", "HEI",
    "INT", "WIL", "FOR", "FOC", "PSY",
    "ARC", "BLS", "MAN", "ALC",
    "CUR", "COR", "SUM", "HEX"
]
SLOT_NAMES = {
    1: "Head", 2: "Chest", 3: "Legs", 4: "Feet",
    5: "Off-Hand", 6: "Main-Hand", 7: "Neck", 8: "Ring"
}
ACTION_KEYS_PLAYER = {
    'a': "Basic Melee", 's': "Basic Magic",
    'z': "Main-Hand Action (Slot 6)", 'x': "Off-Hand Action (Slot 5)",
    'd': "Neck Action (Slot 7)", 'c': "Ring Action (Slot 8)"
}
MAX_ACTIVE_EFFECTS = 2
MAX_COMBAT_LOG_ENTRIES = 10

DEFAULT_MELEE_ACTION_ID = 1 # Punch
DEFAULT_MAGIC_ACTION_ID = 2 # Curse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

CSV_FILES = {
    "toons": os.path.join(BASE_DIR, "pyRL_toons.csv"),
    "actions": os.path.join(BASE_DIR, "pyRL_actions.csv"),
    "npcs": os.path.join(BASE_DIR, "pyRL_npcs.csv"),
    "items": os.path.join(BASE_DIR, "pyRL_items.csv"),
    "saved": os.path.join(BASE_DIR, "pyRL_saved.csv"),
    "leaderboard": os.path.join(BASE_DIR, "pyRL_leaderboard.csv")
}


# --- Utility Functions (formerly utils.py) ---
_old_settings_tty = None # For Unix-like systems

def _init_tty_for_input_non_blocking():
    global _old_settings_tty
    if os.name == 'posix':
        _old_settings_tty = termios.tcgetattr(sys.stdin)
        tty.setcbreak(sys.stdin.fileno())

def _restore_tty_settings_non_blocking():
    if os.name == 'posix' and _old_settings_tty:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, _old_settings_tty)

def get_keypress():
    if os.name == 'nt':
        import msvcrt
        if msvcrt.kbhit():
            try:
                return msvcrt.getch().decode('utf-8', errors='ignore').lower()
            except UnicodeDecodeError:
                return None
        return None
    elif os.name == 'posix':
        if select.select([sys.stdin], [], [], 0)[0]:
            return sys.stdin.read(1).lower()
        return None
    return None

def load_csv_data(filename, key_column=None):
    data = []
    try:
        with open(filename, 'r', newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            if key_column:
                keyed_data = {}
                for row in reader:
                    processed_row = {}
                    for k, v_str in row.items():
                        v = v_str # Keep as string initially
                        if isinstance(v_str, str):
                            if v_str.isdigit():
                                v = int(v_str)
                            elif v_str.replace('.', '', 1).isdigit() and v_str.count('.') < 2:
                                 v = float(v_str)
                            elif v_str == '' or v_str == '-': # Handle empty or placeholder for None
                                v = None
                            # else, keep as string
                        processed_row[k] = v
                    
                    key_value = processed_row.get(key_column)
                    if key_value is not None: # Ensure key exists
                        keyed_data[key_value] = processed_row
                return keyed_data
            else: # Return list of dicts
                for row in reader:
                    processed_row = {}
                    for k, v_str in row.items():
                        v = v_str
                        if isinstance(v_str, str):
                            if v_str.isdigit():
                                v = int(v_str)
                            elif v_str.replace('.', '', 1).isdigit() and v_str.count('.') < 2:
                                 v = float(v_str)
                            elif v_str == '' or v_str == '-':
                                v = None
                        processed_row[k] = v
                    data.append(processed_row)
                return data
    except FileNotFoundError:
        print(f"Warning: File {filename} not found.")
        # Create empty CSV files if they are essential and missing (like saved/leaderboard)
        if filename in [CSV_FILES["saved"], CSV_FILES["leaderboard"]]:
            try:
                with open(filename, 'w', newline='', encoding='utf-8') as f_create:
                    # Write a header if possible, depends on expected structure
                    # For simplicity, just create empty. Load will return empty.
                    pass 
                print(f"Created empty file: {filename}")
            except Exception as e_create:
                print(f"Could not create {filename}: {e_create}")
        return {} if key_column else []
    except Exception as e:
        print(f"Error loading {filename}: {e}")
        return {} if key_column else []

def clear_screen():
    if os.name == 'nt':
        os.system('cls')
    else:
        sys.stdout.write('\033[2J\033[H')
        sys.stdout.flush()

def display_options(options, title="Choose an option:"):
    print(f"{COLOR_CYAN}{title}{COLOR_RESET}")
    print('-' * len(title))
    for i, option_name in enumerate(options, 1):
        print(f"{COLOR_YELLOW}{i}{COLOR_RESET}. {option_name}")
    while True:
        try:
            # Use standard input, not get_keypress for this menu
            if os.name == 'posix': _restore_tty_settings_non_blocking() # Temporarily restore for input()
            choice = input(f"Enter number (1-{len(options)}): ")
            if os.name == 'posix': _init_tty_for_input_non_blocking() # Re-enable non-blocking
            
            choice_idx = int(choice) - 1
            if 0 <= choice_idx < len(options):
                return choice_idx
            else:
                print("Invalid choice. Try again.")
        except ValueError:
            print("Invalid input. Please enter a number.")
        except EOFError: # Handle Ctrl+D or unexpected EOF
            print("Input aborted. Please try again.")
            if os.name == 'posix': _init_tty_for_input_non_blocking() # Ensure it's re-enabled


# --- Data Models (formerly data_models.py) ---
class Item:
    def __init__(self, data):  # data is a dict from CSV
        self.id = data.get('ItemID')
        self.slot = data.get('Slot')
        self.name = data.get('Name', 'Unknown Item')

        self.bonus1_id = data.get('Bonus1id')
        bonus1 = data.get('Bonus1add', 0) or 0
        if isinstance(bonus1, str):
            bonus1 = bonus1.replace('+-', '-')
        self.bonus1_add = int(bonus1)

        self.bonus2_id = data.get('Bonus2id')
        bonus2 = data.get('Bonus2add', 0) or 0
        if isinstance(bonus2, str):
            bonus2 = bonus2.replace('+-', '-')
        self.bonus2_add = int(bonus2)

        self.action_id = data.get('ActionID')

        self.skill_check_attr = data.get('SkillCheck')
        skl = data.get('SklChkAmount', 0) or 0
        self.skill_check_amount = int(skl)
        self.skill_check_opr = data.get('SklChkOpr', 'min')

        cd = data.get('Cooldown', 0) or 0
        self.cooldown_time = int(cd)
        self.current_cooldown = 0  # instance‐specific


class Action:
    def __init__(self, data): # data is a dict from CSV
        self.id = data.get('actionID')
        self.name = data.get('Name', 'Unknown Action')
        self.dmg_stat_source = data.get('DMG') # "AtkPw" or "MgcPw"
        self.base_val = data.get('BaseDMG', 0) if data.get('BaseDMG') is not None else 0

        self.self_buff_target_stat = data.get('selfBUFF')
        self.self_debuff_target_stat = data.get('selfDEBUFF')
        self.enemy_debuff_target_stat = data.get('DEBUFF')
        
        self.duration = data.get('Duration', 0) if data.get('Duration') is not None else 0
        self.timing = data.get('Timing') # 'start', 'end', 'tick'

# --- Global Data Stores for Items and Actions ---
ALL_ITEMS = {}
ALL_ACTIONS = {}

# --- Entity Class (formerly entity.py) ---
class Entity:
    def __init__(self, name, is_player=False):
        self.name = name
        self.is_player = is_player
        self.base_attributes = {attr: 0 for attr in ATTRIBUTES}
        self.equipped_items = {slot: None for slot in range(1, 9)}
        
        self.current_attributes = self.base_attributes.copy()

        self.max_hp = 0
        self.current_hp = 0
        self.atk_pw = 0
        self.atk_sp = 1 # Min 1
        self.mgc_pw = 0
        self.block_val = 0
        self.dodge_val = 0
        self.armor_val = 0
        self.mgc_rs_val = 0
        self.crits_val = 0

        self.attack_bar_progress = 0.0
        self.attack_fill_time = 5.0
        
        self.queued_action_key = 'a' if is_player else None
        self.selected_action_id = None

        self.active_effects = []
        self.total_damage_dealt_session = 0
        self.total_damage_taken_session = 0
        self.combat_start_time = 0
        self.item_cooldowns = {}

        self.xp = 0
        self.save_id = None # For saving player character, should be int or str

        self.npc_data_source = None
        self.action_sequence_index = 0
        self.level = 1
        self.text_start = ""
        self.text_death = ""
        self.text_win = ""

    def load_char_data(self, char_data_dict, is_saved_char=False):
        # Basic stats & name
        self.name = char_data_dict.get('Name', 'Unnamed Character')
        for attr in ATTRIBUTES:
            self.base_attributes[attr] = (
                char_data_dict.get(attr, 0)
                if char_data_dict.get(attr) is not None else 0
            )

        # Saved-character bookkeeping
        if is_saved_char:
            self.save_id = char_data_dict.get('SaveID')
            self.xp = (
                char_data_dict.get('XP', 0)
                if char_data_dict.get('XP') is not None else 0
            )

        # Equip each slot by deep-copying the Item instance
        for i in range(1, 9):
            item_id_val = char_data_dict.get(f'Slot{i}')
            if item_id_val is not None and item_id_val in ALL_ITEMS:
                # Clone the original Item so all its data comes along
                self.equipped_items[i] = copy.deepcopy(ALL_ITEMS[item_id_val])

        # Recalculate derived stats (with gear bonuses) and HP
        self.update_stats_and_effects()
        self.current_hp = self.max_hp


    def load_npc_data(self, npc_data_dict):
        self.npc_data_source = npc_data_dict
        self.name = npc_data_dict.get('Name', 'Unknown NPC')
        self.level = npc_data_dict.get('Level', 1) if npc_data_dict.get('Level') is not None else 1
        self.max_hp = npc_data_dict.get('HP', 100) if npc_data_dict.get('HP') is not None else 100
        self.current_hp = self.max_hp
        self.atk_pw = npc_data_dict.get('AtkPw', 10) if npc_data_dict.get('AtkPw') is not None else 10
        self.atk_sp = max(1, npc_data_dict.get('AtkSp', 20) if npc_data_dict.get('AtkSp') is not None else 20)
        self.mgc_pw = npc_data_dict.get('MgcPw', 10) if npc_data_dict.get('MgcPw') is not None else 10
        self.block_val = npc_data_dict.get('Block', 10) if npc_data_dict.get('Block') is not None else 10
        self.dodge_val = npc_data_dict.get('Dodge', 10) if npc_data_dict.get('Dodge') is not None else 10
        self.armor_val = npc_data_dict.get('Armor', 10) if npc_data_dict.get('Armor') is not None else 10
        self.mgc_rs_val = npc_data_dict.get('MgcRs', 10) if npc_data_dict.get('MgcRs') is not None else 10
        self.crits_val = npc_data_dict.get('Crits', 10) if npc_data_dict.get('Crits') is not None else 10
        
        self.attack_fill_time = 1.2 + (5.0 - 1.2) * (1 - self.atk_sp / 100.0)
        self.attack_fill_time = max(REFRESH_RATE, self.attack_fill_time)

        self.text_start = npc_data_dict.get('TextStart', f"{self.name} appears!")
        self.text_death = npc_data_dict.get('TextDeath', f"{self.name} is defeated.")
        self.text_win = npc_data_dict.get('TextWin', f"{self.name} is victorious!")
        self.selected_action_id = self.npc_data_source.get(f'act1')


    def _recalculate_current_attributes(self):
        self.current_attributes = self.base_attributes.copy()
        for slot, item_obj in self.equipped_items.items():
            if item_obj:
                if item_obj.bonus1_id and item_obj.bonus1_id in ATTRIBUTES:
                    self.current_attributes[item_obj.bonus1_id] = \
                        self.current_attributes.get(item_obj.bonus1_id, 0) + item_obj.bonus1_add
                if item_obj.bonus2_id and item_obj.bonus2_id in ATTRIBUTES:
                    self.current_attributes[item_obj.bonus2_id] = \
                        self.current_attributes.get(item_obj.bonus2_id, 0) + item_obj.bonus2_add
        
        for effect in self.active_effects:
            if "stat_mods" in effect.get("mods", {}):
                for stat, val in effect["mods"]["stat_mods"].items():
                    if stat in ATTRIBUTES:
                        self.current_attributes[stat] = self.current_attributes.get(stat, 0) + val
        
        for attr in ATTRIBUTES:
            if attr not in ["WGT", "HEI"] and self.current_attributes.get(attr,0) < 1 :
                 self.current_attributes[attr] = 1


    def _calculate_derived_stats_player(self):
        attrs = self.current_attributes
        prev_max_hp = self.max_hp

        self.max_hp = (50 +
                       (5 * attrs.get("STA", 0)) + (2 * attrs.get("STR", 0)) +
                       (2 * attrs.get("WIL", 0)) + attrs.get("FOR", 0) +
                       attrs.get("FOC", 0) + attrs.get("BLS", 0))
        
        self.atk_pw = (attrs.get("STR",0) * 2 + attrs.get("AGI",0) + 
                       attrs.get("DEX",0) + attrs.get("BAL",0))
        self.atk_sp = max(1, (attrs.get("AGI",0) * 2 + attrs.get("DEX",0) + 
                              attrs.get("WIL",0) + attrs.get("FOC",0)))
        self.mgc_pw = (attrs.get("INT",0) * 2 + attrs.get("MAN",0) + 
                       attrs.get("ARC",0) + attrs.get("WIL",0))
        self.block_val = (attrs.get("STR",0) + attrs.get("FOR",0) + attrs.get("INT",0) + 
                          attrs.get("BAL",0) + attrs.get("WIL",0))
        self.dodge_val = (attrs.get("FOC",0) + attrs.get("AGI",0) + attrs.get("DEX",0) + 
                          attrs.get("BAL",0) + attrs.get("PSY",0))
        self.armor_val = (attrs.get("STR",0) + attrs.get("FOR",0) + attrs.get("STA",0) + 
                          attrs.get("AGI",0) + attrs.get("BLS",0))
        self.mgc_rs_val = (attrs.get("PSY",0) + attrs.get("BLS",0) + attrs.get("WIL",0) + 
                           attrs.get("MAN",0) + attrs.get("FOR",0))
        self.crits_val = (attrs.get("HIT",0) * 3 + attrs.get("ARC",0) + attrs.get("FOC",0))

        for stat_name in ['atk_pw', 'mgc_pw', 'block_val', 'dodge_val', 'armor_val', 'mgc_rs_val', 'crits_val']:
            setattr(self, stat_name, max(0, getattr(self, stat_name)))
        self.atk_sp = max(1, self.atk_sp)

        self.attack_fill_time = 1.2 + (5.0 - 1.2) * (1 - self.atk_sp / 100.0)
        self.attack_fill_time = max(REFRESH_RATE, self.attack_fill_time)

        if self.current_hp == 0 or self.max_hp > prev_max_hp:
            hp_diff = self.max_hp - prev_max_hp
            self.current_hp += hp_diff if hp_diff > 0 else 0 # only add if max_hp increased
        self.current_hp = min(self.current_hp, self.max_hp)


    def update_stats_and_effects(self):
        if self.is_player:
            self._recalculate_current_attributes()
            self._calculate_derived_stats_player()
        else: # NPC stat updates are simpler, mainly for AtkSp from effects
            original_atk_sp = self.npc_data_source.get('AtkSp', 20) if self.npc_data_source else 20
            current_modified_atk_sp = original_atk_sp
            for effect in self.active_effects:
                if "stat_mods" in effect.get("mods", {}):
                    current_modified_atk_sp += effect["mods"]["stat_mods"].get("AtkSp", 0) # Example: Only AtkSp for now
            self.atk_sp = max(1, current_modified_atk_sp)
            self.attack_fill_time = 1.2 + (5.0 - 1.2) * (1 - self.atk_sp / 100.0)
            self.attack_fill_time = max(REFRESH_RATE, self.attack_fill_time)


    def get_action_for_key(self, key):
        if key == 'a': return DEFAULT_MELEE_ACTION_ID
        if key == 's': return DEFAULT_MAGIC_ACTION_ID
        
        slot_map = {'z': 6, 'x': 5, 'd': 7, 'c': 8}
        if key in slot_map:
            item = self.equipped_items.get(slot_map[key])
            if item and item.action_id:
                if item.slot in [7, 8] and item.id in self.item_cooldowns and self.item_cooldowns[item.id] > 0:
                    return None # On cooldown
                return item.action_id
        return None

    def can_equip_item(self, item_to_check):
        if not item_to_check.skill_check_attr:
            return True
        
        char_attr_val = self.current_attributes.get(item_to_check.skill_check_attr, 0)
        required_val = item_to_check.skill_check_amount

        if item_to_check.skill_check_opr == 'min':
            return char_attr_val >= required_val
        # Add other operators if needed
        return False

    def equip_item(self, new_item_obj, slot_to_equip):
        self.equipped_items[slot_to_equip] = new_item_obj
        if new_item_obj and new_item_obj.slot in [7,8] and new_item_obj.cooldown_time > 0:
            self.item_cooldowns[new_item_obj.id] = 0 # Initialize/reset cooldown tracking
        self.update_stats_and_effects()

    def apply_effect(self, action_obj, source_entity_is_self): # True if source is applying to self
        applies_to_self = (action_obj.self_buff_target_stat or action_obj.self_debuff_target_stat) and source_entity_is_self
        applies_as_enemy_debuff = action_obj.enemy_debuff_target_stat and not source_entity_is_self

        if not (applies_to_self or applies_as_enemy_debuff):
            return "" 

        if len(self.active_effects) >= MAX_ACTIVE_EFFECTS:
            return f"{self.name} resisted {action_obj.name} (max effects)."

        effect_name = action_obj.name
        effect_duration = action_obj.duration
        effect_mods = {"stat_mods": {}, "hp_change_tick": 0, "hp_change_on_end": 0}
        is_buff = False
        log_msg_part = ""

        if source_entity_is_self:
            if action_obj.self_buff_target_stat:
                is_buff = True
                if action_obj.self_buff_target_stat == "HP":
                    if action_obj.timing == 'tick': effect_mods["hp_change_tick"] = (action_obj.base_val / action_obj.duration) if action_obj.duration > 0 else action_obj.base_val
                    elif action_obj.timing == 'end': effect_mods["hp_change_on_end"] = action_obj.base_val
                    else: 
                        heal_amount = min(action_obj.base_val, self.max_hp - self.current_hp)
                        self.current_hp += heal_amount
                        if heal_amount > 0:
                            inst_heal_color = COLOR_GREEN if self.is_player else COLOR_RED
                            log_msg_part += f"{self.name} heals {inst_heal_color}{heal_amount:.0f}{COLOR_RESET} HP. "
                elif action_obj.self_buff_target_stat in ATTRIBUTES + ["AtkPw", "MgcPw", "AtkSp", "Block", "Dodge", "Armor", "MgcRs", "Crits"]: 
                    effect_mods["stat_mods"][action_obj.self_buff_target_stat] = action_obj.base_val
                    log_msg_part += f"{self.name}'s {action_obj.self_buff_target_stat} increases. "
            
            if action_obj.self_debuff_target_stat:
                is_buff = False 
                if action_obj.self_debuff_target_stat == "HP":
                    if action_obj.timing == 'tick': effect_mods["hp_change_tick"] = -(action_obj.base_val / action_obj.duration) if action_obj.duration > 0 else -action_obj.base_val
                    elif action_obj.timing == 'end': effect_mods["hp_change_on_end"] = -action_obj.base_val
                    else: 
                        damage_amount = min(action_obj.base_val, self.current_hp)
                        self.current_hp -= damage_amount
                        if damage_amount > 0:
                            inst_dmg_color = COLOR_RED if self.is_player else COLOR_GREEN
                            log_msg_part += f"{self.name} takes {inst_dmg_color}{damage_amount:.0f}{COLOR_RESET} self-damage. "
                elif action_obj.self_debuff_target_stat in ATTRIBUTES + ["AtkPw", "MgcPw", "AtkSp", "Block", "Dodge", "Armor", "MgcRs", "Crits"]:
                    effect_mods["stat_mods"][action_obj.self_debuff_target_stat] = -action_obj.base_val
                    log_msg_part += f"{self.name}'s {action_obj.self_debuff_target_stat} decreases. "

        if not source_entity_is_self and action_obj.enemy_debuff_target_stat:
            is_buff = False
            if action_obj.enemy_debuff_target_stat == "HP": 
                if action_obj.timing == 'tick': effect_mods["hp_change_tick"] = -(action_obj.base_val / action_obj.duration) if action_obj.duration > 0 else -action_obj.base_val
                elif action_obj.timing == 'end': effect_mods["hp_change_on_end"] = -action_obj.base_val
            elif action_obj.enemy_debuff_target_stat in ATTRIBUTES + ["AtkPw", "MgcPw", "AtkSp", "Block", "Dodge", "Armor", "MgcRs", "Crits"]:
                 effect_mods["stat_mods"][action_obj.enemy_debuff_target_stat] = -action_obj.base_val
                 log_msg_part += f"{self.name}'s {action_obj.enemy_debuff_target_stat} decreases. "

        if effect_mods["stat_mods"] or effect_mods["hp_change_tick"] != 0 or effect_mods["hp_change_on_end"] != 0:
            self.active_effects.append({
                "name": effect_name, "mods": effect_mods, "duration_left": effect_duration,
                "is_buff": is_buff, "timing": action_obj.timing, "source_action_id": action_obj.id
            })
            self.update_stats_and_effects()
            # Add "effect applied" message only if there wasn't already an instant HP change message
            if not ("heals" in log_msg_part or "takes" in log_msg_part and ("HP" in log_msg_part or "self-damage" in log_msg_part)):
                 return f"{log_msg_part}{action_obj.name} effect applied to {self.name}."
            return log_msg_part.strip() # Return only the HP change message if it happened
        elif log_msg_part:
            return log_msg_part.strip()
        return ""


    def update_active_effects(self, refresh_interval):
        log_updates = []
        removed_effect_this_tick = False
        for i in range(len(self.active_effects) - 1, -1, -1):
            effect = self.active_effects[i]
            effect["duration_left"] -= refresh_interval

            if effect["mods"].get("hp_change_tick", 0) != 0:
                hp_change_per_second = effect["mods"]["hp_change_tick"]
                hp_change_this_tick = hp_change_per_second * refresh_interval
                
                actual_hp_change = 0
                if hp_change_this_tick > 0: 
                    actual_hp_change = min(hp_change_this_tick, self.max_hp - self.current_hp)
                    self.current_hp += actual_hp_change
                    if actual_hp_change > 0.01 : 
                        heal_color = COLOR_GREEN if self.is_player else COLOR_RED
                        log_updates.append(f"{self.name} heals {heal_color}{actual_hp_change:.1f}{COLOR_RESET} HP from {effect['name']}.")
                else: 
                    actual_hp_change = min(abs(hp_change_this_tick), self.current_hp)
                    self.current_hp -= actual_hp_change
                    if actual_hp_change > 0: self.total_damage_taken_session += actual_hp_change 
                    if actual_hp_change > 0.01 : 
                        dmg_color = COLOR_RED if self.is_player else COLOR_GREEN
                        log_updates.append(f"{self.name} takes {dmg_color}{actual_hp_change:.1f}{COLOR_RESET} damage from {effect['name']}.")
                self.current_hp = max(0, min(self.max_hp, self.current_hp))


            if effect["duration_left"] <= 0:
                if effect["timing"] == 'end' and effect["mods"].get("hp_change_on_end", 0) != 0:
                    hp_change = effect["mods"]["hp_change_on_end"]
                    if hp_change > 0:
                         heal_amount = min(hp_change, self.max_hp - self.current_hp)
                         self.current_hp += heal_amount
                         if heal_amount > 0:
                             heal_color_end = COLOR_GREEN if self.is_player else COLOR_RED
                             log_updates.append(f"{self.name} heals {heal_color_end}{heal_amount:.0f}{COLOR_RESET} HP as {effect['name']} ends.")
                    else:
                         damage_amount = min(abs(hp_change), self.current_hp)
                         self.current_hp -= damage_amount
                         if damage_amount > 0: self.total_damage_taken_session += damage_amount
                         if damage_amount > 0:
                             dmg_color_end = COLOR_RED if self.is_player else COLOR_GREEN
                             log_updates.append(f"{self.name} takes {dmg_color_end}{damage_amount:.0f}{COLOR_RESET} damage as {effect['name']} ends.")
                    self.current_hp = max(0, min(self.max_hp, self.current_hp))

                log_updates.append(f"{effect['name']} wore off from {self.name}.")
                self.active_effects.pop(i)
                removed_effect_this_tick = True
        
        if removed_effect_this_tick:
            self.update_stats_and_effects()
        return log_updates

    def tick_item_cooldowns(self, refresh_interval):
        for item_id in list(self.item_cooldowns.keys()):
            if self.item_cooldowns[item_id] > 0:
                self.item_cooldowns[item_id] -= refresh_interval
                if self.item_cooldowns[item_id] < 0:
                    self.item_cooldowns[item_id] = 0

# --- Global Game State Variables (formerly in game.py) ---
TOONS_DATA = {}
NPCS_DATA = {}
SAVED_CHARS_DATA = [] 
COMBAT_LOG = []
source_was_default_and_we_want_to_save = True # Default, will be updated

# --- Game Logic Functions (formerly game.py) ---
def add_to_combat_log(message):
    if message:
        COMBAT_LOG.append(f"[{time.strftime('%H:%M:%S')}] {message}")
        if len(COMBAT_LOG) > MAX_COMBAT_LOG_ENTRIES:
            COMBAT_LOG.pop(0)

def initialize_game_data():
    global TOONS_DATA, NPCS_DATA, SAVED_CHARS_DATA, ALL_ITEMS, ALL_ACTIONS
    
    raw_items = load_csv_data(CSV_FILES["items"], key_column='ItemID')
    for item_id, item_data in raw_items.items():
        ALL_ITEMS[item_id] = Item(item_data)

    raw_actions = load_csv_data(CSV_FILES["actions"], key_column='actionID')
    for action_id, action_data in raw_actions.items():
        ALL_ACTIONS[action_id] = Action(action_data)

    essential_data_loaded_successfully = True
    error_messages = []

    if not ALL_ITEMS:
        error_messages.append("FATAL ERROR: Essential item data (pyRL_items.csv) not found or is empty.")
        essential_data_loaded_successfully = False
    if not ALL_ACTIONS:
        error_messages.append("FATAL ERROR: Essential action data (pyRL_actions.csv) not found or is empty.")
        essential_data_loaded_successfully = False

    TOONS_DATA = load_csv_data(CSV_FILES["toons"], key_column='Name')
    if not TOONS_DATA:
        error_messages.append("FATAL ERROR: Essential character template data (pyRL_toons.csv) not found or is empty.")
        essential_data_loaded_successfully = False

    NPCS_DATA = load_csv_data(CSV_FILES["npcs"], key_column='npcID') 
    if not NPCS_DATA:
        error_messages.append("FATAL ERROR: Essential NPC data (pyRL_npcs.csv) not found or is empty.")
        essential_data_loaded_successfully = False
    
    if not essential_data_loaded_successfully:
        print("\n--- CRITICAL DATA LOADING FAILURE ---")
        for msg in error_messages:
            print(msg)
        print("The game cannot continue without these essential data files.")
        print("Please ensure the CSV files are present in the same directory as the script and are correctly formatted.")
        
        if os.name == 'posix' and _old_settings_tty is not None: 
            _restore_tty_settings_non_blocking()
        sys.exit(1) 
        
    raw_saved_chars = load_csv_data(CSV_FILES["saved"]) 
    SAVED_CHARS_DATA = [char_row for char_row in raw_saved_chars if char_row]


def select_character():
    clear_screen()
    print("Choose character source:")
    if os.name == 'posix': _restore_tty_settings_non_blocking()
    source_choice_idx = display_options(["Default Characters", "Saved Characters"])
    if os.name == 'posix': _init_tty_for_input_non_blocking() 

    selected_char_data = None
    is_saved = False
    player_name_for_entity = "Player" 

    if source_choice_idx == 0: 
        if not TOONS_DATA:
            print("No default characters found!")
            return None, False
        char_names = list(TOONS_DATA.keys())
        if not char_names:
            print("No default characters available to choose from.")
            return None, False
        
        if os.name == 'posix': _restore_tty_settings_non_blocking()
        chosen_idx = display_options(char_names, "Choose a default character:")
        if os.name == 'posix': _init_tty_for_input_non_blocking()
        
        selected_char_data = TOONS_DATA[char_names[chosen_idx]]
        player_name_for_entity = char_names[chosen_idx]
    else: 
        if not SAVED_CHARS_DATA:
            print("No saved characters found!")
            return None, False
        
        saved_char_display_names = []
        for s_char_data in SAVED_CHARS_DATA:
            s_id = s_char_data.get('SaveID', 'N/A')
            s_name = s_char_data.get('Name', 'Unknown')
            saved_char_display_names.append(f"ID: {s_id} - {s_name}")

        if not saved_char_display_names:
            print("No saved characters available to choose from.")
            return None, False

        if os.name == 'posix': _restore_tty_settings_non_blocking()
        chosen_idx = display_options(saved_char_display_names, "Choose a saved character:")
        if os.name == 'posix': _init_tty_for_input_non_blocking()
        
        selected_char_data = SAVED_CHARS_DATA[chosen_idx]
        player_name_for_entity = selected_char_data.get('Name', 'Saved Player')
        is_saved = True
        
    player = Entity(player_name_for_entity, is_player=True)
    player.load_char_data(selected_char_data, is_saved_char=is_saved)
    return player, is_saved


def select_opponent():
    clear_screen()
    if not NPCS_DATA:
        print("No NPCs found!")
        return None
    
    npc_display_list = []
    npc_id_map = [] 

    for npc_id, data in NPCS_DATA.items():
        npc_display_list.append(f"{data.get('Name')} (Lvl {data.get('Level')})")
        npc_id_map.append(npc_id)

    if not npc_display_list:
        print("No opponents available to choose from.")
        return None

    if os.name == 'posix': _restore_tty_settings_non_blocking()
    chosen_idx = display_options(npc_display_list, "Choose an opponent:")
    if os.name == 'posix': _init_tty_for_input_non_blocking()
    
    selected_npc_id_from_map = npc_id_map[chosen_idx]
    
    npc_data_to_load = NPCS_DATA.get(selected_npc_id_from_map) 
    if not npc_data_to_load: 
        npc_data_to_load = NPCS_DATA.get(str(selected_npc_id_from_map))
    
    if not npc_data_to_load:
        print(f"Error: Could not find NPC data for ID {selected_npc_id_from_map}")
        return None

    npc = Entity(npc_data_to_load.get('Name', 'Mysterious Opponent'), is_player=False)
    npc.load_npc_data(npc_data_to_load)
    return npc

def display_hud(player, opponent):
    sys.stdout.write('\033[H')
    sys.stdout.flush()
    
    p_bar_fill = int(player.attack_bar_progress / 100 * 20)
    p_bar = f"[{'■' * p_bar_fill}{' ' * (20 - p_bar_fill)}] {player.attack_bar_progress:.0f}%"
    p_action_id = player.get_action_for_key(player.queued_action_key)
    p_action_name = "Nothing"
    if p_action_id and p_action_id in ALL_ACTIONS:
        p_action_name = ALL_ACTIONS[p_action_id].name
    elif p_action_id: 
        p_action_name = f"Unknown Action ({p_action_id})"

    print(f"[{player.name}] HP: {player.current_hp:.0f}/{player.max_hp:.0f}   ATK BAR: {p_bar}")
    print(f"Queued: {ACTION_KEYS_PLAYER.get(player.queued_action_key, 'Unknown')} ({p_action_name})")
    elapsed_time = (time.time() - player.combat_start_time) if player.combat_start_time > 0 else 0
    dps = (player.total_damage_dealt_session / elapsed_time) if elapsed_time > 0.1 else 0 
    print(f"DPS: {dps:.1f}")
    print(f"Stats: AtkP:{player.atk_pw} AtkS:{player.atk_sp} MgcP:{player.mgc_pw} Blk:{player.block_val} Dg:{player.dodge_val} Arm:{player.armor_val} MRs:{player.mgc_rs_val} Crt:{player.crits_val}")
    
    p_effects_str = ", ".join([f"{e['name']}({e['duration_left']:.0f}s{' B' if e['is_buff'] else ' D'})" for e in player.active_effects]) or "None"
    print(f"Effects: {p_effects_str}\n")

    o_bar_fill = int(opponent.attack_bar_progress / 100 * 20)
    o_bar = f"[{'■' * o_bar_fill}{' ' * (20 - o_bar_fill)}] {opponent.attack_bar_progress:.0f}%"
    o_action_id = opponent.npc_data_source.get(f'act{(opponent.action_sequence_index % 9) + 1}') 
    o_action_name = "Thinking"
    if o_action_id and o_action_id in ALL_ACTIONS:
        o_action_name = ALL_ACTIONS[o_action_id].name
    elif o_action_id:
        o_action_name = f"Unknown Action ({o_action_id})"
    
    print(f"[{opponent.name}] HP: {opponent.current_hp:.0f}/{opponent.max_hp:.0f}   ATK BAR: {o_bar}")
    print(f"Queued: {o_action_name}")
    print(f"Stats: AtkP:{opponent.atk_pw} AtkS:{opponent.atk_sp} MgcP:{opponent.mgc_pw} Blk:{opponent.block_val} Dg:{opponent.dodge_val} Arm:{opponent.armor_val} MRs:{opponent.mgc_rs_val} Crt:{opponent.crits_val}")
    
    o_effects_str = ", ".join([f"{e['name']}({e['duration_left']:.0f}s{' B' if e['is_buff'] else ' D'})" for e in opponent.active_effects]) or "None"
    print(f"Effects: {o_effects_str}\n")

    print("--- Combat Log ---")
    for entry in COMBAT_LOG[-MAX_COMBAT_LOG_ENTRIES:]:
        print(entry)
    print("------------------")
    print(f"Controls: ({'/'.join(ACTION_KEYS_PLAYER.keys())}) to queue, (q) to quit combat")


def resolve_attack(attacker, target, action_id):
    action = ALL_ACTIONS.get(action_id)
    if not action:
        add_to_combat_log(f"{attacker.name} tries to use unknown action ID {action_id}!")
        return

    effect_log_attacker = attacker.apply_effect(action, source_entity_is_self=True)
    if effect_log_attacker: add_to_combat_log(effect_log_attacker)
    
    if action.dmg_stat_source or action.enemy_debuff_target_stat:
        dodge_chance = target.dodge_val / 10.0
        if random.random() * 100 < dodge_chance:
            add_to_combat_log(f"{attacker.name} uses {action.name} on {target.name}!")
            add_to_combat_log(f"{target.name} dodges {action.name}!")
            return

        if action.dmg_stat_source:
            base_damage = 0
            is_magic_attack = False
            if action.dmg_stat_source == "AtkPw":
                base_damage = action.base_val + (attacker.atk_pw * 0.2) 
            elif action.dmg_stat_source == "MgcPw":
                base_damage = action.base_val + (attacker.mgc_pw * 0.2)
                is_magic_attack = True
            
            crit_multiplier = 1.0
            crit_message_part = "" 
            if base_damage > 0: 
                crit_chance = attacker.crits_val / 3.0
                if random.random() * 100 < crit_chance:
                    crit_multiplier = 2.0
                    crit_message_part = " (Critical Hit!)" 
            
            damage_before_mitigation = base_damage * crit_multiplier
            
            final_damage_after_mitigation = damage_before_mitigation 
            mitigation_percent_for_log = 0.0

            if damage_before_mitigation > 0: 
                mitigation_percent_calc = 0.0
                if is_magic_attack:
                    mitigation_percent_calc = random.uniform(0.01, target.mgc_rs_val / 100.0) if target.mgc_rs_val > 1 else 0
                else: 
                    block_mit_val = random.uniform(0.01, target.block_val / 100.0) if target.block_val > 1 else 0
                    armor_reduction_factor = target.armor_val / (target.armor_val + 200.0) if target.armor_val > 0 else 0
                    mitigation_percent_calc = block_mit_val + armor_reduction_factor

                mitigation_percent_calc = max(0, min(0.95, mitigation_percent_calc)) 
                mitigation_percent_for_log = mitigation_percent_calc * 100 
                
                final_damage_after_mitigation *= (1 - mitigation_percent_calc)
            
            final_damage_after_mitigation = max(0, int(round(final_damage_after_mitigation)))
            
            actual_damage_dealt = 0
            if final_damage_after_mitigation > 0:
                actual_damage_dealt = min(final_damage_after_mitigation, target.current_hp) 
                target.current_hp -= actual_damage_dealt
                attacker.total_damage_dealt_session += actual_damage_dealt
                if target.is_player: # Player (target) took damage
                    target.total_damage_taken_session += actual_damage_dealt
                elif attacker.is_player: # Player (attacker) dealt damage to NPC target
                    pass # This is covered by total_damage_dealt_session for player
                
                damage_color_str = ""
                if actual_damage_dealt > 0:
                    if attacker.is_player: # Player dealt damage
                        damage_color_str = COLOR_GREEN
                    else: # Opponent dealt damage (player is target)
                        damage_color_str = COLOR_RED
                
                raw_damage_val_log = int(round(damage_before_mitigation))
                log_message = (f"{attacker.name} uses {action.name} on {target.name}!{crit_message_part} "
                               f"({raw_damage_val_log}/{mitigation_percent_for_log:.1f}%/"
                               f"{damage_color_str}{actual_damage_dealt}{COLOR_RESET if damage_color_str else ''})")
                add_to_combat_log(log_message)
            else: 
                add_to_combat_log(f"{attacker.name} uses {action.name} on {target.name}!{crit_message_part} but deals no damage.")
        
        else: 
            add_to_combat_log(f"{attacker.name} uses {action.name} on {target.name}!")

        effect_log_target = target.apply_effect(action, source_entity_is_self=False)
        if effect_log_target: add_to_combat_log(effect_log_target)

    if attacker.is_player:
        used_item_slot_key = None
        if attacker.queued_action_key == 'z': used_item_slot_key = 6 
        elif attacker.queued_action_key == 'x': used_item_slot_key = 5 
        elif attacker.queued_action_key == 'd': used_item_slot_key = 7 
        elif attacker.queued_action_key == 'c': used_item_slot_key = 8 
        
        if used_item_slot_key:
            item_in_slot = attacker.equipped_items.get(used_item_slot_key)
            if item_in_slot and item_in_slot.action_id == action_id and item_in_slot.cooldown_time > 0:
                 if item_in_slot.slot in [7, 8] or action.id == item_in_slot.action_id : 
                    attacker.item_cooldowns[item_in_slot.id] = item_in_slot.cooldown_time
                    add_to_combat_log(f"{item_in_slot.name} is now on cooldown ({item_in_slot.cooldown_time}s).")
                    

def handle_loot_drop(player, defeated_npc):
    add_to_combat_log(f"{player.name} defeated {defeated_npc.name}!")
    xp_yield = defeated_npc.npc_data_source.get('XPYield', 0) or 0
    player.xp += xp_yield
    add_to_combat_log(f"Gained {xp_yield} XP. Total XP: {player.xp}")

    drop_keys = [f"Item{i}ID" for i in range(1, 6)]
    item_ids  = [defeated_npc.npc_data_source.get(key) for key in drop_keys]
    weights   = [30, 30, 30, 8, 2]  

    chosen_id = random.choices(item_ids, weights=weights, k=1)[0]

    if not chosen_id or chosen_id not in ALL_ITEMS:
        add_to_combat_log("No valid loot dropped.")
        return

    blueprint    = ALL_ITEMS[chosen_id]
    dropped_item = copy.deepcopy(blueprint)
    slot_name      = SLOT_NAMES.get(dropped_item.slot, "Unknown")
    add_to_combat_log(f"{defeated_npc.name} dropped: {dropped_item.name} (Slot: {slot_name})!")

    if not player.can_equip_item(dropped_item):
        req_attr = dropped_item.skill_check_attr
        req_val  = dropped_item.skill_check_amount
        add_to_combat_log(
            f"You don't meet requirements for {dropped_item.name} "
            f"({req_attr} ≥ {req_val}). It is discarded."
        )
        return

    current = player.equipped_items.get(dropped_item.slot)
    current_name = current.name if current else "Nothing"
    print(f"\nDo you want to equip {dropped_item.name} (Slot {slot_name})?")
    print(f"It will replace: {current_name}.")
    print(f"New item bonuses: {dropped_item.bonus1_id} +{dropped_item.bonus1_add}, "
          f"{dropped_item.bonus2_id} +{dropped_item.bonus2_add}")
    if current:
        print(f"Old item bonuses: {current.bonus1_id} +{current.bonus1_add}, "
              f"{current.bonus2_id} +{current.bonus2_add}")

    if os.name == 'posix':
        _restore_tty_settings_non_blocking()
    equip_choice = display_options(["Yes", "No"], "Equip it?")
    if os.name == 'posix':
        _init_tty_for_input_non_blocking()

    if equip_choice == 0:
        player.equip_item(dropped_item, dropped_item.slot)
        add_to_combat_log(f"Equipped {dropped_item.name}.")
    else:
        add_to_combat_log(f"Kept {current_name} instead of {dropped_item.name}.")



def save_player_character(player):
    global SAVED_CHARS_DATA

    is_new_character_entry = False
    if player.save_id is None:
        max_id = 0
        if SAVED_CHARS_DATA:
            for char_d in SAVED_CHARS_DATA:
                sid = char_d.get('SaveID')
                if isinstance(sid, (int, str)) and str(sid).isdigit():
                    max_id = max(max_id, int(sid))
        player.save_id = max_id + 1
        is_new_character_entry = True
        print(f"Assigning new SaveID {player.save_id} to {player.name}.")

    current_player_data_to_save = {'SaveID': player.save_id, 'Name': player.name}
    for attr in ATTRIBUTES:
        current_player_data_to_save[attr] = player.base_attributes.get(attr, 0)
    for i in range(1, 9):
        item = player.equipped_items.get(i)
        current_player_data_to_save[f'Slot{i}'] = item.id if item else None
    current_player_data_to_save['XP'] = player.xp

    new_full_saves_list = []
    character_was_updated_in_list = False
    
    if not is_new_character_entry: 
        for char_d in SAVED_CHARS_DATA:
            if str(char_d.get('SaveID')) == str(player.save_id):
                new_full_saves_list.append(current_player_data_to_save) 
                character_was_updated_in_list = True
            else:
                new_full_saves_list.append(char_d) 
    else: 
        new_full_saves_list = list(SAVED_CHARS_DATA) 

    if is_new_character_entry:
        new_full_saves_list.append(current_player_data_to_save)
    elif not character_was_updated_in_list: 
        new_full_saves_list.append(current_player_data_to_save)
        
    SAVED_CHARS_DATA = new_full_saves_list

    fieldnames = ['SaveID', 'Name'] + ATTRIBUTES + [f'Slot{i}' for i in range(1,9)] + ['XP']
    try:
        with open(CSV_FILES["saved"], 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            writer.writeheader()
            writer.writerows(SAVED_CHARS_DATA) 
        add_to_combat_log(f"Character {player.name} saved (ID: {player.save_id}).")
    except Exception as e:
        add_to_combat_log(f"Error saving character: {e}")
        print(f"Error saving character: {e}")


def record_to_leaderboard(player, won_fight, fight_duration, opponent_name):
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    if hasattr(player, 'update_stats_and_effects'):
        player.update_stats_and_effects()

    entry = {
        'timestamp': timestamp,
        'toon_name': player.name,
        'opponent_name': opponent_name,
        'fight_duration_seconds': round(fight_duration, 2),
        'level': getattr(player, 'level', 1),  
        'kills': 1 if won_fight else 0,
        'damage_done': player.total_damage_dealt_session,
        'damage_received': player.total_damage_taken_session,
    }
    for i in range(1, 9):
        item = player.equipped_items.get(i)
        entry[f'item{i}'] = item.name if item else "None"

    for attr in ATTRIBUTES:
        entry[attr] = player.current_attributes.get(attr, 0)

    fieldnames = (
        ['timestamp', 'toon_name', 'opponent_name', 'fight_duration_seconds',
         'level', 'kills', 'damage_done', 'damage_received']
        + [f'item{i}' for i in range(1, 9)]
        + ATTRIBUTES
    )

    try:
        file_exists = os.path.isfile(CSV_FILES["leaderboard"])
        with open(CSV_FILES["leaderboard"], 'a', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction='ignore')
            if not file_exists or os.path.getsize(CSV_FILES["leaderboard"]) == 0:
                writer.writeheader()
            writer.writerow(entry)
        add_to_combat_log(f"{player.name} recorded to leaderboard.")
    except Exception as e:
        add_to_combat_log(f"Error recording to leaderboard: {e}")
        print(f"Error recording to leaderboard: {e}")

    if not won_fight and player.save_id is not None:
        global SAVED_CHARS_DATA
        SAVED_CHARS_DATA = [
            char_d for char_d in SAVED_CHARS_DATA
            if str(char_d.get('SaveID')) != str(player.save_id)
        ]

        save_fieldnames = (
            ['SaveID', 'Name'] + ATTRIBUTES + [f'Slot{i}' for i in range(1, 9)] + ['XP']
        )
        if SAVED_CHARS_DATA: 
            if SAVED_CHARS_DATA: 
                 save_fieldnames = list(SAVED_CHARS_DATA[0].keys())
        elif not os.path.exists(CSV_FILES["saved"]) or os.path.getsize(CSV_FILES["saved"]) == 0 :
             pass 
        else: 
            pass


        try:
            with open(CSV_FILES["saved"], 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=save_fieldnames, extrasaction='ignore')
                writer.writeheader()
                writer.writerows(SAVED_CHARS_DATA) 
            add_to_combat_log(f"Player {player.name} (SaveID: {player.save_id}) removed from saves after loss.")
        except Exception as e:
            add_to_combat_log(f"Error removing player {player.name} from saves: {e}")


def combat_loop(player, opponent):
    clear_screen()
    COMBAT_LOG.clear()
    add_to_combat_log(f"Combat starts: {player.name} vs {opponent.name}!")
    if opponent.text_start: add_to_combat_log(opponent.text_start)

    player.combat_start_time = time.time()
    opponent.combat_start_time = time.time() 
    player.total_damage_dealt_session = 0
    player.total_damage_taken_session = 0
    opponent.total_damage_dealt_session = 0 
    opponent.total_damage_taken_session = 0 
    
    game_over = False
    player_won = False
    last_refresh_time = time.time()

    while not game_over:
        current_time = time.time()
        delta_time = current_time - last_refresh_time
        if delta_time <= 0: delta_time = REFRESH_RATE 
        last_refresh_time = current_time

        keypress = get_keypress()
        if keypress:
            if keypress in ACTION_KEYS_PLAYER:
                player.queued_action_key = keypress
                action_id_to_queue = player.get_action_for_key(keypress)
                action_name_log = "Invalid/CD"
                if action_id_to_queue and action_id_to_queue in ALL_ACTIONS:
                    action_name_log = ALL_ACTIONS[action_id_to_queue].name
                add_to_combat_log(f"Player queues {ACTION_KEYS_PLAYER[keypress]} ({action_name_log}).")
            elif keypress == 'q':
                add_to_combat_log("Player forfeits.")
                game_over = True
                player_won = False
                break
        
        for msg in player.update_active_effects(delta_time): add_to_combat_log(msg)
        player.tick_item_cooldowns(delta_time)
        for msg in opponent.update_active_effects(delta_time): add_to_combat_log(msg)

        if player.current_hp <= 0: game_over = True; player_won = False; break
        if opponent.current_hp <= 0: game_over = True; player_won = True; break

        player.attack_bar_progress += (100.0 / player.attack_fill_time) * delta_time
        opponent.attack_bar_progress += (100.0 / opponent.attack_fill_time) * delta_time
        
        player.attack_bar_progress = min(100.0, player.attack_bar_progress)
        opponent.attack_bar_progress = min(100.0, opponent.attack_bar_progress)

        if player.attack_bar_progress >= 100:
            action_id = player.get_action_for_key(player.queued_action_key)
            if action_id and action_id in ALL_ACTIONS:
                resolve_attack(player, opponent, action_id)
            else:
                add_to_combat_log(f"Player's action ({player.queued_action_key}) fizzles (unavailable/cooldown).")
            player.attack_bar_progress = 0

        if opponent.current_hp <= 0: game_over = True; player_won = True; break 

        if opponent.attack_bar_progress >= 100:
            act_idx_str = f'act{(opponent.action_sequence_index % 9) + 1}'
            action_id = opponent.npc_data_source.get(act_idx_str) if opponent.npc_data_source else None
            if action_id and action_id in ALL_ACTIONS:
                resolve_attack(opponent, player, action_id)
            else:
                add_to_combat_log(f"{opponent.name} confused (invalid action ID: {action_id} from {act_idx_str}).")
            opponent.attack_bar_progress = 0
            opponent.action_sequence_index += 1


        if player.current_hp <= 0: game_over = True; player_won = False; break

        display_hud(player, opponent)
        
        elapsed_tick_time = time.time() - current_time
        sleep_duration = REFRESH_RATE - elapsed_tick_time
        if sleep_duration > 0:
            time.sleep(sleep_duration)

    if os.name == 'posix': _restore_tty_settings_non_blocking() 
    display_hud(player, opponent) 
    print("\n--- COMBAT END ---")
    for entry in COMBAT_LOG: print(entry)

    fight_duration = (time.time() - player.combat_start_time) if player.combat_start_time > 0 else 0

    if player_won:
        if opponent.text_death: add_to_combat_log(opponent.text_death) 
        print(f"\n{opponent.text_death if opponent.text_death else opponent.name + ' is defeated.'}")
        print(f"Congratulations! You defeated {opponent.name}.")
        handle_loot_drop(player, opponent)
        if player.is_player: 
             save_player_character(player)
    else:
        if player.current_hp <=0:
            if opponent.text_win: add_to_combat_log(opponent.text_win)
            print(f"\n{opponent.text_win if opponent.text_win else 'You have been defeated.'}")
        else: 
             print(f"\nYou forfeited the match against {opponent.name}.")

    record_to_leaderboard(player, player_won, fight_duration, opponent.name)
    
    input("\nPress Enter to continue...")
    if os.name == 'posix': _init_tty_for_input_non_blocking() 


def main_game_loop():
    initialize_game_data()
    
    while True: 
        current_player, is_saved_char = select_character()
        if not current_player:
            print("Failed to select a character. Exiting game.")
            break 

        while True: 
            opponent = select_opponent()
            if not opponent:
                print("Failed to select an opponent. Returning to character selection.")
                break 

            combat_loop(current_player, opponent) 

            if os.name == 'posix': _restore_tty_settings_non_blocking()
            print("\nWhat would you like to do next?")
            next_action_idx = display_options(["Fight Again (Same Character)", "Change Character", "Exit Game"])
            if os.name == 'posix' and next_action_idx != 2: _init_tty_for_input_non_blocking()

            if next_action_idx == 0: 
                current_player.current_hp = current_player.max_hp
                current_player.attack_bar_progress = 0
                current_player.active_effects.clear()
                for item_id_key in list(current_player.item_cooldowns.keys()): 
                    current_player.item_cooldowns[item_id_key] = 0
                current_player.update_stats_and_effects()
                continue 
            elif next_action_idx == 1: 
                break 
            else: 
                print("Thanks for playing!")
                return 

if __name__ == "__main__":
    if os.name == 'nt':
        os.system('') 
    if os.name == 'posix':
        _init_tty_for_input_non_blocking()
        atexit.register(_restore_tty_settings_non_blocking) 
    
    try:
        main_game_loop()
    except KeyboardInterrupt:
        print("\nGame interrupted. Exiting.")
    finally:
        if os.name == 'posix':
            _restore_tty_settings_non_blocking()
