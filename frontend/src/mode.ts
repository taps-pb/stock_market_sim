export type Mode = 'basic' | 'pro';
export const MODE_KEY = 'market-lab-mode';

export function readMode(storage: Pick<Storage, 'getItem'> = localStorage): Mode {
  try { return storage.getItem(MODE_KEY) === 'pro' ? 'pro' : 'basic'; }
  catch { return 'basic'; }
}
