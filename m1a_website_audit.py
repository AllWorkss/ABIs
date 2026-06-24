# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE
#  m1a_website_audit.py — Website Scraper & Scorer
#  Module 1A: Scrapes URL, scores SEO/content/trust/perf/compliance
# ============================================================

import re
import time
import requests
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from textblob import TextBlob

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}

def fetch_page(url: str) -> dict:
    """
    Fetches the HTML content of a given URL.
    Returns dict with html, status_code, load_time, and error if any.
    """
    if not url.startswith("http"):
        url = "https://" + url

    result = {
        "url": url,
        "html": None,
        "status_code": None,
        "load_time_seconds": None,
        "error": None,
        "final_url": url,
    }

    try:
        start = time.time()
        response = requests.get(url, headers=HEADERS, timeout=15, allow_redirects=True)
        end = time.time()

        result["html"] = response.text
        result["status_code"] = response.status_code
        result["load_time_seconds"] = round(end - start, 2)
        result["final_url"] = response.url

    except requests.exceptions.ConnectionError:
        result["error"] = "Could not connect to website. Check the URL."
    except requests.exceptions.Timeout:
        result["error"] = "Website took too long to respond (>15s)."
    except Exception as e:
        result["error"] = str(e)

    return result


# ────────────────────────────────────────────────────────────
# CELL 4 - Metadata Extractor
# Pulls title, description, keywords from <head>
# ────────────────────────────────────────────────────────────

def extract_metadata(soup: BeautifulSoup) -> dict:
    """
    Extracts SEO metadata from parsed HTML.
    """
    meta = {}

    # Page title
    title_tag = soup.find("title")
    meta["title"] = title_tag.get_text(strip=True) if title_tag else ""

    # Meta description
    desc_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
    meta["description"] = desc_tag.get("content", "").strip() if desc_tag else ""

    # Meta keywords
    kw_tag = soup.find("meta", attrs={"name": re.compile("keywords", re.I)})
    meta["keywords"] = kw_tag.get("content", "").strip() if kw_tag else ""

    # Open Graph tags (for social sharing)
    og_title = soup.find("meta", property="og:title")
    meta["og_title"] = og_title.get("content", "") if og_title else ""

    og_desc = soup.find("meta", property="og:description")
    meta["og_description"] = og_desc.get("content", "") if og_desc else ""

    # Canonical URL
    canonical = soup.find("link", rel="canonical")
    meta["canonical"] = canonical.get("href", "") if canonical else ""

    # Viewport (mobile responsiveness signal)
    viewport = soup.find("meta", attrs={"name": "viewport"})
    meta["has_viewport"] = bool(viewport)

    return meta


# ────────────────────────────────────────────────────────────
# CELL 5 - Headings Extractor
# Builds the H1/H2/H3 hierarchy of the page
# ────────────────────────────────────────────────────────────

def extract_headings(soup: BeautifulSoup) -> dict:
    """
    Extracts heading structure from the page.
    Returns counts and actual heading texts.
    """
    headings = {}

    for level in ["h1", "h2", "h3", "h4"]:
        tags = soup.find_all(level)
        headings[level] = [t.get_text(strip=True) for t in tags if t.get_text(strip=True)]

    headings["h1_count"] = len(headings["h1"])
    headings["h2_count"] = len(headings["h2"])
    headings["h3_count"] = len(headings["h3"])

    # SEO flag: should have exactly 1 H1
    headings["h1_ok"] = headings["h1_count"] == 1

    return headings


# ────────────────────────────────────────────────────────────
# CELL 6 - Links Auditor
# Checks for broken links, empty anchors, external links
# ────────────────────────────────────────────────────────────

def audit_links(soup: BeautifulSoup, base_url: str) -> dict:
    """
    Audits all anchor tags on the page.
    Checks for broken links and empty href attributes.
    Note: Full broken link checking makes real HTTP requests - 
    we sample max 20 links to keep it fast.
    """
    links_data = {
        "total_links": 0,
        "internal_links": 0,
        "external_links": 0,
        "empty_anchors": 0,
        "broken_links": [],
        "checked_count": 0,
    }

    domain = urlparse(base_url).netloc
    all_anchors = soup.find_all("a", href=True)
    links_data["total_links"] = len(all_anchors)

    # Count empty anchors (href="#" or href="")
    empty = [a for a in soup.find_all("a") if not a.get("href") or a.get("href").strip() in ["#", ""]]
    links_data["empty_anchors"] = len(empty)

    # Classify internal vs external
    for anchor in all_anchors:
        href = anchor.get("href", "")
        if href.startswith("http"):
            if domain in href:
                links_data["internal_links"] += 1
            else:
                links_data["external_links"] += 1
        elif href.startswith("/") or href.startswith("./"):
            links_data["internal_links"] += 1

    # Sample up to 10 internal links for broken link check
    internal_to_check = [
        urljoin(base_url, a.get("href"))
        for a in all_anchors
        if a.get("href", "").startswith("/")
    ][:10]

    broken = []
    for link in internal_to_check:
        try:
            r = requests.head(link, headers=HEADERS, timeout=5, allow_redirects=True)
            if r.status_code >= 400:
                broken.append({"url": link, "status": r.status_code})
        except Exception:
            broken.append({"url": link, "status": "timeout/error"})

    links_data["broken_links"] = broken
    links_data["checked_count"] = len(internal_to_check)

    return links_data


