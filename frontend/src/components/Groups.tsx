import { useStore } from "../store";

const ORDER = ["institutional", "informed", "professional", "retail"];
const LABEL: Record<string, string> = {
  institutional: "Institutions", informed: "Informed",
  professional: "Pros", retail: "Retail crowd",
};

// Who is in the market — few big players vs the retail crowd they trade against.
export default function Groups() {
  const groups = useStore((s) => s.snap?.groups);
  if (!groups) return null;
  const max = Math.max(1, ...ORDER.map((k) => groups[k] ?? 0));
  return (
    <div className="panel">
      <h2>Participants</h2>
      {ORDER.map((k) => (
        <div key={k} className="grp">
          <span className="glabel">{LABEL[k]}</span>
          <div className="gbar"><i className={`gfill ${k}`} style={{ width: `${((groups[k] ?? 0) / max) * 100}%` }} /></div>
          <span className="gn">{groups[k] ?? 0}</span>
        </div>
      ))}
    </div>
  );
}
