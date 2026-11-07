"""Conservative numeric ambiguity check, not financial statement reconciliation."""
import re
from collections import defaultdict


def evidence_gaps(evidence):
    values = defaultdict(set)
    for item in evidence:
        for metric, number in re.findall(r"\b(revenue|profit|debt)\s+(?:was\s+|is\s+|of\s+)?(?:INR\s*|Rs\.?\s*)?([0-9][0-9,.]*)", item["text"], re.IGNORECASE):
            key = (item["company"], item.get("period"), metric.lower())
            values[key].add(number.replace(",", "").rstrip("."))
    return [f"Potentially conflicting {metric} figures for {company} ({period or 'period unspecified'}). Review cited pages and units; no value was chosen."
        for (company, period, metric), figures in values.items() if len(figures) > 1]
