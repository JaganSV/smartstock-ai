import { cloneElement, createContext, useContext, type ReactElement } from 'react';
import { ResponsiveContainer } from 'recharts';

/**
 * A fixed chart width for environments that cannot measure layout (jsdom in tests). In the app
 * it is null and charts fill their container through Recharts' ``ResponsiveContainer``.
 */
export const ChartWidthContext = createContext<number | null>(null);

interface Props {
  height: number;
  /** A Recharts chart element; it receives ``width`` and ``height``. */
  children: ReactElement<{ width?: number; height?: number }>;
}

/** Sizes a Recharts chart: responsive in the browser, fixed when a test provides a width. */
export default function ChartFrame({ height, children }: Props) {
  const fixedWidth = useContext(ChartWidthContext);
  if (fixedWidth !== null) return cloneElement(children, { width: fixedWidth, height });
  return (
    <ResponsiveContainer width="100%" height={height}>
      {children}
    </ResponsiveContainer>
  );
}
