export const ACTION_GROUPS = {
  movement: [
    ["Idle", "idle", "Idling in place."], ["Walk", "walk", "Walking forward naturally."], ["Run", "run", "Running forward with dynamic movement."], ["Sprint", "sprint", "A fast maximum-speed run."], ["Crouch", "crouch", "A controlled crouching pose."], ["Crawl", "crawl", "Moving close to the ground."], ["Jump", "jump", "Anticipation, airborne pose, and landing."], ["Double Jump", "double_jump", "Two distinct airborne phases."], ["Fall", "fall", "A clear falling pose."], ["Land", "land", "Impact and recovery after landing."], ["Roll", "roll", "A forward combat roll."], ["Dodge", "dodge", "A quick evasive dodge."], ["Dash", "dash", "A fast directional dash."], ["Climb", "climb", "Alternating limbs moving upward."],
  ],
  combat: [
    ["Attack", "attack", "Legacy-compatible clear attack animation."], ["Punch", "punch", "Forward punch with body rotation."], ["Jab", "jab", "A quick sharp jab."], ["Kick", "kick", "A dynamic forward kick."], ["Heavy Punch", "heavy_punch", "Powerful punch with follow-through."], ["Heavy Kick", "heavy_kick", "Powerful kick with body rotation."], ["Combo Attack", "combo_attack", "A fast multi-hit combo."], ["Sword Slash", "sword_slash", "Fast sword slash with follow-through."], ["Heavy Sword Slash", "heavy_sword_slash", "Powerful sword attack with body rotation."], ["Sword Stab", "sword_stab", "Forward sword thrust and recovery."], ["Axe Swing", "axe_swing", "A wide powerful axe swing."], ["Spear Thrust", "spear_thrust", "A precise forward spear thrust."], ["Dagger Attack", "dagger_attack", "A quick close-range dagger attack."], ["Bow Shoot", "bow_shoot", "Aim, draw, and release a bow."], ["Magic Attack", "magic_attack", "Expressive magical casting movement."], ["Ranged Attack", "ranged_attack", "A readable ranged release."], ["Special Attack", "special_attack", "Dramatic anticipation and follow-through."],
  ],
  defense: [["Block", "block", "A defensive block."], ["Shield Block", "shield_block", "A strong shield block."], ["Parry", "parry", "A precise parry and recovery."], ["Guard", "guard", "A ready defensive stance."], ["Dodge", "dodge_defense", "A quick defensive dodge."], ["Counter Attack", "counter_attack", "A block followed by a counter."],],
  damage: [["Hurt", "hurt", "A brief hurt reaction."], ["Hit Reaction", "hit_reaction", "A readable full-body reaction."], ["Knockback", "knockback", "Staggering backward from impact."], ["Stagger", "stagger", "Recovering balance unsteadily."], ["Fall Down", "fall_down", "Falling after being hit."], ["Get Up", "get_up", "A clear recovery from the ground."], ["Death", "death", "Defeat and final resting pose."],],
  character: [["Idle", "character_idle", "Subtle natural idle movement."], ["Look Around", "look_around", "Curious head and body movement."], ["Sit", "sit", "A readable seated pose."], ["Stand", "stand", "Standing up with recovery."], ["Wave", "wave", "A clear friendly arm gesture."], ["Talk", "talk", "Expressive conversational gestures."], ["Celebrate", "celebrate", "Energetic celebratory movement."], ["Cheer", "cheer", "Raised arms and joyful movement."], ["Sad", "sad", "A subdued sad reaction."], ["Angry", "angry", "An expressive angry reaction."], ["Laugh", "laugh", "Expressive laughing movement."],],
  interaction: [["Pick Up", "pick_up", "Reach down and pick up an item."], ["Drop", "drop", "A clear item drop gesture."], ["Push", "push", "Pushing with full-body effort."], ["Pull", "pull", "Pulling with visible effort."], ["Open", "open", "A clear opening gesture."], ["Close", "close", "A clear closing gesture."], ["Activate", "activate", "A deliberate activation gesture."], ["Use Item", "use_item", "A readable item-use gesture."],],
};

export const CATEGORY_LABELS = { movement: "Movement", combat: "Combat", defense: "Defense", damage: "Damage", character: "Character", interaction: "Interaction" };
export const QUICK_ACTIONS = ["idle", "walk", "run", "jump", "attack"];
export const LEGACY_ACTION_LABELS = { idle: "Idle", walk: "Walk", run: "Run", jump: "Jump", attack: "Attack" };

export function findAction(value) {
  for (const [category, actions] of Object.entries(ACTION_GROUPS)) {
    const action = actions.find((item) => item[1] === value);
    if (action) return { category, label: action[0], value: action[1], description: action[2] };
  }
  if (LEGACY_ACTION_LABELS[value]) return { category: "combat", label: LEGACY_ACTION_LABELS[value], value, description: "Legacy-compatible animation action." };
  return null;
}
