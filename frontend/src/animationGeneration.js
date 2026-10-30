export const SELECTED_CHARACTER_ENDPOINT = "/generate-sprite";
export const PROMPT_GENERATION_ENDPOINT = "/generate-sprite-from-prompt";
export const SUPPORTED_FRAME_COUNTS = [4, 8, 12, 16];

export function createSelectedCharacterRequest(characterUrl, action, frameCount) {
  if (!/^\/assets\/\d+\/file$/.test(characterUrl || "")) {
    throw new Error("Choose one of your processed characters before generating an animation.");
  }
  if (!action || !SUPPORTED_FRAME_COUNTS.includes(Number(frameCount))) {
    throw new Error("Choose a supported action and frame count.");
  }

  return {
    endpoint: SELECTED_CHARACTER_ENDPOINT,
    payload: {
      character_path: characterUrl,
      action,
      frame_count: Number(frameCount),
    },
  };
}

export function createPromptGenerationRequest(prompt, action, frameCount, imageProviderSettings) {
  const cleanPrompt = (prompt || "").trim();
  if (!cleanPrompt) throw new Error("Please enter a prompt before generating from text.");
  if (!action || !SUPPORTED_FRAME_COUNTS.includes(Number(frameCount))) {
    throw new Error("Choose a supported action and frame count.");
  }

  const payload = {
    prompt: cleanPrompt,
    action,
    frame_count: Number(frameCount),
  };
  if (imageProviderSettings) {
    Object.assign(payload, imageProviderSettings);
  }

  return {
    endpoint: PROMPT_GENERATION_ENDPOINT,
    payload,
  };
}

export function canGenerateFromCharacter({ characterUrl, action, frameCount, isBusy }) {
  return Boolean(
    /^\/assets\/\d+\/file$/.test(characterUrl || "")
    && action
    && SUPPORTED_FRAME_COUNTS.includes(Number(frameCount))
    && !isBusy,
  );
}

export function canGenerateFromPrompt({ prompt, action, frameCount, isBusy }) {
  return Boolean(
    (prompt || "").trim()
    && action
    && SUPPORTED_FRAME_COUNTS.includes(Number(frameCount))
    && !isBusy,
  );
}
