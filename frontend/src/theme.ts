export type Theme = 'light' | 'dark';
export const THEME_KEY = 'market-lab-theme';

export function readTheme(storage: Pick<Storage, 'getItem'> = localStorage): Theme {
  try { return storage.getItem(THEME_KEY) === 'dark' ? 'dark' : 'light'; }
  catch { return 'light'; }
}
