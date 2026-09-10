import { useEffect, useMemo, useState } from "react";
import GeneratedAnimation from "./GeneratedAnimation";
import "./App.css";
import { ACTION_GROUPS, CATEGORY_LABELS, LEGACY_ACTION_LABELS, QUICK_ACTIONS, findAction } from "./actionCatalog";

const API_BASE = "http://127.0.0.1:8000";
const FRAME_COUNTS = [4, 8, 12, 16];

function SectionEyebrow({ children }) {
  return <p className="section-eyebrow">{children}</p>;
}

function Navbar() {
  return (
    <header className="topbar">
      <a className="brand" href="#top" aria-label="SpriteForge home">
        <span className="brand-mark" aria-hidden="true"><span /></span>
        <span>SpriteForge</span>
      </a>
      <nav className="nav-links" aria-label="Main navigation">
        <a className="active" href="#generator">Generator</a>
        <a href="#about">About</a>
      </nav>
      <span className="status-pill"><span className="status-dot" /> Studio online</span>
    </header>
  );
}

function ImageTile({ label, src, muted = false }) {
  return (
    <div className={`image-tile${muted ? " muted" : ""}`}>
      <div className="image-tile-header"><span>{label}</span>{src && <span className="tile-check">Ready</span>}</div>
      <div className="image-tile-canvas checkerboard">
        {src ? <img src={src} alt={`${label} character preview`} /> : <span className="tile-placeholder">Waiting for image</span>}
      </div>
    </div>
  );
}

function UploadPanel({ image, previewUrl, originalImage, removedImage, processedImage, isUploading, uploadError, onImageChange, onUpload }) {
  const [isDragging, setIsDragging] = useState(false);

  const handleDrop = (event) => {
    event.preventDefault();
    setIsDragging(false);
    const [file] = event.dataTransfer.files;
    if (file?.type.startsWith("image/")) onImageChange(file);
  };

  return (
    <section className="panel input-panel" aria-labelledby="character-input-title">
      <div className="panel-heading"><div><SectionEyebrow>01 / Character input</SectionEyebrow><h2 id="character-input-title">Bring a character to life</h2></div><span className={`ready-badge${processedImage ? " ready" : ""}`}><span className="badge-dot" /> {processedImage ? "Ready to animate" : "Awaiting image"}</span></div>
      <label className={`dropzone${isDragging ? " is-dragging" : ""}`} onDragOver={(event) => { event.preventDefault(); setIsDragging(true); }} onDragLeave={() => setIsDragging(false)} onDrop={handleDrop}>
        <input type="file" accept="image/*" onChange={(event) => onImageChange(event.target.files[0])} />
        <span className="upload-icon" aria-hidden="true">+</span><strong>{image ? image.name : "Drop a character image here"}</strong><span>PNG, JPG or WEBP · transparent backgrounds welcome</span><span className="browse-link">Browse files</span>
      </label>
      {previewUrl && !originalImage && <div className="selected-preview"><span className="preview-label">Selected preview</span><img src={previewUrl} alt="Selected character preview" /></div>}
      <button className="button button-secondary full-width" type="button" onClick={onUpload} disabled={!image || isUploading}><span aria-hidden="true">{isUploading ? "..." : "↑"}</span>{isUploading ? "Processing character..." : "Upload and process"}</button>
      {uploadError && <div className="alert error-alert" role="alert"><strong>Upload failed</strong><span>{uploadError}</span></div>}
      {(originalImage || removedImage || processedImage) && <div className="image-grid" aria-label="Character processing results"><ImageTile label="Original" src={originalImage} /><ImageTile label="Background removed" src={removedImage} /><ImageTile label="Processed" src={processedImage} /></div>}
    </section>
  );
}