# ────────────────────────────────────────────────────────────
# CELL 7 - Text & Content Analyzer
# Word count, content depth, readability
# ────────────────────────────────────────────────────────────

def analyze_content(soup: BeautifulSoup) -> dict:
    """
    Analyzes the text content of the page.
    """
    content = {}

    # Remove script and style tags first
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()

    body_text = soup.get_text(separator=" ", strip=True)
    words = [w for w in body_text.split() if len(w) > 1]

    content["word_count"] = len(words)
    content["char_count"] = len(body_text)
    content["body_text"] = body_text[:3000]  # first 3000 chars for sentiment

    # Paragraph count
    paragraphs = soup.find_all("p")
    content["paragraph_count"] = len(paragraphs)

    # Image count and alt text check
    images = soup.find_all("img")
    imgs_without_alt = [img for img in images if not img.get("alt")]
    content["image_count"] = len(images)
    content["images_missing_alt"] = len(imgs_without_alt)

    # Has contact info signals?
    contact_patterns = [
        r"\b\d{10}\b",           # phone number
        r"[a-zA-Z0-9+_.-]+@[a-zA-Z0-9.-]+",  # email
        r"contact|reach us|get in touch",      # contact text
    ]
    content["has_contact_info"] = any(
        re.search(p, body_text, re.I) for p in contact_patterns
    )

    # Has privacy policy / terms?
    content["has_privacy_policy"] = bool(
        re.search(r"privacy policy|terms of service|terms & conditions", body_text, re.I)
    )

    # Has testimonials / reviews?
    content["has_testimonials"] = bool(
        re.search(r"testimonial|review|feedback|what our customers|clients say", body_text, re.I)
    )

    return content


# ────────────────────────────────────────────────────────────
# CELL 8 - Compliance ID Extractor
# Regex scan for GSTIN and CIN numbers
# ────────────────────────────────────────────────────────────

def extract_compliance_ids(text: str) -> dict:
    """
    Scans page text for Indian business compliance identifiers.
    GSTIN format: 15-char alphanumeric
    CIN format: 21-char starting with U or L
    """
    compliance = {}

    # GSTIN pattern: 2 digits + 5 letters + 4 digits + 1 letter + 1 char + 1 char + 1 char
    gstin_pattern = r"\b[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z]{1}[1-9A-Z]{1}Z[0-9A-Z]{1}\b"
    gstins = re.findall(gstin_pattern, text.upper())
    compliance["gstins_found"] = list(set(gstins))
    compliance["has_gstin"] = len(gstins) > 0

    # CIN pattern: U/L + 5 digits + 2 letters + 4 digits + PTC/PLC + 6 digits
    cin_pattern = r"\b[UL][0-9]{5}[A-Z]{2}[0-9]{4}[A-Z]{3}[0-9]{6}\b"
    cins = re.findall(cin_pattern, text.upper())
    compliance["cins_found"] = list(set(cins))
    compliance["has_cin"] = len(cins) > 0

    # PAN pattern (bonus)
    pan_pattern = r"\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b"
    pans = re.findall(pan_pattern, text.upper())
    compliance["pans_found"] = list(set(pans))[:3]  # limit to 3

    return compliance


# ────────────────────────────────────────────────────────────
# CELL 9 - Sentiment Analyzer
# Analyzes tone of the website content
# ────────────────────────────────────────────────────────────

def analyze_sentiment(text: str) -> dict:
    """
    Uses TextBlob to analyze sentiment of page content.
    Returns polarity (-1 to 1) and subjectivity (0 to 1).
    """
    sentiment = {}

    # Limit to first 2000 words for speed
    short_text = " ".join(text.split()[:2000])

    blob = TextBlob(short_text)
    polarity = blob.sentiment.polarity        # -1 (negative) to 1 (positive)
    subjectivity = blob.sentiment.subjectivity  # 0 (objective) to 1 (subjective)

    sentiment["polarity"] = round(polarity, 3)
    sentiment["subjectivity"] = round(subjectivity, 3)

    # Human-readable labels
    if polarity > 0.2:
        sentiment["tone"] = "Positive"
        sentiment["tone_detail"] = "Website communicates with a confident, positive tone."
    elif polarity < -0.1:
        sentiment["tone"] = "Negative"
        sentiment["tone_detail"] = "Website has a negative or cautious tone - review copy."
    else:
        sentiment["tone"] = "Neutral"
        sentiment["tone_detail"] = "Website tone is neutral and factual."

    if subjectivity > 0.6:
        sentiment["objectivity"] = "Opinion-heavy"
        sentiment["objectivity_detail"] = "Content is subjective - add facts and data for trust."
    elif subjectivity < 0.3:
        sentiment["objectivity"] = "Very factual"
        sentiment["objectivity_detail"] = "Content is data-driven and objective - good for B2B."
    else:
        sentiment["objectivity"] = "Balanced"
        sentiment["objectivity_detail"] = "Good mix of factual content and personality."

    return sentiment


