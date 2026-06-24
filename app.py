# ============================================================
#  ALLWORKSS BUSINESS INTELLIGENCE SUITE — app.py
#  FINAL WORKING VERSION
#  Uses gr.Tabs (hidden nav) + Python gr.update for sidebar sync
#  This is the ONLY approach that works reliably in Gradio 6 SSR
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

DOC_CHOICES = ["Auto Detect","GSTR-1 (Outward Supplies)","GSTR-3B (Monthly Summary)",
    "GSTR-9 (Annual Return)","ITR (Income Tax Return)","Balance Sheet",
    "P&L (Profit & Loss)","MCA / Company Filing","Manual / Informal Business"]
DOC_MAP = {"Auto Detect":"Auto Detect","GSTR-1 (Outward Supplies)":"GSTR-1",
    "GSTR-3B (Monthly Summary)":"GSTR-3B","GSTR-9 (Annual Return)":"GSTR-9",
    "ITR (Income Tax Return)":"ITR","Balance Sheet":"Balance Sheet",
    "P&L (Profit & Loss)":"P&L","MCA / Company Filing":"MCA",
    "Manual / Informal Business":"Manual/Informal"}

# ── Tab IDs in order ──
TABS = ["web","docs","manual","full",
        "vendors","import_csv","add_vendor","logistics",
        "m3f","m3a","m3p","m3s"]
TAB_MOD = {"web":"m1","docs":"m1","manual":"m1","full":"m1",
           "vendors":"m2","import_csv":"m2","add_vendor":"m2","logistics":"m2",
           "m3f":"m3","m3a":"m3","m3p":"m3","m3s":"m3"}
MOD_FIRST = {"m1":"web","m2":"vendors","m3":"m3f"}
MOD_TABS = {
    "m1":["web","docs","manual","full"],
    "m2":["vendors","import_csv","add_vendor","logistics"],
    "m3":["m3f","m3a","m3p","m3s"],
}

CSS = """
html,body{height:100%;margin:0;padding:0;overflow:hidden;}
.gradio-container{height:100vh!important;max-height:100vh!important;overflow:hidden!important;padding:0!important;max-width:100%!important;}
footer,.footer{display:none!important;}
/* Main layout */
.aw-wrap{display:flex!important;height:100vh!important;overflow:hidden!important;gap:0!important;}
/* Sidebar */
.aw-nav{width:220px!important;min-width:220px!important;max-width:220px!important;height:100vh!important;max-height:100vh!important;overflow-y:auto!important;overflow-x:hidden!important;background:#111!important;border-right:1px solid #1e1e1e!important;flex-shrink:0!important;}
.aw-nav::-webkit-scrollbar{width:3px;}.aw-nav::-webkit-scrollbar-thumb{background:#222;}
/* Content */
.aw-main{flex:1!important;height:100vh!important;overflow-y:auto!important;background:#0f0f0f!important;}
.aw-main::-webkit-scrollbar{width:5px;}.aw-main::-webkit-scrollbar-thumb{background:#2a2a2a;border-radius:3px;}
.aw-page{padding:22px 24px;max-width:1080px;}
/* Logo */
.aw-logo{padding:18px 14px 14px;border-bottom:1px solid #1e1e1e;}
.aw-logo-t{font-size:14px;font-weight:700;color:#1D9E75;}
.aw-logo-s{font-size:9px;color:#444;letter-spacing:.08em;text-transform:uppercase;margin-top:3px;}
/* Module header — explicit styles, NO all:unset */
.aw-nav button.mbtn{
    display:flex!important;justify-content:space-between!important;align-items:center!important;
    width:100%!important;min-height:38px!important;padding:11px 14px!important;box-sizing:border-box!important;
    font-size:9px!important;font-weight:700!important;letter-spacing:.09em!important;
    text-transform:uppercase!important;color:#555!important;cursor:pointer!important;
    border:none!important;border-bottom:1px solid #1e1e1e!important;border-left:3px solid transparent!important;
    border-radius:0!important;background:transparent!important;box-shadow:none!important;
    font-family:system-ui,-apple-system,sans-serif!important;line-height:1.2!important;
}
.aw-nav button.mbtn:hover{background:#181818!important;color:#888!important;}
.aw-nav button.mbtn.mopen{color:#1D9E75!important;background:#0c1e16!important;border-left:3px solid #1D9E75!important;}
/* Sub-menu */
.aw-sub{background:#0d0d0d!important;}
.aw-sub > div,.aw-sub > .gap{gap:0!important;}
/* Nav item buttons */
.aw-nav button.nbtn{
    display:flex!important;align-items:center!important;gap:8px!important;
    width:100%!important;min-height:34px!important;padding:9px 14px 9px 20px!important;box-sizing:border-box!important;
    font-size:12px!important;color:#666!important;cursor:pointer!important;
    border:none!important;border-left:2px solid transparent!important;border-radius:0!important;
    background:transparent!important;box-shadow:none!important;
    font-family:system-ui,-apple-system,sans-serif!important;line-height:1.2!important;
}
.aw-nav button.nbtn:hover{background:#161616!important;color:#bbb!important;}
.aw-nav button.nbtn.nact{color:#1D9E75!important;background:#0a1c13!important;border-left:2px solid #1D9E75!important;font-weight:600!important;}
/* Page header */
.ph{margin-bottom:16px;padding-bottom:12px;border-bottom:1px solid #1e1e1e;}
.ph-t{font-size:19px;font-weight:600;color:#e0e0e0;margin-bottom:3px;}
.ph-s{font-size:12px;color:#555;}
/* Utilities */
button.fw{width:100%!important;}
/* Hide Gradio tab nav bar completely */
.aw-tabs > .tab-nav{display:none!important;visibility:hidden!important;height:0!important;overflow:hidden!important;}
/* Ensure all module header buttons always visible regardless of sub-menu state */
.aw-nav > .gap > button.mbtn,
.aw-nav button.mbtn { display:flex!important; }
/* Mobile */
@media(max-width:600px){
    .aw-wrap{flex-direction:column!important;height:auto!important;overflow:visible!important;}
    .aw-nav{width:100%!important;height:auto!important;}
    .aw-main{height:auto!important;}
}
"""

