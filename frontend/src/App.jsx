import { useCallback, useEffect, useRef, useState } from "react";
import { BrowserRouter, NavLink, Route, Routes, useNavigate, useParams } from "react-router-dom";
import AssetAnalysis from "./AssetAnalysis.jsx";
import GeneratedAnimation from "./GeneratedAnimation";
import { API_BASE, downloadAsset } from "./api";
import {
  canGenerateFromCharacter,
  canGenerateFromPrompt,
  createPromptGenerationRequest,
  createSelectedCharacterRequest,
  SUPPORTED_FRAME_COUNTS,
} from "./animationGeneration.js";
import { getGenerationStatusClass } from "./generationHistory.js";
import {
  createImageProviderRequestOptions,
  formatImageProviderError,
  IMAGE_PROVIDER_OPTIONS,
  loadImageProviderSettings,
  saveImageProviderSettings,
} from "./imageProviderSettings.js";
import "./App.css";

const THEME_OPTIONS = [
  { value: "dark", label: "Dark" },
  { value: "light", label: "Light" },
  { value: "neon", label: "Neon" },
  { value: "spider", label: "Spider-Man" },
  { value: "pastel", label: "Pastel" },
];
const PASTEL_PALETTES = [
  { value: "pink", label: "Pink" },
  { value: "yellow", label: "Yellow" },
  { value: "blue", label: "Blue" },
  { value: "lavender", label: "Lavender" },
  { value: "mint", label: "Mint" },
  { value: "peach", label: "Peach" },
];
const IMAGE_EXTENSIONS = new Set([".png", ".jpg", ".jpeg", ".webp"]);
const MAX_IMAGE_SIZE = 10 * 1024 * 1024;

function imageFileError(file) {
  const extension = file.name.slice(file.name.lastIndexOf(".")).toLowerCase();
  if (!IMAGE_EXTENSIONS.has(extension)) return "Choose a PNG, JPG, JPEG, or WEBP image.";
  if (file.size > MAX_IMAGE_SIZE) return "Image uploads must be 10 MB or smaller.";
  return "";
}

function getStoredProcessedCharacter(userId) {
  if (!userId) return "";
  const url = localStorage.getItem(`assetai-processed-character-${userId}`) || "";
  return /^\/assets\/\d+\/file$/.test(url) ? url : "";
}

function useCatalog(path, failureMessage) {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchJson(`${API_BASE}${path}`)
      .then((data) => {
        if (active) setItems(Array.isArray(data) ? data : []);
      })
      .catch((loadError) => {
        if (active) setError(loadError.message || failureMessage);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => { active = false; };
  }, [path, failureMessage]);

  return { items, loading, error };
}

async function fetchJson(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData) && !headers["Content-Type"] && typeof options.body === "string") {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    if (error instanceof TypeError) {
      throw new Error(
        "Could not reach the AssetAI backend. Confirm it is running and that this frontend origin is allowed by CORS.",
        { cause: error },
      );
    }
    throw error;
  }
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json") ? await response.json() : await response.text();

  if (!response.ok) {
    const message = typeof payload === "object" && payload !== null ? payload.detail || payload.error || "Request failed." : payload || "Request failed.";
    throw new Error(message);
  }

  return payload;
}

function assetRequestUrl(url) {
  return url.startsWith("http") ? url : `${API_BASE}${url}`;
}

