# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m1b_document_analyzer.py — Advanced Document Analyzer
#  Module 1B: GST, ITR, Balance Sheet, P&L, MCA, Manual Entry
# ============================================================

import re
import json
from pathlib import Path
from datetime import datetime

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

# SECTION A - FILE READERS
# ════════════════════════════════════════════════════════════

def read_any_file(filepath: str) -> tuple:
    """
    Universal file reader.
    Returns (text: str, tables: list, error: str)
    Supports: PDF, CSV, Excel, TXT, DOCX
    """
    path = Path(filepath)
    ext  = path.suffix.lower()
    text   = ""
    tables = []
    error  = ""

    try:
        # ── PDF ──
        if ext == ".pdf":
            if not PDFPLUMBER_OK:
                return "", [], "pdfplumber not installed. Add to requirements.txt"
            with pdfplumber.open(filepath) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"
                    # Extract tables from PDF
                    page_tables = page.extract_tables()
                    if page_tables:
                        tables.extend(page_tables)

        # ── CSV ──
        elif ext == ".csv":
            if PANDAS_OK:
                df = pd.read_csv(filepath, encoding="utf-8", errors="replace")
                text   = df.to_string(index=False)
                tables = [df.values.tolist()]
            else:
                with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                    text = f.read()

        # ── Excel ──
        elif ext in [".xlsx", ".xls"]:
            if PANDAS_OK:
                xl = pd.ExcelFile(filepath)
                all_text = []
                for sheet in xl.sheet_names:
                    df = xl.parse(sheet)
                    all_text.append(f"[Sheet: {sheet}]\n{df.to_string(index=False)}")
                    tables.append(df.values.tolist())
                text = "\n\n".join(all_text)
            else:
                error = "pandas + openpyxl needed for Excel files"

        # ── Plain text / notes ──
        elif ext in [".txt", ".text"]:
            with open(filepath, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()

        # ── Word doc ──
        elif ext == ".docx":
            try:
                import docx
                doc  = docx.Document(filepath)
                text = "\n".join([p.text for p in doc.paragraphs])
            except ImportError:
                error = "python-docx not installed for .docx support"

        else:
            error = f"Unsupported file type: {ext}"

    except Exception as e:
        error = str(e)

    return text.strip(), tables, error


# ════════════════════════════════════════════════════════════
# SECTION B - DOCUMENT TYPE DETECTOR
# ════════════════════════════════════════════════════════════

DOC_SIGNATURES = {
    "GSTR-1":       ["GSTR-1", "GSTR1", "OUTWARD SUPPLIES", "B2B INVOICES", "B2C INVOICES", "HSN SUMMARY"],
    "GSTR-3B":      ["GSTR-3B", "GSTR3B", "OUTWARD TAXABLE", "ITC AVAILABLE", "NET TAX PAYABLE", "3B"],
    "GSTR-9":       ["GSTR-9", "GSTR9", "ANNUAL RETURN", "AGGREGATE TURNOVER"],
    "ITR":          ["INCOME TAX RETURN", "ITR-", "ASSESSMENT YEAR", "GROSS TOTAL INCOME",
                     "TAX DEDUCTED AT SOURCE", "TDS", "DEDUCTIONS UNDER", "ACKNOWLEDGEMENT NUMBER"],
    "Balance Sheet":["BALANCE SHEET", "ASSETS AND LIABILITIES", "SHAREHOLDERS EQUITY",
                     "FIXED ASSETS", "CURRENT ASSETS", "CURRENT LIABILITIES", "RESERVES AND SURPLUS"],
    "P&L":          ["PROFIT AND LOSS", "PROFIT & LOSS", "STATEMENT OF INCOME",
                     "REVENUE FROM OPERATIONS", "GROSS PROFIT", "EBITDA", "PAT", "PBT",
                     "COST OF GOODS SOLD", "COGS", "OPERATING EXPENSES"],
    "MCA":          ["ANNUAL RETURN", "FORM MGT", "CIN", "REGISTERED OFFICE",
                     "COMPANY MASTER", "ROC", "DIRECTOR IDENTIFICATION"],
    "Manual/Informal": ["SALES", "PURCHASE", "EXPENSE", "PROFIT", "LOSS", "CASH",
                        "RENT", "SALARY", "STOCK", "CLOSING BALANCE", "OPENING BALANCE"],
}

def detect_document_type(text: str, user_selected: str = "Auto Detect") -> str:
    """
    Detects document type from text content.
    If user_selected is not 'Auto Detect', returns that directly.
    """
    if user_selected and user_selected != "Auto Detect":
        return user_selected

    text_upper = text.upper()
    scores = {}

    for doc_type, keywords in DOC_SIGNATURES.items():
        score = sum(1 for kw in keywords if kw in text_upper)
        if score > 0:
            scores[doc_type] = score

    if not scores:
        return "Manual/Informal"

    return max(scores, key=scores.get)


# ════════════════════════════════════════════════════════════
# SECTION C - EXTRACTORS PER DOCUMENT TYPE
# ════════════════════════════════════════════════════════════

def _find(patterns: list, text: str, default="Not found") -> str:
    """Helper: tries multiple regex patterns, returns first match."""
    for pattern in patterns:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            val = m.group(1).strip().replace(",", "")
            return val
    return default

def _find_amount(patterns: list, text: str) -> str:
    """Helper: finds monetary amounts, returns formatted string."""
    val = _find(patterns, text)
    if val != "Not found":
        try:
            num = float(val.replace(",", "").replace(" ", ""))
            return f"Rs. {num:,.2f}"
        except Exception:
            return val
    return "Not found"

def _clean_amount(val: str) -> float:
    """Converts string amount to float."""
    try:
        return float(re.sub(r"[^\d.]", "", str(val)))
    except Exception:
        return 0.0


# ── C1: GST Return Extractor ──
def extract_gst(text: str, doc_subtype: str) -> dict:
    data = {}

    # Common GST fields
    data["GSTIN"] = _find([
        r"GSTIN\s*[:\-]?\s*([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})",
        r"\b([0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1})\b",
    ], text.upper())

    data["Legal Name"] = _find([
        r"(?:LEGAL\s+NAME|TRADE\s+NAME|TAXPAYER\s+NAME)\s*[:\-]?\s*([A-Z][A-Za-z\s&\.\-]+(?:PVT|PRIVATE|LTD|LIMITED|LLP|INDIA)?\.?\s*(?:PVT\.?\s*LTD\.?)?)",
    ], text)

    data["Filing Period"] = _find([
        r"(?:TAX\s+PERIOD|PERIOD|FOR\s+THE\s+MONTH\s+OF)\s*[:\-]?\s*((?:JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)[A-Z]*[\s\-]*20[0-9]{2})",
        r"((?:JANUARY|FEBRUARY|MARCH|APRIL|MAY|JUNE|JULY|AUGUST|SEPTEMBER|OCTOBER|NOVEMBER|DECEMBER)\s+20[0-9]{2})",
    ], text.upper())

    data["Financial Year"] = _find([
        r"(?:FINANCIAL\s+YEAR|FY|F\.Y\.)\s*[:\-]?\s*(20[0-9]{2}[\-\/]20?[0-9]{2})",
        r"(20[0-9]{2}[\-\/]20?[0-9]{2})",
    ], text.upper())

    data["Filing Status"] = "Filed" if any(k in text.upper() for k in [
        "DATE OF FILING", "FILED ON", "ACKNOWLEDGEMENT NO", "ARN"
    ]) else "Not confirmed"

    data["ARN"] = _find([r"ARN\s*[:\-]?\s*([A-Z0-9]{15,20})"], text.upper())

    if doc_subtype in ["GSTR-3B", "Auto Detect", "GSTR-1"]:
        data["Taxable Turnover"] = _find_amount([
            r"(?:TAXABLE\s+TURNOVER|TAXABLE\s+VALUE|TOTAL\s+TAXABLE)[^\d]*([\d,\.]+)",
            r"(?:OUTWARD\s+TAXABLE\s+SUPPLIES)[^\d]*([\d,\.]+)",
        ], text)

        data["Total CGST"] = _find_amount([r"CGST[^\d]*([\d,\.]+)"], text)
        data["Total SGST"] = _find_amount([r"SGST[^\d]*([\d,\.]+)"], text)
        data["Total IGST"] = _find_amount([r"IGST[^\d]*([\d,\.]+)"], text)

        data["ITC Claimed"] = _find_amount([
            r"(?:ITC\s+CLAIMED|INPUT\s+TAX\s+CREDIT|ITC\s+AVAILED)[^\d]*([\d,\.]+)",
        ], text)

        data["Net Tax Payable"] = _find_amount([
            r"(?:NET\s+TAX\s+PAYABLE|TAX\s+PAYABLE|NET\s+PAYABLE)[^\d]*([\d,\.]+)",
        ], text)

        data["Interest / Late Fee"] = _find_amount([
            r"(?:INTEREST|LATE\s+FEE)[^\d]*([\d,\.]+)",
        ], text)

    if doc_subtype == "GSTR-9":
        data["Annual Aggregate Turnover"] = _find_amount([
            r"(?:AGGREGATE\s+TURNOVER|ANNUAL\s+TURNOVER)[^\d]*([\d,\.]+)",
        ], text)

    return data


# ── C2: ITR Extractor ──
def extract_itr(text: str) -> dict:
    data = {}

    data["PAN"] = _find([r"\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b"], text.upper())

    data["Assessee Name"] = _find([
        r"(?:NAME\s+OF\s+ASSESSEE|ASSESSEE\s+NAME|NAME)[:\s]+([A-Z][A-Za-z\s\.]+)",
    ], text)

    data["Assessment Year"] = _find([
        r"(?:ASSESSMENT\s+YEAR|A\.Y\.)\s*[:\-]?\s*(20[0-9]{2}[\-\/]20?[0-9]{2})",
    ], text.upper())

    data["ITR Form"] = _find([
        r"(ITR[\-\s]?[1-7U])",
    ], text.upper())

    data["Acknowledgement No"] = _find([
        r"(?:ACKNOWLEDGEMENT\s+NO|ACKNOWLEDGEMENT\s+NUMBER)[:\s]*([\d]{15})",
    ], text.upper())

    data["Gross Total Income"] = _find_amount([
        r"(?:GROSS\s+TOTAL\s+INCOME)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Deductions (80C etc)"] = _find_amount([
        r"(?:TOTAL\s+DEDUCTIONS?|DEDUCTIONS\s+UNDER\s+CHAPTER)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Taxable Income"] = _find_amount([
        r"(?:TOTAL\s+TAXABLE\s+INCOME|NET\s+TAXABLE\s+INCOME)[^\d]*([\d,\.]+)",
    ], text)

    data["Tax Payable"] = _find_amount([
        r"(?:TAX\s+PAYABLE|TAX\s+DUE)[^\d]*([\d,\.]+)",
    ], text)

    data["TDS Deducted"] = _find_amount([
        r"(?:TDS\s+DEDUCTED|TAX\s+DEDUCTED\s+AT\s+SOURCE)[^\d]*([\d,\.]+)",
    ], text)

    data["Tax Refund / Balance Due"] = _find_amount([
        r"(?:REFUND\s+DUE|TAX\s+REFUND|BALANCE\s+TAX)[^\d]*([\d,\.]+)",
    ], text)

    data["Income from Salary"]   = _find_amount([r"(?:INCOME\s+FROM\s+SALARY|SALARIES)[^\d]*([\d,\.]+)"], text)
    data["Income from Business"] = _find_amount([r"(?:INCOME\s+FROM\s+BUSINESS|BUSINESS\s+INCOME)[^\d]*([\d,\.]+)"], text)
    data["Income from House Property"] = _find_amount([r"(?:INCOME\s+FROM\s+HOUSE\s+PROPERTY)[^\d]*([\d,\.]+)"], text)
    data["Capital Gains"]        = _find_amount([r"(?:CAPITAL\s+GAINS?)[^\d]*([\d,\.]+)"], text)

    # Effective tax rate
    gross = _clean_amount(data["Gross Total Income"])
    tax   = _clean_amount(data["Tax Payable"])
    if gross > 0 and tax > 0:
        data["Effective Tax Rate"] = f"{round((tax/gross)*100, 2)}%"
    else:
        data["Effective Tax Rate"] = "N/A"

    return data


# ── C3: Balance Sheet Extractor ──
def extract_balance_sheet(text: str) -> dict:
    data = {}

    data["Company Name"] = _find([
        r"^([A-Z][A-Za-z\s&\.\-]+(?:PVT|PRIVATE|LTD|LIMITED|LLP)?\.?\s*(?:PVT\.?\s*LTD\.?)?)",
    ], text)

    data["As at Date"] = _find([
        r"(?:AS\s+AT|AS\s+ON)\s+((?:\d{1,2}[\s\-\/])?(?:MARCH|MARCH|DECEMBER|SEPTEMBER|JUNE)\s+\d{4}|\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})",
    ], text.upper())

    # ASSETS
    data["Total Fixed Assets"] = _find_amount([
        r"(?:NET\s+FIXED\s+ASSETS|TOTAL\s+FIXED\s+ASSETS|FIXED\s+ASSETS\s+\(NET\))[^\d]*([\d,\.]+)",
        r"(?:PROPERTY,?\s*PLANT\s*(?:AND|&)\s*EQUIPMENT)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Current Assets"] = _find_amount([
        r"(?:TOTAL\s+CURRENT\s+ASSETS)[^\d]*([\d,\.]+)",
    ], text)

    data["Cash & Bank"] = _find_amount([
        r"(?:CASH\s+AND\s+(?:CASH\s+)?EQUIVALENTS|CASH\s+AND\s+BANK\s+BALANCES)[^\d]*([\d,\.]+)",
    ], text)

    data["Trade Receivables"] = _find_amount([
        r"(?:TRADE\s+RECEIVABLES|SUNDRY\s+DEBTORS|DEBTORS)[^\d]*([\d,\.]+)",
    ], text)

    data["Inventory / Stock"] = _find_amount([
        r"(?:INVENTORIES|INVENTORY|CLOSING\s+STOCK|STOCK)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Assets"] = _find_amount([
        r"(?:TOTAL\s+ASSETS)[^\d]*([\d,\.]+)",
    ], text)

    # LIABILITIES
    data["Share Capital"] = _find_amount([
        r"(?:SHARE\s+CAPITAL|EQUITY\s+SHARE\s+CAPITAL)[^\d]*([\d,\.]+)",
    ], text)

    data["Reserves & Surplus"] = _find_amount([
        r"(?:RESERVES\s+AND\s+SURPLUS|RESERVES\s*&\s*SURPLUS|RETAINED\s+EARNINGS)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Equity / Net Worth"] = _find_amount([
        r"(?:TOTAL\s+EQUITY|SHAREHOLDERS\s+EQUITY|NET\s+WORTH|TOTAL\s+SHAREHOLDERS)[^\d]*([\d,\.]+)",
    ], text)

    data["Long Term Borrowings"] = _find_amount([
        r"(?:LONG[\s\-]+TERM\s+BORROWINGS?|LONG[\s\-]+TERM\s+DEBT)[^\d]*([\d,\.]+)",
    ], text)

    data["Short Term Borrowings"] = _find_amount([
        r"(?:SHORT[\s\-]+TERM\s+BORROWINGS?|SHORT[\s\-]+TERM\s+DEBT)[^\d]*([\d,\.]+)",
    ], text)

    data["Trade Payables"] = _find_amount([
        r"(?:TRADE\s+PAYABLES|SUNDRY\s+CREDITORS|CREDITORS)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Current Liabilities"] = _find_amount([
        r"(?:TOTAL\s+CURRENT\s+LIABILITIES)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Liabilities"] = _find_amount([
        r"(?:TOTAL\s+LIABILITIES)[^\d]*([\d,\.]+)",
    ], text)

    # ── FINANCIAL RATIOS ──
    ca   = _clean_amount(data["Total Current Assets"])
    cl   = _clean_amount(data["Total Current Liabilities"])
    eq   = _clean_amount(data["Total Equity / Net Worth"])
    debt = _clean_amount(data["Long Term Borrowings"]) + _clean_amount(data["Short Term Borrowings"])
    ta   = _clean_amount(data["Total Assets"])

    data["Current Ratio"] = f"{round(ca/cl, 2)}" if cl > 0 else "N/A"
    data["Debt-to-Equity Ratio"] = f"{round(debt/eq, 2)}" if eq > 0 else "N/A"
    data["Debt-to-Assets Ratio"] = f"{round(debt/ta, 2)}" if ta > 0 else "N/A"

    # Health flags
    cr = _clean_amount(data["Current Ratio"])
    if cr > 0:
        data["Liquidity Health"] = (
            "Excellent (>2)" if cr >= 2 else
            "Good (1.5-2)" if cr >= 1.5 else
            "Acceptable (1-1.5)" if cr >= 1 else
            "POOR - Liquidity Risk (<1)"
        )

    de = _clean_amount(data["Debt-to-Equity Ratio"])
    if de > 0:
        data["Leverage Health"] = (
            "Conservative (<0.5)" if de < 0.5 else
            "Moderate (0.5-1)" if de < 1 else
            "High (1-2)" if de < 2 else
            "Very High (>2) - Review Urgently"
        )

    return data


# ── C4: P&L Extractor ──
def extract_pl(text: str) -> dict:
    data = {}

    data["Company Name"] = _find([
        r"^([A-Z][A-Za-z\s&\.\-]+(?:PVT|PRIVATE|LTD|LIMITED|LLP)?\.?)",
    ], text)

    data["Period"] = _find([
        r"(?:FOR\s+THE\s+(?:YEAR|PERIOD)\s+ENDED?|YEAR\s+ENDED?)\s+(\d{1,2}[\s\-\/]?(?:MARCH|DECEMBER|SEPTEMBER|JUNE)[\s\-\/]?\d{4}|\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})",
    ], text.upper())

    # INCOME
    data["Revenue from Operations"] = _find_amount([
        r"(?:REVENUE\s+FROM\s+OPERATIONS|NET\s+SALES|SALES\s+REVENUE|TOTAL\s+REVENUE)[^\d]*([\d,\.]+)",
    ], text)

    data["Other Income"] = _find_amount([
        r"(?:OTHER\s+INCOME|NON[\s\-]+OPERATING\s+INCOME)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Income"] = _find_amount([
        r"(?:TOTAL\s+INCOME|TOTAL\s+REVENUE)[^\d]*([\d,\.]+)",
    ], text)

    # EXPENSES
    data["Cost of Materials / COGS"] = _find_amount([
        r"(?:COST\s+OF\s+(?:MATERIALS|GOODS\s+SOLD)|COGS|COST\s+OF\s+SALES)[^\d]*([\d,\.]+)",
    ], text)

    data["Employee / Staff Costs"] = _find_amount([
        r"(?:EMPLOYEE\s+BENEFIT|STAFF\s+COST|SALARIES\s+AND\s+WAGES|PERSONNEL\s+COST)[^\d]*([\d,\.]+)",
    ], text)

    data["Finance Costs / Interest"] = _find_amount([
        r"(?:FINANCE\s+COSTS?|INTEREST\s+EXPENSE|INTEREST\s+PAID)[^\d]*([\d,\.]+)",
    ], text)

    data["Depreciation"] = _find_amount([
        r"(?:DEPRECIATION|AMORTISATION|AMORTIZATION)[^\d]*([\d,\.]+)",
    ], text)

    data["Total Expenses"] = _find_amount([
        r"(?:TOTAL\s+EXPENSES?|TOTAL\s+EXPENDITURE)[^\d]*([\d,\.]+)",
    ], text)

    # PROFIT LEVELS
    data["Gross Profit"] = _find_amount([
        r"(?:GROSS\s+PROFIT)[^\d]*([\d,\.]+)",
    ], text)

    data["EBITDA / Operating Profit"] = _find_amount([
        r"(?:EBITDA|OPERATING\s+PROFIT|PROFIT\s+BEFORE\s+INTEREST)[^\d]*([\d,\.]+)",
    ], text)

    data["PBT (Profit Before Tax)"] = _find_amount([
        r"(?:PROFIT\s+BEFORE\s+TAX|PBT)[^\d]*([\d,\.]+)",
    ], text)

    data["Tax Expense"] = _find_amount([
        r"(?:TAX\s+EXPENSE|INCOME\s+TAX|PROVISION\s+FOR\s+TAX)[^\d]*([\d,\.]+)",
    ], text)

    data["PAT (Net Profit)"] = _find_amount([
        r"(?:PROFIT\s+AFTER\s+TAX|PAT|NET\s+PROFIT)[^\d]*([\d,\.]+)",
    ], text)

    # ── PROFIT RATIOS ──
    rev = _clean_amount(data["Revenue from Operations"])
    gp  = _clean_amount(data["Gross Profit"])
    pat = _clean_amount(data["PAT (Net Profit)"])
    ebt = _clean_amount(data["PBT (Profit Before Tax)"])
    tax = _clean_amount(data["Tax Expense"])

    data["Gross Margin %"]      = f"{round((gp/rev)*100,1)}%" if rev > 0 and gp > 0 else "N/A"
    data["Net Profit Margin %"] = f"{round((pat/rev)*100,1)}%" if rev > 0 and pat > 0 else "N/A"
    data["Effective Tax Rate %"]= f"{round((tax/ebt)*100,1)}%" if ebt > 0 and tax > 0 else "N/A"

    npm = (pat/rev)*100 if rev > 0 and pat > 0 else -1
    data["Profitability Health"] = (
        "Excellent (>15%)" if npm >= 15 else
        "Good (10-15%)" if npm >= 10 else
        "Acceptable (5-10%)" if npm >= 5 else
        "Thin (2-5%)" if npm >= 2 else
        "Loss / Near-Zero - Urgent Review" if npm >= 0 else
        "Net Loss"
    )

    return data


# ── C5: MCA / Company Filing Extractor ──
def extract_mca(text: str) -> dict:
    data = {}

    data["CIN"] = _find([
        r"\b([UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6})\b",
    ], text.upper())

    data["Company Name"] = _find([
        r"(?:COMPANY\s+NAME|NAME\s+OF\s+COMPANY)[:\s]+([A-Z][A-Za-z\s&\.\-]+(?:PVT|PRIVATE|LTD|LIMITED|LLP)?\.?)",
    ], text.upper())

    data["PAN"] = _find([r"\b([A-Z]{5}[0-9]{4}[A-Z]{1})\b"], text.upper())

    data["ROC"] = _find([
        r"(?:ROC|REGISTRAR\s+OF\s+COMPANIES)[:\s]+([A-Za-z\s\-,]+)",
    ], text.upper())

    data["Incorporation Date"] = _find([
        r"(?:DATE\s+OF\s+INCORPORATION|INCORPORATED\s+ON)[:\s]+(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})",
    ], text.upper())

    data["Company Type"] = _find([
        r"(PRIVATE\s+LIMITED|PUBLIC\s+LIMITED|ONE\s+PERSON\s+COMPANY|LLP|SECTION\s+8)",
    ], text.upper())

    data["Registered Address"] = _find([
        r"(?:REGISTERED\s+(?:OFFICE|ADDRESS))[:\s]+([A-Za-z0-9\s,\.\-\/]+(?:Mumbai|Delhi|Chennai|Bangalore|Nashik|Pune|Hyderabad)[A-Za-z0-9\s,\.\-]*)",
    ], text)

    data["Authorized Capital"] = _find_amount([
        r"(?:AUTHORIZED|AUTHORISED)\s+CAPITAL[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Paid-up Capital"] = _find_amount([
        r"(?:PAID[\s\-]+UP\s+CAPITAL|PAIDUP\s+CAPITAL)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Directors Count"] = str(len(re.findall(r"DIN\s*[:\-]?\s*\d{8}", text.upper())))

    data["Filing Date"] = _find([
        r"(?:DATE\s+OF\s+FILING|FILED\s+ON)[:\s]+(\d{1,2}[\-\/]\d{1,2}[\-\/]\d{2,4})",
    ], text.upper())

    data["Financial Year"] = _find([
        r"(?:FINANCIAL\s+YEAR|FY)[:\s]*(20[0-9]{2}[\-\/]20?[0-9]{2})",
    ], text.upper())

    return data


# ── C6: Manual / Informal Business Entry ──
def extract_manual_entry(text: str) -> dict:
    """
    For small/informal businesses that write their own notes.
    Tries to extract any financial numbers mentioned in plain language.
    Also used when user fills the manual form fields.
    """
    data = {}

    # Sales / Revenue
    data["Total Sales / Revenue"] = _find_amount([
        r"(?:TOTAL\s+SALES|SALES|REVENUE|INCOME|EARNINGS)[^\d]*([\d,\.]+)",
        r"(?:BIKRI|INCOME)[^\d]*([\d,\.]+)",
    ], text.upper())

    # Purchases
    data["Total Purchases"] = _find_amount([
        r"(?:TOTAL\s+PURCHASE|PURCHASE|KHARIDI)[^\d]*([\d,\.]+)",
    ], text.upper())

    # Expenses
    data["Total Expenses"] = _find_amount([
        r"(?:TOTAL\s+EXPENSE|EXPENSES|KHARCHA)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Rent"] = _find_amount([r"(?:RENT|KIRAYA)[^\d]*([\d,\.]+)"], text.upper())
    data["Salaries / Labour"] = _find_amount([r"(?:SALARY|SALARIES|LABOUR|STAFF)[^\d]*([\d,\.]+)"], text.upper())
    data["Electricity"] = _find_amount([r"(?:ELECTRICITY|LIGHT\s+BILL|BIJLI)[^\d]*([\d,\.]+)"], text.upper())
    data["Raw Material"] = _find_amount([r"(?:RAW\s+MATERIAL|MATERIAL\s+COST)[^\d]*([\d,\.]+)"], text.upper())
    data["Transport"] = _find_amount([r"(?:TRANSPORT|LOGISTICS|DELIVERY)[^\d]*([\d,\.]+)"], text.upper())

    # Profit
    data["Gross Profit"] = _find_amount([
        r"(?:GROSS\s+PROFIT|PROFIT)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Net Profit"] = _find_amount([
        r"(?:NET\s+PROFIT|FINAL\s+PROFIT|NAFA)[^\d]*([\d,\.]+)",
    ], text.upper())

    # Cash & Stock
    data["Closing Cash / Bank Balance"] = _find_amount([
        r"(?:CLOSING\s+BALANCE|CASH\s+BALANCE|BANK\s+BALANCE|NAKIT)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Closing Stock"] = _find_amount([
        r"(?:CLOSING\s+STOCK|STOCK\s+IN\s+HAND)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Outstanding Receivables"] = _find_amount([
        r"(?:RECEIVABLE|OUTSTANDING|UDHAR\s+LENA)[^\d]*([\d,\.]+)",
    ], text.upper())

    data["Outstanding Payables"] = _find_amount([
        r"(?:PAYABLE|UDHAR\s+DENA|CREDIT\s+TAKEN)[^\d]*([\d,\.]+)",
    ], text.upper())

    # ── Auto-compute profit if possible ──
    sales = _clean_amount(data["Total Sales / Revenue"])
    exp   = _clean_amount(data["Total Expenses"])
    purch = _clean_amount(data["Total Purchases"])

    if sales > 0 and exp > 0:
        computed_profit = sales - exp - purch
        data["Computed Net Profit (Auto)"] = f"Rs. {computed_profit:,.2f}"
        margin = (computed_profit / sales) * 100 if sales > 0 else 0
        data["Profit Margin (Auto)"] = f"{round(margin, 1)}%"
        data["Business Health"] = (
            "Profitable" if computed_profit > 0 else
            "Breaking Even" if computed_profit == 0 else
            "Loss - Review Expenses"
        )

    return data


# ════════════════════════════════════════════════════════════
# SECTION D - ANOMALY & RISK DETECTOR
# ════════════════════════════════════════════════════════════

def detect_anomalies(doc_type: str, data: dict) -> list:
    """Flags financial risks and anomalies across all document types."""
    flags = []

    if doc_type in ["Balance Sheet"]:
        cr = _clean_amount(data.get("Current Ratio", "0"))
        de = _clean_amount(data.get("Debt-to-Equity Ratio", "0"))
        if 0 < cr < 1:
            flags.append({"level": "critical", "msg": f"Current ratio {cr} is below 1 - serious liquidity risk. Company may not meet short-term obligations."})
        if de > 3:
            flags.append({"level": "critical", "msg": f"Debt-to-equity {de} is very high - over-leveraged. High bankruptcy risk."})
        elif de > 2:
            flags.append({"level": "warning", "msg": f"Debt-to-equity {de} - high leverage. Monitor closely."})
        if data.get("Cash & Bank") == "Not found":
            flags.append({"level": "warning", "msg": "Cash & Bank balance not detected - verify liquidity position."})

    if doc_type in ["P&L"]:
        npm_str = data.get("Net Profit Margin %", "N/A")
        if npm_str != "N/A":
            npm = _clean_amount(npm_str)
            if npm < 0:
                flags.append({"level": "critical", "msg": f"Net profit margin is negative ({npm_str}) - company is in loss."})
            elif npm < 3:
                flags.append({"level": "warning", "msg": f"Very thin margin ({npm_str}) - vulnerable to any cost increase."})
        if data.get("Finance Costs / Interest") not in ["Not found", "Rs. 0.00"]:
            flags.append({"level": "info", "msg": "Finance costs detected - ensure interest coverage ratio > 1.5x."})

    if doc_type in ["GSTR-3B", "GSTR-1", "GSTR-9", "GST Return"]:
        if data.get("GSTIN") == "Not found":
            flags.append({"level": "critical", "msg": "GSTIN not found in document - verify authenticity."})
        if data.get("Filing Status") != "Filed":
            flags.append({"level": "warning", "msg": "Filing acknowledgement not confirmed - check GST portal."})
        if data.get("Interest / Late Fee") not in ["Not found", "Rs. 0.00"]:
            flags.append({"level": "warning", "msg": "Late fee / interest detected - past filing delays found."})

    if doc_type == "ITR":
        if data.get("PAN") == "Not found":
            flags.append({"level": "critical", "msg": "PAN not found in ITR document - verify document authenticity."})
        eff_tax = data.get("Effective Tax Rate", "N/A")
        if eff_tax != "N/A":
            rate = _clean_amount(eff_tax)
            if rate > 35:
                flags.append({"level": "warning", "msg": f"Effective tax rate {eff_tax} seems high - check for missed deductions."})
            elif rate < 5 and rate > 0:
                flags.append({"level": "info", "msg": f"Very low effective tax rate {eff_tax} - ensure all income is declared."})

    if doc_type == "Manual/Informal":
        profit_str = data.get("Computed Net Profit (Auto)", "Not found")
        if profit_str != "Not found" and "-" in profit_str:
            flags.append({"level": "critical", "msg": "Business is running at a loss based on provided figures."})
        if data.get("Outstanding Receivables") not in ["Not found", "Rs. 0.00"]:
            flags.append({"level": "info", "msg": "Outstanding receivables detected - follow up to improve cash flow."})

    if not flags:
        flags.append({"level": "good", "msg": "No major anomalies detected in this document."})

    return flags


# ════════════════════════════════════════════════════════════
# SECTION E - REPORT FORMATTER
# ════════════════════════════════════════════════════════════

def format_document_report(doc_type: str, data: dict, anomalies: list, filename: str) -> str:
    """Formats extraction results as clean professional markdown."""

    out = f"## {filename}\n"
    out += f"**Document Type:** {doc_type}\n"
    out += f"**Analyzed at:** {datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\n"
    out += "---\n\n"

    # Group fields intelligently
    sections = {
        "GSTR-1":  [("Identity", ["GSTIN","Legal Name","Filing Period","Financial Year","ARN","Filing Status"]),
                    ("Tax Details", ["Taxable Turnover","Total CGST","Total SGST","Total IGST","ITC Claimed","Net Tax Payable","Interest / Late Fee"])],

        "GSTR-3B": [("Identity", ["GSTIN","Legal Name","Filing Period","Financial Year","ARN","Filing Status"]),
                    ("Tax Details", ["Taxable Turnover","Total CGST","Total SGST","Total IGST","ITC Claimed","Net Tax Payable","Interest / Late Fee"])],

        "GSTR-9":  [("Identity", ["GSTIN","Legal Name","Financial Year","ARN","Filing Status"]),
                    ("Annual Summary", ["Annual Aggregate Turnover","Total CGST","Total SGST","Total IGST","ITC Claimed"])],

        "ITR":     [("Identity", ["PAN","Assessee Name","Assessment Year","ITR Form","Acknowledgement No"]),
                    ("Income Breakdown", ["Income from Salary","Income from Business","Income from House Property","Capital Gains","Gross Total Income"]),
                    ("Tax Computation", ["Total Deductions (80C etc)","Total Taxable Income","Tax Payable","TDS Deducted","Tax Refund / Balance Due","Effective Tax Rate"])],

        "Balance Sheet": [("Company", ["Company Name","As at Date"]),
                          ("Assets", ["Total Fixed Assets","Inventory / Stock","Trade Receivables","Cash & Bank","Total Current Assets","Total Assets"]),
                          ("Liabilities & Equity", ["Share Capital","Reserves & Surplus","Total Equity / Net Worth","Long Term Borrowings","Short Term Borrowings","Trade Payables","Total Current Liabilities","Total Liabilities"]),
                          ("Ratios", ["Current Ratio","Liquidity Health","Debt-to-Equity Ratio","Debt-to-Assets Ratio","Leverage Health"])],

        "P&L":     [("Company", ["Company Name","Period"]),
                    ("Income", ["Revenue from Operations","Other Income","Total Income"]),
                    ("Expenses", ["Cost of Materials / COGS","Employee / Staff Costs","Finance Costs / Interest","Depreciation","Total Expenses"]),
                    ("Profit", ["Gross Profit","EBITDA / Operating Profit","PBT (Profit Before Tax)","Tax Expense","PAT (Net Profit)"]),
                    ("Ratios", ["Gross Margin %","Net Profit Margin %","Effective Tax Rate %","Profitability Health"])],

        "MCA":     [("Company Identity", ["Company Name","CIN","PAN","Company Type","Incorporation Date"]),
                    ("Registration", ["ROC","Registered Address","Authorized Capital","Paid-up Capital","Directors Count","Filing Date","Financial Year"])],

        "Manual/Informal": [("Revenue", ["Total Sales / Revenue","Total Purchases"]),
                            ("Expenses", ["Total Expenses","Rent","Salaries / Labour","Electricity","Raw Material","Transport"]),
                            ("Profit & Cash", ["Gross Profit","Net Profit","Computed Net Profit (Auto)","Profit Margin (Auto)","Business Health"]),
                            ("Balance", ["Closing Cash / Bank Balance","Closing Stock","Outstanding Receivables","Outstanding Payables"])],
    }

    doc_sections = sections.get(doc_type, [("Extracted Data", list(data.keys()))])

    for section_name, fields in doc_sections:
        out += f"### {section_name}\n"
        out += "| Field | Value |\n|---|---|\n"
        for field in fields:
            val = data.get(field, "-")
            if val and val != "Not found":
                # Color-code health indicators
                if "POOR" in str(val) or "Loss" in str(val) or "Risk" in str(val) or "Urgent" in str(val):
                    val = f"🔴 {val}"
                elif "Excellent" in str(val) or "Good" in str(val) or "Profitable" in str(val):
                    val = f"✅ {val}"
                elif "Acceptable" in str(val) or "Moderate" in str(val) or "Thin" in str(val):
                    val = f"🟡 {val}"
            out += f"| {field} | {val if val and val != 'Not found' else '-'} |\n"
        out += "\n"

    # Anomaly section
    out += "### Risk & Anomaly Assessment\n"
    for flag in anomalies:
        icon = "🔴" if flag["level"] == "critical" else "🟡" if flag["level"] == "warning" else "ℹ️" if flag["level"] == "info" else "✅"
        out += f"{icon} {flag['msg']}\n\n"

    return out


# ════════════════════════════════════════════════════════════
# SECTION F - MANUAL ENTRY PROCESSOR
# (For small businesses entering data directly in form fields)
# ════════════════════════════════════════════════════════════

def process_manual_entry(
    sales: str, purchases: str, expenses: str,
    rent: str, salary: str, electricity: str,
    raw_material: str, transport: str, other_exp: str,
    cash_balance: str, closing_stock: str,
    receivables: str, payables: str,
    business_name: str, period: str,
) -> str:
    """Processes manually entered business figures."""

    def to_rs(val):
        try:
            return f"Rs. {float(str(val).replace(',','').replace('Rs.','').strip()):,.2f}"
        except Exception:
            return "-"

    def to_float(val):
        try:
            return float(str(val).replace(',','').replace('Rs.','').strip())
        except Exception:
            return 0.0

    s  = to_float(sales)
    p  = to_float(purchases)
    r  = to_float(rent)
    sa = to_float(salary)
    el = to_float(electricity)
    rm = to_float(raw_material)
    tr = to_float(transport)
    ot = to_float(other_exp)
    e  = to_float(expenses) if to_float(expenses) > 0 else (r + sa + el + rm + tr + ot)

    gross_profit = s - p
    net_profit   = gross_profit - e
    margin       = round((net_profit / s) * 100, 1) if s > 0 else 0

    data = {
        "Business Name": business_name or "Not provided",
        "Period": period or "Not provided",
        "Total Sales / Revenue": to_rs(sales),
        "Total Purchases": to_rs(purchases),
        "Gross Profit": f"Rs. {gross_profit:,.2f}",
        "Rent": to_rs(rent),
        "Salaries / Labour": to_rs(salary),
        "Electricity": to_rs(electricity),
        "Raw Material": to_rs(raw_material),
        "Transport": to_rs(transport),
        "Other Expenses": to_rs(other_exp),
        "Total Expenses": f"Rs. {e:,.2f}",
        "Net Profit": f"Rs. {net_profit:,.2f}",
        "Profit Margin": f"{margin}%",
        "Closing Cash / Bank": to_rs(cash_balance),
        "Closing Stock": to_rs(closing_stock),
        "Outstanding Receivables": to_rs(receivables),
        "Outstanding Payables": to_rs(payables),
    }

    health = (
        "✅ Profitable" if net_profit > 0 else
        "🟡 Breaking Even" if net_profit == 0 else
        "🔴 Loss - Review Expenses"
    )
    data["Business Health"] = health

    anomalies = []
    if net_profit < 0:
        anomalies.append({"level": "critical", "msg": f"Business is in loss of Rs. {abs(net_profit):,.2f}. Review expense structure immediately."})
    if margin < 5 and margin >= 0:
        anomalies.append({"level": "warning", "msg": f"Very thin margin ({margin}%) - vulnerable to any cost increase."})
    if to_float(receivables) > s * 0.3:
        anomalies.append({"level": "warning", "msg": "Outstanding receivables exceed 30% of sales - cash flow risk. Follow up with debtors."})
    if to_float(payables) > to_float(cash_balance):
        anomalies.append({"level": "warning", "msg": "Payables exceed cash balance - liquidity pressure. Plan payments carefully."})
    if not anomalies:
        anomalies.append({"level": "good", "msg": "No major issues detected based on provided figures."})

    return format_document_report("Manual/Informal", data, anomalies, f"{business_name or 'Business'} - Manual Entry")


# ════════════════════════════════════════════════════════════
# SECTION G - MASTER ANALYZER (Gradio entry point)
# ════════════════════════════════════════════════════════════

def analyze_documents_v2(files, doc_type_override: str) -> str:
    """
    Processes uploaded documents.
    doc_type_override: user selected type or 'Auto Detect'
    """
    if not files:
        return "Please upload at least one document."

    all_results = []

    for file in (files if isinstance(files, list) else [files]):
        if file is None:
            continue

        filepath = file.name if hasattr(file, "name") else str(file)
        filename = Path(filepath).name

        text, tables, error = read_any_file(filepath)

        if error:
            all_results.append(f"**{filename}:** Error - {error}")
            continue

        if len(text.strip()) < 30:
            all_results.append(f"**{filename}:** Could not extract readable text. File may be scanned/image-based or password protected.")
            continue

        doc_type = detect_document_type(text, doc_type_override)

        # Route to correct extractor
        if doc_type in ["GSTR-1", "GSTR-3B", "GSTR-9"]:
            data = extract_gst(text, doc_type)
        elif doc_type == "ITR":
            data = extract_itr(text)
        elif doc_type == "Balance Sheet":
            data = extract_balance_sheet(text)
        elif doc_type == "P&L":
            data = extract_pl(text)
        elif doc_type == "MCA":
            data = extract_mca(text)
        else:
            data = extract_manual_entry(text)

        anomalies = detect_anomalies(doc_type, data)
        report    = format_document_report(doc_type, data, anomalies, filename)
        all_results.append(report)

    return "\n\n---\n\n".join(all_results) if all_results else "No documents could be processed."


# ════════════════════════════════════════════════════════════
# COMBINED GRADIO UI - Module 1A + Module 1B
# ════════════════════════════════════════════════════════════

def gradio_audit(url: str):
    """Gradio wrapper for website-only audit tab."""
    if not url.strip():
        return "Please enter a valid URL.", "", "", "", "", None

    result = run_full_audit(url.strip())

    if "error" in result:
        return f"Website audit error: {result['error']}", "", "", "", "", None

    scores     = result["scores"]
    metadata   = result["metadata"]
    headings   = result["headings"]
    links      = result["links"]
    content    = result["content"]
    compliance = result["compliance"]
    sentiment  = result["sentiment"]
    perf       = result["perf"]
    suggs      = result["suggestions"]

    summary = f"""
## Website Score: {scores['overall']}/100  |  {scores['grade']}

| Dimension | Score |
|---|---|
| SEO Health | {scores['seo']}/100 |
| Content Quality | {scores['content']}/100 |
| Trust Signals | {scores['trust']}/100 |
| Performance | {scores['performance']}/100 |
| Compliance | {scores['compliance']}/100 |

**Load Time:** {perf['load_time_seconds']}s  |  **Mobile Ready:** {"Yes" if metadata['has_viewport'] else "No"}  |  **URL:** {result['url']}
""".strip()

    meta_out = f"""
**Title:** {metadata['title'] or 'NOT FOUND'}
**Description:** {metadata['description'] or 'NOT FOUND'}
**Keywords:** {metadata['keywords'] or 'Not set'}
**Canonical:** {metadata['canonical'] or 'Not set'}
**H1:** {headings['h1_count']} tag(s) - {headings['h1'][:2]}
**H2:** {headings['h2_count']}  |  **H3:** {headings['h3_count']}
""".strip()

    sentiment_out = f"""
**Word Count:** {content['word_count']}  |  **Paragraphs:** {content['paragraph_count']}
**Images:** {content['image_count']} ({content['images_missing_alt']} missing alt)
**Contact Info:** {"Yes" if content['has_contact_info'] else "No"}  |  **Testimonials:** {"Yes" if content['has_testimonials'] else "No"}  |  **Privacy Policy:** {"Yes" if content['has_privacy_policy'] else "No"}

**Tone:** {sentiment['tone']} - {sentiment['tone_detail']}
**Objectivity:** {sentiment['objectivity']} - {sentiment['objectivity_detail']}
""".strip()

    compliance_out = f"""
**GSTIN:** {"Found: " + ", ".join(compliance['gstins_found']) if compliance['has_gstin'] else "NOT FOUND on website"}
**CIN:** {"Found: " + ", ".join(compliance['cins_found']) if compliance['has_cin'] else "Not found"}
**Total Links:** {links['total_links']}  |  **Internal:** {links['internal_links']}  |  **External:** {links['external_links']}
**Broken Links:** {len(links['broken_links'])}  |  **Empty Anchors:** {links['empty_anchors']}
{chr(10).join([f"  - {b['url']} Status: {b['status']}" for b in links['broken_links']]) if links['broken_links'] else "No broken links detected"}
""".strip()

    critical = [s for s in suggs if s["type"] == "critical"]
    warnings = [s for s in suggs if s["type"] == "warning"]
    good     = [s for s in suggs if s["type"] == "good"]
    sugg_out = ""
    if critical:
        sugg_out += "### Critical Issues\n" + "\n".join([f"- {s['msg']}" for s in critical]) + "\n\n"
    if warnings:
        sugg_out += "### Warnings\n" + "\n".join([f"- {s['msg']}" for s in warnings]) + "\n\n"
    if good:
        sugg_out += "### What is Working\n" + "\n".join([f"- {s['msg']}" for s in good])

    pdf_path = generate_pdf_report(url, scores, suggs, metadata, compliance, sentiment, perf)

    return summary, meta_out, sentiment_out, compliance_out, sugg_out, pdf_path


# ── Combined URL + Doc handler ──
def run_combined_audit(url: str, files, doc_type_override: str):
    """Runs web audit and/or document analysis depending on what is provided."""
    has_url  = bool(url and url.strip())
    has_docs = bool(files and len(files) > 0)

    web_summary = web_meta = web_sentiment = web_compliance = web_sugg = ""
    pdf_path = None
    doc_result = ""

    if not has_url and not has_docs:
        return "Please enter a URL, upload documents, or both.", "", "", "", "", None, "No documents uploaded."

    if has_url:
        result = run_full_audit(url.strip())
        if "error" not in result:
            scores     = result["scores"]
            metadata   = result["metadata"]
            headings   = result["headings"]
            links      = result["links"]
            content    = result["content"]
            compliance = result["compliance"]
            sentiment  = result["sentiment"]
            perf       = result["perf"]
            suggs      = result["suggestions"]

            web_summary = f"""
## Website Score: {scores['overall']}/100  |  {scores['grade']}
| Dimension | Score |
|---|---|
| SEO Health | {scores['seo']}/100 |
| Content Quality | {scores['content']}/100 |
| Trust Signals | {scores['trust']}/100 |
| Performance | {scores['performance']}/100 |
| Compliance | {scores['compliance']}/100 |
**Load Time:** {perf['load_time_seconds']}s  |  **Mobile:** {"Yes" if metadata['has_viewport'] else "No"}
""".strip()

            web_meta = f"**Title:** {metadata['title'] or 'NOT FOUND'}\n**H1:** {headings['h1_count']}  |  **H2:** {headings['h2_count']}\n**Description:** {metadata['description'] or 'NOT FOUND'}"

            web_sentiment = f"**Words:** {content['word_count']}  |  **Tone:** {sentiment['tone']}\n{sentiment['tone_detail']}\n**Objectivity:** {sentiment['objectivity']} - {sentiment['objectivity_detail']}"

            web_compliance = f"**GSTIN:** {'Found: ' + ', '.join(compliance['gstins_found']) if compliance['has_gstin'] else 'NOT FOUND'}\n**Links:** {links['total_links']}  |  **Broken:** {len(links['broken_links'])}  |  **Empty:** {links['empty_anchors']}"

            critical = [s for s in suggs if s["type"] == "critical"]
            warnings = [s for s in suggs if s["type"] == "warning"]
            good     = [s for s in suggs if s["type"] == "good"]
            web_sugg = ""
            if critical: web_sugg += "### Critical\n" + "\n".join([f"- {s['msg']}" for s in critical]) + "\n\n"
            if warnings: web_sugg += "### Warnings\n" + "\n".join([f"- {s['msg']}" for s in warnings]) + "\n\n"
            if good:     web_sugg += "### Working\n" + "\n".join([f"- {s['msg']}" for s in good])

            pdf_path = generate_pdf_report(url, scores, suggs, metadata, compliance, sentiment, perf)
        else:
            web_summary = f"Web Audit Error: {result['error']}"

    if has_docs:
        doc_result = analyze_documents_v2(files, doc_type_override)

    return web_summary, web_meta, web_sentiment, web_compliance, web_sugg, pdf_path, doc_result


# ════════════════════════════════════════════════════════════
# GRADIO INTERFACE — MOBILE RESPONSIVE
