import { useState } from "react";

function App() {
  const [image, setImage] = useState(null);
  const [originalImage, setOriginalImage] = useState("");
  const [removedImage, setRemovedImage] = useState("");
  const [processedImage, setProcessedImage] = useState("");
  const [prompt, setPrompt] = useState("A pixel art dog running near a tree");
  const [generatedImage, setGeneratedImage] = useState("");
  const [isGenerating, setIsGenerating] = useState(false);
  const [generationError, setGenerationError] = useState("");

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

  return (
    <div className="min-h-screen bg-slate-900 p-10 text-white">
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
        <div className="grid grid-cols-3 gap-10 mt-12">
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
    </div>
  );
}

export default App;