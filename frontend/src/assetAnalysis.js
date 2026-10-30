export const QUALITY_ASSET_TYPES = new Set(["sprite_sheet", "frame"]);

export function supportsQualityAnalysis(assetType) {
  return QUALITY_ASSET_TYPES.has(assetType);
}

export function supportsFrameComparison(assetType) {
  return assetType === "sprite_sheet";
}

export function createAssetAnalysisRequest(assetId, analysisType, token, apiBase) {
  if (!Number.isSafeInteger(Number(assetId)) || Number(assetId) <= 0) {
    throw new Error("This asset does not have a valid ID.");
  }
  if (!["quality", "frame-comparison"].includes(analysisType)) {
    throw new Error("Choose a supported asset analysis.");
  }
  if (!token) {
    throw new Error("Sign in to analyze this asset.");
  }

  return {
    url: `${apiBase}/assets/${Number(assetId)}/${analysisType}`,
    options: {
      headers: { Authorization: `Bearer ${token}` },
    },
  };
}

export function getAssetAnalysisError(error, analysisType) {
  if (error?.status === 404 && analysisType === "frame-comparison") {
    return "Frame comparison is unavailable. This sprite sheet may be older and have no saved frame association.";
  }
  if (error?.status === 404 && analysisType === "quality") {
    return "This asset could not be found or is no longer available.";
  }
  return error?.message || "Asset analysis failed. Please try again.";
}

export function getAssetIdFromFileUrl(fileUrl) {
  const match = /^\/assets\/([1-9]\d*)\/file$/.exec(fileUrl || "");
  if (!match) return null;
  const assetId = Number(match[1]);
  return Number.isSafeInteger(assetId) ? assetId : null;
}
