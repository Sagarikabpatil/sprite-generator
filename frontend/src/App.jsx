import { useState } from "react";
import GeneratedAnimation from "./GeneratedAnimation";

function App() {
  const [image, setImage] = useState(null);
  const [originalImage, setOriginalImage] = useState("");
  const [removedImage, setRemovedImage] = useState("");
  const [processedImage, setProcessedImage] = useState("");
  const [prompt, setPrompt] = useState("A pixel art dog running near a tree");
  const [generatedImage, setGeneratedImage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");
  const [action, setAction] = useState("walk");
  const [frameCount, setFrameCount] = useState(8);
  const [isGeneratingSprite, setIsGeneratingSprite] = useState(false);
  const [spriteError, setSpriteError] = useState("");
  const [animationResult, setAnimationResult] = useState(null);

  const uploadImage = async () => {
    if (!image) {
      alert("Please select an image.");
      return;
    }

    const formData = new FormData();
    formData.append("file", image);

    const response = await fetch("http://127.0.0.1:8000/upload", {
      method: "POST",
      body: formData,
    });

    const data = await response.json();

    setOriginalImage(data.original);
    setRemovedImage(data.removed);
    setProcessedImage(data.processed);
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
      const response = await fetch("http://127.0.0.1:8000/generate", {
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
      const response = await fetch("http://127.0.0.1:8000/generate-sprite", {
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

  return (
    <div className="min-h-screen bg-slate-900 p-5 text-white sm:p-10">
      <h1 className="text-5xl font-bold text-cyan-400 text-center mb-10">
        AI Sprite Generator
      </h1>

      <div className="flex flex-col items-center">
        <input
          type="file"
          accept="image/*"
          onChange={(e) => setImage(e.target.files[0])}
        />

        <button
          onClick={uploadImage}
          className="mt-5 px-6 py-3 bg-cyan-500 rounded-lg hover:bg-cyan-600 transition"
        >
          Upload Image
        </button>
      </div>

      <div className="mt-12 max-w-2xl mx-auto bg-slate-800 p-6 rounded-lg shadow-lg">
        <h2 className="text-2xl font-semibold mb-4">AI Character Generation</h2>

        <label className="block text-sm font-medium text-slate-200 mb-2">
          Prompt
        </label>

        <textarea
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder="A pixel art dog running near a tree"
          className="w-full h-32 p-3 rounded-lg text-slate-900"
        />

        <button
          onClick={generateCharacter}
          disabled={isGenerating}
          className="mt-4 px-6 py-3 bg-emerald-500 rounded-lg hover:bg-emerald-600 transition disabled:opacity-60 disabled:cursor-not-allowed"
        >
          {isGenerating ? "Generating..." : "Generate Character"}
        </button>

        {generationError && (
          <div className="mt-4 p-3 rounded-lg bg-red-900/60 text-red-100">
            {generationError}
          </div>
        )}

        {generatedImage && (
          <div className="mt-6">
            <h3 className="text-xl font-semibold mb-3">Generated Character</h3>
            <img
              src={generatedImage}
              alt="Generated character"
              className="w-full max-w-md rounded-lg shadow-lg border border-slate-700"
            />
          </div>
        )}
      </div>

      {removedImage && (
        <div className="mx-auto mt-12 grid max-w-6xl grid-cols-1 gap-10 md:grid-cols-3">
          {/* Original Image */}
          <div>
            <h2 className="text-xl mb-4 text-center">Original</h2>
            <img
              src={originalImage}
              className="rounded-lg shadow-lg"
              alt="Original"
            />
          </div>

          {/* Background Removed */}
          <div>
            <h2 className="text-xl mb-4 text-center">Background Removed</h2>
            <div className="bg-gray-200 p-4 rounded-lg">
              <img
                src={removedImage}
                className="rounded-lg"
                alt="Background Removed"
              />
            </div>
          </div>

          {/* Processed Character */}
          <div>
            <h2 className="text-xl mb-4 text-center">Processed Character</h2>
            <div className="bg-gray-200 p-4 rounded-lg flex justify-center">
              <img
                src={processedImage}
                className="rounded-lg"
                alt="Processed Character"
              />
            </div>
          </div>
        </div>
      )}

      <section className="mx-auto mt-12 max-w-6xl rounded-2xl border border-slate-700 bg-slate-800 p-6 shadow-lg sm:p-8">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-sm font-semibold uppercase tracking-[0.2em] text-cyan-300">
              MiniMax animation
            </p>
            <h2 className="mt-2 text-2xl font-semibold">Generate Sprite</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-300">
              Use the processed character image to create a complete animation preview and sprite sheet.
            </p>
          </div>
          <span className="rounded-full bg-slate-700 px-3 py-1 text-xs text-slate-300">
            {processedImage ? "Character ready" : "Upload a character first"}
          </span>
        </div>

        <div className="mt-6 grid gap-4 sm:grid-cols-[1fr_1fr_auto] sm:items-end">
          <label className="text-sm font-medium text-slate-200">
            Action
            <select
              value={action}
              onChange={(event) => setAction(event.target.value)}
              disabled={isGeneratingSprite}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-3 text-white outline-none focus:border-cyan-400"
            >
              {['idle', 'walk', 'run', 'jump', 'attack'].map((option) => (
                <option key={option} value={option}>
                  {option.charAt(0).toUpperCase() + option.slice(1)}
                </option>
              ))}
            </select>
          </label>

          <label className="text-sm font-medium text-slate-200">
            Frame count
            <select
              value={frameCount}
              onChange={(event) => setFrameCount(Number(event.target.value))}
              disabled={isGeneratingSprite}
              className="mt-2 w-full rounded-lg border border-slate-600 bg-slate-900 px-3 py-3 text-white outline-none focus:border-cyan-400"
            >
              {[4, 8, 12, 16].map((count) => (
                <option key={count} value={count}>
                  {count} frames
                </option>
              ))}
            </select>
          </label>

          <button
            onClick={generateSprite}
            disabled={isGeneratingSprite || !processedImage}
            className="rounded-lg bg-cyan-500 px-6 py-3 font-semibold text-slate-950 transition hover:bg-cyan-400 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isGeneratingSprite ? "Generating animation..." : "Generate Sprite"}
          </button>
        </div>

        {isGeneratingSprite && (
          <div className="mt-5 rounded-lg border border-cyan-400/30 bg-cyan-400/10 p-4 text-cyan-100">
            Generating animation...
          </div>
        )}

        {spriteError && (
          <div className="mt-5 rounded-lg border border-red-400/30 bg-red-900/50 p-4 text-red-100" role="alert">
            {spriteError}
          </div>
        )}

        {animationResult && <GeneratedAnimation result={animationResult} />}
      </section>
    </div>
  );
}

export default App;