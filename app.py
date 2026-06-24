# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE — app.py
#  Clean interface: gr.Tabs for modules, gr.Tabs for sub-pages
#  Zero JS, zero CSS fighting, zero scroll glitch
#  Gradio-native layout only — guaranteed to work
# ============================================================

import gradio as gr
from m1a_website_audit     import run_full_audit
from utils                 import generate_pdf_report
from m1b_document_analyzer import analyze_documents_v2, process_manual_entry
from m3_inventory          import run_inventory_forecast, run_scenario_simulation, get_sku_list
from m2_logistics_router   import run_logistics_router
from m2_supply_chain       import (
    import_vendors_from_csv, add_vendor_manual,
    format_vendor_list_html, format_vendor_detail, get_vendor_names,
)

from m5_growth import (
    run_growth_analysis, run_market_analysis, run_pricing_analysis,
    run_competitor_benchmark, run_whatif, run_ai_strategy_and_pdf,
)

from m4_intelligence import (
    run_customer_analysis, run_financial_analysis, run_ai_chat,
)

DOC_CHOICES = ["Auto Detect","GSTR-1 (Outward Supplies)","GSTR-3B (Monthly Summary)",
    "GSTR-9 (Annual Return)","ITR (Income Tax Return)","Balance Sheet",
    "P&L (Profit & Loss)","MCA / Company Filing","Manual / Informal Business"]
DOC_MAP = {"Auto Detect":"Auto Detect","GSTR-1 (Outward Supplies)":"GSTR-1",
    "GSTR-3B (Monthly Summary)":"GSTR-3B","GSTR-9 (Annual Return)":"GSTR-9",
    "ITR (Income Tax Return)":"ITR","Balance Sheet":"Balance Sheet",
    "P&L (Profit & Loss)":"P&L","MCA / Company Filing":"MCA",
    "Manual / Informal Business":"Manual/Informal"}

CSS = """
/* Clean professional dark theme */
.gradio-container { max-width:100% !important; }
footer { display:none !important; }

/* Module tab bar styling */
.mod-tabs > .tab-nav {
    background: #0d0d0d !important;
    border-bottom: 2px solid #1D9E75 !important;
    padding: 0 16px !important;
}
.mod-tabs > .tab-nav button {
    font-size: 11px !important;
    font-weight: 700 !important;
    letter-spacing: 0.08em !important;
    text-transform: uppercase !important;
    color: #555 !important;
    padding: 14px 18px !important;
    border-radius: 0 !important;
    border-bottom: 3px solid transparent !important;
    margin-bottom: -2px !important;
}
.mod-tabs > .tab-nav button.selected {
    color: #1D9E75 !important;
    border-bottom: 3px solid #1D9E75 !important;
    background: transparent !important;
}
.mod-tabs > .tab-nav button:hover {
    color: #aaa !important;
    background: #161616 !important;
}

/* Sub-tab bar styling */
.sub-tabs > .tab-nav {
    background: #111 !important;
    border-bottom: 1px solid #1e1e1e !important;
    padding: 0 16px !important;
}
.sub-tabs > .tab-nav button {
    font-size: 12px !important;
    color: #666 !important;
    padding: 10px 16px !important;
    border-radius: 0 !important;
    border-bottom: 2px solid transparent !important;
}
.sub-tabs > .tab-nav button.selected {
    color: #1D9E75 !important;
    border-bottom: 2px solid #1D9E75 !important;
    background: transparent !important;
}
.sub-tabs > .tab-nav button:hover {
    color: #ccc !important;
    background: #1a1a1a !important;
}

/* Content area */
.tab-content { background: #0f0f0f; padding: 20px 24px; }
.ph { margin-bottom: 18px; padding-bottom: 12px; border-bottom: 1px solid #1e1e1e; }
.ph-t { font-size: 20px; font-weight: 600; color: #e0e0e0; margin-bottom: 4px; }
.ph-s { font-size: 13px; color: #555; }

/* Full width buttons */
button.fw { width: 100% !important; }
"""

# ── Handlers ──────────────────────────────────────────────

def h_web(url):
    if not url or not url.strip(): return "Enter a URL.","","","","",None
    r = run_full_audit(url.strip())
    if "error" in r: return f"Error: {r['error']}","","","","",None
    s,m,h,l,c,co,sen,p = r["scores"],r["metadata"],r["headings"],r["links"],r["content"],r["compliance"],r["sentiment"],r["perf"]
    sug = r["suggestions"]
    sc = (f"## Score: {s['overall']}/100 — {s['grade']}\n"
          f"| Dimension | Score | Status |\n|---|---|---|\n"
          +"\n".join([f"| {k} | {v}/100 | {'✅ Good' if v>=70 else '⚠️ Needs Work'} |"
                     for k,v in [("SEO",s["seo"]),("Content",s["content"]),
                                  ("Trust",s["trust"]),("Performance",s["performance"]),
                                  ("Compliance",s["compliance"])]])
          +f"\n\n**Load:** {p['load_time_seconds']}s | **Mobile:** {'Yes' if m['has_viewport'] else 'No'} | **URL:** {r['url']}")
    mt = (f"**Title:** {m['title'] or 'NOT FOUND'}\n**Description:** {m['description'] or 'NOT FOUND'}\n"
          f"**H1:** {h['h1_count']} | **H2:** {h['h2_count']} | **H3:** {h['h3_count']}\n**H1 Text:** {h['h1'][:2]}")
    se = (f"**Words:** {c['word_count']} | **Paragraphs:** {c['paragraph_count']}\n"
          f"**Images:** {c['image_count']} ({c['images_missing_alt']} missing alt)\n"
          f"**Contact:** {'Yes' if c['has_contact_info'] else 'No'} | **Testimonials:** {'Yes' if c['has_testimonials'] else 'No'} | **Privacy Policy:** {'Yes' if c['has_privacy_policy'] else 'No'}\n"
          f"**Tone:** {sen['tone']} — {sen['tone_detail']}\n**Objectivity:** {sen['objectivity']} — {sen['objectivity_detail']}")
    gs  = "Found: "+", ".join(co["gstins_found"]) if co["has_gstin"] else "NOT FOUND on website"
    cin = "Found: "+", ".join(co["cins_found"])   if co["has_cin"]   else "Not found"
    brk = "\n".join([f"  - {b['url']} ({b['status']})" for b in l["broken_links"]]) if l["broken_links"] else "No broken links"
    co2 = f"**GSTIN:** {gs}\n**CIN:** {cin}\n**Links:** {l['total_links']} | **Broken:** {len(l['broken_links'])} | **Empty:** {l['empty_anchors']}\n{brk}"
    sg  = ""
    for t,hdr in [("critical","### 🔴 Critical Issues"),("warning","### 🟡 Warnings"),("good","### ✅ What is Working")]:
        items=[x for x in sug if x["type"]==t]
        if items: sg += hdr+"\n"+"\n".join(f"- {x['msg']}" for x in items)+"\n\n"
    return sc, mt, se, co2, sg, generate_pdf_report(url,s,sug,m,co,sen,p)