# ── Sidebar state → nav button classes + sub visibility ──
def sidebar_state(active_tab: str, active_mod: str):
    """Returns: 12 nav btn updates + 3 mod btn updates + 3 sub visibility updates"""
    nb = [gr.update(elem_classes=["nbtn","nact"] if t==active_tab else ["nbtn"]) for t in TABS]
    mb = [gr.update(elem_classes=["mbtn","mopen"] if m==active_mod else ["mbtn"]) for m in ["m1","m2","m3"]]
    sv = [gr.update(visible=(m==active_mod)) for m in ["m1","m2","m3"]]
    return nb + mb + sv  # 18 updates

# ── Handlers ──
def h_web(url):
    if not url or not url.strip(): return "Enter a URL.","","","","",None
    r = run_full_audit(url.strip())
    if "error" in r: return f"Error: {r['error']}","","","","",None
    s,m,h,l,c,co,sen,p = r["scores"],r["metadata"],r["headings"],r["links"],r["content"],r["compliance"],r["sentiment"],r["perf"]
    sug = r["suggestions"]
    sc = (f"## Score: {s['overall']}/100 — {s['grade']}\n| Dimension | Score | Status |\n|---|---|---|\n"
          +"\n".join([f"| {k} | {v}/100 | {'Good' if v>=70 else 'Needs Work'} |"
                      for k,v in [("SEO",s["seo"]),("Content",s["content"]),("Trust",s["trust"]),
                                  ("Performance",s["performance"]),("Compliance",s["compliance"])]])
          +f"\n\n**Load:** {p['load_time_seconds']}s | **Mobile:** {'Yes' if m['has_viewport'] else 'No'} | **URL:** {r['url']}")
    mt=(f"**Title:** {m['title'] or 'NOT FOUND'}\n**Description:** {m['description'] or 'NOT FOUND'}\n"
        f"**H1:** {h['h1_count']} | **H2:** {h['h2_count']} | **H3:** {h['h3_count']}\n**H1 Text:** {h['h1'][:2]}")
    se=(f"**Words:** {c['word_count']} | **Paragraphs:** {c['paragraph_count']}\n"
        f"**Images:** {c['image_count']} ({c['images_missing_alt']} missing alt)\n"
        f"**Contact:** {'Yes' if c['has_contact_info'] else 'No'} | **Testimonials:** {'Yes' if c['has_testimonials'] else 'No'} | **Privacy:** {'Yes' if c['has_privacy_policy'] else 'No'}\n"
        f"**Tone:** {sen['tone']} — {sen['tone_detail']}\n**Objectivity:** {sen['objectivity']} — {sen['objectivity_detail']}")
    gs  = "Found: "+", ".join(co["gstins_found"]) if co["has_gstin"] else "NOT FOUND on website"
    cin = "Found: "+", ".join(co["cins_found"]) if co["has_cin"] else "Not found"
    brk = "\n".join([f"  - {b['url']} (Status: {b['status']})" for b in l["broken_links"]]) if l["broken_links"] else "No broken links"
    co2 = f"**GSTIN:** {gs}\n**CIN:** {cin}\n**Links:** {l['total_links']} | **Broken:** {len(l['broken_links'])} | **Empty:** {l['empty_anchors']}\n{brk}"
    sg=""
    for t,hdr in [("critical","### Critical Issues"),("warning","### Warnings"),("good","### What is Working")]:
        items=[x for x in sug if x["type"]==t]
        if items: sg+=hdr+"\n"+"\n".join(f"- {x['msg']}" for x in items)+"\n\n"
    return sc,mt,se,co2,sg,generate_pdf_report(url,s,sug,m,co,sen,p)

