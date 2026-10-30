export const IMAGE_PROVIDER_OPTIONS = [
  { value: "pollinations", label: "Pollinations" },
  { value: "cloudflare", label: "Cloudflare Workers AI" },
];

export const DEFAULT_IMAGE_PROVIDER_SETTINGS = {
  provider: "pollinations",
  allowCloudflareFallback: false,
};

const IMAGE_PROVIDER_VALUES = new Set(IMAGE_PROVIDER_OPTIONS.map((option) => option.value));
const STORAGE_KEY_PREFIX = "assetai-image-provider-settings-";

export function normalizeImageProviderSettings(settings) {
  return {
    provider: IMAGE_PROVIDER_VALUES.has(settings?.provider)
      ? settings.provider
      : DEFAULT_IMAGE_PROVIDER_SETTINGS.provider,
    allowCloudflareFallback:
      settings?.provider === "pollinations" && settings.allowCloudflareFallback === true,
  };
}

export function loadImageProviderSettings(userId, storage = localStorage) {
  if (!userId) return { ...DEFAULT_IMAGE_PROVIDER_SETTINGS };
  const stored = storage.getItem(`${STORAGE_KEY_PREFIX}${userId}`);
  if (!stored) return { ...DEFAULT_IMAGE_PROVIDER_SETTINGS };

  try {
    return normalizeImageProviderSettings(JSON.parse(stored));
  } catch (error) {
    if (error instanceof SyntaxError) return { ...DEFAULT_IMAGE_PROVIDER_SETTINGS };
    throw error;
  }
}

export function saveImageProviderSettings(userId, settings, storage = localStorage) {
  const normalized = normalizeImageProviderSettings(settings);
  if (userId) {
    storage.setItem(`${STORAGE_KEY_PREFIX}${userId}`, JSON.stringify(normalized));
  }
  return normalized;
}

export function createImageProviderRequestOptions(settings) {
  const normalized = normalizeImageProviderSettings(settings);
  return {
    provider: normalized.provider,
    allow_cloudflare_fallback:
      normalized.provider === "pollinations" && normalized.allowCloudflareFallback,
  };
}

export function formatImageProviderError(error, provider) {
  const message = error?.message || "Image generation failed.";
  if (/authentication|unauthorized|forbidden|\b401\b|\b403\b/i.test(message)) {
    return `${providerLabel(provider)} authentication failed. Check the provider configuration on the backend.`;
  }
  if (/quota|billing|payment|required credits|\b402\b|\b429\b/i.test(message)) {
    return `The ${providerLabel(provider)} request was blocked by a quota or billing restriction. Check provider limits; no automatic upgrade was attempted.`;
  }
  return message;
}

function providerLabel(provider) {
  return IMAGE_PROVIDER_OPTIONS.find((option) => option.value === provider)?.label || "Image provider";
}