# ────────────────────────────────────────────────────────────
# CELL 10 - Scoring Engine
# Computes scores for each dimension and overall
# ────────────────────────────────────────────────────────────

def compute_scores(metadata, headings, links, content, compliance, perf, sentiment) -> dict:
    """
    Scores the website across 5 dimensions.
    Each dimension is 0-100. Overall is weighted average.
    """
    scores = {}

    # ── SEO Score (0-100) ──
    seo = 0
    if metadata["title"]:             seo += 20
    if len(metadata["title"]) < 60:   seo += 10
    if metadata["description"]:       seo += 20
    if len(metadata["description"]) < 160: seo += 10
    if headings["h1_ok"]:             seo += 20
    if headings["h2_count"] >= 2:     seo += 10
    if metadata["canonical"]:         seo += 10
    scores["seo"] = min(seo, 100)

    # ── Content Quality Score (0-100) ──
    cq = 0
    if content["word_count"] >= 300:  cq += 25
    if content["word_count"] >= 600:  cq += 15
    if content["paragraph_count"] >= 3: cq += 15
    if content["has_contact_info"]:   cq += 20
    if content["has_testimonials"]:   cq += 15
    if content["images_missing_alt"] == 0: cq += 10
    scores["content"] = min(cq, 100)

    # ── Trust Signals Score (0-100) ──
    trust = 0
    if compliance["has_gstin"]:       trust += 30
    if compliance["has_cin"]:         trust += 20
    if content["has_privacy_policy"]: trust += 20
    if content["has_testimonials"]:   trust += 15
    if content["has_contact_info"]:   trust += 15
    scores["trust"] = min(trust, 100)

    # ── Performance Score (0-100) ──
    perf_score = 0
    load = perf.get("load_time_seconds", 10)
    if load <= 2:    perf_score += 50
    elif load <= 4:  perf_score += 35
    elif load <= 6:  perf_score += 20
    else:            perf_score += 5
    if metadata["has_viewport"]:      perf_score += 30
    if links["broken_links"] == []:   perf_score += 20
    scores["performance"] = min(perf_score, 100)

    # ── Compliance Score (0-100) ──
    comp_score = 0
    if compliance["has_gstin"]:       comp_score += 50
    if compliance["has_cin"]:         comp_score += 30
    if content["has_privacy_policy"]: comp_score += 20
    scores["compliance"] = min(comp_score, 100)

    # ── Overall Score (weighted) ──
    scores["overall"] = round(
        scores["seo"] * 0.25 +
        scores["content"] * 0.25 +
        scores["trust"] * 0.20 +
        scores["performance"] * 0.15 +
        scores["compliance"] * 0.15
    )

    # ── Grade ──
    o = scores["overall"]
    if o >= 80:   scores["grade"] = "A · Excellent"
    elif o >= 65: scores["grade"] = "B · Good"
    elif o >= 50: scores["grade"] = "C · Needs Improvement"
    else:         scores["grade"] = "D · Critical Issues Found"

    return scores


# ────────────────────────────────────────────────────────────
# CELL 11 - Suggestion Generator
# Creates actionable recommendations from audit results
# ────────────────────────────────────────────────────────────

