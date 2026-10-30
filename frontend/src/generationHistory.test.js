import assert from "node:assert/strict";
import test from "node:test";
import { getGenerationStatusClass } from "./generationHistory.js";

test("generation statuses map to accurate history styles", () => {
  assert.equal(getGenerationStatusClass("completed"), "ready");
  assert.equal(getGenerationStatusClass("failed"), "failed");
  assert.equal(getGenerationStatusClass("pending"), "");
});
