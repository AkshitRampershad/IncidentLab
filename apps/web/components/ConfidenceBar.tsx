// Color thresholds here are a display convention (0.90 / 0.70), matching
// core.config.Settings' defaults for confidence_strong_threshold /
// confidence_review_threshold — but the API doesn't expose those settings,
// so this is a visual approximation, not a live binding to backend config.
function tierColor(confidence: number): string {
  if (confidence >= 0.9) return "var(--success)";
  if (confidence >= 0.7) return "var(--warning)";
  return "var(--critical)";
}

export function ConfidenceBar({
  confidence,
  label,
}: {
  confidence: number;
  label?: string;
}) {
  const pct = Math.round(confidence * 100);
  return (
    <div className="stack" style={{ gap: 4 }}>
      {label && (
        <div className="row" style={{ justifyContent: "space-between" }}>
          <span className="small">{label}</span>
          <span className="small mono dim">{pct}%</span>
        </div>
      )}
      <div className="confidence-bar-track">
        <div
          className="confidence-bar-fill"
          style={{ width: `${pct}%`, background: tierColor(confidence) }}
        />
      </div>
    </div>
  );
}
