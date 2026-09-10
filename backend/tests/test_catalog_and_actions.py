from app.generation.prompt_catalog import enrich_prompt
from app.sprite.action_taxonomy import get_action


def test_prompt_enrichment_preserves_explicit_style_and_adds_asset_constraints():
    prompt = "anime mage with a staff"
    enhanced = enrich_prompt(prompt)

    assert enhanced.startswith(prompt)
    assert "anime" in enhanced.lower()
    assert "full body" in enhanced.lower()
    assert "transparent-background friendly" in enhanced.lower()


def test_specific_action_resolves_to_legacy_provider_action():
    action = get_action("sword_slash")

    assert action["value"] == "sword_slash"
    assert action["provider_action"] == "attack"
    assert "sword slash" in action["prompt"]


def test_existing_actions_remain_supported():
    assert get_action("walk")["provider_action"] == "walk"
    assert get_action("idle")["provider_action"] == "idle"
    assert get_action("run")["provider_action"] == "run"
    assert get_action("jump")["provider_action"] == "jump"
    assert get_action("attack")["provider_action"] == "attack"
