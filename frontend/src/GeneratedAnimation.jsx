function MetadataCard({ label, value }) {
  return <div className="metadata-card"><span>{label}</span><strong>{value || "Not returned"}</strong></div>;
}

function GeneratedAnimation({ result }) {
  if (!result) {
    return <section className="result-empty" aria-live="polite"><span className="empty-mark" aria-hidden="true">✦</span><div><h2>Your generated animation will appear here.</h2><p>Upload a processed character, choose an action, and start a new generation.</p></div></section>;
  }

  const actionLabel = result.action ? `${result.action.charAt(0).toUpperCase()}${result.action.slice(1)}` : "Animation";
  const frames = result.frames || [];

  return (
    <section className="result-section" aria-live="polite">
      <div className="result-heading"><div><p className="section-eyebrow">03 / Output studio</p><h2>Generated result</h2><p>Review the motion, inspect individual frames, and export your sprite sheet.</p></div><span className="result-status"><span /> Complete</span></div>
      <div className="result-layout">
        <div className="result-main">
          <section className="result-card video-card"><div className="card-label"><h3>{actionLabel} preview</h3><span>Video</span></div><video className="generated-video" controls preload="metadata" src={result.generated_video}>Your browser does not support video playback.</video></section>
          <section className="frames-section"><div className="subsection-heading"><div><p className="section-eyebrow">Frame by frame</p><h3>Animation frames</h3></div><span>{frames.length || result.frame_count} frames</span></div><div className="frames-grid">{frames.map((frameUrl, index) => <figure className="frame-card" key={frameUrl}><div className="frame-canvas checkerboard"><img src={frameUrl} alt={`Animation frame ${index + 1}`} /></div><figcaption><span>{String(index + 1).padStart(2, "0")}</span><span>Frame {index + 1}</span></figcaption></figure>)}</div></section>
        </div>
        <aside className="result-side">
          <section className="result-card sprite-card"><div className="card-label"><h3>Sprite sheet</h3><span>Export</span></div><div className="sprite-canvas checkerboard"><img src={result.sprite_sheet} alt={`${actionLabel} sprite sheet`} /></div>{result.sprite_sheet && <a className="button button-secondary full-width download-button" href={result.sprite_sheet} download><span aria-hidden="true">↓</span> Download sprite sheet</a>}</section>
          <section className="metadata-section"><div className="subsection-heading"><div><p className="section-eyebrow">Run details</p><h3>Generation info</h3></div></div><div className="metadata-grid"><MetadataCard label="Action" value={actionLabel} /><MetadataCard label="Frame count" value={result.frame_count} /><MetadataCard label="Provider" value={result.provider} /></div>{result.generation_report && <div className="report-card"><span>Generation report</span><p>{result.generation_report}</p></div>}</section>
        </aside>
      </div>
    </section>
  );
}

export default GeneratedAnimation;
