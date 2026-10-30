import { useRef, useState } from "react";
import { API_BASE, fetchJson } from "./api";
import {
  createAssetAnalysisRequest,
  getAssetAnalysisError,
  supportsFrameComparison,
  supportsQualityAnalysis,
} from "./assetAnalysis";

function ReportWarnings({ warnings }) {
  if (!Array.isArray(warnings) || warnings.length === 0) return null;
  return (
    <div className="analysis-warnings">
      <h4>Warnings</h4>
      <ul>{warnings.map((warning, index) => <li key={`${warning}-${index}`}>{warning}</li>)}</ul>
    </div>
  );
}

function QualityReport({ response }) {
  const report = response.quality_report;
  if (!report || typeof report !== "object") {
    return <p role="status">The backend returned no quality report.</p>;
  }
  const frameAnalysis = report.frame_analysis;

  return (
    <div className="analysis-report">
      <dl className="analysis-metrics">
        <div><dt>Dimensions</dt><dd>{report.image_width} × {report.image_height} px</dd></div>
        <div><dt>Image format</dt><dd>{report.image_format || "Not reported"}</dd></div>
        <div><dt>Transparency</dt><dd>{report.has_transparency ? "Present" : "Not detected"}</dd></div>
        <div><dt>Fully transparent</dt><dd>{report.fully_transparent_pixels} pixels ({report.transparent_pixel_percentage}%)</dd></div>
        <div><dt>Partially transparent</dt><dd>{report.partially_transparent_pixels} pixels</dd></div>
        <div><dt>Opaque</dt><dd>{report.opaque_pixels} pixels</dd></div>
      </dl>
      {frameAnalysis && (
        <section className="analysis-subreport">
          <h4>Frame grid</h4>
          <p>
            {frameAnalysis.columns} columns × {frameAnalysis.rows} rows;{" "}
            {frameAnalysis.frame_count} frames at {frameAnalysis.frame_width} × {frameAnalysis.frame_height} px.
            {" "}{frameAnalysis.empty_frame_count} fully transparent frame(s).
          </p>
          {Array.isArray(frameAnalysis.frames) && frameAnalysis.frames.length > 0 && (
            <ul className="analysis-frame-list">
              {frameAnalysis.frames.map((frame) => (
                <li key={frame.index}>
                  Frame {frame.index + 1} (row {frame.row + 1}, column {frame.column + 1}):{" "}
                  {frame.is_empty ? "empty" : `content bounds ${Array.isArray(frame.content_bounds) ? frame.content_bounds.join(", ") : "available"}`}
                </li>
              ))}
            </ul>
          )}
        </section>
      )}
      <ReportWarnings warnings={report.warnings} />
    </div>
  );
}

function FrameComparisonReport({ response }) {
  const report = response.frame_comparison;
  if (!report || typeof report !== "object") {
    return <p role="status">The backend returned no frame comparison.</p>;
  }

  return (
    <div className="analysis-report">
      <dl className="analysis-metrics">
        <div><dt>Frames compared</dt><dd>{report.frame_count}</dd></div>
        <div><dt>Consistent dimensions</dt><dd>{report.consistent_dimensions ? "Yes" : "No"}</dd></div>
      </dl>
      {Array.isArray(report.dimensions) && report.dimensions.length > 0 && (
        <section className="analysis-subreport">
          <h4>Frame dimensions</h4>
          <ul className="analysis-frame-list">
            {report.dimensions.map((dimensions, index) => (
              <li key={index}>Frame {index + 1}: {dimensions.join(" × ")} px</li>
            ))}
          </ul>
        </section>
      )}
      {Array.isArray(report.frames) && report.frames.length > 0 && (
        <section className="analysis-subreport">
          <h4>Visual comparison</h4>
          <ul className="analysis-frame-list">
            {report.frames.map((frame) => (
              <li key={frame.index}>
                Frame {frame.index + 1}: {frame.identical_to_first_frame ? "identical to first frame" : "different from first frame"}
                {" "}(mean difference {frame.mean_difference_from_first_frame})
              </li>
            ))}
          </ul>
        </section>
      )}
      <ReportWarnings warnings={report.warnings} />
    </div>
  );
}

function AssetAnalysis({ assetId, assetType, token, showQuality = true, showComparison = true }) {
  const [activeAnalysis, setActiveAnalysis] = useState("");
  const [report, setReport] = useState(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const requestId = useRef(0);

  const closeReport = () => {
    requestId.current += 1;
    setActiveAnalysis("");
    setReport(null);
    setError("");
    setLoading(false);
  };

  const runAnalysis = async (analysisType) => {
    const currentRequestId = ++requestId.current;
    setActiveAnalysis(analysisType);
    setReport(null);
    setError("");
    setLoading(true);
    try {
      const request = createAssetAnalysisRequest(assetId, analysisType, token, API_BASE);
      const result = await fetchJson(request.url, request.options);
      if (currentRequestId === requestId.current) setReport(result);
    } catch (requestError) {
      if (currentRequestId === requestId.current) {
        setError(getAssetAnalysisError(requestError, analysisType));
      }
    } finally {
      if (currentRequestId === requestId.current) setLoading(false);
    }
  };

  const canAnalyzeQuality = showQuality && supportsQualityAnalysis(assetType);
  const canCompareFrames = showComparison && supportsFrameComparison(assetType);
  if (!canAnalyzeQuality && !canCompareFrames) return null;

  return (
    <div className="asset-analysis">
      <div className="button-row">
        {canAnalyzeQuality && (
          <button className="button button-secondary action-button" type="button" onClick={() => runAnalysis("quality")} disabled={loading}>
            Analyze Quality
          </button>
        )}
        {canCompareFrames && (
          <button className="button button-secondary action-button" type="button" onClick={() => runAnalysis("frame-comparison")} disabled={loading}>
            Compare Frames
          </button>
        )}
      </div>
      {activeAnalysis && (
        <section className="analysis-panel" aria-live="polite" aria-busy={loading}>
          <div className="analysis-panel-heading">
            <h3>{activeAnalysis === "quality" ? "Sprite Quality Report" : "Frame Comparison"}</h3>
            <button className="button button-secondary compact" type="button" onClick={closeReport} aria-label="Close analysis results">
              Close
            </button>
          </div>
          {loading && <div className="loading-status" role="status">Analyzing asset...</div>}
          {error && <div className="alert error-alert" role="alert">{error}</div>}
          {report && (
            activeAnalysis === "quality"
              ? <QualityReport response={report} />
              : <FrameComparisonReport response={report} />
          )}
        </section>
      )}
    </div>
  );
}

export default AssetAnalysis;
