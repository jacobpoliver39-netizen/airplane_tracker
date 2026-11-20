import type {
  AccuracySegment,
  ErrorSummary,
  PredictionAccuracy,
} from "../types/observers";

const STRATEGIES: { name: string; label: string }[] = [
  { name: "straight", label: "Straight line" },
  { name: "curved", label: "Curved (CTRV)" },
  { name: "historical", label: "Historical fit" },
];

const SEGMENTS: { name: AccuracySegment; label: string }[] = [
  { name: "all", label: "All flight" },
  { name: "turning", label: "Turning" },
  { name: "straight", label: "Straight flight" },
];

interface PredictionAccuracyPanelProps {
  accuracy: PredictionAccuracy | null;
}

function cellTitle(summary: ErrorSummary): string {
  return (
    `Mean ${summary.mean_miles.toFixed(3)} mi, ` +
    `median ${summary.median_miles.toFixed(3)} mi, ` +
    `${summary.count.toLocaleString()} predictions`
  );
}

export default function PredictionAccuracyPanel({
  accuracy,
}: PredictionAccuracyPanelProps) {
  const hasData = accuracy !== null && accuracy.scored_updates > 0;

  return (
    <section className="insight-panel">
      <div className="insight-heading">
        <div>
          <p className="eyebrow">PREDICTION ACCURACY</p>
          <h3>Mean error per strategy</h3>
        </div>
        <span className="insight-unit">miles</span>
      </div>

      {!hasData ? (
        <p className="insight-empty">
          Each strategy is scored when an aircraft reports its next
          position. Results appear after a few updates.
        </p>
      ) : (
        <>
          <table className="accuracy-table">
            <thead>
              <tr>
                <th scope="col">Strategy</th>
                {SEGMENTS.map((segment) => (
                  <th key={segment.name} scope="col">
                    {segment.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {STRATEGIES.map((strategy) => (
                <tr key={strategy.name}>
                  <th scope="row">{strategy.label}</th>
                  {SEGMENTS.map((segment) => (
                    <AccuracyCell
                      key={segment.name}
                      column={accuracy.segments[segment.name] ?? {}}
                      strategy={strategy.name}
                    />
                  ))}
                </tr>
              ))}
            </tbody>
          </table>

          <p className="insight-footnote">
            {accuracy.scored_updates.toLocaleString()} scored updates · error
            = distance between the predicted and the next reported position ·
            turning = estimated turn rate ≥{" "}
            {accuracy.turning_threshold_deg_per_s}°/s · lowest in each column
            highlighted
          </p>
        </>
      )}
    </section>
  );
}

function AccuracyCell({
  column,
  strategy,
}: {
  column: Record<string, ErrorSummary>;
  strategy: string;
}) {
  const summary = column[strategy];

  if (!summary) {
    return <td className="accuracy-cell accuracy-cell--empty">—</td>;
  }

  const means = Object.values(column).map((entry) => entry.mean_miles);
  const best = Math.min(...means);
  const worst = Math.max(...means);
  const isBest = summary.mean_miles === best && means.length > 1;

  return (
    <td
      className={`accuracy-cell${isBest ? " accuracy-cell--best" : ""}`}
      title={cellTitle(summary)}
    >
      <span className="accuracy-value">{summary.mean_miles.toFixed(3)}</span>
      <span className="accuracy-bar" aria-hidden="true">
        <span
          style={{ width: `${worst > 0 ? (summary.mean_miles / worst) * 100 : 0}%` }}
        />
      </span>
    </td>
  );
}
