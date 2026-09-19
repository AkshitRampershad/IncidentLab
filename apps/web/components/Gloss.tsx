export function Gloss({ term, children }: { term: string; children: React.ReactNode }) {
  return (
    <span className="gloss" tabIndex={0}>
      {term}
      <span className="tip">{children}</span>
    </span>
  );
}