def generate_suggestions(metadata, headings, links, content, compliance, scores, perf) -> list:
    """
    Returns a list of actionable suggestions based on audit findings.
    Each suggestion has: type (critical/warning/good), message
    """
    suggestions = []

    # SEO suggestions
    if not metadata["title"]:
        suggestions.append({"type": "critical", "msg": "No page title found - add a clear, keyword-rich <title> tag."})
    elif len(metadata["title"]) > 60:
        suggestions.append({"type": "warning", "msg": f"Title is {len(metadata['title'])} chars - keep it under 60 for better Google display."})

    if not metadata["description"]:
        suggestions.append({"type": "critical", "msg": "No meta description - add one under 160 chars to improve search click rates."})

    if headings["h1_count"] == 0:
        suggestions.append({"type": "critical", "msg": "No H1 heading found - every page needs exactly one H1."})
    elif headings["h1_count"] > 1:
        suggestions.append({"type": "warning", "msg": f"Found {headings['h1_count']} H1 tags - use only one H1 per page."})
    else:
        suggestions.append({"type": "good", "msg": "H1 heading structure is correct ✓"})

    # Content suggestions
    if content["word_count"] < 300:
        suggestions.append({"type": "critical", "msg": f"Only {content['word_count']} words - add more content for SEO and customer trust."})
    elif content["word_count"] >= 600:
        suggestions.append({"type": "good", "msg": f"Good content depth - {content['word_count']} words ✓"})

    if not content["has_testimonials"]:
        suggestions.append({"type": "warning", "msg": "No testimonials found - add customer reviews to boost conversions."})

    if not content["has_contact_info"]:
        suggestions.append({"type": "critical", "msg": "No contact info detected - add phone/email on every page."})

    if content["images_missing_alt"] > 0:
        suggestions.append({"type": "warning", "msg": f"{content['images_missing_alt']} images missing alt text - fix for accessibility and SEO."})

    # Compliance suggestions
    if not compliance["has_gstin"]:
        suggestions.append({"type": "critical", "msg": "GSTIN not visible on website - display it to build compliance trust with customers."})
    else:
        suggestions.append({"type": "good", "msg": f"GSTIN found: {compliance['gstins_found'][0]} ✓"})

    if not compliance["has_cin"]:
        suggestions.append({"type": "warning", "msg": "CIN number not found - consider adding it to the footer for credibility."})

    if not content["has_privacy_policy"]:
        suggestions.append({"type": "warning", "msg": "No privacy policy detected - required for GDPR/IT Act compliance."})

    # Performance suggestions
    load = perf.get("load_time_seconds", 0)
    if load > 6:
        suggestions.append({"type": "critical", "msg": f"Page load time: {load}s - very slow. Compress images and enable caching."})
    elif load > 3:
        suggestions.append({"type": "warning", "msg": f"Page load time: {load}s - aim for under 3s."})
    else:
        suggestions.append({"type": "good", "msg": f"Page load time: {load}s - fast ✓"})

    if not metadata["has_viewport"]:
        suggestions.append({"type": "critical", "msg": "No viewport meta tag - website may not be mobile responsive."})
    else:
        suggestions.append({"type": "good", "msg": "Mobile viewport tag found ✓"})

    # Links
    if links["broken_links"]:
        suggestions.append({"type": "critical", "msg": f"{len(links['broken_links'])} broken links found - fix these immediately."})
    if links["empty_anchors"] > 0:
        suggestions.append({"type": "warning", "msg": f"{links['empty_anchors']} empty anchor tags found - remove or fix them."})

    return suggestions


# ────────────────────────────────────────────────────────────
# CELL 12 - PDF Report Generator
# Creates a downloadable audit report
# ────────────────────────────────────────────────────────────
from utils import sanitize, generate_pdf_report


# ────────────────────────────────────────────────────────────
# CELL 13 - Master Audit Function
# Runs all engines and returns complete results
# ────────────────────────────────────────────────────────────

def run_full_audit(url: str) -> dict:
    """
    Master function that runs all audit engines on a URL.
    Returns a complete audit result dictionary.
    """
    print(f"[1/7] Fetching page: {url}")
    fetch = fetch_page(url)

    if fetch["error"]:
        return {"error": fetch["error"]}

    html = fetch["html"]
    soup = BeautifulSoup(html, "html.parser")

    print("[2/7] Extracting metadata...")
    metadata = extract_metadata(soup)

    print("[3/7] Analyzing headings...")
    headings = extract_headings(soup)

    print("[4/7] Auditing links...")
    links = audit_links(soup, fetch["final_url"])

    print("[5/7] Analyzing content & sentiment...")
    content = analyze_content(soup)
    sentiment = analyze_sentiment(content["body_text"])

    print("[6/7] Scanning compliance IDs...")
    full_text = soup.get_text()
    compliance = extract_compliance_ids(full_text)

    print("[7/7] Computing scores & suggestions...")
    perf = {"load_time_seconds": fetch["load_time_seconds"]}
    scores = compute_scores(metadata, headings, links, content, compliance, perf, sentiment)
    suggestions = generate_suggestions(metadata, headings, links, content, compliance, scores, perf)

    return {
        "url": fetch["final_url"],
        "fetch": fetch,
        "metadata": metadata,
        "headings": headings,
        "links": links,
        "content": content,
        "compliance": compliance,
        "sentiment": sentiment,
        "scores": scores,
        "suggestions": suggestions,
        "perf": perf,
    }


# ────────────────────────────────────────────────────────────
# CELL 14 - Gradio Interface
# Professional UI for the auditor - runs in Colab & HF Spaces
# ────────────────────────────────────────────────────────────

