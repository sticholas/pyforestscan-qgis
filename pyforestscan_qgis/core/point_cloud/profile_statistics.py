"""Bounded statistics contracts for authoritative profile source queries."""
from __future__ import annotations

QUANTILE_SAMPLE_LIMIT = 100_000
HISTOGRAM_BINS = 16


def finalize_numeric_statistics(values, *, count, minimum, maximum, total, np):
    """Summarize source-query values without retaining an unbounded array."""
    if not count:
        return None
    sample = np.asarray(values, dtype="f8")
    sample = sample[np.isfinite(sample)]
    if not len(sample):
        return {"count": int(count), "minimum": minimum, "maximum": maximum,
                "mean": total / count, "quantiles": {}, "histogram": [],
                "quantile_scope": "NO_FINITE_VALUES"}
    quantiles = {str(percentile): float(np.percentile(sample, percentile))
                 for percentile in (0, 25, 50, 75, 95, 100)}
    if maximum > minimum:
        frequencies, edges = np.histogram(sample, bins=HISTOGRAM_BINS,
                                          range=(minimum, maximum))
        histogram = [{"minimum": float(edges[index]), "maximum": float(edges[index + 1]),
                      "count": int(frequencies[index])}
                     for index in range(len(frequencies))]
    else:
        histogram = [{"minimum": float(minimum), "maximum": float(maximum),
                      "count": int(len(sample))}]
    return {"count": int(count), "minimum": float(minimum), "maximum": float(maximum),
            "mean": float(total / count), "quantiles": quantiles,
            "histogram": histogram,
            "quantile_scope": "AUTHORITATIVE_SOURCE_QUERY_BOUNDED_SAMPLE"}


def distribution_summary(counts, total):
    return [{"value": key, "count": int(value),
             "percentage": (100.0 * value / total) if total else 0.0}
            for key, value in sorted(counts.items(), key=lambda item: (-item[1], item[0]))]