function CharacterGeneration({ prompt, setPrompt, generatedImage, isGenerating, generationError, onGenerate, onGenerateSprite, onGeneratePromptSprite, isGeneratingSprite, isGeneratingPromptSprite, hasCharacter, selectedActionLabel }) {
  return (
    <section className="panel prompt-panel" aria-labelledby="prompt-title">
      <div className="panel-heading compact-heading"><div><SectionEyebrow>Optional</SectionEyebrow><h2 id="prompt-title">Create a new character</h2></div><span className="sparkle-mark" aria-hidden="true">✦</span></div>
      <label className="field-label" htmlFor="character-prompt">Describe your character</label><textarea id="character-prompt" value={prompt} onChange={(event) => setPrompt(event.target.value)} placeholder="A pixel art dog running near a tree" />
      <button className="button button-ghost" type="button" onClick={onGenerate} disabled={isGenerating}>{isGenerating ? "Creating character..." : "Generate character"}</button>
      <button className="button button-primary full-width prompt-sprite-button" type="button" onClick={onGenerateSprite} disabled={isGeneratingSprite || isGenerating || !hasCharacter}><span aria-hidden="true">{isGeneratingSprite ? "◌" : "✦"}</span>{isGeneratingSprite ? "Generating sprite..." : `Generate ${selectedActionLabel} sprite`}</button>
      <button className="button button-ghost full-width prompt-one-click-button" type="button" onClick={onGeneratePromptSprite} disabled={isGeneratingPromptSprite || isGenerating}><span aria-hidden="true">{isGeneratingPromptSprite ? "◌" : "↗"}</span>{isGeneratingPromptSprite ? "Generating from prompt..." : "One-click prompt → sprite"}</button>
      {isGeneratingSprite && <div className="loading-state" aria-live="polite"><span className="spinner" /><div><strong>Building your sprite...</strong><span>Using the generated character, then animating it.</span></div></div>}
      {generationError && <div className="alert error-alert" role="alert"><strong>Character generation failed</strong><span>{generationError}</span></div>}
      {generatedImage && <div className="generated-character"><span className="preview-label">Generated character</span><img src={generatedImage} alt="Generated character" /></div>}
    </section>
  );
}