def h_doc(f,dd): return analyze_documents_v2(f, DOC_MAP.get(dd,"Auto Detect"))
def h_man(sa,pu,te,re,sl,el,rw,tr,oe,ca,st,rc,pa,bn,pe):
    return process_manual_entry(sa,pu,te,re,sl,el,rw,tr,oe,ca,st,rc,pa,bn,pe)
def h_full(url,files,dd):
    hv=bool(url and url.strip()); hd=bool(files and len(files)>0)
    if not hv and not hd: return "Enter URL or upload docs.","","","","",None,""
    sm=mm=se=cm=su=dm=""; pdf=None
    if hv: sm,mm,se,cm,su,pdf = h_web(url)
    if hd: dm = analyze_documents_v2(files, DOC_MAP.get(dd,"Auto Detect"))
    return sm,mm,se,cm,su,pdf,dm



# ── App ───────────────────────────────────────────────────
with gr.Blocks(title="Allworkss BI Suite", css=CSS,
               theme=gr.themes.Soft(primary_hue="green",
                                    neutral_hue="slate",
                                    font=gr.themes.GoogleFont("Inter"))) as demo:

    # Header
    gr.HTML("""
    <div style="background:#0d0d0d;border-bottom:1px solid #1e1e1e;padding:12px 20px;
                display:flex;align-items:center;justify-content:space-between;">
      <div style="display:flex;align-items:center;gap:12px;">
        <div style="width:32px;height:32px;background:#1D9E75;border-radius:6px;
                    display:flex;align-items:center;justify-content:center;
                    font-size:16px;font-weight:700;color:#000;">A</div>
        <div>
          <div style="font-size:15px;font-weight:700;color:#e0e0e0;line-height:1.1;">Allworkss BI Suite</div>
          <div style="font-size:10px;color:#555;letter-spacing:0.07em;text-transform:uppercase;">360° AI for Indian SMEs</div>
        </div>
      </div>
      <div style="display:flex;gap:8px;">
        <span style="background:#0a1f17;color:#1D9E75;font-size:10px;font-weight:600;padding:4px 10px;border-radius:20px;border:1px solid #1D9E75;">Module 1: Auditor</span>
        <span style="background:#1a1a1a;color:#555;font-size:10px;font-weight:600;padding:4px 10px;border-radius:20px;border:1px solid #2a2a2a;">Module 2: Supply Chain</span>
        <span style="background:#1a1a1a;color:#555;font-size:10px;font-weight:600;padding:4px 10px;border-radius:20px;border:1px solid #2a2a2a;">Module 3: Inventory</span>
      </div>
    </div>
    """)

                                        
                                        
 
    # ═══════════════════════════════════════════════════
    # TOP-LEVEL MODULE TABS
    # ═══════════════════════════════════════════════════
    with gr.Tabs(elem_classes=["mod-tabs"]):

        # ──────────────────────────────────────────────
        # MODULE 1 — AUDITOR
        # ──────────────────────────────────────────────
        with gr.Tab("🔎  Module 1 — Business Auditor"):
            with gr.Tabs(elem_classes=["sub-tabs"]):

                # Sub: Website Audit
                with gr.Tab("🌐  Website Audit"):
                    gr.HTML('<div class="ph"><div class="ph-t">🌐 Website Audit</div>'
                            '<div class="ph-s">Full AI-powered audit — SEO, compliance, sentiment, performance</div></div>')
                    w_url = gr.Textbox(label="Business Website URL", placeholder="https://yourbusiness.com")
                    w_btn = gr.Button("▶  Run Website Audit", variant="primary", elem_classes=["fw"])
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("#### Score & Dimensions")
                            w_sc = gr.Markdown()
                            gr.Markdown("#### Metadata & SEO")
                            w_mt = gr.Markdown()
                        with gr.Column():
                            gr.Markdown("#### Content & Sentiment")
                            w_se = gr.Markdown()
                            gr.Markdown("#### Compliance & Links")
                            w_co = gr.Markdown()
                    gr.Markdown("#### Recommendations")
                    w_sg  = gr.Markdown()
                    w_pdf = gr.File(label="📥 Download PDF Report")
                    w_btn.click(fn=h_web, inputs=[w_url], outputs=[w_sc,w_mt,w_se,w_co,w_sg,w_pdf])
                    gr.Examples(examples=[["https://www.flipkart.com"],["https://www.tatacliq.com"],
                                          ["https://www.nykaa.com"],["https://www.hitechengineer.in"]],
                                inputs=w_url, label="Quick examples")

                # Sub: Document Analyzer
                with gr.Tab("📄  Documents"):
                    gr.HTML('<div class="ph"><div class="ph-t">📄 Document Analyzer</div>'
                            '<div class="ph-s">GST Returns · ITR · Balance Sheet · P&L · MCA · Informal notes</div></div>')
                    d_dd = gr.Dropdown(choices=DOC_CHOICES, value="Auto Detect", label="Document Type")
                    d_f  = gr.File(label="Upload — PDF, CSV, Excel, TXT, DOCX",
                                   file_types=[".pdf",".csv",".xlsx",".xls",".txt",".docx"],
                                   file_count="multiple")
                    d_btn = gr.Button("▶  Analyze Documents", variant="primary", elem_classes=["fw"])
                    d_out = gr.Markdown()
                    d_btn.click(fn=h_doc, inputs=[d_f,d_dd], outputs=[d_out])

                # Sub: Manual Entry
                with gr.Tab("✏️  Manual Entry"):
                    gr.HTML('<div class="ph"><div class="ph-t">✏️ Manual Entry</div>'
                            '<div class="ph-s">For small shops, traders, and informal businesses — no documents needed</div></div>')
                    with gr.Row():
                        me_n = gr.Textbox(label="Business Name", placeholder="e.g. Sharma General Store")
                        me_p = gr.Textbox(label="Period / Financial Year", placeholder="e.g. April 2024 - March 2025")
                    gr.Markdown("#### Revenue")
                    with gr.Row():
                        me_sa = gr.Number(label="Total Sales / Revenue (Rs.)", value=0)
                        me_pu = gr.Number(label="Total Purchases / COGS (Rs.)", value=0)
                    gr.Markdown("#### Expenses — fill individually OR total only")
                    with gr.Row():
                        me_re = gr.Number(label="Rent (Rs.)", value=0)
                        me_sl = gr.Number(label="Salaries / Labour (Rs.)", value=0)
                        me_el = gr.Number(label="Electricity / Utilities (Rs.)", value=0)
                    with gr.Row():
                        me_rw = gr.Number(label="Raw Material (Rs.)", value=0)
                        me_tr = gr.Number(label="Transport / Delivery (Rs.)", value=0)
                        me_oe = gr.Number(label="Other Expenses (Rs.)", value=0)
                    me_te = gr.Number(label="Total Expenses — fill ONLY if skipping individual items above (Rs.)", value=0)
                    gr.Markdown("#### Cash & Balances")
                    with gr.Row():
                        me_ca = gr.Number(label="Closing Cash / Bank Balance (Rs.)", value=0)
                        me_st = gr.Number(label="Closing Stock / Inventory (Rs.)", value=0)
                    with gr.Row():
                        me_rc = gr.Number(label="Receivables — Udhar Lena (Rs.)", value=0)
                        me_pa = gr.Number(label="Payables — Udhar Dena (Rs.)", value=0)
                    me_btn = gr.Button("▶  Generate Business Report", variant="primary", elem_classes=["fw"])
                    me_out = gr.Markdown()
                    me_btn.click(fn=h_man,
                                 inputs=[me_sa,me_pu,me_te,me_re,me_sl,me_el,
                                         me_rw,me_tr,me_oe,me_ca,me_st,me_rc,me_pa,me_n,me_p],
                                 outputs=[me_out])

                # Sub: Full Combined Audit
                with gr.Tab("🔍  Full Audit"):
                    gr.HTML('<div class="ph"><div class="ph-t">🔍 Full Combined Audit</div>'
                            '<div class="ph-s">URL audit + Document analysis together — both optional</div></div>')
                    fa_u = gr.Textbox(label="Website URL (optional)", placeholder="https://yourbusiness.com")
                    fa_d = gr.Dropdown(choices=DOC_CHOICES, value="Auto Detect", label="Document Type")
                    fa_f = gr.File(label="Upload Documents (optional)",
                                   file_types=[".pdf",".csv",".xlsx",".xls",".txt",".docx"],
                                   file_count="multiple")
                    fa_btn = gr.Button("▶  Run Full Audit", variant="primary", elem_classes=["fw"])
                    gr.Markdown("### Website Audit Results")
                    fa_sc=gr.Markdown(); fa_mt=gr.Markdown()
                    fa_se=gr.Markdown(); fa_co=gr.Markdown()
                    fa_sg=gr.Markdown(); fa_pdf=gr.File(label="PDF")
                    gr.Markdown("### Document Analysis Results")
                    fa_dm = gr.Markdown()
                    fa_btn.click(fn=h_full, inputs=[fa_u,fa_f,fa_d],
                                 outputs=[fa_sc,fa_mt,fa_se,fa_co,fa_sg,fa_pdf,fa_dm])

        # ──────────────────────────────────────────────
        # MODULE 2 — SUPPLY CHAIN
        # ──────────────────────────────────────────────
        with gr.Tab("🏭  Module 2 — Supply Chain"):
            with gr.Tabs(elem_classes=["sub-tabs"]):

                # Sub: Vendor Intelligence
                with gr.Tab("🏭  Vendor Intelligence"):
                    gr.HTML('<div class="ph"><div class="ph-t">🏭 Vendor Intelligence</div>'
                            '<div class="ph-s">ML-scored vendors — select one to see full profile, routes and 3PL recommendations</div></div>')
                    with gr.Row():
                        with gr.Column(scale=1, min_width=220):
                            gr.Markdown("### Vendors")
                            v_li  = gr.HTML(value=format_vendor_list_html())
                            v_sel = gr.Dropdown(choices=get_vendor_names(), label="Select Vendor", interactive=True)
                            gr.Markdown("**Route parameters for 3PL scoring:**")
                            v_wt  = gr.Slider(label="Shipment Weight (kg)", minimum=1, maximum=5000, value=50, step=10)
                            v_di  = gr.Slider(label="Distance (km)", minimum=1, maximum=1500, value=30, step=5)
                            v_btn = gr.Button("View Vendor Detail", variant="primary")
                        with gr.Column(scale=2):
                            v_det = gr.HTML(value="<div style='padding:40px;color:#555;text-align:center;font-family:system-ui;'>Select a vendor from the list above and click View Vendor Detail.</div>")
                    v_btn.click(fn=format_vendor_detail, inputs=[v_sel,v_wt,v_di], outputs=[v_det])
                    v_sel.change(fn=format_vendor_detail, inputs=[v_sel,v_wt,v_di], outputs=[v_det])

                # Sub: Import CSV
                with gr.Tab("📥  Import CSV"):
                    gr.HTML('<div class="ph"><div class="ph-t">📥 Import Vendors from CSV</div>'
                            '<div class="ph-s">Upload supplier CSV or Excel — auto-detects columns, ML scoring applied instantly</div></div>')
                    gr.Markdown("**Required columns (any order, case-insensitive):**\n`Supplier Name · On Time Delivery % · Quality Score % · Lead Time Days · Reliability % · Location · Route · Transport Mode`")
                    gr.Markdown("**Sample:**\n```\nSupplier Name,On Time Delivery %,Quality Score %,Lead Time Days,Reliability %,Location,Route,Transport Mode\nMetalWorks Co,92,88,5,90,Mumbai,Mumbai-Pune,Truck\n```")
                    ic_f   = gr.File(label="Upload CSV / Excel", file_types=[".csv",".xlsx",".xls",".txt"], file_count="multiple")
                    ic_btn = gr.Button("▶  Import Vendors", variant="primary", elem_classes=["fw"])
                    ic_st  = gr.Markdown()
                    ic_li  = gr.HTML()
                    ic_dd  = gr.Dropdown(label="", choices=[], visible=False)
                    ic_btn.click(fn=import_vendors_from_csv, inputs=[ic_f], outputs=[ic_st,ic_li,ic_dd])

                # Sub: Add Vendor
                with gr.Tab("➕  Add Vendor"):
                    gr.HTML('<div class="ph"><div class="ph-t">➕ Add Vendor Manually</div>'
                            '<div class="ph-s">Enter vendor details — ML scores and ranks instantly on save</div></div>')
                    with gr.Row():
                        av_n = gr.Textbox(label="Vendor / Supplier Name *", placeholder="e.g. MetalWorks Co")
                        av_l = gr.Textbox(label="City / Location", placeholder="e.g. Mumbai")
                    with gr.Row():
                        av_g = gr.Textbox(label="GSTIN", placeholder="27AABCU9603R1ZX")
                        av_c = gr.Textbox(label="Contact (Phone / Email)")
                    gr.Markdown("#### Performance Metrics")
                    with gr.Row():
                        av_ot = gr.Number(label="On-Time Delivery %", value=80, minimum=0, maximum=100)
                        av_q  = gr.Number(label="Quality Score %", value=80, minimum=0, maximum=100)
                        av_r  = gr.Number(label="Reliability %", value=80, minimum=0, maximum=100)
                    with gr.Row():
                        av_ld = gr.Number(label="Lead Time (days)", value=7, minimum=1)
                        av_pr = gr.Number(label="Avg Unit Price (Rs.)", value=0, minimum=0)
                    gr.Markdown("#### Route & Transport")
                    with gr.Row():
                        av_ro = gr.Textbox(label="Route", placeholder="e.g. Mumbai to Pune")
                        av_mo = gr.Dropdown(choices=["Bike","Auto","Tata Ace","Truck","Air","Rail","Not specified"],
                                            value="Truck", label="Transport Mode")
                    av_btn = gr.Button("▶  Add Vendor", variant="primary", elem_classes=["fw"])
                    av_st  = gr.Markdown()
                    av_li  = gr.HTML()
                    av_dd  = gr.Dropdown(label="", choices=[], visible=False)
                    av_btn.click(fn=add_vendor_manual,
                                 inputs=[av_n,av_g,av_c,av_l,av_ot,av_q,av_ld,av_pr,av_r,av_ro,av_mo],
                                 outputs=[av_st,av_li,av_dd])

                # Sub: Logistics Router
                with gr.Tab("🚚  Logistics Router"):
                    gr.HTML('<div class="ph"><div class="ph-t">🚚 Smart Logistics Router</div>'
                            '<div class="ph-s">Real-time rates across 6 providers · Real road distance · Interactive map · Gemini AI parcel scanner</div></div>')
                    with gr.Row():
                        with gr.Column():
                            gr.Markdown("### Step 1 — AI Parcel Scanner *(Optional)*")
                            gr.Markdown("Upload a parcel photo. Gemini Vision estimates weight and dimensions. Set `GEMINI_API_KEY` in HF Spaces → Settings → Secrets.")
                            lr_img = gr.Image(label="Upload or Take Photo of Parcel", type="filepath", sources=["upload","webcam"])
                            lr_sb  = gr.Button("Scan with Gemini AI", variant="secondary")
                            lr_ph  = gr.HTML()
                        with gr.Column():
                            gr.Markdown("### Step 2 — Route & Weight")
                            lr_pu  = gr.Textbox(label="Pick-up Address", placeholder="e.g. Andheri East Mumbai")
                            lr_do  = gr.Textbox(label="Drop-off Address", placeholder="e.g. Hinjewadi Pune")
                            lr_wt  = gr.Number(label="Shipment Weight (kg)", value=1.0, minimum=0.1, step=0.5)
                            lr_btn = gr.Button("▶  Find Best Rates — All 6 Providers", variant="primary", elem_classes=["fw"])
                    gr.Markdown("### Route Map")
                    lr_map   = gr.HTML()
                    gr.Markdown("### Rate Comparison — All Providers")
                    lr_rates = gr.HTML()
                    def lr_scan(img,wt):
                        if img is None: return "<div style='color:#888;padding:12px;background:#1a1a1a;border-radius:8px;'>Upload a parcel photo first.</div>",wt
                        from m2_logistics_router import scan_parcel_gemini,format_parcel_scan_html
                        sc=scan_parcel_gemini(img); return format_parcel_scan_html(sc),(sc["weight_kg"] if sc.get("success") else wt)
                    lr_sb.click(fn=lr_scan, inputs=[lr_img,lr_wt], outputs=[lr_ph,lr_wt])
                    def lr_run(p,d,w,img):
                        ph,mh,rh,wt=run_logistics_router(p,d,w,img); return ph,mh,rh,wt
                    lr_btn.click(fn=lr_run, inputs=[lr_pu,lr_do,lr_wt,lr_img], outputs=[lr_ph,lr_map,lr_rates,lr_wt])

        # ──────────────────────────────────────────────
        # MODULE 3 — INVENTORY FORECASTING
        # ──────────────────────────────────────────────
        with gr.Tab("📦  Module 3 — Inventory Forecasting"):
            with gr.Tabs(elem_classes=["sub-tabs"]):

                # Sub: Demand Forecast
                with gr.Tab("📈  Demand Forecast"):
                    gr.HTML('<div class="ph"><div class="ph-t">📈 Demand Forecast</div>'
                            '<div class="ph-s">ARIMA + Prophet + LSTM ensemble — SKU-level 30/60/90 day demand forecasting</div></div>')
                    with gr.Row():
                        m3f_file = gr.File(label="Upload Sales CSV/Excel — leave empty for built-in sample data",
                                           file_types=[".csv",".xlsx",".xls"], scale=3)
                        with gr.Column(scale=1):
                            m3f_days = gr.Slider(label="Forecast Horizon (days)", minimum=7, maximum=90, value=30, step=7)
                            m3f_svc  = gr.Slider(label="Service Level %", minimum=0.90, maximum=0.99, value=0.95, step=0.01)
                            m3f_lead = gr.Number(label="Default Lead Time (days)", value=7, minimum=1)
                    m3f_btn  = gr.Button("▶  Run Forecast — ARIMA + Prophet + LSTM", variant="primary", elem_classes=["fw"])
                    m3f_sum  = gr.HTML()
                    m3f_ch   = gr.HTML()
                    gr.Markdown("**CSV Format:** `Date, SKU, Product, Category, Quantity_Sold, Unit_Price, Stock_Level, Lead_Time_Days`")
                    m3f_btn.click(fn=lambda f,d,s,l: run_inventory_forecast(f,int(d),s,int(l))[:2],
                                  inputs=[m3f_file,m3f_days,m3f_svc,m3f_lead], outputs=[m3f_sum,m3f_ch])

                # Sub: Stock Alerts
                with gr.Tab("🔔  Stock Alerts"):
                    gr.HTML('<div class="ph"><div class="ph-t">🔔 Stock Alerts & Reorder Intelligence</div>'
                            '<div class="ph-s">Reorder points · Safety stock · EOQ · Color-coded urgency per SKU</div></div>')
                    m3a_file = gr.File(label="Upload Sales CSV/Excel — leave empty for sample", file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3a_days = gr.Slider(label="Forecast Days", minimum=7, maximum=90, value=30, step=7)
                        m3a_svc  = gr.Slider(label="Service Level", minimum=0.90, maximum=0.99, value=0.95, step=0.01)
                        m3a_lead = gr.Number(label="Lead Time (days)", value=7, minimum=1)
                    m3a_btn = gr.Button("▶  Generate Stock Alerts", variant="primary", elem_classes=["fw"])
                    m3a_out = gr.HTML()
                    m3a_btn.click(fn=lambda f,d,s,l: run_inventory_forecast(f,int(d),s,int(l))[2],
                                  inputs=[m3a_file,m3a_days,m3a_svc,m3a_lead], outputs=[m3a_out])

                # Sub: Purchase Orders
                with gr.Tab("📋  Purchase Orders"):
                    gr.HTML('<div class="ph"><div class="ph-t">📋 Auto-Generate Purchase Orders</div>'
                            '<div class="ph-s">ML-driven PO generation for all SKUs below reorder point</div></div>')
                    m3p_file = gr.File(label="Upload Sales CSV/Excel — leave empty for sample", file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3p_days = gr.Slider(label="Forecast Days", minimum=7, maximum=90, value=30, step=7)
                        m3p_svc  = gr.Slider(label="Service Level", minimum=0.90, maximum=0.99, value=0.95, step=0.01)
                        m3p_lead = gr.Number(label="Lead Time (days)", value=7, minimum=1)
                    m3p_btn = gr.Button("▶  Generate Purchase Order", variant="primary", elem_classes=["fw"])
                    m3p_out = gr.Markdown()
                    m3p_btn.click(fn=lambda f,d,s,l: run_inventory_forecast(f,int(d),s,int(l))[3],
                                  inputs=[m3p_file,m3p_days,m3p_svc,m3p_lead], outputs=[m3p_out])

                # Sub: Scenario Simulation
                with gr.Tab("🎲  Scenario Sim"):
                    gr.HTML('<div class="ph"><div class="ph-t">🎲 What-If Scenario Simulation</div>'
                            '<div class="ph-s">Test demand spikes, supplier delays, price hikes, stockouts — see impact and recommendations</div></div>')
                    m3s_file = gr.File(label="Upload Sales CSV/Excel — leave empty for sample", file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3s_sku  = gr.Dropdown(label="Select SKU", choices=["SKU001","SKU002","SKU003"],
                                               value="SKU001", interactive=True)
                        m3s_sc   = gr.Dropdown(label="Scenario Type",
                                               choices=["demand_spike","demand_drop","supplier_delay",
                                                        "price_increase","stockout"],
                                               value="demand_spike")
                        m3s_par  = gr.Number(label="Parameter (% or days)", value=30, minimum=1)
                    with gr.Row():
                        m3s_days = gr.Slider(label="Forecast Days", minimum=7, maximum=90, value=30, step=7)
                        m3s_lead = gr.Number(label="Lead Time (days)", value=7, minimum=1)
                    m3s_btn = gr.Button("▶  Run Scenario", variant="primary", elem_classes=["fw"])
                    m3s_out = gr.HTML()
                    def upd_skus(f):
                        skus=get_sku_list(f); return gr.Dropdown(choices=skus, value=skus[0] if skus else "SKU001")
                    m3s_file.change(fn=upd_skus, inputs=[m3s_file], outputs=[m3s_sku])
                    m3s_btn.click(fn=lambda f,sk,sc,p,d,l: run_scenario_simulation(f,sk,sc,p,int(d),int(l)),
                                  inputs=[m3s_file,m3s_sku,m3s_sc,m3s_par,m3s_days,m3s_lead],
                                  outputs=[m3s_out])


        # ──────────────────────────────────────────────
        # MODULE 4 — CUSTOMER & FINANCIAL INTELLIGENCE
        # ──────────────────────────────────────────────
        with gr.Tab("🧠  Module 4 — Intelligence & Risk"):
            with gr.Tabs(elem_classes=["sub-tabs"]):

                # Sub: Customer Intelligence
                with gr.Tab("👥  Customer Intelligence"):
                    gr.HTML('''<div class="ph">
<div class="ph-t">👥 Customer Intelligence</div>
<div class="ph-s">KMeans segmentation · Churn prediction · Anomaly detection · Revenue forecasting</div></div>''')
                    gr.Markdown("""
Upload your customer transaction data. The AI will automatically:
- **Segment** customers into behavioral groups (Champions, Loyal, At Risk, Churned)
- **Predict churn** probability per customer with intervention recommendations
- **Detect anomalies** — unusual spending or behavior patterns
- **Forecast** next period revenue using linear trend

**CSV columns:** `CustomerID, TotalRevenue, TotalOrders, LastPurchaseDays, AvgOrderValue, Category, City`
Leave empty to run on built-in sample data.
""")
                    c_file = gr.File(label="Upload Customer CSV/Excel (leave empty for sample data)",
                                     file_types=[".csv",".xlsx",".xls"])
                    c_btn  = gr.Button("▶  Run Customer Intelligence — ML Segmentation + Churn + Anomaly",
                                       variant="primary", elem_classes=["fw"])
                    c_status    = gr.Markdown()
                    c_dashboard = gr.HTML()
                    c_btn.click(fn=run_customer_analysis, inputs=[c_file],
                                outputs=[c_dashboard, c_status])

                # Sub: Financial Risk Scoring
                with gr.Tab("📊  Financial Risk Score"):
                    gr.HTML('''<div class="ph">
<div class="ph-t">📊 Financial Risk & Credit Scoring</div>
<div class="ph-s">12 financial ratios · Credit rating AAA→CCC · Loan eligibility · Risk flags</div></div>''')
                    with gr.Tabs():
                        with gr.Tab("Upload Financial Data"):
                            gr.Markdown("""
**CSV columns:** `Month, Revenue, COGS, GrossProfit, OperatingExpenses, EBITDA, NetProfit, CashBalance, Receivables, Payables, TotalAssets, TotalDebt, Equity`
Leave empty for built-in 12-month sample P&L data.
""")
                            f_file = gr.File(label="Upload Financial CSV/Excel (leave empty for sample)",
                                             file_types=[".csv",".xlsx",".xls"])
                            f_btn  = gr.Button("▶  Run Financial Health & Credit Scoring",
                                               variant="primary", elem_classes=["fw"])
                            f_use_manual = gr.State(False)

                        with gr.Tab("Manual Entry"):
                            gr.Markdown("### Enter your latest financial figures manually")
                            with gr.Row():
                                f_rev   = gr.Number(label="Monthly Revenue (Rs.)",    value=500000, minimum=0)
                                f_cogs  = gr.Number(label="COGS / Cost of Sales (Rs.)",value=300000, minimum=0)
                            with gr.Row():
                                f_np    = gr.Number(label="Net Profit (Rs.)",          value=50000,  minimum=0)
                                f_ebitda= gr.Number(label="EBITDA (Rs.)",              value=80000,  minimum=0)
                            with gr.Row():
                                f_cash  = gr.Number(label="Cash / Bank Balance (Rs.)", value=200000, minimum=0)
                                f_debt  = gr.Number(label="Total Debt / Loans (Rs.)",  value=300000, minimum=0)
                            with gr.Row():
                                f_assets= gr.Number(label="Total Assets (Rs.)",        value=900000, minimum=0)
                                f_equity= gr.Number(label="Equity / Net Worth (Rs.)",  value=600000, minimum=0)
                            with gr.Row():
                                f_recv  = gr.Number(label="Receivables (Rs.)",          value=100000, minimum=0)
                                f_pay   = gr.Number(label="Payables (Rs.)",             value=50000,  minimum=0)
                            f_manual_btn = gr.Button("▶  Score My Business Financials",
                                                     variant="primary", elem_classes=["fw"])
                            f_use_manual2 = gr.State(True)

                    f_status    = gr.Markdown()
                    f_dashboard = gr.HTML()

                    f_btn.click(fn=run_financial_analysis,
                                inputs=[f_file,
                                        gr.State(0),gr.State(0),gr.State(0),gr.State(0),
                                        gr.State(0),gr.State(0),gr.State(0),gr.State(0),
                                        gr.State(0),gr.State(0), f_use_manual],
                                outputs=[f_dashboard, f_status])
                    f_manual_btn.click(fn=run_financial_analysis,
                                       inputs=[gr.State(None),
                                               f_rev,f_cogs,f_np,f_ebitda,
                                               f_cash,f_debt,f_assets,f_equity,
                                               f_recv,f_pay, f_use_manual2],
                                       outputs=[f_dashboard, f_status])

                # Sub: AI Chat Q&A
                with gr.Tab("💬  AI Chat on Your Data"):
                    gr.HTML('''<div class="ph">
<div class="ph-t">💬 AI Chat — Ask Questions About Your Business Data</div>
<div class="ph-s">Powered by Gemini AI · Run Customer or Financial analysis first · Ask anything</div></div>''')
                    gr.Markdown("""
**How to use:**
1. Run **Customer Intelligence** or **Financial Risk Score** tab first
2. Then come here and ask any question about your data

**Example questions:**
- *"Which customer segment is most profitable?"*
- *"What is my biggest financial risk right now?"*
- *"Which customers should I call this week to prevent churn?"*
- *"Am I eligible for a bank loan? How much?"*
- *"What should I improve to raise my credit score?"*

Set `GEMINI_API_KEY` in HF Spaces → Settings → Secrets to enable.
""")
                    ai_history = gr.State([])
                    with gr.Row():
                        ai_q   = gr.Textbox(label="Ask a question about your business data",
                                            placeholder="e.g. Which customers are at highest churn risk?",
                                            scale=4)
                        ai_btn = gr.Button("Ask AI", variant="primary", scale=1)
                    ai_answer = gr.Markdown(label="AI Answer")

                    ai_btn.click(fn=run_ai_chat,
                                 inputs=[ai_q, ai_history],
                                 outputs=[ai_answer, ai_history])
                    ai_q.submit(fn=run_ai_chat,
                                inputs=[ai_q, ai_history],
                                outputs=[ai_answer, ai_history])


        # ──────────────────────────────────────────────
        # MODULE 5 — GROWTH & EXPANSION INTELLIGENCE
        # ──────────────────────────────────────────────
        with gr.Tab("🚀  Module 5 — Growth & Expansion"):
            with gr.Tabs(elem_classes=["sub-tabs"]):

                # ── Growth Score ──
                with gr.Tab("📊  Growth Score"):
                    gr.HTML('''<div class="ph"><div class="ph-t">📊 Growth Score</div>
<div class="ph-s">6-dimension growth rating · Revenue growth · Market position · Churn · NPS · Innovation · A+ to D grade</div></div>''')
                    with gr.Tabs():
                        with gr.Tab("Upload Business Data"):
                            gs_file = gr.File(label="Upload monthly business CSV (leave empty for sample 12-month data)",
                                              file_types=[".csv",".xlsx",".xls"])
                            gs_file_btn = gr.Button("▶  Calculate Growth Score", variant="primary", elem_classes=["fw"])
                            gs_use_manual = gr.State(False)

                        with gr.Tab("Manual Entry"):
                            gr.Markdown("### Enter your key growth metrics")
                            with gr.Row():
                                gs_rev_growth = gr.Number(label="Revenue Growth % (YTD)", value=20)
                                gs_gm         = gr.Number(label="Gross Margin %", value=40)
                                gs_share      = gr.Number(label="Market Share %", value=5)
                            with gr.Row():
                                gs_churn      = gr.Number(label="Monthly Churn Rate %", value=4)
                                gs_nps        = gr.Number(label="NPS Score", value=35)
                                gs_new_custs  = gr.Number(label="New Customers / Month", value=80)
                            with gr.Row():
                                gs_mktg_roi   = gr.Number(label="Marketing ROI (x)", value=3.0)
                                gs_rnd_pct    = gr.Number(label="R&D % of Revenue", value=3.0)
                                gs_runway     = gr.Number(label="Cash Runway (months)", value=18)
                            gs_manual_btn = gr.Button("▶  Calculate Growth Score", variant="primary", elem_classes=["fw"])
                            gs_use_manual2 = gr.State(True)

                    gs_status = gr.Markdown()
                    gs_dashboard = gr.HTML()

                    gs_file_btn.click(
                        fn=lambda f: run_growth_analysis(f, False),
                        inputs=[gs_file], outputs=[gs_dashboard, gs_status])
                    gs_manual_btn.click(
                        fn=lambda rv,gm,sh,ch,nps,nc,mr,rd,rw: run_growth_analysis(
                            None, True,
                            revenue_growth_pct=rv, gross_margin_pct=gm, market_share_pct=sh,
                            churn_rate_pct=ch, nps_score=nps, new_customers_monthly=nc,
                            marketing_roi=mr, rnd_pct_revenue=rd, cash_runway_months=rw),
                        inputs=[gs_rev_growth,gs_gm,gs_share,gs_churn,gs_nps,gs_new_custs,gs_mktg_roi,gs_rnd_pct,gs_runway],
                        outputs=[gs_dashboard, gs_status])

                # ── Market Entry ──
                with gr.Tab("🗺️  Market Entry"):
                    gr.HTML('''<div class="ph"><div class="ph-t">🗺️ Market Entry Analyzer</div>
<div class="ph-s">18 Indian cities scored · Entry cost · Revenue opportunity · Break-even timeline · Top recommendation</div></div>''')
                    gr.Markdown("Enter your business details to see which Indian city/market to expand into next.")
                    with gr.Row():
                        me_cat    = gr.Textbox(label="Business Category", placeholder="e.g. Electronics, Fashion, Grocery", value="Electronics")
                        me_rev    = gr.Number(label="Current Monthly Revenue (Rs.)", value=500000, minimum=0)
                    with gr.Row():
                        me_budget = gr.Number(label="Expansion Budget (Rs. Lakhs)", value=20, minimum=1)
                        me_risk   = gr.Dropdown(label="Risk Appetite", choices=["Low","Medium","High"], value="Medium")
                    me_btn    = gr.Button("▶  Analyze All 18 Markets", variant="primary", elem_classes=["fw"])
                    me_status = gr.Markdown()
                    me_html   = gr.HTML()
                    me_btn.click(fn=run_market_analysis, inputs=[me_cat,me_rev,me_budget,me_risk],
                                 outputs=[me_html, me_status])

                # ── Competitor Benchmarking ──
                with gr.Tab("⚔️  Competitor Benchmark"):
                    gr.HTML('''<div class="ph"><div class="ph-t">⚔️ Competitor Benchmarking</div>
<div class="ph-s">KMeans clustering · Composite scoring · Your position · Premium vs Value vs Mid-market</div></div>''')
                    gr.Markdown("""Upload a competitor CSV or leave empty to use sample data.
**Columns:** `Competitor, Revenue_Cr, Market_Share_Pct, Price_Index, Product_Quality, Brand_Strength, Digital_Presence, Customer_Rating, Headcount`
Include a row for **"Our Business"** to see your position.""")
                    cb_file   = gr.File(label="Upload Competitor CSV (leave empty for sample)", file_types=[".csv",".xlsx",".xls"])
                    cb_btn    = gr.Button("▶  Run Competitor Analysis", variant="primary", elem_classes=["fw"])
                    cb_status = gr.Markdown()
                    cb_html   = gr.HTML()
                    cb_btn.click(fn=run_competitor_benchmark, inputs=[cb_file], outputs=[cb_html, cb_status])

                # ── Pricing Optimization ──
                with gr.Tab("💰  Pricing Optimizer"):
                    gr.HTML('''<div class="ph"><div class="ph-t">💰 Pricing Optimization Engine</div>
<div class="ph-s">Demand elasticity model · Optimal price point · Competitor comparison · Profit uplift</div></div>''')
                    with gr.Tabs():
                        with gr.Tab("Upload Business Data"):
                            pr_file = gr.File(label="Upload CSV with Price, Units, COGS columns (empty = sample)",
                                              file_types=[".csv",".xlsx",".xls"])
                            pr_file_btn = gr.Button("▶  Optimize Pricing", variant="primary", elem_classes=["fw"])
                            pr_use_manual = gr.State(False)

                        with gr.Tab("Manual Entry"):
                            with gr.Row():
                                pr_price  = gr.Number(label="Current Selling Price (Rs.)", value=300)
                                pr_units  = gr.Number(label="Current Monthly Units Sold", value=1500)
                            with gr.Row():
                                pr_comp   = gr.Number(label="Main Competitor Price (Rs.)", value=310)
                                pr_cost   = gr.Number(label="Cost Per Unit (Rs.)", value=180)
                            pr_elast      = gr.Slider(label="Price Elasticity (how sensitive customers are to price)",
                                                      minimum=-3.0, maximum=-0.5, value=-1.5, step=0.1)
                            pr_manual_btn = gr.Button("▶  Find Optimal Price", variant="primary", elem_classes=["fw"])
                            pr_use_manual2 = gr.State(True)

                    pr_status = gr.Markdown()
                    pr_html   = gr.HTML()
                    pr_file_btn.click(
                        fn=lambda f: run_pricing_analysis(f,False,0,0,0,0,0),
                        inputs=[pr_file], outputs=[pr_html, pr_status])
                    pr_manual_btn.click(
                        fn=lambda p,u,c,co,e: run_pricing_analysis(None,True,p,u,c,co,e),
                        inputs=[pr_price,pr_units,pr_comp,pr_cost,pr_elast],
                        outputs=[pr_html, pr_status])

                # ── What-If Simulator ──
                with gr.Tab("🔮  What-If Simulator"):
                    gr.HTML('''<div class="ph"><div class="ph-t">🔮 What-If Growth Simulator</div>
<div class="ph-s">Simulate revenue under Conservative, Base, or Aggressive scenarios · 3-24 month projection</div></div>''')
                    with gr.Row():
                        wi_base_rev    = gr.Number(label="Current Monthly Revenue (Rs.)", value=500000)
                        wi_base_growth = gr.Number(label="Current Annual Growth Rate %", value=20)
                        wi_months      = gr.Slider(label="Projection Months", minimum=3, maximum=24, value=12, step=3)
                    wi_scenario = gr.Dropdown(label="Scenario",
                                             choices=["Conservative","Base Case","Aggressive","Custom"],
                                             value="Base Case")
                    gr.Markdown("#### Custom Levers (only used when Scenario = Custom)")
                    with gr.Row():
                        wi_mktg   = gr.Slider(label="Marketing Spend Multiplier", minimum=0.5, maximum=3.0, value=1.2, step=0.1)
                        wi_price  = gr.Slider(label="Price Increase %", minimum=-10, maximum=20, value=3, step=1)
                    with gr.Row():
                        wi_churn  = gr.Slider(label="Churn Reduction (pp)", minimum=-5, maximum=5, value=-0.5, step=0.5)
                        wi_market = gr.Slider(label="Market Share Gain (pp)", minimum=0, maximum=5, value=0.2, step=0.1)
                    wi_btn    = gr.Button("▶  Run Simulation", variant="primary", elem_classes=["fw"])
                    wi_status = gr.Markdown()
                    wi_html   = gr.HTML()
                    wi_btn.click(fn=run_whatif,
                                 inputs=[wi_base_rev,wi_base_growth,wi_scenario,
                                         wi_mktg,wi_price,wi_churn,wi_market,wi_months],
                                 outputs=[wi_html, wi_status])

                # ── AI Strategy + PDF ──
                with gr.Tab("🤖  AI Strategy + PDF"):
                    gr.HTML('''<div class="ph"><div class="ph-t">🤖 AI Growth Strategy & Investor Report</div>
<div class="ph-s">Gemini AI · 90-day action plan · Investor talking points · Downloadable PDF report</div></div>''')
                    gr.Markdown("""
**Run the other tabs first** (Growth Score, Market Entry, Pricing, Competitor), then come here for a complete AI strategy.

The AI will generate:
- Executive summary with key insights
- Top 3 immediate opportunities with timelines
- Market expansion playbook
- 90-day action plan (weeks 1-4, 5-8, 9-12)
- Investor talking points for fundraising

Then download as a professional PDF report.

Set `GEMINI_API_KEY` in HF Spaces → Settings → Secrets to enable.
""")
                    with gr.Row():
                        ai_biz_name = gr.Textbox(label="Business Name", placeholder="e.g. Sharma Electronics", scale=2)
                        ai_category = gr.Textbox(label="Category", placeholder="e.g. Electronics", scale=1)
                        ai_founded  = gr.Textbox(label="Founded Year", placeholder="e.g. 2020", scale=1)
                    ai_btn    = gr.Button("▶  Generate AI Growth Strategy + PDF Report", variant="primary", elem_classes=["fw"])
                    ai_status_out = gr.Markdown()
                    ai_strategy   = gr.Markdown(label="AI Growth Strategy")
                    ai_pdf        = gr.File(label="📥 Download Investor PDF Report")
                    ai_btn.click(fn=run_ai_strategy_and_pdf,
                                 inputs=[ai_biz_name, ai_category, ai_founded],
                                 outputs=[ai_strategy, ai_pdf])


demo.launch()
