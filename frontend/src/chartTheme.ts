import { useEffect, useState } from 'react';

export function useChartPalette() {
  const read = () => {
    const css = getComputedStyle(document.documentElement);
    const token = (name: string) => css.getPropertyValue(name).trim();
    return {
      bg: token('--panel'), text: token('--ink'), grid: token('--line'),
      up: token('--green'), down: token('--red'), accent: token('--accent'),
    };
  };
  const [palette, setPalette] = useState(read);
  useEffect(() => {
    const observer = new MutationObserver(() => setPalette(read()));
    observer.observe(document.documentElement, { attributes: true, attributeFilter: ['data-theme'] });
    return () => observer.disconnect();
  }, []);
  return palette;
}