function GenerationControls({ category, setCategory, action, setAction, frameCount, setFrameCount, isGenerating, hasCharacter, characterSource, onGenerate }) {
  const selectedAction = findAction(action);
  const categoryActions = ACTION_GROUPS[category];

  const changeCategory = (event) => {
    const nextCategory = event.target.value;
    setCategory(nextCategory);
    setAction(ACTION_GROUPS[nextCategory][0][1]);
  };

  return (
    <section className="panel controls-panel" aria-labelledby="generation-title">
      <div className="panel-heading"><div><SectionEyebrow>02 / Animation recipe</SectionEyebrow><h2 id="generation-title">Generate animation</h2></div><span className="shortcut-hint">AI powered</span></div>
      <p className="panel-copy">Choose a movement and let SpriteForge build a clean, game-ready cycle from your processed character.</p>
      <div className="control-stack action-controls"><label className="field-label" htmlFor="action-category">Action category<select id="action-category" value={category} onChange={changeCategory} disabled={isGenerating}>{Object.entries(CATEGORY_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="field-label" htmlFor="action-select">Specific action<select id="action-select" value={action} onChange={(event) => setAction(event.target.value)} disabled={isGenerating}>{categoryActions.map(([label, value]) => <option key={value} value={value}>{label}</option>)}</select></label></div>
      {selectedAction && <div className="selected-action"><span className="selected-action-category">{CATEGORY_LABELS[selectedAction.category]}</span><strong>{selectedAction.label}</strong><span>{selectedAction.description}</span></div>}
      <label className="field-label frame-field" htmlFor="frame-count">Frame count<select id="frame-count" value={frameCount} onChange={(event) => setFrameCount(Number(event.target.value))} disabled={isGenerating}>{FRAME_COUNTS.map((count) => <option key={count} value={count}>{count} frames</option>)}</select></label>
      <div className="quick-actions" aria-label="Common actions"><span>Quick select</span>{QUICK_ACTIONS.map((quickAction) => <button key={quickAction} className={action === quickAction ? "selected" : ""} type="button" onClick={() => { setAction(quickAction); setCategory(quickAction === "attack" ? "combat" : "movement"); }} disabled={isGenerating}>{LEGACY_ACTION_LABELS[quickAction]}</button>)}</div>
      <button className="button button-primary generate-button" type="button" onClick={onGenerate} disabled={isGenerating || !hasCharacter}><span aria-hidden="true">{isGenerating ? "◌" : "✦"}</span>{isGenerating ? "Generating animation..." : "Generate animation"}</button>
      {hasCharacter ? <p className="helper-text active-character-note">Using {characterSource === "generated" ? "generated character" : "uploaded character"}</p> : <p className="helper-text">Upload and process a character, or generate one from a prompt.</p>}
      {isGenerating && <div className="loading-state" aria-live="polite"><span className="spinner" /><div><strong>Generating animation...</strong><span>This may take a little while.</span></div></div>}
    </section>
  );
}

function App() {
  const [image, setImage] = useState(null);
  const [originalImage, setOriginalImage] = useState("");
  const [removedImage, setRemovedImage] = useState("");
  const [processedImage, setProcessedImage] = useState("");
  const [prompt, setPrompt] = useState("A pixel art dog running near a tree");
  const [generatedImage, setGeneratedImage] = useState("");
  const [activeCharacterSource, setActiveCharacterSource] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [action, setAction] = useState("walk");
  const [actionCategory, setActionCategory] = useState("movement");
  const [frameCount, setFrameCount] = useState(8);
  const [isGeneratingSprite, setIsGeneratingSprite] = useState(false);
  const [isGeneratingPromptSprite, setIsGeneratingPromptSprite] = useState(false);
  const [spriteError, setSpriteError] = useState("");
  const [uploadError, setUploadError] = useState("");
  const [isUploading, setIsUploading] = useState(false);
  const [animationResult, setAnimationResult] = useState(null);

  const previewUrl = useMemo(() => (image ? URL.createObjectURL(image) : ""), [image]);

  useEffect(() => {
    return () => {
      if (previewUrl) URL.revokeObjectURL(previewUrl);
    };
  }, [previewUrl]);

  const selectImage = (file) => {
    if (!file) return;
    setImage(file);
    setUploadError("");
  };

  const uploadImage = async () => {
    if (!image) {
      setUploadError("Please select an image first.");
      return;
    }

    setIsUploading(true);
    setUploadError("");
    const formData = new FormData();
    formData.append("file", image);

    try {
      const response = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Upload failed.");
      setOriginalImage(data.original);
      setRemovedImage(data.removed);
      setProcessedImage(data.processed);
      setActiveCharacterSource("uploaded");
    } catch (error) {
      setUploadError(error.message || "Something went wrong while processing the image.");
    } finally {
      setIsUploading(false);
    }
  };

  const generateCharacter = async () => {
    if (!prompt.trim()) {
      setGenerationError("Please enter a prompt before generating.");
      setGeneratedImage("");
      return;
    }

    setIsGenerating(true);
    setGenerationError("");
    setGeneratedImage("");

    try {
      const response = await fetch(`${API_BASE}/generate`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({ prompt }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Generation failed.");
      }

      setGeneratedImage(data.image);
      setOriginalImage("");
      setRemovedImage("");
      setProcessedImage("");
      setActiveCharacterSource("");
      const imageResponse = await fetch(data.image);
      if (!imageResponse.ok) throw new Error("Generated character could not be prepared for animation.");
      const imageBlob = await imageResponse.blob();
      const generatedFilename = decodeURIComponent(new URL(data.image).pathname.split("/").pop() || "generated-character.png");
      const generatedFile = new File([imageBlob], generatedFilename, { type: imageBlob.type || "image/png" });
      const formData = new FormData();
      formData.append("file", generatedFile);
      const processResponse = await fetch(`${API_BASE}/upload`, { method: "POST", body: formData });
      const processData = await processResponse.json();
      if (!processResponse.ok) throw new Error(processData.detail || "Generated character preprocessing failed.");
      setRemovedImage(processData.removed);
      setProcessedImage(processData.processed);
      setActiveCharacterSource("generated");
    } catch (error) {
      setGenerationError(error.message || "Something went wrong while generating the image.");
    } finally {
      setIsGenerating(false);
    }
  };

  const generateSprite = async () => {
    if (!processedImage) {
      setSpriteError("Upload and process a character image first.");
      return;
    }

    setIsGeneratingSprite(true);
    setSpriteError("");
    setAnimationResult(null);

    try {
      const response = await fetch(`${API_BASE}/generate-sprite`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          character_path: processedImage,
          action,
          frame_count: Number(frameCount),
        }),
      });

      const data = await response.json();

      if (!response.ok) {
        throw new Error(data.detail || "Sprite generation failed.");
      }

      setAnimationResult(data);
    } catch (error) {
      setSpriteError(error.message || "Something went wrong while generating the animation.");
    } finally {
      setIsGeneratingSprite(false);
    }
  };

  const generateSpriteFromPrompt = async () => {
    if (!prompt.trim()) {
      setGenerationError("Please enter a prompt before generating.");
      return;
    }

    setIsGeneratingPromptSprite(true);
    setGenerationError("");
    setSpriteError("");
    setAnimationResult(null);

    try {
      const response = await fetch(`${API_BASE}/generate-sprite-from-prompt`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt, action, frame_count: Number(frameCount) }),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Prompt-to-sprite generation failed.");
      setGeneratedImage(data.generated_character_url);
      setProcessedImage(data.processed_character_url);
      setActiveCharacterSource("generated");
      setAnimationResult(data);
    } catch (error) {
      setGenerationError(error.message || "Something went wrong while generating the sprite.");
    } finally {
      setIsGeneratingPromptSprite(false);
    }
  };

  return (
    <div className="app-shell" id="top">
      <Navbar />
      <main className="page-content">
        <section className="hero" id="about"><div className="hero-copy"><SectionEyebrow>AI GAME ASSET STUDIO</SectionEyebrow><h1>AI Game Asset <em>Studio</em></h1><p>Turn character images into animation-ready game assets.</p></div><div className="hero-orbit" aria-hidden="true"><span /><span /><span /></div></section>
        <section className="workspace" id="generator"><div className="workspace-column"><UploadPanel image={image} previewUrl={previewUrl} originalImage={originalImage} removedImage={removedImage} processedImage={processedImage} isUploading={isUploading} uploadError={uploadError} onImageChange={selectImage} onUpload={uploadImage} /><CharacterGeneration prompt={prompt} setPrompt={setPrompt} generatedImage={generatedImage} isGenerating={isGenerating} generationError={generationError} onGenerate={generateCharacter} onGenerateSprite={generateSprite} onGeneratePromptSprite={generateSpriteFromPrompt} isGeneratingSprite={isGeneratingSprite} isGeneratingPromptSprite={isGeneratingPromptSprite} hasCharacter={Boolean(processedImage)} selectedActionLabel={findAction(action)?.label || action} /></div><div className="workspace-column"><GenerationControls category={actionCategory} setCategory={setActionCategory} action={action} setAction={setAction} frameCount={frameCount} setFrameCount={setFrameCount} isGenerating={isGeneratingSprite || isGeneratingPromptSprite} hasCharacter={Boolean(processedImage)} characterSource={activeCharacterSource} onGenerate={generateSprite} /><div className="tip-card"><span className="tip-icon">i</span><p><strong>Good to know</strong> Transparent, front-facing character art produces the cleanest animation cycles.</p></div></div></section>
        {spriteError && <div className="alert error-alert workspace-alert" role="alert"><strong>Animation generation failed</strong><span>{spriteError}</span><button type="button" onClick={generateSprite} disabled={isGeneratingSprite || !processedImage}>Retry generation</button></div>}
        <GeneratedAnimation result={animationResult} />
      </main>
      <footer className="footer" id="footer"><span>SpriteForge</span><span>Made for game makers</span></footer>
    </div>
  );
}

export default App;