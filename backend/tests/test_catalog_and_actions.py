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


def test_action_catalogue_api_uses_backend_taxonomy(isolated_client):
    client, _, _ = isolated_client

    response = client.get("/actions")

    assert response.status_code == 200
    groups = {group["value"]: group for group in response.json()}
    assert {"movement", "combat", "defense", "damage", "character", "interaction"} <= groups.keys()
    actions = {action["value"]: action for group in groups.values() for action in group["actions"]}
    assert actions["sword_slash"]["label"] == "Sword Slash"
    assert "sword slash" in actions["sword_slash"]["description"]


def test_prompt_ideas_api_returns_varied_curated_prompts(isolated_client):
    client, _, _ = isolated_client

    response = client.get("/prompt-ideas")

    assert response.status_code == 200
    ideas = response.json()
    assert len(ideas) >= 10
    assert len({idea["prompt"] for idea in ideas}) == len(ideas)
    assert {idea["label"] for idea in ideas} >= {"Forest fox ranger", "Space mechanic"}


def test_cors_allows_localhost_and_loopback_vite_origins(isolated_client):
    client, _, _ = isolated_client

    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        response = client.options(
            "/actions",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert response.status_code == 200
        assert response.headers["access-control-allow-origin"] == origin
