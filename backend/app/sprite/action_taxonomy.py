"""Data-driven animation action taxonomy with legacy provider compatibility."""

from __future__ import annotations

ACTION_GROUPS: dict[str, tuple[dict[str, str], ...]] = {
    "movement": (
        {"label": "Idle", "value": "idle", "provider_action": "idle", "prompt": "idling in place"},
        {"label": "Walk", "value": "walk", "provider_action": "walk", "prompt": "walking forward naturally"},
        {"label": "Run", "value": "run", "provider_action": "run", "prompt": "running forward with dynamic full-body movement"},
        {"label": "Sprint", "value": "sprint", "provider_action": "run", "prompt": "sprinting forward at maximum speed"},
        {"label": "Crouch", "value": "crouch", "provider_action": "idle", "prompt": "crouching down with a controlled pose"},
        {"label": "Crawl", "value": "crawl", "provider_action": "walk", "prompt": "crawling forward close to the ground"},
        {"label": "Jump", "value": "jump", "provider_action": "jump", "prompt": "jumping upward with anticipation, airborne pose, and landing"},
        {"label": "Double Jump", "value": "double_jump", "provider_action": "jump", "prompt": "performing a double jump with two distinct airborne phases"},
        {"label": "Fall", "value": "fall", "provider_action": "jump", "prompt": "falling downward with a clear airborne pose"},
        {"label": "Land", "value": "land", "provider_action": "jump", "prompt": "landing with a clear impact and recovery pose"},
        {"label": "Roll", "value": "roll", "provider_action": "attack", "prompt": "performing a forward combat roll"},
        {"label": "Dodge", "value": "dodge", "provider_action": "attack", "prompt": "performing a quick evasive dodge"},
        {"label": "Dash", "value": "dash", "provider_action": "run", "prompt": "performing a fast directional dash"},
        {"label": "Climb", "value": "climb", "provider_action": "walk", "prompt": "climbing upward with alternating limbs"},
    ),
    "combat": (
        {"label": "Punch", "value": "punch", "provider_action": "attack", "prompt": "performing a forward punch with clear arm extension and body rotation"},
        {"label": "Jab", "value": "jab", "provider_action": "attack", "prompt": "performing a quick sharp jab"},
        {"label": "Kick", "value": "kick", "provider_action": "attack", "prompt": "performing a dynamic forward kick"},
        {"label": "Heavy Punch", "value": "heavy_punch", "provider_action": "attack", "prompt": "performing a powerful heavy punch with full-body follow-through"},
        {"label": "Heavy Kick", "value": "heavy_kick", "provider_action": "attack", "prompt": "performing a powerful heavy kick with strong body rotation"},
        {"label": "Combo Attack", "value": "combo_attack", "provider_action": "attack", "prompt": "performing a fast multi-hit combo attack"},
        {"label": "Sword Slash", "value": "sword_slash", "provider_action": "attack", "prompt": "performing a fast sword slash attack with clear full-body follow-through"},
        {"label": "Heavy Sword Slash", "value": "heavy_sword_slash", "provider_action": "attack", "prompt": "performing a powerful heavy sword attack with strong body rotation and follow-through"},
        {"label": "Sword Stab", "value": "sword_stab", "provider_action": "attack", "prompt": "performing a forward sword thrust with clear extension and recovery"},
        {"label": "Axe Swing", "value": "axe_swing", "provider_action": "attack", "prompt": "performing a wide powerful axe swing"},
        {"label": "Spear Thrust", "value": "spear_thrust", "provider_action": "attack", "prompt": "performing a precise forward spear thrust"},
        {"label": "Dagger Attack", "value": "dagger_attack", "provider_action": "attack", "prompt": "performing a quick close-range dagger attack"},
        {"label": "Bow Shoot", "value": "bow_shoot", "provider_action": "attack", "prompt": "drawing and firing a bow with clear aim and release"},
        {"label": "Magic Attack", "value": "magic_attack", "provider_action": "attack", "prompt": "casting a magical attack with expressive arm and body movement"},
        {"label": "Ranged Attack", "value": "ranged_attack", "provider_action": "attack", "prompt": "performing a readable ranged attack with clear release"},
        {"label": "Special Attack", "value": "special_attack", "provider_action": "attack", "prompt": "performing a dramatic special attack with strong anticipation and follow-through"},
    ),
    "defense": (
        {"label": "Block", "value": "block", "provider_action": "attack", "prompt": "raising a defensive block against an incoming attack"},
        {"label": "Shield Block", "value": "shield_block", "provider_action": "attack", "prompt": "performing a strong shield block"},
        {"label": "Parry", "value": "parry", "provider_action": "attack", "prompt": "performing a precise parry and quick recovery"},
        {"label": "Guard", "value": "guard", "provider_action": "idle", "prompt": "holding a ready defensive guard stance"},
        {"label": "Dodge", "value": "dodge_defense", "provider_action": "attack", "prompt": "performing a quick evasive dodge"},
        {"label": "Counter Attack", "value": "counter_attack", "provider_action": "attack", "prompt": "blocking and immediately performing a counter attack"},
    ),
    "damage": (
        {"label": "Hurt", "value": "hurt", "provider_action": "attack", "prompt": "reacting clearly to a hit with a brief hurt pose"},
        {"label": "Hit Reaction", "value": "hit_reaction", "provider_action": "attack", "prompt": "showing a readable full-body hit reaction"},
        {"label": "Knockback", "value": "knockback", "provider_action": "attack", "prompt": "staggering backward from strong knockback"},
        {"label": "Stagger", "value": "stagger", "provider_action": "walk", "prompt": "staggering unsteadily while recovering balance"},
        {"label": "Fall Down", "value": "fall_down", "provider_action": "jump", "prompt": "falling down after being hit"},
        {"label": "Get Up", "value": "get_up", "provider_action": "jump", "prompt": "getting up from the ground with a clear recovery"},
        {"label": "Death", "value": "death", "provider_action": "jump", "prompt": "falling after being defeated and transitioning to a final resting pose"},
    ),
    "character": (
        {"label": "Idle", "value": "character_idle", "provider_action": "idle", "prompt": "idling with subtle natural character movement"},
        {"label": "Look Around", "value": "look_around", "provider_action": "idle", "prompt": "looking around with curious head and body movement"},
        {"label": "Sit", "value": "sit", "provider_action": "idle", "prompt": "sitting down in a readable relaxed pose"},
        {"label": "Stand", "value": "stand", "provider_action": "idle", "prompt": "standing up with a clear recovery pose"},
        {"label": "Wave", "value": "wave", "provider_action": "idle", "prompt": "waving warmly with a clear arm gesture"},
        {"label": "Talk", "value": "talk", "provider_action": "idle", "prompt": "talking with expressive hand and body gestures"},
        {"label": "Celebrate", "value": "celebrate", "provider_action": "attack", "prompt": "celebrating with energetic expressive movement"},
        {"label": "Cheer", "value": "cheer", "provider_action": "attack", "prompt": "cheering with raised arms and joyful movement"},
        {"label": "Sad", "value": "sad", "provider_action": "idle", "prompt": "showing a subdued sad character reaction"},
        {"label": "Angry", "value": "angry", "provider_action": "attack", "prompt": "showing an expressive angry character reaction"},
        {"label": "Laugh", "value": "laugh", "provider_action": "idle", "prompt": "laughing with expressive upper-body movement"},
    ),
    "interaction": (
        {"label": "Pick Up", "value": "pick_up", "provider_action": "jump", "prompt": "reaching down to pick up an item and standing back up"},
        {"label": "Drop", "value": "drop", "provider_action": "attack", "prompt": "dropping an item with a clear hand movement"},
        {"label": "Push", "value": "push", "provider_action": "attack", "prompt": "pushing a heavy object with clear exertion"},
        {"label": "Pull", "value": "pull", "provider_action": "attack", "prompt": "pulling an object with clear full-body effort"},
        {"label": "Open", "value": "open", "provider_action": "attack", "prompt": "opening an object with a clear interaction gesture"},
        {"label": "Close", "value": "close", "provider_action": "attack", "prompt": "closing an object with a clear interaction gesture"},
        {"label": "Activate", "value": "activate", "provider_action": "attack", "prompt": "activating an object with a deliberate gesture"},
        {"label": "Use Item", "value": "use_item", "provider_action": "attack", "prompt": "using an item with a clear readable gesture"},
    ),
}

ACTION_LOOKUP = {item["value"]: item for group in ACTION_GROUPS.values() for item in group}
LEGACY_ACTIONS = {"idle", "walk", "run", "jump", "attack"}


def get_action(value: str) -> dict[str, str]:
    """Return a taxonomy action, or a legacy action fallback."""
    normalized = value.strip().lower()
    if normalized in ACTION_LOOKUP:
        return ACTION_LOOKUP[normalized]
    if normalized in LEGACY_ACTIONS:
        return {"label": normalized.title(), "value": normalized, "provider_action": normalized, "prompt": normalized}
    raise ValueError(f"Unsupported action '{value}'.")
