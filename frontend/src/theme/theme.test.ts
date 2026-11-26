import { describe, expect, it } from 'vitest';

import { aiGenerated, RISK_CLASSES, riskColors, theme, verified } from './theme';

/** WCAG 2.x relative luminance and contrast ratio. */
function luminance(hex: string): number {
  const channels = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const [r, g, b] = channels.map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe('theme contrast (NFR-14, WCAG AA)', () => {
  it.each(RISK_CLASSES)('risk colour %s passes AA for normal text', (risk) => {
    const { background, text } = riskColors[risk];
    expect(contrast(background, text)).toBeGreaterThanOrEqual(4.5);
  });

  it('verified and AI surfaces pass AA and stay visually distinct', () => {
    expect(contrast(verified.background, verified.text)).toBeGreaterThanOrEqual(4.5);
    expect(contrast(aiGenerated.background, aiGenerated.text)).toBeGreaterThanOrEqual(4.5);
    expect(verified.background).not.toBe(aiGenerated.background);
  });

  it('primary and secondary text pass AA on the page and paper backgrounds', () => {
    const { palette } = theme;
    for (const bg of [palette.background.default, palette.background.paper]) {
      expect(contrast(palette.text.primary, bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(palette.text.secondary, bg)).toBeGreaterThanOrEqual(4.5);
      expect(contrast(palette.primary.main, bg)).toBeGreaterThanOrEqual(4.5);
    }
    expect(contrast(palette.primary.main, palette.primary.contrastText)).toBeGreaterThanOrEqual(
      4.5,
    );
  });

  it('exposes the surface and risk tokens on the theme', () => {
    expect(theme.verified).toEqual(verified);
    expect(theme.aiGenerated).toEqual(aiGenerated);
    expect(theme.risk).toEqual(riskColors);
  });
});
