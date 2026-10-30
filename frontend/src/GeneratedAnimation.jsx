import { useEffect, useState } from "react";
import AssetAnalysis from "./AssetAnalysis.jsx";
import { API_BASE } from "./api";
import { getAssetIdFromFileUrl } from "./assetAnalysis";

function MetadataCard({ label, value }) {
  return <div className="metadata-card"><span>{label}</span><strong>{value || "Not returned"}</strong></div>;
}

function useAssetUrl(url, token) {
  const key = `${url || ""}:${token || ""}`;
  const [asset, setAsset] = useState({ key: "", url: "", error: "" });

  useEffect(() => {
    if (!url || !token) return undefined;
    let active = true;
    let currentUrl = "";
    const assetUrl = url.startsWith("http") ? url : `${API_BASE}${url}`;
    fetch(assetUrl, { headers: { Authorization: `Bearer ${token}` } })
      .then((response) => {
        if (!response.ok) throw new Error("Asset could not be loaded.");
        return response.blob();
      })
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

function DownloadButton({ href, label, token }) {
  const [downloading, setDownloading] = useState(false);
  const [error, setError] = useState("");
  if (!href) return null;

  const download = async () => {
    setDownloading(true);
    setError("");
    try {
      const assetUrl = href.startsWith("http") ? href : `${API_BASE}${href}`;
      const response = await fetch(assetUrl, { headers: { Authorization: `Bearer ${token}` } });
      if (!response.ok) throw new Error("Asset download failed.");
      const blobUrl = URL.createObjectURL(await response.blob());
      const anchor = document.createElement("a");
      anchor.href = blobUrl;
      anchor.download = response.headers.get("X-Asset-Filename") || label || "asset";
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
    } catch (downloadError) {
      setError(downloadError.message || "Asset download failed.");
    } finally {
      setDownloading(false);
    }
  };

  return <>
    <button className="button button-secondary full-width download-button" type="button" onClick={download} disabled={downloading}>
      <span aria-hidden="true">↓</span>
      {downloading ? "Preparing download..." : label}
    </button>
    {error && <span className="download-error" role="alert">{error}</span>}
  </>;
}

function GeneratedAnimation({ result, token }) {
  const videoUrl = useAssetUrl(result?.generated_video, token);
  const sheetUrl = useAssetUrl(result?.sprite_sheet, token);
  if (!result) {
    return <section className="result-empty" aria-live="polite"><span className="empty-mark" aria-hidden="true">✦</span><div><h2>Your generated animation will appear here.</h2><p>Upload a processed character, choose an action, and start a new generation.</p></div></section>;
  }

  const actionLabel = result.action_label || (result.action ? `${result.action.charAt(0).toUpperCase()}${result.action.slice(1)}` : "Animation");
  const frames = result.frames || [];
  const spriteSheetId = getAssetIdFromFileUrl(result.sprite_sheet);

  return (
    <section className="result-section" aria-live="polite">
      <div className="result-heading"><div><p className="section-eyebrow">03 / Output studio</p><h2>Generated result</h2><p>Review the motion, inspect individual frames, and export your sprite sheet.</p></div><span className="result-status"><span /> Complete</span></div>
      <div className="result-layout">
        <div className="result-main">
          <section className="result-card video-card"><div className="card-label"><h3>{actionLabel} preview</h3><span>Video</span></div>{videoUrl.url ? <video className="generated-video" controls preload="metadata" src={videoUrl.url}>Your browser does not support video playback.</video> : <p role="status">{videoUrl.error || "Loading video..."}</p>}{result.generated_video && <DownloadButton href={result.generated_video} label="Download video" token={token} />}</section>
          <section className="frames-section"><div className="subsection-heading"><div><p className="section-eyebrow">Frame by frame</p><h3>Animation frames</h3></div><span>{frames.length || result.frame_count} frames</span></div><div className="frames-grid">{frames.map((frameUrl, index) => <FramePreview key={frameUrl} frameUrl={frameUrl} index={index} token={token} />)}</div></section>
        </div>
        <aside className="result-side">
          <section className="result-card sprite-card"><div className="card-label"><h3>Sprite sheet</h3><span>Export</span></div><div className="sprite-canvas checkerboard">{sheetUrl.url ? <img src={sheetUrl.url} alt={`${actionLabel} sprite sheet`} /> : <span role="status">{sheetUrl.error || "Loading sprite sheet..."}</span>}</div>{result.sprite_sheet && <DownloadButton href={result.sprite_sheet} label="Download sprite sheet" token={token} />}<AssetAnalysis assetId={spriteSheetId} assetType="sprite_sheet" token={token} /></section>
          <section className="metadata-section"><div className="subsection-heading"><div><p className="section-eyebrow">Run details</p><h3>Generation info</h3></div></div><div className="metadata-grid"><MetadataCard label="Action" value={actionLabel} /><MetadataCard label="Frame count" value={result.frame_count} /><MetadataCard label="Provider" value={result.provider} /></div>{result.generation_report && <div className="report-card"><span>Generation report</span><p>{result.generation_report}</p></div>}</section>
        </aside>
      </div>
    </section>
  );
}

function FramePreview({ frameUrl, index, token }) {
  const imageUrl = useAssetUrl(frameUrl, token);
  return (
    <figure className="frame-card">
      <div className="frame-canvas checkerboard">{imageUrl.url ? <img src={imageUrl.url} alt={`Animation frame ${index + 1}`} /> : <span role="status">{imageUrl.error || "Loading frame..."}</span>}</div>
      <figcaption><span>{String(index + 1).padStart(2, "0")}</span><span>Frame {index + 1}</span></figcaption>
      <DownloadButton href={frameUrl} label="Download frame" token={token} />
    </figure>
  );
}

export default GeneratedAnimation;
