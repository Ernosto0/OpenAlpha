import type { TradingBar } from "./trading-chart-data";

export function TradingChart({ bars }: { bars: TradingBar[] }) {
  const chartBars = bars.slice(-48);
  const width = 880;
  const height = 280;
  const padding = { top: 24, right: 18, bottom: 42, left: 52 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const { min, max } = getChartRange(chartBars);
  const range = max - min || 1;
  const step = innerWidth / Math.max(1, chartBars.length);
  const bodyWidth = Math.max(4, step * 0.55);

  const scaleY = (value: number) =>
    padding.top + ((max - value) / range) * innerHeight;

  const scaleX = (index: number) =>
    padding.left + index * step + step / 2;

  const gridLines = [0.25, 0.5, 0.75].map((ratio) => {
    const y = padding.top + innerHeight * ratio;
    return { y, value: max - range * ratio };
  });

  const startLabel = chartBars[0] ? formatChartLabel(chartBars[0].timestamp) : "";
  const endLabel = chartBars.length ? formatChartLabel(chartBars[chartBars.length - 1].timestamp) : "";

  return (
    <div className="overflow-x-auto">
      <svg
        className="w-full min-w-[640px] rounded-lg border border-border bg-muted/10"
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Trading chart showing recent price history"
      >
        <rect x="0" y="0" width={width} height={height} rx="12" fill="transparent" />

        {gridLines.map((line) => (
          <g key={line.y}>
            <line
              x1={padding.left}
              x2={width - padding.right}
              y1={line.y}
              y2={line.y}
              stroke="hsl(var(--border))"
              strokeDasharray="4 4"
              strokeWidth="1"
            />
            <text
              x={padding.left - 10}
              y={line.y + 4}
              textAnchor="end"
              className="fill-muted-foreground"
              style={{ fontSize: "11px" }}
            >
              {formatMoney(line.value)}
            </text>
          </g>
        ))}

        {chartBars.map((bar, index) => {
          const x = scaleX(index);
          const open = bar.open ?? bar.close;
          const high = bar.high ?? Math.max(open, bar.close);
          const low = bar.low ?? Math.min(open, bar.close);
          const candleTop = scaleY(Math.max(open, bar.close));
          const candleBottom = scaleY(Math.min(open, bar.close));
          const wickTop = scaleY(high);
          const wickBottom = scaleY(low);
          const bullish = bar.close >= open;
          const fill = bullish ? "hsl(142 71% 45%)" : "hsl(0 84% 60%)";

          return (
            <g key={`${bar.timestamp}-${index}`}>
              <line
                x1={x}
                x2={x}
                y1={wickTop}
                y2={wickBottom}
                stroke={fill}
                strokeWidth="1.5"
              />
              <rect
                x={x - bodyWidth / 2}
                y={Math.min(candleTop, candleBottom)}
                width={bodyWidth}
                height={Math.max(2, Math.abs(candleBottom - candleTop))}
                rx="1.5"
                fill={fill}
                opacity="0.85"
              />
            </g>
          );
        })}

        <text
          x={padding.left}
          y={height - 14}
          textAnchor="start"
          className="fill-muted-foreground"
          style={{ fontSize: "11px" }}
        >
          {startLabel}
        </text>
        <text
          x={width - padding.right}
          y={height - 14}
          textAnchor="end"
          className="fill-muted-foreground"
          style={{ fontSize: "11px" }}
        >
          {endLabel}
        </text>
      </svg>
    </div>
  );
}

function getChartRange(bars: TradingBar[]) {
  const values = bars.flatMap((bar) => [
    bar.high ?? bar.close,
    bar.low ?? bar.close,
  ]);

  const min = values.length ? Math.min(...values) : 0;
  const max = values.length ? Math.max(...values) : 0;

  if (min === max) {
    const delta = min === 0 ? 1 : Math.abs(min * 0.05);
    return { min: min - delta, max: max + delta };
  }

  const padding = (max - min) * 0.08;
  return { min: min - padding, max: max + padding };
}

function formatMoney(value: number) {
  return `$${value.toFixed(2)}`;
}

function formatChartLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "numeric",
  }).format(date);
}
