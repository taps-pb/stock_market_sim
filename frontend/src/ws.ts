import type { Snapshot } from "./store";

// Connect to the sim stream; auto-reconnect on drop.
export function connectWs(onSnap: (s: Snapshot) => void): void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${proto}://${location.host}/ws`);
  ws.onmessage = (e) => onSnap(JSON.parse(e.data));
  ws.onclose = () => setTimeout(() => connectWs(onSnap), 1000);
  ws.onerror = () => ws.close();
}
