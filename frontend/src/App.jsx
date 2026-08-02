import { useState } from "react";

function App() {
  const [image, setImage] = useState(null);
  const [originalImage, setOriginalImage] = useState("");
  const [removedImage, setRemovedImage] = useState("");

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
          className="mt-5 px-6 py-3 bg-cyan-500 rounded-lg"
        >
          Upload Image
        </button>
      </div>

      {removedImage && (
        <div className="grid grid-cols-2 gap-10 mt-12">
          <div>
            <h2 className="text-xl mb-4">Original</h2>
            <img
              src={originalImage}
              className="rounded-lg shadow-lg"
              alt="Original"
            />
          </div>

          <div>
            <h2 className="text-xl mb-4">Background Removed</h2>
            <div className="bg-gray-200 p-4 rounded-lg">
              <img
                src={removedImage}
                className="rounded-lg"
                alt="Background Removed"
              />
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;