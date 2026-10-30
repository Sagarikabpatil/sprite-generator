import assert from "node:assert/strict";
import test from "node:test";
import {
  createAssetAnalysisRequest,
  getAssetAnalysisError,
  getAssetIdFromFileUrl,
  supportsFrameComparison,
  supportsQualityAnalysis,
} from "./assetAnalysis.js";

test("quality analysis is limited to supported image asset types", () => {
  assert.equal(supportsQualityAnalysis("sprite_sheet"), true);
  assert.equal(supportsQualityAnalysis("frame"), true);
  assert.equal(supportsQualityAnalysis("processed"), false);
  assert.equal(supportsQualityAnalysis("video"), false);
});

test("frame comparison is available only for sprite sheets", () => {
  assert.equal(supportsFrameComparison("sprite_sheet"), true);
  assert.equal(supportsFrameComparison("frame"), false);
  assert.equal(supportsFrameComparison("character"), false);
});

test("analysis requests use the authenticated API route for the asset", () => {
  assert.deepEqual(
    createAssetAnalysisRequest(42, "quality", "session-token", "https://api.example"),
    {
      url: "https://api.example/assets/42/quality",
      options: { headers: { Authorization: "Bearer session-token" } },
    },
  );
  assert.deepEqual(
    createAssetAnalysisRequest("42", "frame-comparison", "session-token", "https://api.example"),
    {
      url: "https://api.example/assets/42/frame-comparison",
      options: { headers: { Authorization: "Bearer session-token" } },
    },
  );
});

test("analysis request rejects invalid ids, modes, and missing authentication", () => {
  assert.throws(
    () => createAssetAnalysisRequest("42x", "quality", "token", ""),
    /valid ID/,
  );
  assert.throws(
    () => createAssetAnalysisRequest(42, "history", "token", ""),
    /supported asset analysis/,
  );
  assert.throws(
    () => createAssetAnalysisRequest(42, "quality", "", ""),
    /Sign in/,
  );
  assert.throws(
    () => createAssetAnalysisRequest(Number.MAX_SAFE_INTEGER + 1, "quality", "token", ""),
    /valid ID/,
  );
});

test("older sheets without associations receive a clear comparison message", () => {
  assert.match(
    getAssetAnalysisError({ status: 404, message: "No saved frame association exists." }, "frame-comparison"),
    /older.*no saved frame association/i,
  );
  assert.equal(
    getAssetAnalysisError({ status: 404, message: "Not found." }, "quality"),
    "This asset could not be found or is no longer available.",
  );
  assert.equal(
    getAssetAnalysisError({ message: "Backend unavailable." }, "quality"),
    "Backend unavailable.",
  );
});

test("generated sheet file URLs yield a safe asset id", () => {
  assert.equal(getAssetIdFromFileUrl("/assets/42/file"), 42);
  assert.equal(getAssetIdFromFileUrl("https://api.example/assets/42/file"), null);
  assert.equal(getAssetIdFromFileUrl("/assets/0/file"), null);
  assert.equal(getAssetIdFromFileUrl("/assets/42/file?download=1"), null);
});
