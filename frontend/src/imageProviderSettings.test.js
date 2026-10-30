import assert from "node:assert/strict";
import test from "node:test";
import { createPromptGenerationRequest } from "./animationGeneration.js";
import {
  DEFAULT_IMAGE_PROVIDER_SETTINGS,
  IMAGE_PROVIDER_OPTIONS,
  createImageProviderRequestOptions,
  formatImageProviderError,
  loadImageProviderSettings,
  normalizeImageProviderSettings,
  saveImageProviderSettings,
} from "./imageProviderSettings.js";
import { createSelectedCharacterRequest } from "./animationGeneration.js";

function createStorage(initial = {}) {
  const values = new Map(Object.entries(initial));
  return {
    getItem(key) {
      return values.get(key) || null;
    },
    setItem(key, value) {
      values.set(key, value);
    },
  };
}

test("provider selection exposes only the two supported image providers", () => {
  assert.deepEqual(IMAGE_PROVIDER_OPTIONS.map(({ value }) => value), ["pollinations", "cloudflare"]);
  assert.deepEqual(
    normalizeImageProviderSettings({ provider: "unknown", allowCloudflareFallback: true }),
    DEFAULT_IMAGE_PROVIDER_SETTINGS,
  );
});

test("prompt generation request includes the selected image provider and fallback choice", () => {
  const settings = createImageProviderRequestOptions({
    provider: "pollinations",
    allowCloudflareFallback: true,
  });

  assert.deepEqual(
    createPromptGenerationRequest("  A fox  ", "walk", 8, settings),
    {
      endpoint: "/generate-sprite-from-prompt",
      payload: {
        prompt: "A fox",
        action: "walk",
        frame_count: 8,
        provider: "pollinations",
        allow_cloudflare_fallback: true,
      },
    },
  );
});

test("selected-character animation requests do not receive image provider settings", () => {
  const request = createSelectedCharacterRequest("/assets/42/file", "walk", 8);
  assert.equal("provider" in request.payload, false);
  assert.equal("allow_cloudflare_fallback" in request.payload, false);
});

test("cloudflare selection cannot request cloudflare fallback", () => {
  assert.deepEqual(
    createImageProviderRequestOptions({
      provider: "cloudflare",
      allowCloudflareFallback: true,
    }),
    { provider: "cloudflare", allow_cloudflare_fallback: false },
  );
});

test("image provider preferences persist separately for each signed-in user", () => {
  const storage = createStorage();
  saveImageProviderSettings(
    "user-1",
    { provider: "cloudflare", allowCloudflareFallback: true },
    storage,
  );

  assert.deepEqual(loadImageProviderSettings("user-1", storage), {
    provider: "cloudflare",
    allowCloudflareFallback: false,
  });
  assert.deepEqual(loadImageProviderSettings("user-2", storage), DEFAULT_IMAGE_PROVIDER_SETTINGS);
  assert.deepEqual(loadImageProviderSettings(null, storage), DEFAULT_IMAGE_PROVIDER_SETTINGS);
});

test("invalid saved settings reset to safe defaults", () => {
  const storage = createStorage({
    "assetai-image-provider-settings-user-1": JSON.stringify({
      provider: "replicate",
      allowCloudflareFallback: "yes",
    }),
    "assetai-image-provider-settings-user-2": "{",
  });

  assert.deepEqual(loadImageProviderSettings("user-1", storage), DEFAULT_IMAGE_PROVIDER_SETTINGS);
  assert.deepEqual(loadImageProviderSettings("user-2", storage), DEFAULT_IMAGE_PROVIDER_SETTINGS);
});

test("provider quota and authentication responses get clear user-facing errors", () => {
  assert.match(
    formatImageProviderError(new Error("HTTP 429: quota exhausted"), "cloudflare"),
    /Cloudflare Workers AI request was blocked by a quota or billing restriction/,
  );
  assert.match(
    formatImageProviderError(new Error("HTTP 401: unauthorized"), "pollinations"),
    /Pollinations authentication failed/,
  );
  assert.match(
    formatImageProviderError(new Error("HTTP 402: payment required"), "pollinations"),
    /quota or billing restriction/,
  );
  assert.match(
    formatImageProviderError(new Error("HTTP 403: forbidden"), "cloudflare"),
    /Cloudflare Workers AI authentication failed/,
  );
  assert.equal(
    formatImageProviderError(new Error("service unavailable"), "pollinations"),
    "service unavailable",
  );
});
