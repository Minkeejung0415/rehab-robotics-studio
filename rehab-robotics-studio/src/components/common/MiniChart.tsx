/** Lightweight canvas chart for high-frequency display data; keep acquisition logic outside this component. */
import { useEffect, useRef } from 'react';

export interface MiniChartProps {
  readonly data: readonly number[];
  readonly color: string;
  readonly height?: number;
  readonly width?: number;
  readonly fill?: boolean;
  readonly ariaLabel?: string;
}

/** Small canvas trace used by dashboard cards and high-density signal views. */
export function MiniChart({
  data,
  color,
  height = 64,
  width = 260,
  fill = true,
  ariaLabel,
}: MiniChartProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const context = canvas.getContext('2d');
    if (!context) return;

    const canvasWidth = canvas.width;
    const canvasHeight = canvas.height;
    context.clearRect(0, 0, canvasWidth, canvasHeight);
    if (data.length < 2) return;

    let minimum = Math.min(...data);
    let maximum = Math.max(...data);
    if (maximum - minimum < 1e-6) maximum = minimum + 1;
    const padding = (maximum - minimum) * 0.18;
    minimum -= padding;
    maximum += padding;

    context.beginPath();
    data.forEach((value, index) => {
      const x = (index / Math.max(1, data.length - 1)) * canvasWidth;
      const y = canvasHeight - ((value - minimum) / (maximum - minimum)) * canvasHeight;
      if (index === 0) context.moveTo(x, y);
      else context.lineTo(x, y);
    });
    context.strokeStyle = color;
    context.lineWidth = 1.4;
    context.lineJoin = 'round';
    context.stroke();

    if (fill) {
      context.lineTo(canvasWidth, canvasHeight);
      context.lineTo(0, canvasHeight);
      context.closePath();
      context.fillStyle = `${color}22`;
      context.fill();
    }
  }, [data, color, fill]);

  return (
    <canvas
      ref={canvasRef}
      width={width}
      height={height}
      aria-label={ariaLabel}
      role={ariaLabel ? 'img' : undefined}
      style={{ width: '100%', height, display: 'block' }}
    />
  );
}
