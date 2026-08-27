import { useStore } from "../store";

// The population's mood — the thing that actually drives price.
export default function Sentiment() {
  const snap = useStore((s) => s.snap);
  if (!snap) return null;
  const { fear, greed } = snap.sentiment;
  return (
    <div className="sentiment">
      <span>tick {snap.tick}</span>
      <div className="meter">
        <label>fear</label>
        <div className="bar"><i className="fear" style={{ width: `${fear * 100}%` }} /></div>
      </div>
      <div className="meter">
        <label>greed</label>
        <div className="bar"><i className="greed" style={{ width: `${greed * 100}%` }} /></div>
      </div>
    </div>
  );
}
