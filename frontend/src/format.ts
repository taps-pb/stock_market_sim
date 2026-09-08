export const money = (value: number, digits = 0) => new Intl.NumberFormat('en-US', {
  style: 'currency', currency: 'USD', maximumFractionDigits: digits, minimumFractionDigits: digits,
}).format(value);
export const signedMoney = (value: number) => `${value >= 0 ? '+' : '−'}${money(Math.abs(value), 2)}`;
export const pct = (value: number) => `${value >= 0 ? '+' : ''}${value.toFixed(2)}%`;
export const compact = (value: number) => new Intl.NumberFormat('en-US', { notation: 'compact', maximumFractionDigits: 1 }).format(value);
export const terminal = (status: string) => ['completed', 'failed', 'interrupted'].includes(status);
