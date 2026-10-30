import assert from "node:assert/strict";
import test from "node:test";
import {
  canGenerateFromCharacter,
  canGenerateFromPrompt,
  createPromptGenerationRequest,
  createSelectedCharacterRequest,
} from "./animationGeneration.js";
import { createImageProviderRequestOptions } from "./imageProviderSettings.js";

test("selected-character workflow submits its owned asset URL to the sprite endpoint", () => {
  assert.deepEqual(
    createSelectedCharacterRequest("/assets/42/file", "walk", 8),
    {
      endpoint: "/generate-sprite",
      payload: {
        character_path: "/assets/42/file",
        action: "walk",
        frame_count: 8,
      },
    },
  );
});

test("prompt workflow submits a non-empty prompt without an asset URL", () => {
  assert.deepEqual(
    createPromptGenerationRequest("  A fox running  ", "run", "4"),
    {
      endpoint: "/generate-sprite-from-prompt",
      payload: {
        prompt: "A fox running",
        action: "run",
        frame_count: 4,
      },
    },
  );
  assert.throws(() => createPromptGenerationRequest("  ", "run", 4), /enter a prompt/i);
});

test("prompt workflow includes image provider and fallback preferences in its API request", () => {
  const providerOptions = createImageProviderRequestOptions({
    provider: "cloudflare",
    allowCloudflareFallback: true,
  });

  assert.deepEqual(
    createPromptGenerationRequest("A fox running", "run", 8, providerOptions).payload,
    {
      prompt: "A fox running",
      action: "run",
      frame_count: 8,
      provider: "cloudflare",
      allow_cloudflare_fallback: false,
    },
  );
});

test("generation controls enable only for valid inputs while idle", () => {
  assert.equal(canGenerateFromCharacter({
    characterUrl: "/assets/42/file",
    action: "walk",
    frameCount: 8,
    isBusy: false,
  }), true);
  assert.equal(canGenerateFromCharacter({
    characterUrl: "",
    action: "walk",
    frameCount: 8,
    isBusy: false,
  }), false);
  assert.equal(canGenerateFromCharacter({
    characterUrl: "/assets/42/file",
    action: "walk",
    frameCount: 8,
    isBusy: true,
  }), false);
  assert.equal(canGenerateFromPrompt({
    prompt: "A fox",
    action: "walk",
    frameCount: 8,
    isBusy: false,
  }), true);
  assert.equal(canGenerateFromPrompt({
    prompt: "A fox",
    action: "",
    frameCount: 8,
    isBusy: false,
  }), false);
  assert.equal(canGenerateFromPrompt({
    prompt: "A fox",
    action: "walk",
    frameCount: 8,
    isBusy: true,
  }), false);
});