def h_doc(f,dd): return analyze_documents_v2(f,DOC_MAP.get(dd,"Auto Detect"))
def h_man(sa,pu,te,re,sl,el,rw,tr,oe,ca,st,rc,pa,bn,pe):
    return process_manual_entry(sa,pu,te,re,sl,el,rw,tr,oe,ca,st,rc,pa,bn,pe)
def h_full(url,files,dd):
    hv=bool(url and url.strip()); hd=bool(files and len(files)>0)
    if not hv and not hd: return "Enter URL or upload docs.","","","","",None,""
    sm=mm=se=cm=su=dm=""; pdf=None
    if hv: sm,mm,se,cm,su,pdf=h_web(url)
    if hd: dm=analyze_documents_v2(files,DOC_MAP.get(dd,"Auto Detect"))
    return sm,mm,se,cm,su,pdf,dm

# ── App ──
with gr.Blocks(title="Allworkss BI Suite", css=CSS) as demo:

    st_tab = gr.State("web")
    st_mod = gr.State("m1")

    # Outer flex wrapper via HTML — safe because it's just a div wrapper
    with gr.Row(elem_classes=["aw-wrap"]):

        # ════════ SIDEBAR ════════
        with gr.Column(scale=0, min_width=220, elem_classes=["aw-nav"]):
            gr.HTML('<div class="aw-logo"><div class="aw-logo-t">Allworkss BI</div>'
                    '<div class="aw-logo-s">360° AI for SMEs</div></div>')

            # Module 1 header + sub
            mb1 = gr.Button("MODULE 1 — AUDITOR  ▾", elem_classes=["mbtn","mopen"])
            with gr.Column(visible=True, elem_classes=["aw-sub"]) as sb1:
                nb1  = gr.Button("🌐  Website Audit",   elem_classes=["nbtn","nact"])
                nb2  = gr.Button("📄  Documents",        elem_classes=["nbtn"])
                nb3  = gr.Button("✏️  Manual Entry",    elem_classes=["nbtn"])
                nb4  = gr.Button("🔍  Full Audit",       elem_classes=["nbtn"])

            # Module 2 header + sub
            mb2 = gr.Button("MODULE 2 — SUPPLY CHAIN  ▾", elem_classes=["mbtn"])
            with gr.Column(visible=False, elem_classes=["aw-sub"]) as sb2:
                nb5  = gr.Button("🏭  Vendor Intelligence",  elem_classes=["nbtn"])
                nb6  = gr.Button("📥  Import CSV",           elem_classes=["nbtn"])
                nb7  = gr.Button("➕  Add Vendor",           elem_classes=["nbtn"])
                nb8  = gr.Button("🚚  Logistics Router",     elem_classes=["nbtn"])

            # Module 3 header + sub
            mb3 = gr.Button("MODULE 3 — INVENTORY  ▾", elem_classes=["mbtn"])
            with gr.Column(visible=False, elem_classes=["aw-sub"]) as sb3:
                nb9  = gr.Button("📈  Demand Forecast",  elem_classes=["nbtn"])
                nb10 = gr.Button("🔔  Stock Alerts",     elem_classes=["nbtn"])
                nb11 = gr.Button("📋  Purchase Orders",  elem_classes=["nbtn"])
                nb12 = gr.Button("🎲  Scenario Sim",     elem_classes=["nbtn"])

        # ════════ CONTENT — gr.Tabs with hidden nav ════════
        with gr.Column(scale=1, elem_classes=["aw-main"]):
            with gr.Tabs(selected="web", elem_classes=["aw-tabs"]) as tabs:

                with gr.Tab("Website Audit", id="web", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🌐 Website Audit</div>'
                            '<div class="ph-s">Full AI-powered audit — SEO, compliance, sentiment, performance</div></div>')
                    w_url=gr.Textbox(label="Business Website URL",placeholder="https://yourbusiness.com")
                    w_btn=gr.Button("Run Website Audit",variant="primary",elem_classes=["fw"])
                    w_sc=gr.Markdown(); w_mt=gr.Markdown(); w_se=gr.Markdown()
                    w_co=gr.Markdown(); w_sg=gr.Markdown(); w_pdf=gr.File(label="Download PDF Report")
                    w_btn.click(fn=h_web,inputs=[w_url],outputs=[w_sc,w_mt,w_se,w_co,w_sg,w_pdf])
                    gr.Examples(examples=[["https://www.flipkart.com"],["https://www.tatacliq.com"],
                                          ["https://www.nykaa.com"],["https://www.hitechengineer.in"]],
                                inputs=w_url,label="Quick examples")

                with gr.Tab("Documents", id="docs", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">📄 Document Analyzer</div>'
                            '<div class="ph-s">GST Returns | ITR | Balance Sheet | P&L | MCA | Informal notes</div></div>')
                    d_dd=gr.Dropdown(choices=DOC_CHOICES,value="Auto Detect",label="Document Type")
                    d_f=gr.File(label="Upload — PDF, CSV, Excel, TXT, DOCX",
                                file_types=[".pdf",".csv",".xlsx",".xls",".txt",".docx"],file_count="multiple")
                    d_btn=gr.Button("Analyze Documents",variant="primary",elem_classes=["fw"])
                    d_out=gr.Markdown()
                    d_btn.click(fn=h_doc,inputs=[d_f,d_dd],outputs=[d_out])

                with gr.Tab("Manual Entry", id="manual", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">✏️ Manual Entry</div>'
                            '<div class="ph-s">For small shops, traders, informal businesses — no documents needed</div></div>')
                    me_n=gr.Textbox(label="Business Name",placeholder="e.g. Sharma General Store")
                    me_p=gr.Textbox(label="Period / Financial Year",placeholder="e.g. April 2024 - March 2025")
                    gr.Markdown("#### Revenue")
                    with gr.Row():
                        me_sa=gr.Number(label="Total Sales / Revenue (Rs.)",value=0,minimum=0)
                        me_pu=gr.Number(label="Total Purchases / COGS (Rs.)",value=0,minimum=0)
                    gr.Markdown("#### Expenses — fill individually OR enter total below")
                    with gr.Row():
                        me_re=gr.Number(label="Rent (Rs.)",value=0,minimum=0)
                        me_sl=gr.Number(label="Salaries / Labour (Rs.)",value=0,minimum=0)
                        me_el=gr.Number(label="Electricity / Utilities (Rs.)",value=0,minimum=0)
                    with gr.Row():
                        me_rw=gr.Number(label="Raw Material (Rs.)",value=0,minimum=0)
                        me_tr=gr.Number(label="Transport / Delivery (Rs.)",value=0,minimum=0)
                        me_oe=gr.Number(label="Other Expenses (Rs.)",value=0,minimum=0)
                    me_te=gr.Number(label="Total Expenses — fill ONLY if skipping items above (Rs.)",value=0,minimum=0)
                    gr.Markdown("#### Cash & Balances")
                    with gr.Row():
                        me_ca=gr.Number(label="Closing Cash / Bank Balance (Rs.)",value=0,minimum=0)
                        me_st=gr.Number(label="Closing Stock / Inventory (Rs.)",value=0,minimum=0)
                    with gr.Row():
                        me_rc=gr.Number(label="Outstanding Receivables — Udhar Lena (Rs.)",value=0,minimum=0)
                        me_pa=gr.Number(label="Outstanding Payables — Udhar Dena (Rs.)",value=0,minimum=0)
                    me_btn=gr.Button("Generate Business Report",variant="primary",elem_classes=["fw"])
                    me_out=gr.Markdown()
                    me_btn.click(fn=h_man,
                                 inputs=[me_sa,me_pu,me_te,me_re,me_sl,me_el,
                                         me_rw,me_tr,me_oe,me_ca,me_st,me_rc,me_pa,me_n,me_p],
                                 outputs=[me_out])

                with gr.Tab("Full Audit", id="full", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🔍 Full Combined Audit</div>'
                            '<div class="ph-s">URL audit + Document analysis together — both optional</div></div>')
                    fa_u=gr.Textbox(label="Website URL (optional)",placeholder="https://yourbusiness.com")
                    fa_d=gr.Dropdown(choices=DOC_CHOICES,value="Auto Detect",label="Document Type")
                    fa_f=gr.File(label="Upload Documents (optional)",
                                 file_types=[".pdf",".csv",".xlsx",".xls",".txt",".docx"],file_count="multiple")
                    fa_btn=gr.Button("Run Full Audit",variant="primary",elem_classes=["fw"])
                    gr.Markdown("### Website Audit Results")
                    fa_sc=gr.Markdown(); fa_mt=gr.Markdown()
                    fa_se=gr.Markdown(); fa_co=gr.Markdown()
                    fa_sg=gr.Markdown(); fa_pdf=gr.File(label="PDF")
                    gr.Markdown("### Document Analysis Results"); fa_dm=gr.Markdown()
                    fa_btn.click(fn=h_full,inputs=[fa_u,fa_f,fa_d],
                                 outputs=[fa_sc,fa_mt,fa_se,fa_co,fa_sg,fa_pdf,fa_dm])

                with gr.Tab("Vendor Intelligence", id="vendors", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🏭 Vendor Intelligence</div>'
                            '<div class="ph-s">ML-scored vendors — select one to see profile, routes and 3PL</div></div>')
                    with gr.Row():
                        with gr.Column(scale=1,min_width=200):
                            gr.Markdown("**Vendors**")
                            v_li=gr.HTML(value=format_vendor_list_html())
                            v_sel=gr.Dropdown(choices=get_vendor_names(),label="Select Vendor",interactive=True)
                            gr.Markdown("**Route parameters:**")
                            v_wt=gr.Slider(label="Weight (kg)",minimum=1,maximum=5000,value=50,step=10)
                            v_di=gr.Slider(label="Distance (km)",minimum=1,maximum=1500,value=30,step=5)
                            v_btn=gr.Button("View Vendor Detail",variant="primary")
                        with gr.Column(scale=2):
                            v_det=gr.HTML(value="<div style='padding:40px;color:#555;text-align:center;'>Select a vendor and click View Vendor Detail.</div>")
                    v_btn.click(fn=format_vendor_detail,inputs=[v_sel,v_wt,v_di],outputs=[v_det])
                    v_sel.change(fn=format_vendor_detail,inputs=[v_sel,v_wt,v_di],outputs=[v_det])

                with gr.Tab("Import CSV", id="import_csv", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">📥 Import Vendors from CSV</div>'
                            '<div class="ph-s">Upload supplier CSV or Excel — auto-detects columns, ML scoring applied</div></div>')
                    gr.Markdown("**Sample:** `Supplier Name, On Time Delivery %, Quality Score %, Lead Time Days, Reliability %, Location, Route, Transport Mode`")
                    ic_f=gr.File(label="Upload CSV / Excel",file_types=[".csv",".xlsx",".xls",".txt"],file_count="multiple")
                    ic_btn=gr.Button("Import Vendors",variant="primary",elem_classes=["fw"])
                    ic_st=gr.Markdown(); ic_li=gr.HTML(); ic_dd=gr.Dropdown(label="",choices=[],visible=False)
                    ic_btn.click(fn=import_vendors_from_csv,inputs=[ic_f],outputs=[ic_st,ic_li,ic_dd])

                with gr.Tab("Add Vendor", id="add_vendor", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">➕ Add Vendor Manually</div>'
                            '<div class="ph-s">Enter vendor details — ML scores instantly on save</div></div>')
                    with gr.Row():
                        av_n=gr.Textbox(label="Vendor / Supplier Name *",placeholder="e.g. MetalWorks Co")
                        av_l=gr.Textbox(label="City / Location",placeholder="e.g. Mumbai")
                    with gr.Row():
                        av_g=gr.Textbox(label="GSTIN",placeholder="27AABCU9603R1ZX")
                        av_c=gr.Textbox(label="Contact (Phone / Email)")
                    gr.Markdown("#### Performance Metrics")
                    with gr.Row():
                        av_ot=gr.Number(label="On-Time Delivery %",value=80,minimum=0,maximum=100)
                        av_q=gr.Number(label="Quality Score %",value=80,minimum=0,maximum=100)
                        av_r=gr.Number(label="Reliability %",value=80,minimum=0,maximum=100)
                    with gr.Row():
                        av_ld=gr.Number(label="Lead Time (days)",value=7,minimum=1)
                        av_pr=gr.Number(label="Avg Unit Price (Rs.)",value=0,minimum=0)
                    gr.Markdown("#### Route & Transport")
                    with gr.Row():
                        av_ro=gr.Textbox(label="Route",placeholder="e.g. Mumbai to Pune")
                        av_mo=gr.Dropdown(choices=["Bike","Auto","Tata Ace","Truck","Air","Rail","Not specified"],
                                          value="Truck",label="Transport Mode")
                    av_btn=gr.Button("Add Vendor",variant="primary",elem_classes=["fw"])
                    av_st=gr.Markdown(); av_li=gr.HTML(); av_dd=gr.Dropdown(label="",choices=[],visible=False)
                    av_btn.click(fn=add_vendor_manual,
                                 inputs=[av_n,av_g,av_c,av_l,av_ot,av_q,av_ld,av_pr,av_r,av_ro,av_mo],
                                 outputs=[av_st,av_li,av_dd])

                with gr.Tab("Logistics Router", id="logistics", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🚚 Smart Logistics Router</div>'
                            '<div class="ph-s">Real-time rates across 6 providers · Road map · Gemini AI parcel scanner</div></div>')
                    gr.Markdown("### Step 1 — AI Parcel Scanner *(Optional)*")
                    gr.Markdown("Upload a parcel photo. **Gemini Vision** estimates weight and dimensions. Set `GEMINI_API_KEY` in HF Spaces → Settings → Secrets.")
                    lr_img=gr.Image(label="Upload or Take Photo of Parcel",type="filepath",sources=["upload","webcam"])
                    lr_sb=gr.Button("Scan Parcel with Gemini AI",variant="secondary")
                    lr_ph=gr.HTML()
                    gr.Markdown("---")
                    gr.Markdown("### Step 2 — Enter Route & Shipment Weight")
                    with gr.Row():
                        lr_pu=gr.Textbox(label="Pick-up Address",placeholder="e.g. Andheri East Mumbai",scale=2)
                        lr_do=gr.Textbox(label="Drop-off Address",placeholder="e.g. Hinjewadi Pune",scale=2)
                        lr_wt=gr.Number(label="Weight (kg)",value=1.0,minimum=0.1,step=0.5,scale=1)
                    lr_btn=gr.Button("Find Best Rates — Scan All 6 Providers",variant="primary",elem_classes=["fw"])
                    gr.Markdown("### Route Map"); lr_map=gr.HTML()
                    gr.Markdown("### Rate Comparison — All Providers"); lr_rates=gr.HTML()
                    def lr_scan(img,wt):
                        if img is None: return "<div style='color:#888;padding:12px;background:#1a1a1a;border-radius:8px;'>Upload a parcel photo first.</div>",wt
                        from m2_logistics_router import scan_parcel_gemini,format_parcel_scan_html
                        sc=scan_parcel_gemini(img); return format_parcel_scan_html(sc),(sc["weight_kg"] if sc.get("success") else wt)
                    lr_sb.click(fn=lr_scan,inputs=[lr_img,lr_wt],outputs=[lr_ph,lr_wt])
                    def lr_run(p,d,w,img):
                        ph,mh,rh,wt=run_logistics_router(p,d,w,img); return ph,mh,rh,wt
                    lr_btn.click(fn=lr_run,inputs=[lr_pu,lr_do,lr_wt,lr_img],outputs=[lr_ph,lr_map,lr_rates,lr_wt])

                with gr.Tab("Demand Forecast", id="m3f", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">📈 Demand Forecast</div>'
                            '<div class="ph-s">ARIMA + Prophet + LSTM ensemble — SKU-level 30/60/90 day forecasts</div></div>')
                    with gr.Row():
                        m3f_file=gr.File(label="Upload Sales CSV/Excel (leave empty for sample data)",
                                         file_types=[".csv",".xlsx",".xls"],scale=3)
                        with gr.Column(scale=1):
                            m3f_days=gr.Slider(label="Forecast Horizon (days)",minimum=7,maximum=90,value=30,step=7)
                            m3f_svc=gr.Slider(label="Service Level %",minimum=0.90,maximum=0.99,value=0.95,step=0.01)
                            m3f_lead=gr.Number(label="Default Lead Time (days)",value=7,minimum=1)
                    m3f_btn=gr.Button("Run Forecast — ARIMA + Prophet + LSTM",variant="primary",elem_classes=["fw"])
                    m3f_sum=gr.HTML(); m3f_ch=gr.HTML()
                    gr.Markdown("**CSV Format:** `Date,SKU,Product,Category,Quantity_Sold,Unit_Price,Stock_Level,Lead_Time_Days`")
                    m3f_btn.click(fn=lambda f,d,s,l:run_inventory_forecast(f,int(d),s,int(l))[:2],
                                  inputs=[m3f_file,m3f_days,m3f_svc,m3f_lead],outputs=[m3f_sum,m3f_ch])

                with gr.Tab("Stock Alerts", id="m3a", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🔔 Stock Alerts & Reorder Intelligence</div>'
                            '<div class="ph-s">Reorder points, safety stock, EOQ — color-coded by urgency</div></div>')
                    m3a_file=gr.File(label="Upload Sales CSV/Excel (or leave empty for sample)",file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3a_days=gr.Slider(label="Forecast Days",minimum=7,maximum=90,value=30,step=7)
                        m3a_svc=gr.Slider(label="Service Level",minimum=0.90,maximum=0.99,value=0.95,step=0.01)
                        m3a_lead=gr.Number(label="Lead Time (days)",value=7,minimum=1)
                    m3a_btn=gr.Button("Generate Stock Alerts",variant="primary",elem_classes=["fw"])
                    m3a_out=gr.HTML()
                    m3a_btn.click(fn=lambda f,d,s,l:run_inventory_forecast(f,int(d),s,int(l))[2],
                                  inputs=[m3a_file,m3a_days,m3a_svc,m3a_lead],outputs=[m3a_out])

                with gr.Tab("Purchase Orders", id="m3p", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">📋 Auto-Generate Purchase Orders</div>'
                            '<div class="ph-s">ML-driven PO generation for all SKUs below reorder point</div></div>')
                    m3p_file=gr.File(label="Upload Sales CSV/Excel (or leave empty for sample)",file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3p_days=gr.Slider(label="Forecast Days",minimum=7,maximum=90,value=30,step=7)
                        m3p_svc=gr.Slider(label="Service Level",minimum=0.90,maximum=0.99,value=0.95,step=0.01)
                        m3p_lead=gr.Number(label="Lead Time (days)",value=7,minimum=1)
                    m3p_btn=gr.Button("Generate Purchase Order",variant="primary",elem_classes=["fw"])
                    m3p_out=gr.Markdown()
                    m3p_btn.click(fn=lambda f,d,s,l:run_inventory_forecast(f,int(d),s,int(l))[3],
                                  inputs=[m3p_file,m3p_days,m3p_svc,m3p_lead],outputs=[m3p_out])

                with gr.Tab("Scenario Simulation", id="m3s", elem_classes=["aw-page"]):
                    gr.HTML('<div class="ph"><div class="ph-t">🎲 What-If Scenario Simulation</div>'
                            '<div class="ph-s">Test demand spikes, supplier delays, price hikes, stockouts</div></div>')
                    m3s_file=gr.File(label="Upload Sales CSV/Excel (or leave empty for sample)",file_types=[".csv",".xlsx",".xls"])
                    with gr.Row():
                        m3s_sku=gr.Dropdown(label="Select SKU",choices=["SKU001","SKU002","SKU003"],value="SKU001",interactive=True)
                        m3s_sc=gr.Dropdown(label="Scenario Type",
                                           choices=["demand_spike","demand_drop","supplier_delay","price_increase","stockout"],
                                           value="demand_spike")
                        m3s_par=gr.Number(label="Parameter (% or days)",value=30,minimum=1)
                    with gr.Row():
                        m3s_days=gr.Slider(label="Forecast Days",minimum=7,maximum=90,value=30,step=7)
                        m3s_lead=gr.Number(label="Lead Time (days)",value=7,minimum=1)
                    m3s_btn=gr.Button("Run Scenario",variant="primary",elem_classes=["fw"])
                    m3s_out=gr.HTML()
                    def upd_skus(f):
                        skus=get_sku_list(f); return gr.Dropdown(choices=skus,value=skus[0] if skus else "SKU001")
                    m3s_file.change(fn=upd_skus,inputs=[m3s_file],outputs=[m3s_sku])
                    m3s_btn.click(fn=lambda f,sk,sc,p,d,l:run_scenario_simulation(f,sk,sc,p,int(d),int(l)),
                                  inputs=[m3s_file,m3s_sku,m3s_sc,m3s_par,m3s_days,m3s_lead],outputs=[m3s_out])

    # ── Wire ALL navigation ──────────────────────────────
    # Sidebar nav buttons update: tabs.selected + 12 nav btn classes + 3 mod btn classes + 3 sub visibility
    # = 19 outputs total (1 tabs + 18 sidebar_state)
    ALL_NB = [nb1,nb2,nb3,nb4,nb5,nb6,nb7,nb8,nb9,nb10,nb11,nb12]
    ALL_MB = [mb1,mb2,mb3]
    ALL_SB = [sb1,sb2,sb3]
    SIDEBAR_OUT = ALL_NB + ALL_MB + ALL_SB  # 18 outputs
    ALL_OUT = [tabs, st_tab, st_mod] + SIDEBAR_OUT  # 21 outputs

    def do_nav(tab_id: str):
        mod = TAB_MOD.get(tab_id, "m1")
        nb  = [gr.update(elem_classes=["nbtn","nact"] if t==tab_id else ["nbtn"]) for t in TABS]
        mb  = [gr.update(elem_classes=["mbtn","mopen"] if m==mod else ["mbtn"]) for m in ["m1","m2","m3"]]
        sv  = [gr.update(visible=(m==mod)) for m in ["m1","m2","m3"]]
        return [gr.update(selected=tab_id), tab_id, mod] + nb + mb + sv  # 3+12+3+3=21

    # Wire page nav buttons
    for tab_id, btn in zip(TABS, ALL_NB):
        btn.click(fn=lambda t=tab_id: do_nav(t), inputs=[], outputs=ALL_OUT)

    # Wire module header buttons → first page of that module
    for mod_id, btn in zip(["m1","m2","m3"], ALL_MB):
        first = MOD_FIRST[mod_id]
        btn.click(fn=lambda t=first: do_nav(t), inputs=[], outputs=ALL_OUT)

demo.launch(theme=gr.themes.Soft(primary_hue="green"))