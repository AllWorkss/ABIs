# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  utils.py — Shared utilities used by all modules
#  Includes: imports, PDF generator, text sanitizer
# ============================================================

import re
import os
import time
import json
from pathlib import Path
from datetime import datetime
from fpdf import FPDF

try:
    import pdfplumber
    PDFPLUMBER_OK = True
except ImportError:
    PDFPLUMBER_OK = False

try:
    import pandas as pd
    PANDAS_OK = True
except ImportError:
    PANDAS_OK = False

def sanitize(text: str) -> str:
    """Replace common unicode chars that latin-1 can't encode."""
    replacements = {
        "-": "-", "-": "-", "'": "'", "'": "'",
        """: '"', """: '"', "-": "*", "…": "...",
        "é": "e", "è": "e", "ê": "e", "à": "a",
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    # Remove any remaining non-latin-1 chars
    return text.encode("latin-1", errors="ignore").decode("latin-1")

def generate_pdf_report(url, scores, suggestions, metadata, compliance, sentiment, perf) -> str:
    """
    Generates a PDF audit report and saves it locally.
    Returns the file path.
    """
    pdf = FPDF()
    pdf.set_margins(15, 15, 15)   # left, top, right margins
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    PAGE_W = pdf.w - pdf.l_margin - pdf.r_margin  # usable width ~180mm

    # Header
    pdf.set_font("Helvetica", "B", 20)
    pdf.set_text_color(15, 158, 117)  # brand green
    pdf.cell(PAGE_W, 12, sanitize("Allworkss Business Intelligence Suite"), new_x="LMARGIN", new_y="NEXT")

    pdf.set_font("Helvetica", "", 12)
    pdf.set_text_color(100, 100, 100)
    pdf.cell(PAGE_W, 6, sanitize("Website Audit Report"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(PAGE_W, 6, sanitize(f"Generated: {datetime.now().strftime('%d %B %Y, %I:%M %p')}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # URL
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(PAGE_W, 8, sanitize(f"Audited URL: {url}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Divider
    pdf.set_draw_color(220, 220, 220)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    # Overall Score
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(15, 158, 117)
    pdf.cell(PAGE_W, 10, sanitize(f"Overall Score: {scores['overall']}/100  -  {scores['grade']}"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(3)

    # Dimension Scores
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(PAGE_W, 8, sanitize("Score Breakdown"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)

    dims = [
        ("SEO Health", scores["seo"]),
        ("Content Quality", scores["content"]),
        ("Trust Signals", scores["trust"]),
        ("Performance", scores["performance"]),
        ("Compliance", scores["compliance"]),
    ]
    for label, val in dims:
        color = (15, 158, 117) if val >= 70 else (186, 117, 23) if val >= 50 else (163, 45, 45)
        pdf.set_text_color(*color)
        pdf.cell(60, 7, sanitize(f"  {label}"), new_x="RIGHT", new_y="TOP")
        pdf.cell(PAGE_W, 7, sanitize(f"{val}/100"), new_x="LMARGIN", new_y="NEXT")

    pdf.ln(4)
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)

    # Sentiment
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(PAGE_W, 8, sanitize("Sentiment Analysis"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    pdf.cell(PAGE_W, 6, sanitize(f"  Tone: {sentiment['tone']}  ({sentiment['tone_detail']})"), new_x="LMARGIN", new_y="NEXT")
    pdf.cell(PAGE_W, 6, sanitize(f"  Objectivity: {sentiment['objectivity']}  ({sentiment['objectivity_detail']})"), new_x="LMARGIN", new_y="NEXT")
    pdf.ln(4)

    # Compliance IDs
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(30, 30, 30)
    pdf.cell(PAGE_W, 8, sanitize("Compliance IDs Found"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 11)
    if compliance["gstins_found"]:
        pdf.cell(PAGE_W, 6, sanitize(f"  GSTIN: {', '.join(compliance['gstins_found'])}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(163, 45, 45)
        pdf.cell(PAGE_W, 6, sanitize("  GSTIN: NOT FOUND on website"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
    if compliance["cins_found"]:
        pdf.cell(PAGE_W, 6, sanitize(f"  CIN: {', '.join(compliance['cins_found'])}"), new_x="LMARGIN", new_y="NEXT")
    else:
        pdf.set_text_color(186, 117, 23)
        pdf.cell(PAGE_W, 6, sanitize("  CIN: Not found on website"), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(30, 30, 30)
    pdf.ln(4)

    # Suggestions
    pdf.line(pdf.l_margin, pdf.get_y(), pdf.w - pdf.r_margin, pdf.get_y())
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(PAGE_W, 8, sanitize("Actionable Recommendations"), new_x="LMARGIN", new_y="NEXT")
    pdf.set_font("Helvetica", "", 10)

    for s in suggestions:
        if s["type"] == "critical":
            pdf.set_text_color(163, 45, 45)
            prefix = "[CRITICAL] "
        elif s["type"] == "warning":
            pdf.set_text_color(186, 117, 23)
            prefix = "[WARNING]  "
        else:
            pdf.set_text_color(59, 109, 17)
            prefix = "[GOOD]     "

        # Handle long lines
        msg = prefix + s["msg"]
        pdf.multi_cell(PAGE_W, 6, sanitize(msg), new_x='LMARGIN', new_y='NEXT')

    # Footer
    pdf.set_text_color(150, 150, 150)
    pdf.set_font("Helvetica", "", 9)
    pdf.ln(6)
    pdf.cell(PAGE_W, 6, sanitize("Allworkss BI Suite - 360 AI for SMEs  |  Confidential Report"), new_x="LMARGIN", new_y="NEXT")

    # Save
    filepath = f"/tmp/allworkss_audit_{int(time.time())}.pdf"
    pdf.output(filepath)
    return filepath


# ────────────────────────────────────────────────────────────
# CELL 13 - Master Audit Function
# Runs all engines and returns complete results
# ────────────────────────────────────────────────────────────