async function fetchAsset(url, token) {
  const response = await fetch(assetRequestUrl(url), {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) {
    throw new Error("Asset could not be loaded.");
  }
  return response;
}

function useAssetUrl(url, token) {
  const key = `${url || ""}:${token || ""}`;
  const [asset, setAsset] = useState({ key: "", url: "", error: "" });

  useEffect(() => {
    if (!url || !token) return undefined;

    let active = true;
    let currentUrl = "";
    fetchAsset(url, token)
      .then((response) => response.blob())
      .then((blob) => {
        if (active) {
          currentUrl = URL.createObjectURL(blob);
          setAsset({ key, url: currentUrl, error: "" });
        }
      })
      .catch((error) => {
        if (active) setAsset({ key, url: "", error: error.message || "Asset could not be loaded." });
      });

    return () => {
      active = false;
      if (currentUrl) URL.revokeObjectURL(currentUrl);
    };
  }, [url, token, key]);

  return asset.key === key ? asset : { url: "", error: "" };
}

function AssetImage({ url, token, alt, ...props }) {
  const source = useAssetUrl(url, token);
  return source.url ? <img src={source.url} alt={alt} {...props} /> : <span className="asset-loading">{source.error || alt}</span>;
}

function getInitials(name) {
  if (!name) return "AI";
  const parts = name.trim().split(/\s+/).slice(0, 2);
  return parts.map((part) => part.charAt(0).toUpperCase()).join("") || "AI";
}

function DownloadButton({ href, label, type = "asset", token }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  if (!href) return null;

  const download = async () => {
    setDownloading(true);
    setError("");
    try {
      await downloadAsset(href, token, label || "asset");
    } catch (downloadError) {
      setError(downloadError.message || "Asset download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return <>
    <button className="button button-secondary action-button" type="button" onClick={download} disabled={downloading}>
      <span aria-hidden="true">↓</span>
      {downloading ? "Preparing download..." : label || (type === "video" ? "Download video" : "Download")}
    </button>
    {error && <span className="download-error" role="alert">{error}</span>}
  </>;
}

function PageLayout({ eyebrow, title, subtitle, actions, children }) {
  return (
    <div className="page-shell">
      <header className="page-header">
        <div>
          <p className="eyebrow">{eyebrow}</p>
          <h1 className="page-title">{title}</h1>
          {subtitle && <p className="page-subtitle">{subtitle}</p>}
        </div>
        {actions}
      </header>
      {children}
    </div>
  );
}

function StatCard({ label, value, tone = "neutral" }) {
  return (
    <article className={`stat-card tone-${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </article>
  );
}

function AppHeader({ token, user, onLogout }) {
  const [menuOpen, setMenuOpen] = useState(false);

  const closeMenu = () => setMenuOpen(false);

  return (
    <header className="topbar">
      <div className="topbar-inner">
        <NavLink className="brand" to="/" aria-label="AssetAI home">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <span>AssetAI</span>
        </NavLink>

        <nav className="nav-links" aria-label="Main navigation">
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/">Home</NavLink>
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/studio/character">Character Studio</NavLink>
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/studio/animation">Animation Studio</NavLink>
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/assets">Assets Library</NavLink>
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/history">History</NavLink>
          <NavLink onClick={closeMenu} className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")} to="/settings">Settings</NavLink>
        </nav>

        <div className="profile-area">
          {token ? (
            <div className="profile-menu-wrap">
              <button type="button" className="profile-button" onClick={() => setMenuOpen((open) => !open)} aria-expanded={menuOpen} aria-haspopup="menu">
                <span className="profile-avatar">{getInitials(user?.display_name || user?.email || "AI")}</span>
                <span>{user?.display_name || user?.email || "Studio user"}</span>
              </button>

              {menuOpen && (
                <div className="profile-menu" role="menu">
                  <div className="profile-menu-header">
                    <strong>{user?.display_name || "Studio user"}</strong>
                    <small>{user?.email || "Not signed in"}</small>
                  </div>
                  <NavLink to="/settings" role="menuitem" onClick={closeMenu}>Account settings</NavLink>
                  <button type="button" onClick={() => { closeMenu(); onLogout(); }} role="menuitem">Log out</button>
                </div>
              )}
            </div>
          ) : (
            <div className="auth-links">
              <NavLink className="button button-secondary compact" to="/auth/login">Login</NavLink>
              <NavLink className="button button-primary compact" to="/auth/signup">Sign up</NavLink>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}

function AuthPage({ onAuthenticate }) {
  const navigate = useNavigate();
  const { mode } = useParams();
  const authMode = mode === "signup" ? "signup" : "login";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (event) => {
    event.preventDefault();
    setError("");
    setIsSubmitting(true);

    try {
      const data = await fetchJson(`${API_BASE}/auth/${authMode}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!data.token) {
        throw new Error("Authentication response was incomplete.");
      }
      onAuthenticate(data.token, data.user);
      navigate("/");
    } catch (submitError) {
      setError(submitError.message || "Authentication failed.");
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="auth-shell">
      <div className="auth-card">
        <div className="auth-brand">
          <span className="brand-mark" aria-hidden="true"><span /></span>
          <div>
            <div className="brand-name">AssetAI</div>
            <div className="brand-subtitle">Studio access</div>
          </div>
        </div>

        <div className="auth-tabs" role="tablist" aria-label="Authentication mode">
          <NavLink to="/auth/login" className={({ isActive }) => (isActive ? "auth-tab active" : "auth-tab")}>Login</NavLink>
          <NavLink to="/auth/signup" className={({ isActive }) => (isActive ? "auth-tab active" : "auth-tab")}>Sign up</NavLink>
        </div>

        <form className="auth-form" onSubmit={handleSubmit}>
          <label className="field-label" htmlFor="auth-email">
            <span>Email</span>
            <input id="auth-email" type="email" value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
          </label>

          <label className="field-label" htmlFor="auth-password">
            <span>Password</span>
            <input id="auth-password" type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="••••••••" minLength={8} required />
          </label>

          {error && (
            <div className="alert error-alert" role="alert">
              <strong>Authentication error</strong>
              <span>{error}</span>
            </div>
          )}

          <button className="button button-primary full-width" type="submit" disabled={isSubmitting}>
            {isSubmitting ? (authMode === "login" ? "Logging in..." : "Creating account...") : authMode === "login" ? "Log in" : "Create account"}
          </button>
        </form>
      </div>
    </div>
  );
}

function CharacterUploadPanel({ image, previewUrl, originalImage, removedImage, processedImage, isUploading, uploadError, onImageChange, onUpload, token }) {
  const [isDragging, setIsDragging] = useState(false);
  const originalUrl = useAssetUrl(originalImage, token);
  const removedUrl = useAssetUrl(removedImage, token);
  const processedUrl = useAssetUrl(processedImage, token);

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const [file] = event.dataTransfer.files;
    if (file) onImageChange(file);
  };

  return (
    <section className="surface">
      <div className="panel-header">
        <div>
          <p className="eyebrow">Character source</p>
          <h2>Upload or prepare a reference</h2>
        </div>
        <span className={`status-pill ${processedImage ? "ready" : ""}`}>{processedImage ? "Ready" : "Waiting"}</span>
      </div>

      <label className={`upload-dropzone ${isDragging ? "dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
        <input type="file" accept=".png,.jpg,.jpeg,.webp" onChange={(event) => onImageChange(event.target.files[0])} />
        <span className="upload-icon" aria-hidden="true">+</span>
        <strong>{image ? image.name : "Drop a character image"}</strong>
        <span>PNG, JPG or WEBP · transparent backgrounds welcome</span>
        <em>Browse files</em>
      </label>

      <button className="button button-secondary full-width" type="button" onClick={onUpload} disabled={!image || isUploading}>
        <span aria-hidden="true">↥</span>
        {isUploading ? "Processing..." : "Upload and preprocess"}
      </button>

      {uploadError && (
        <div className="alert error-alert" role="alert">
          <strong>Upload failed</strong>
          <span>{uploadError}</span>
        </div>
      )}

      {(previewUrl && !originalImage) && (
        <div className="preview-strip">
          <span>Selected preview</span>
          <img src={previewUrl} alt="Selected reference preview" />
        </div>
      )}

      {(originalImage || removedImage || processedImage) && (
        <div className="image-grid">
          <div className="image-card"><header>Original</header><img src={originalUrl.url || previewUrl} alt="Original character" /></div>
          <div className="image-card"><header>Background removed</header>{removedUrl.url ? <img src={removedUrl.url} alt="Background removed" /> : removedUrl.error}</div>
          <div className="image-card"><header>Processed</header>{processedUrl.url ? <img src={processedUrl.url} alt="Processed character" /> : processedUrl.error}</div>
        </div>
      )}
    </section>
  );
}

function CharacterStudioPage({ token, onProcessedCharacterChange }) {
  const [image, setImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [originalImage, setOriginalImage] = useState("");
  const [removedImage, setRemovedImage] = useState("");
  const [processedImage, setProcessedImage] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState("");
  const uploadRequestId = useRef(0);

  useEffect(() => {
    return () => {
      uploadRequestId.current += 1;
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const selectImage = (file) => {
    if (!file) return;
    uploadRequestId.current += 1;
    setIsUploading(false);
    const fileError = imageFileError(file);
    if (fileError) {
      setImage(null);
      setUploadError(fileError);
      setOriginalImage("");
      setRemovedImage("");
      setProcessedImage("");
      onProcessedCharacterChange("");
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return "";
      });
      return;
    }
    setImage(file);
    setUploadError("");
    setOriginalImage("");
    setRemovedImage("");
    setProcessedImage("");
    onProcessedCharacterChange("");
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return URL.createObjectURL(file);
    });
  };

  const uploadImage = async () => {
    if (!image) {
      setUploadError("Please select an image first.");
      return;
    }

    setIsUploading(true);
    setUploadError("");
    const requestId = ++uploadRequestId.current;
    const formData = new FormData();
    formData.append("file", image);

    try {
      const data = await fetchJson(`${API_BASE}/upload`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: formData });
      if (!data.processed) throw new Error("Upload completed without a processed character asset.");
      if (requestId === uploadRequestId.current) {
        setOriginalImage(data.original || "");
        setRemovedImage(data.removed || "");
        setProcessedImage(data.processed);
        onProcessedCharacterChange(data.processed);
      }
    } catch (error) {
      if (requestId === uploadRequestId.current) setUploadError(error.message || "Upload failed.");
    } finally {
      if (requestId === uploadRequestId.current) setIsUploading(false);
    }
  };

  return (
    <PageLayout
      eyebrow="AssetAI"
      title="Character Studio"
      subtitle="Upload a character reference and prepare its processed image for animation."
    >
      <div className="content-grid two-column">
        <CharacterUploadPanel image={image} previewUrl={previewUrl} originalImage={originalImage} removedImage={removedImage} processedImage={processedImage} isUploading={isUploading} uploadError={uploadError} onImageChange={selectImage} onUpload={uploadImage} token={token} />

        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Next step</p>
              <h2>Animate your character</h2>
            </div>
          </div>

          <div className="empty-state">
            <p>After preprocessing, continue to Animation Studio to select this processed character and choose an action. Text-prompt animation is available there too.</p>
            <NavLink className="button button-secondary" to="/studio/animation">Open Animation Studio</NavLink>
          </div>
        </section>
      </div>
    </PageLayout>
  );
}

function AnimationStudioPage({
  token,
  userId,
  selectedProcessedCharacter,
  onProcessedCharacterChange,
  imageProviderSettings,
}) {
  const [prompt, setPrompt] = useState("A pixel art dog running near a tree");
  const promptCatalog = useCatalog("/prompt-ideas", "Could not load prompt ideas.");
  const actionCatalog = useCatalog("/actions", "Could not load animation actions.");
  const [selectedPrompt, setSelectedPrompt] = useState("");
  const [image, setImage] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [processedAssets, setProcessedAssets] = useState([]);
  const [processedAssetsOwnerId, setProcessedAssetsOwnerId] = useState(null);
  const [processedAssetsError, setProcessedAssetsError] = useState("");
  const [selectionError, setSelectionError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [spriteGenerationError, setSpriteGenerationError] = useState("");
  const [promptGenerationError, setPromptGenerationError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [isGeneratingPrompt, setIsGeneratingPrompt] = useState(false);
  const [action, setAction] = useState("walk");
  const [actionCategory, setActionCategory] = useState("movement");
  const [frameCount, setFrameCount] = useState(8);
  const [animationResult, setAnimationResult] = useState(null);
  const generationRequestId = useRef(0);
  const uploadRequestId = useRef(0);
  const processedImage = processedAssets.find((asset) => asset.file_url === selectedProcessedCharacter)?.file_url || "";
  const isLoadingProcessedAssets = Boolean(userId) && processedAssetsOwnerId !== userId;
  const isGenerationBusy = isGenerating || isGeneratingPrompt;

  const invalidateGeneration = () => {
    generationRequestId.current += 1;
    setAnimationResult(null);
    setSpriteGenerationError("");
    setPromptGenerationError("");
    setIsGenerating(false);
    setIsGeneratingPrompt(false);
  };

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);
  useEffect(() => () => {
    generationRequestId.current += 1;
    uploadRequestId.current += 1;
  }, []);
  useEffect(() => {
    let active = true;
    fetchJson(`${API_BASE}/assets`, { headers: { Authorization: `Bearer ${token}` } })
      .then((assets) => {
        if (!active) return;
        const available = assets.filter((asset) => asset.asset_type === "processed");
        setProcessedAssets(available);
        setProcessedAssetsError("");
        setProcessedAssetsOwnerId(userId);
        if (selectedProcessedCharacter && !available.some((asset) => asset.file_url === selectedProcessedCharacter)) {
          onProcessedCharacterChange("");
          setSelectionError("The previously selected processed character is no longer available. Choose another processed image.");
          invalidateGeneration();
        }
      })
      .catch((error) => {
        if (active) {
          setProcessedAssets([]);
          setProcessedAssetsError(error.message || "Could not load your processed character assets.");
          setProcessedAssetsOwnerId(userId);
        }
      });
    return () => { active = false; };
  }, [token, userId, selectedProcessedCharacter, onProcessedCharacterChange]);
  const selectImage = (file) => {
    if (!file) return;
    const fileError = imageFileError(file);
    if (fileError) {
      setImage(null);
      setUploadError(fileError);
      onProcessedCharacterChange("");
      setSelectionError("");
      invalidateGeneration();
      uploadRequestId.current += 1;
      setIsUploading(false);
      setPreviewUrl((current) => {
        if (current) URL.revokeObjectURL(current);
        return "";
      });
      return;
    }
    generationRequestId.current += 1;
    uploadRequestId.current += 1;
    setImage(file);
    setUploadError("");
    onProcessedCharacterChange("");
    setSelectionError("");
    invalidateGeneration();
    setIsUploading(false);
    setIsGenerating(false);
    setIsGeneratingPrompt(false);
    setPreviewUrl((current) => {
      if (current) URL.revokeObjectURL(current);
      return URL.createObjectURL(file);
    });
  };

  const uploadImage = async () => {
    if (!image) {
      setUploadError("Please choose a character image first.");
      return;
    }

    setIsUploading(true);
    setUploadError("");
    const requestId = ++uploadRequestId.current;
    try {
      const formData = new FormData();
      formData.append("file", image);
      const data = await fetchJson(`${API_BASE}/upload`, { method: "POST", headers: { Authorization: `Bearer ${token}` }, body: formData });
      if (requestId === uploadRequestId.current) {
        if (!data.processed) throw new Error("Preprocessing completed without a processed character asset.");
        setProcessedAssets((assets) => [
          ...assets.filter((asset) => asset.file_url !== data.processed),
          { id: data.processed, asset_type: "processed", file_url: data.processed, name: "Processed character" },
        ]);
        onProcessedCharacterChange(data.processed);
        setSelectionError("");
      }
    } catch (error) {
      if (requestId === uploadRequestId.current) setUploadError(error.message || "Could not preprocess the image.");
    } finally {
      if (requestId === uploadRequestId.current) setIsUploading(false);
    }
  };

  const selectedCategory = actionCatalog.items.find((item) => item.value === actionCategory);
  const categoryActions = selectedCategory?.actions || [];
  const selectedAction = categoryActions.find((item) => item.value === action);

  const generateSprite = async () => {
    setIsGenerating(true);
    setSpriteGenerationError("");
    setAnimationResult(null);
    const requestId = ++generationRequestId.current;

    try {
      const { endpoint, payload } = createSelectedCharacterRequest(processedImage, selectedAction?.value, frameCount);
      const data = await fetchJson(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      if (requestId === generationRequestId.current) setAnimationResult(data);
    } catch (error) {
      if (requestId === generationRequestId.current) {
        setSpriteGenerationError(error.message || "Sprite generation failed.");
      }
    } finally {
      if (requestId === generationRequestId.current) setIsGenerating(false);
    }
  };

  const generateSpriteFromPrompt = async () => {
    setIsGeneratingPrompt(true);
    setPromptGenerationError("");
    setAnimationResult(null);
    const requestId = ++generationRequestId.current;

    try {
      const { endpoint, payload } = createPromptGenerationRequest(
        prompt,
        selectedAction?.value,
        frameCount,
        createImageProviderRequestOptions(imageProviderSettings),
      );
      const data = await fetchJson(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(payload),
      });
      if (requestId === generationRequestId.current) {
        const processedUrl = data.processed_character_url || "";
        if (processedUrl) {
          setProcessedAssets((assets) => [
            ...assets.filter((asset) => asset.file_url !== processedUrl),
            { id: processedUrl, asset_type: "processed", file_url: processedUrl, name: "Prompt-generated character" },
          ]);
          onProcessedCharacterChange(processedUrl);
        }
        setAnimationResult(data);
      }
    } catch (error) {
      if (requestId === generationRequestId.current) {
        setPromptGenerationError(
          formatImageProviderError(error, imageProviderSettings.provider)
          || "Prompt-to-animation failed.",
        );
      }
    } finally {
      if (requestId === generationRequestId.current) setIsGeneratingPrompt(false);
    }
  };

  return (
    <PageLayout
      eyebrow="AssetAI"
      title="Animation Studio"
      subtitle="Generate a sprite cycle from a processed character or a text prompt. Animation uses its separate animation provider."
    >
      <div className="content-grid two-column">
        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Input</p>
              <h2>Character and action</h2>
            </div>
          </div>

          <label className="field-label">
            <span>Prompt</span>
            <textarea value={prompt} onChange={(event) => {
              invalidateGeneration();
              setPrompt(event.target.value);
            }} placeholder="A pixel art dog walking gracefully" />
          </label>
          <label className="field-label">
            <span>Prompt ideas</span>
            <select
              value={selectedPrompt}
              onChange={(event) => {
                const idea = promptCatalog.items.find((item) => item.prompt === event.target.value);
                invalidateGeneration();
                setSelectedPrompt(event.target.value);
                if (idea) setPrompt(idea.prompt);
              }}
              disabled={promptCatalog.loading || promptCatalog.items.length === 0}
            >
              <option value="">{promptCatalog.loading ? "Loading ideas..." : "Choose a curated idea"}</option>
              {promptCatalog.items.map((idea) => <option key={idea.label} value={idea.prompt}>{idea.label}</option>)}
            </select>
          </label>

          <div className="form-grid">
            <label className="field-label">
              <span>Action category</span>
              <select value={actionCategory} disabled={actionCatalog.loading || actionCatalog.items.length === 0} onChange={(event) => {
                const nextCategory = event.target.value;
                const group = actionCatalog.items.find((item) => item.value === nextCategory);
                invalidateGeneration();
                setActionCategory(nextCategory);
                setAction(group?.actions[0]?.value || "");
              }}>
                {actionCatalog.items.map((group) => <option key={group.value} value={group.value}>{group.label}</option>)}
              </select>
            </label>

            <label className="field-label">
              <span>Specific action</span>
              <select value={action} disabled={actionCatalog.loading || categoryActions.length === 0} onChange={(event) => {
                invalidateGeneration();
                setAction(event.target.value);
              }}>
                {categoryActions.map((item) => <option key={item.value} value={item.value}>{item.label}</option>)}
              </select>
            </label>
          </div>
          {actionCatalog.loading && <div className="loading-status" role="status">Loading animation actions...</div>}
          {actionCatalog.error && <div className="alert error-alert" role="alert">{actionCatalog.error}</div>}
          {promptCatalog.error && <div className="alert error-alert" role="alert">{promptCatalog.error}</div>}

          {uploadError && (
            <div className="alert error-alert" role="alert">
              <strong>Image preprocess failed</strong>
              <span>{uploadError}</span>
            </div>
          )}

          <label className="field-label">
            <span>Processed character</span>
            <select
              value={selectedProcessedCharacter}
              onChange={(event) => {
                onProcessedCharacterChange(event.target.value);
                setSelectionError("");
                invalidateGeneration();
              }}
              disabled={isLoadingProcessedAssets || processedAssets.length === 0}
            >
              <option value="">{isLoadingProcessedAssets ? "Loading your characters..." : "Choose a processed character"}</option>
              {processedAssets.map((asset) => (
                <option key={asset.id || asset.file_url} value={asset.file_url}>{asset.name || "Processed character"}</option>
              ))}
            </select>
          </label>
          {processedAssetsError && <div className="alert error-alert" role="alert">{processedAssetsError}</div>}
          {selectionError && <div className="alert error-alert" role="alert">{selectionError}</div>}
          {!isLoadingProcessedAssets && !processedAssetsError && processedAssets.length === 0 && (
            <div className="empty-state"><p>No processed characters are available. Upload and preprocess one in Character Studio first.</p></div>
          )}
          {!processedImage && !isLoadingProcessedAssets && processedAssets.length > 0 && (
            <div className="empty-state"><p>Select a processed character before generating an animation from an image.</p></div>
          )}

          <div className="button-row split">
            <button
              className="button button-primary"
              type="button"
              onClick={generateSprite}
              disabled={!canGenerateFromCharacter({
                characterUrl: processedImage,
                action: selectedAction?.value,
                frameCount,
                isBusy: isGenerationBusy || isLoadingProcessedAssets,
              })}
            >
              {isGenerating ? "Generating from character..." : "Generate from selected character"}
            </button>
          </div>
          {spriteGenerationError && (
            <div className="alert error-alert" role="alert">
              <strong>Character animation failed</strong>
              <span>{spriteGenerationError}</span>
              <button className="button button-secondary" type="button" onClick={generateSprite} disabled={isGenerationBusy}>
                Retry selected-character generation
              </button>
            </div>
          )}
          {isGenerating && <div className="loading-status" role="status" aria-live="polite">Requesting animation from MiniMax for the selected processed character.</div>}

          <label className="field-label">
            <span>Frame count</span>
            <select value={frameCount} onChange={(event) => {
              invalidateGeneration();
              setFrameCount(Number(event.target.value));
            }}>{SUPPORTED_FRAME_COUNTS.map((count) => <option key={count} value={count}>{count} frames</option>)}</select>
          </label>

          <div className="button-row split">
            <button
              className="button button-secondary"
              type="button"
              onClick={generateSpriteFromPrompt}
              disabled={!canGenerateFromPrompt({
                prompt,
                action: selectedAction?.value,
                frameCount,
                isBusy: isGenerationBusy,
              })}
            >
              {isGeneratingPrompt ? "Generating from prompt..." : "Generate from prompt"}
            </button>
          </div>
          {promptGenerationError && (
            <div className="alert error-alert" role="alert">
              <strong>Prompt animation failed</strong>
              <span>{promptGenerationError}</span>
              <button className="button button-secondary" type="button" onClick={generateSpriteFromPrompt} disabled={isGenerationBusy}>
                Retry prompt generation
              </button>
            </div>
          )}
          {isGeneratingPrompt && <div className="loading-status" role="status" aria-live="polite">Generating the character image with {IMAGE_PROVIDER_OPTIONS.find((option) => option.value === imageProviderSettings.provider)?.label || "the selected provider"}, then requesting animation from the separate animation provider.</div>}

          {selectedAction && (
            <div className="selected-action-box">
              <small>{selectedCategory?.label || actionCategory}</small>
              <strong>{selectedAction.label}</strong>
              <span>{selectedAction.description}</span>
            </div>
          )}

          <div className="upload-panel-compact">
            <label className="upload-dropzone small" onChange={(event) => selectImage(event.target.files[0])}>
              <input type="file" accept=".png,.jpg,.jpeg,.webp" />
              <span className="upload-icon" aria-hidden="true">+</span>
              <strong>{image ? image.name : "Upload processed character"}</strong>
              <span>Use existing image workflow</span>
            </label>
            <button className="button button-secondary" type="button" onClick={uploadImage} disabled={!image || isUploading}>{isUploading ? "Processing..." : "Preprocess image"}</button>
          </div>

          {processedImage && (
            <div className="generated-preview compact-preview">
              <AssetImage url={processedImage} token={token} alt="Processed character preview" />
              <div className="generated-meta">
                <strong>Ready for animation</strong>
                <DownloadButton href={processedImage} label="Download character" token={token} />
              </div>
            </div>
          )}
        </section>

        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Output</p>
              <h2>Generated result</h2>
            </div>
          </div>

          {animationResult ? (
            <GeneratedAnimation result={animationResult} token={token} />
          ) : (
            <div className="empty-state large">
              <p>Generate an animation to view the sprite sheet, frames, video, and export choices here.</p>
            </div>
          )}
        </section>
      </div>
    </PageLayout>
  );
}

function AssetsPage({ token }) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadAssets() {
      setLoading(true);
      setError("");
      try {
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const data = await fetchJson(`${API_BASE}/assets`, { headers });
        if (active) setAssets(Array.isArray(data) ? data : []);
      } catch (loadError) {
        if (active) setError(loadError.message || "Unable to load assets.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadAssets();
    return () => { active = false; };
  }, [token]);

  return (
    <PageLayout eyebrow="AssetAI" title="Assets Library" subtitle="Browse generated and uploaded files associated with your account.">
      <section className="surface">
        {loading && <div className="empty-state"><p>Loading library...</p></div>}
        {error && <div className="alert error-alert"><strong>Library unavailable</strong><span>{error}</span></div>}
        {!loading && !error && assets.length === 0 && <div className="empty-state"><p>No assets are available yet. Generate or upload content from the studio pages.</p></div>}

        {!loading && assets.length > 0 && (
          <div className="asset-grid">
            {assets.map((asset) => (
              <article key={`${asset.asset_type}-${asset.name}-${asset.id || asset.file_url}`} className="asset-card">
                <div className="asset-thumb">
                  {asset.file_url ? <AssetImage url={asset.file_url} token={token} alt={asset.name || asset.asset_type} /> : <span>{asset.asset_type}</span>}
                </div>
                <div className="asset-copy">
                  <div className="asset-row">
                    <span className="tag subtle">{asset.asset_type || "Asset"}</span>
                    <span className="asset-date">{asset.created_at ? new Date(asset.created_at).toLocaleDateString() : "Recently"}</span>
                  </div>
                  <strong>{asset.name || "Generated asset"}</strong>
                  {asset.prompt && <p>{asset.prompt}</p>}
                  <div className="button-row">
                    {asset.file_url && <DownloadButton href={asset.file_url} label={`Download ${asset.asset_type}`} token={token} />}
                  </div>
                  <AssetAnalysis
                    assetId={asset.id}
                    assetType={asset.asset_type}
                    token={token}
                  />
                </div>
              </article>
            ))}
          </div>
        )}
      </section>
    </PageLayout>
  );
}

function HistoryPage({ token }) {
  const [records, setRecords] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    if (!token) {
      return;
    }

    let active = true;

    async function loadHistory() {
      setLoading(true);
      setError("");
      try {
        const data = await fetchJson(`${API_BASE}/history`, { headers: { Authorization: `Bearer ${token}` } });
        if (active) setRecords(Array.isArray(data) ? data : []);
      } catch (loadError) {
        if (active) setError(loadError.message || "Unable to load generation history.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadHistory();
    return () => { active = false; };
  }, [token]);

  return (
    <PageLayout eyebrow="AssetAI" title="History" subtitle="Review the user-specific generation records for characters, sprites, and video outputs.">
      {!token ? (
        <div className="empty-state"><p>Please log in to view your personal generation history.</p></div>
      ) : (
        <section className="surface">
          {loading && <div className="empty-state"><p>Loading history...</p></div>}
          {error && <div className="alert error-alert"><strong>History unavailable</strong><span>{error}</span></div>}
          {!loading && !error && records.length === 0 && <div className="empty-state"><p>No generations yet. Start from Character Studio or Animation Studio to populate your activity log.</p></div>}

          {!loading && records.length > 0 && (
            <div className="history-list">
              {records.map((record) => (
                <article key={record.id} className="history-item">
                  <div className="history-main">
                    <div className="history-row"><span className="tag">{record.action || "activity"}</span><span className={`status-pill ${getGenerationStatusClass(record.status)}`}>{record.status || "completed"}</span></div>
                    <strong>{record.prompt || "Generated asset"}</strong>
                    <small>{record.created_at ? new Date(record.created_at).toLocaleString() : "Recently"}</small>
                  </div>
                  <div className="history-actions">
                    {record.video_path && <DownloadButton href={record.video_path} label="Download video" type="video" token={token} />}
                    {record.sprite_sheet_path && <DownloadButton href={record.sprite_sheet_path} label="Download sprite sheet" token={token} />}
                    {(record.processed_path || record.character_path) && <DownloadButton href={record.processed_path || record.character_path} label="Download output" token={token} />}
                  </div>
                </article>
              ))}
            </div>
          )}
        </section>
      )}
    </PageLayout>
  );
}

function SettingsPage({
  token,
  user,
  theme,
  setTheme,
  palette,
  setPalette,
  imageProviderSettings,
  onImageProviderSettingsChange,
}) {
  return (
    <PageLayout eyebrow="AssetAI" title="Settings" subtitle="Customize the workspace theme and keep your local profile details aligned with the current session.">
      <div className="content-grid two-column">
        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Theme</p>
              <h2>Workspace appearance</h2>
            </div>
          </div>

          <div className="theme-grid">
            {THEME_OPTIONS.map((option) => (
              <button key={option.value} type="button" className={theme === option.value ? "theme-option active" : "theme-option"} onClick={() => setTheme(option.value)}>
                <span className="theme-swatch" data-theme={option.value} aria-hidden="true" />
                <strong>{option.label}</strong>
              </button>
            ))}
          </div>

          {theme === "pastel" && (
            <div className="palette-grid">
              {PASTEL_PALETTES.map((option) => (
                <button key={option.value} type="button" className={palette === option.value ? "palette-button active" : "palette-button"} onClick={() => setPalette(option.value)}>
                  <span className={`swatches sw-${option.value}`} aria-hidden="true" />
                  {option.label}
                </button>
              ))}
            </div>
          )}
        </section>

        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Character images</p>
              <h2>Image generation provider</h2>
            </div>
          </div>

          <label className="field-label" htmlFor="image-provider">
            <span>Provider</span>
            <select
              id="image-provider"
              value={imageProviderSettings.provider}
              onChange={(event) => onImageProviderSettingsChange({
                ...imageProviderSettings,
                provider: event.target.value,
              })}
            >
              {IMAGE_PROVIDER_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
          </label>

          <label className="settings-toggle">
            <input
              type="checkbox"
              checked={imageProviderSettings.allowCloudflareFallback}
              disabled={imageProviderSettings.provider !== "pollinations"}
              onChange={(event) => onImageProviderSettingsChange({
                ...imageProviderSettings,
                allowCloudflareFallback: event.target.checked,
              })}
            />
            <span>
              <strong>Allow Cloudflare fallback</strong>
              <small>Only used after an ordinary Pollinations failure. Authentication, billing, and quota errors never fall back. The backend must also be explicitly configured for Cloudflare.</small>
            </span>
          </label>

          <div className="settings-notice">
            Cloudflare Workers AI generates character images only; it does not generate animation video. Enabling Cloudflare does not verify the account plan, quota, or charges. Billing may apply depending on account plan and usage. Never enter provider credentials here; configure them on the backend.
          </div>
        </section>

        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Account</p>
              <h2>Profile</h2>
            </div>
          </div>

          <div className="profile-card">
            <div className="profile-avatar large">{getInitials(user?.display_name || user?.email || "AI")}</div>
            <div>
              <strong>{user?.display_name || "Studio user"}</strong>
              <p>{user?.email || "Not signed in"}</p>
            </div>
          </div>

          <div className="settings-meta">
            <div><span>Authentication</span><strong>{token ? "Active session" : "Logged out"}</strong></div>
            <div><span>Theme</span><strong>{theme}</strong></div>
            <div><span>Palette</span><strong>{palette}</strong></div>
          </div>
        </section>
      </div>
    </PageLayout>
  );
}

function HomePage({ token }) {
  const [history, setHistory] = useState([]);
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [overviewError, setOverviewError] = useState("");

  useEffect(() => {
    let active = true;

    async function loadOverview() {
      setLoading(true);
      setOverviewError("");
      setHistory([]);
      setAssets([]);
      if (!token) {
        setLoading(false);
        return;
      }
      try {
        const headers = token ? { Authorization: `Bearer ${token}` } : {};
        const [historyData, assetData] = await Promise.all([
          fetchJson(`${API_BASE}/history`, { headers }),
          fetchJson(`${API_BASE}/assets`, { headers }),
        ]);
        if (active) {
          setHistory(Array.isArray(historyData) ? historyData.slice(0, 3) : []);
          setAssets(Array.isArray(assetData) ? assetData.slice(0, 4) : []);
        }
      } catch (error) {
        if (active) setOverviewError(error.message || "Unable to load workspace activity.");
      } finally {
        if (active) setLoading(false);
      }
    }

    loadOverview();
    return () => { active = false; };
  }, [token]);

  return (
    <PageLayout eyebrow="AssetAI" title="Home" subtitle="A unified workspace for character creation, animation generation, asset tracking, and project history." actions={<div className="action-row"><NavLink className="button button-primary" to="/studio/character">Launch studio</NavLink></div>}>
      {overviewError && <div className="alert error-alert" role="alert"><strong>Workspace overview unavailable</strong><span>{overviewError}</span></div>}
      <div className="stat-grid">
        <StatCard label="Total assets" value={assets.length || 0} tone="primary" />
        <StatCard label="Recent generations" value={history.length || 0} tone="secondary" />
        <StatCard label="Workspace" value={token ? "Authenticated" : "Guest"} tone="accent" />
      </div>

      <div className="content-grid two-column">
        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Latest activity</p>
              <h2>Recent history</h2>
            </div>
          </div>

          {loading ? (
            <div className="empty-state"><p>Loading project activity...</p></div>
          ) : overviewError ? null : history.length === 0 ? (
            <div className="empty-state"><p>No recent activity yet.</p></div>
          ) : (
            <div className="history-list compact">
              {history.map((record) => (
                <article key={record.id} className="history-item compact">
                  <div className="history-main">
                    <span className="tag">{record.action || "activity"}</span>
                    <strong>{record.prompt || "Generated asset"}</strong>
                    <small>{record.created_at ? new Date(record.created_at).toLocaleString() : "Recently"}</small>
                  </div>
                  <span className={`status-pill ${getGenerationStatusClass(record.status)}`}>{record.status || "completed"}</span>
                </article>
              ))}
            </div>
          )}
        </section>

        <section className="surface">
          <div className="panel-header">
            <div>
              <p className="eyebrow">Library</p>
              <h2>Recent assets</h2>
            </div>
          </div>

          {loading ? (
            <div className="empty-state"><p>Loading assets...</p></div>
          ) : !overviewError && assets.length === 0 ? (
            <div className="empty-state"><p>No assets generated yet.</p></div>
          ) : !overviewError ? (
            <div className="mini-asset-grid">
              {assets.map((asset) => (
                <div key={`${asset.asset_type}-${asset.name}-${asset.file_url}`} className="mini-asset">
                  <AssetImage url={asset.file_url} token={token} alt={asset.name || asset.asset_type} />
                  <div>
                    <strong>{asset.name || asset.asset_type}</strong>
                    <small>{asset.asset_type}</small>
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </section>
      </div>
    </PageLayout>
  );
}

function App() {
  const [token, setToken] = useState(() => localStorage.getItem("assetai-token") || "");
  const [user, setUser] = useState(() => {
    const item = localStorage.getItem("assetai-user");
    return item ? JSON.parse(item) : null;
  });
  const [selectedProcessedCharacter, setSelectedProcessedCharacter] = useState(() => getStoredProcessedCharacter(user?.id));
  const [theme, setTheme] = useState(() => localStorage.getItem("assetai-theme") || "dark");
  const [palette, setPalette] = useState(() => localStorage.getItem("assetai-palette") || "pink");
  const [imageProviderPreference, setImageProviderPreference] = useState(() => ({
    userId: user?.id ?? null,
    settings: loadImageProviderSettings(user?.id),
  }));
  const imageProviderSettings =
    imageProviderPreference.userId === (user?.id ?? null)
      ? imageProviderPreference.settings
      : loadImageProviderSettings(user?.id);
  const [logoutError, setLogoutError] = useState("");

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    document.documentElement.dataset.palette = palette;
    localStorage.setItem("assetai-theme", theme);
    localStorage.setItem("assetai-palette", palette);
  }, [theme, palette]);

  useEffect(() => {
    if (!token) {
      localStorage.removeItem("assetai-token");
      localStorage.removeItem("assetai-user");
      return;
    }

    localStorage.setItem("assetai-token", token);
    fetchJson(`${API_BASE}/auth/me`, { headers: { Authorization: `Bearer ${token}` } })
      .then((data) => {
        setUser(data);
        setSelectedProcessedCharacter(getStoredProcessedCharacter(data.id));
        localStorage.setItem("assetai-user", JSON.stringify(data));
      })
      .catch(() => {
        setToken("");
        setUser(null);
        setSelectedProcessedCharacter("");
        localStorage.removeItem("assetai-token");
        localStorage.removeItem("assetai-user");
      });
  }, [token]);

  const handleAuthenticate = (nextToken, nextUser) => {
    setToken(nextToken);
    setUser(nextUser);
    setSelectedProcessedCharacter(getStoredProcessedCharacter(nextUser.id));
    localStorage.setItem("assetai-token", nextToken);
    localStorage.setItem("assetai-user", JSON.stringify(nextUser));
  };

  const handleProcessedCharacterChange = useCallback((url) => {
    setSelectedProcessedCharacter(url);
    if (!user?.id) return;
    const key = `assetai-processed-character-${user.id}`;
    if (url) localStorage.setItem(key, url);
    else localStorage.removeItem(key);
  }, [user]);

  const handleImageProviderSettingsChange = (nextSettings) => {
    const savedSettings = saveImageProviderSettings(user?.id, nextSettings);
    setImageProviderPreference({
      userId: user?.id ?? null,
      settings: savedSettings,
    });
  };

  const handleLogout = async () => {
    setLogoutError("");
    try {
      await fetchJson(`${API_BASE}/auth/logout`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (error) {
      setLogoutError(error.message || "The server could not invalidate this session.");
    } finally {
      setToken("");
      setUser(null);
      setSelectedProcessedCharacter("");
      localStorage.removeItem("assetai-token");
      localStorage.removeItem("assetai-user");
    }
  };

  return (
    <BrowserRouter>
      <div className="assetai-app">
        <AppHeader token={token} user={user} onLogout={handleLogout} />
        {logoutError && <div className="alert error-alert" role="alert">{logoutError}</div>}
        <main className="workspace-shell">
          <Routes>
            <Route path="/auth/:mode" element={<AuthPage onAuthenticate={handleAuthenticate} />} />
            <Route path="/" element={<HomePage token={token} />} />
            <Route path="/studio/character" element={<CharacterStudioPage token={token} onProcessedCharacterChange={handleProcessedCharacterChange} />} />
            <Route path="/studio/animation" element={<AnimationStudioPage token={token} userId={user?.id} selectedProcessedCharacter={selectedProcessedCharacter} onProcessedCharacterChange={handleProcessedCharacterChange} imageProviderSettings={imageProviderSettings} />} />
            <Route path="/assets" element={<AssetsPage token={token} />} />
            <Route path="/history" element={<HistoryPage token={token} />} />
            <Route path="/settings" element={<SettingsPage token={token} user={user} theme={theme} setTheme={setTheme} palette={palette} setPalette={setPalette} imageProviderSettings={imageProviderSettings} onImageProviderSettingsChange={handleImageProviderSettingsChange} />} />
            <Route path="*" element={<HomePage token={token} />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
