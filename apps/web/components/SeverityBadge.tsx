const SEVERITY_CLASS: Record<string, string> = {
  critical: "badge-critical",
  warning: "badge-warning",
  info: "badge-info",
};

export function SeverityBadge({ severity }: { severity: string }) {
  const cls = SEVERITY_CLASS[severity.toLowerCase()] ?? "badge-dim";
  return <span className={`badge ${cls}`}>{severity}</span>;
}
