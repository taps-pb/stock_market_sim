import type { Snapshot } from "./store";

// Connect to the sim stream; auto-reconnect on drop.
export function connectWs(onSnap: (s: Snapshot) => void): () => void {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  let stopped = false;
  let timer: ReturnType<typeof setTimeout> | undefined;
  let ws: WebSocket;
  const connect = () => {
    ws = new WebSocket(`${proto}://${location.host}/ws`);
    ws.onmessage = (e) => { if (!stopped) onSnap(JSON.parse(e.data)); };
    ws.onclose = () => { if (!stopped) timer = setTimeout(connect, 1000); };
    ws.onerror = () => ws.close();
  };
  connect();
  return () => { stopped = true; clearTimeout(timer); ws.close(); };
}
