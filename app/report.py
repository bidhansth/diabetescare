"""Shared monthly PDF report builder.

Reused by both the EC2 FastAPI local fallback and the report-generation
Lambda (the Lambda vendors this module in its deployment zip). It depends
only on `reportlab` and the standard library, so it is cheap to ship to
Lambda.
"""

import io
from collections import Counter
from datetime import datetime
from decimal import Decimal
from typing import Any, Iterable, List, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)

# Color palette mirrors the dashboard CSS (static/css/style.css):
# success=#28a745 (used #198754 in charts), warning=#ffc107, danger=#dc3545.
GREEN = colors.HexColor("#198754")
YELLOW = colors.HexColor("#ffc107")
RED = colors.HexColor("#dc3545")

TYPE_ORDER = ["glucose", "meal", "medication", "exercise"]
TYPE_LABELS = {
    "glucose": "Glucose",
    "meal": "Meal",
    "medication": "Medication",
    "exercise": "Exercise",
}

MAX_ROWS_PER_TABLE = 40  # chunk large type tables onto multiple pages


def _num(value: Any) -> Optional[float]:
    """Convert DynamoDB Decimal / str / float into a float."""
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _to_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, Decimal):
        return str(value)
    return str(value)


def _glucose_color(value: float) -> colors.Color:
    if value < 70 or value > 180:
        return RED
    if value > 140:
        return YELLOW
    return GREEN


def _format_value(entry: dict) -> str:
    """Render the value cell the same way the dashboard does."""
    if entry.get("type") == "medication" and entry.get("medicationName"):
        return f'{_to_str(entry.get("medicationName"))} - {_to_str(entry.get("value"))} {_to_str(entry.get("unit"))}'
    return f'{_to_str(entry.get("value"))} {_to_str(entry.get("unit"))}'


def _human_date(ts: str) -> str:
    if not ts:
        return ""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M")
    except ValueError:
        return ts


def _chunked(rows: List[dict], size: int) -> Iterable[List[dict]]:
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


def build_monthly_pdf(
    entries: List[dict],
    month_label: str,
    user_name: str = "",
    start_iso: str = "",
    end_iso: str = "",
) -> bytes:
    """Build a monthly health report PDF and return it as raw bytes."""
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=15 * mm,
        bottomMargin=15 * mm,
        title=f"DiabetesCare Report {month_label}",
        author=user_name or "DiabetesCare User",
        subject="Monthly health report",
    )
    styles = getSampleStyleSheet()
    styles.add(
        ParagraphStyle(
            name="ReportTitle",
            parent=styles["Title"],
            fontSize=22,
            spaceAfter=6,
        )
    )
    styles.add(
        ParagraphStyle(name="ReportSub", parent=styles["Normal"], fontSize=10, spaceAfter=2)
    )
    styles.add(ParagraphStyle(name="Section", parent=styles["Heading2"], spaceAfter=6))
    styles.add(ParagraphStyle(name="Cell", parent=styles["Normal"], fontSize=8, leading=10))

    story = []

    # ── Header
    story.append(Paragraph("DiabetesCare", styles["ReportTitle"]))
    story.append(Paragraph("Monthly Health Report", styles["Normal"]))
    period = f"{_human_date(start_iso)} to {_human_date(end_iso)}" if start_iso and end_iso else month_label
    story.append(Paragraph(f"<b>Period:</b> {period}", styles["ReportSub"]))
    story.append(Paragraph(f"<b>Patient:</b> {_to_str(user_name) or '—'}", styles["ReportSub"]))
    story.append(Paragraph(f"<b>Generated:</b> {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}", styles["ReportSub"]))
    story.append(Spacer(1, 10))

    # ── Summary
    counts = Counter(e.get("type") for e in entries)
    glucoses = sorted((_num(e.get("value")) for e in entries if e.get("type") == "glucose"), reverse=False)
    glucoses = [g for g in glucoses if g is not None]
    total = len(entries)

    story.append(Paragraph("Summary", styles["Section"]))
    summary_data = [["Total entries", str(total)]]
    for t in TYPE_ORDER:
        summary_data.append([TYPE_LABELS[t], str(counts.get(t, 0))])
    if glucoses:
        summary_data.append(["Glucose min", f"{min(glucoses)} mg/dL"])
        summary_data.append(["Glucose max", f"{max(glucoses)} mg/dL"])
        summary_data.append(["Glucose avg", f"{round(sum(glucoses) / len(glucoses), 1)} mg/dL"])
        low_high = len([g for g in glucoses if g < 70 or g > 180])
        summary_data.append(["Out-of-range readings", str(low_high)])
    else:
        summary_data.append(["Glucose min", "—"])

    summary_tbl = Table(summary_data, colWidths=[50 * mm, 30 * mm])
    summary_tbl.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8f5e9")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(summary_tbl)
    story.append(Spacer(1, 8))

    # ── Per-type tables
    for entry_type in TYPE_ORDER:
        rows = sorted(
            [e for e in entries if e.get("type") == entry_type],
            key=lambda e: e.get("timestamp") or "",
        )
        if not rows:
            continue
        story.append(Paragraph(TYPE_LABELS[entry_type], styles["Section"]))

        for page_rows in _chunked(rows, MAX_ROWS_PER_TABLE):
            data = [["Timestamp", "Value", "Notes"]]
            row_colors: list = []
            for e in page_rows:
                data.append([_human_date(e.get("timestamp", "")), _format_value(e), e.get("notes") or ""])
                row_colors.append(e.get("type") == "glucose" and _glucose_color(_num(e.get("value")) or 0))

            tbl = Table(data, colWidths=[48 * mm, 32 * mm, 70 * mm])
            style = [
                ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ROWBACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f3f4")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
            ]
            # color the glucose value cell (column index 1) based on the reading
            if entry_type == "glucose":
                for idx, col in enumerate(row_colors, start=1):
                    style.append(("TEXTCOLOR", (1, idx), (1, idx), col))
            tbl.setStyle(TableStyle(style))
            story.append(tbl)
            story.append(Spacer(1, 6))

        story.append(PageBreak())

    doc.build(story)
    return buf.getvalue()
