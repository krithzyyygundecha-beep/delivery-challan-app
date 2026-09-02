import os, json, webbrowser
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__, static_folder=".", static_url_path="")
DATA_DIR = os.path.join(os.path.dirname(__file__), "challans")
os.makedirs(DATA_DIR, exist_ok=True)
REC_FILE = os.path.join(DATA_DIR, "records.json")

DELETE_PASSWORD = "090676"

def load_r():
    if os.path.exists(REC_FILE):
        try:
            with open(REC_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_r(data):
    with open(REC_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def make_pdf(data, path):
    # 5.5 cm top margin for pre-printed letterhead
    doc = SimpleDocTemplate(
        path, 
        pagesize=A4, 
        rightMargin=20, 
        leftMargin=20, 
        topMargin=5.5 * cm, 
        bottomMargin=20
    )
    s = getSampleStyleSheet()
    normal = s["Normal"]
    normal.fontSize = 8
    normal.leading = 10
    
    elems = [
        Paragraph("<b>DELIVERY CHALLAN</b>", ParagraphStyle("T", parent=s["Heading1"], alignment=1, fontSize=13)),
        Paragraph("<font size=7 color=gray>Issued under Rule 55 of CGST / SGST Rules</font>", ParagraphStyle("S", alignment=1, spaceAfter=8))
    ]
    
    is_interstate = (data.get("sender_state", "").strip().lower() != data.get("receiver_state", "").strip().lower())
    
    hd = [
        [Paragraph(f"<b>Consignor (Sender):</b><br/>{data.get('sender_name','')}<br/>{data.get('sender_address','')}<br/>State: {data.get('sender_state','')}<br/>GSTIN: {data.get('sender_gstin','')}", normal),
         Paragraph(f"<b>Challan No:</b> {data.get('challan_no','')}<br/><b>Date:</b> {data.get('date','')}<br/><b>Reason:</b> {data.get('reason','')}", normal)],
        [Paragraph(f"<b>Consignee (Recipient):</b><br/>{data.get('receiver_name','')}<br/>{data.get('receiver_address','')}<br/>State: {data.get('receiver_state','')}<br/>GSTIN/PAN: {data.get('receiver_gstin','')}", normal),
         Paragraph(f"<b>Vehicle / Docket:</b> {data.get('vehicle_no','')}<br/><b>Place of Supply:</b> {data.get('receiver_state','')}", normal)]
    ]
    t_h = Table(hd, colWidths=[280, 275])
    t_h.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 3)
    ]))
    elems.extend([t_h, Spacer(1, 8)])
    
    # Tables with Gross Wt included
    if is_interstate:
        headers = ["Sr.", "Description", "HSN", "Qty", "Gross Wt", "Net Wt", "Rate (Rs.)", "Taxable (Rs.)", "IGST (Rs.)", "Total (Rs.)"]
        col_w = [20, 105, 50, 26, 45, 45, 55, 69, 65, 75]
    else:
        headers = ["Sr.", "Description", "HSN", "Qty", "Gross Wt", "Net Wt", "Rate (Rs.)", "Taxable (Rs.)", "CGST (Rs.)", "SGST (Rs.)", "Total (Rs.)"]
        col_w = [18, 95, 48, 25, 43, 43, 50, 63, 55, 55, 60]

    rows = [headers]
    tot_gross = 0
    tot_net = 0
    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    items = data.get("items", [])
    for i, itm in enumerate(items, 1):
        taxable = float(itm.get("value", 0) or 0)
        tot_taxable += taxable
        
        gw = float(itm.get("gross_wt", 0) or 0)
        nw = float(itm.get("net_wt", 0) or 0)
        tot_gross += gw
        tot_net += nw
        
        gw_str = f"{gw:.3f}" if gw else ""
        nw_str = f"{nw:.3f}" if nw else ""

        if is_interstate:
            igst = float(itm.get("igst", 0) or 0)
            tot_igst += igst
            item_tot = taxable + igst
            tot_grand += item_tot
            rows.append([
                str(i), itm.get("description",""), itm.get("hsn",""), str(itm.get("qty","")),
                gw_str, nw_str, f"{float(itm.get('rate',0) or 0):.2f}", f"{taxable:.2f}",
                f"{igst:.2f}", f"{item_tot:.2f}"
            ])
        else:
            cgst = float(itm.get("cgst", 0) or 0)
            sgst = float(itm.get("sgst", 0) or 0)
            tot_cgst += cgst
            tot_sgst += sgst
            item_tot = taxable + cgst + sgst
            tot_grand += item_tot
            rows.append([
                str(i), itm.get("description",""), itm.get("hsn",""), str(itm.get("qty","")),
                gw_str, nw_str, f"{float(itm.get('rate',0) or 0):.2f}", f"{taxable:.2f}",
                f"{cgst:.2f}", f"{sgst:.2f}", f"{item_tot:.2f}"
            ])

    # Extend table with empty blank rows
    min_rows = 8
    empty_cols = 10 if is_interstate else 11
    while len(rows) - 1 < min_rows:
        rows.append([""] * empty_cols)

    # Total row
    tot_gw_display = f"{tot_gross:.3f}" if tot_gross > 0 else ""
    tot_nw_display = f"{tot_net:.3f}" if tot_net > 0 else ""

    if is_interstate:
        rows.append(["", "Total", "", "", tot_gw_display, tot_nw_display, "", f"{tot_taxable:.2f}", f"{tot_igst:.2f}", f"{tot_grand:.2f}"])
    else:
        rows.append(["", "Total", "", "", tot_gw_display, tot_nw_display, "", f"{tot_taxable:.2f}", f"{tot_cgst:.2f}", f"{tot_sgst:.2f}", f"{tot_grand:.2f}"])

    row_heights = [20] + [22] * (len(rows) - 2) + [22]

    t_i = Table(rows, colWidths=col_w, rowHeights=row_heights)
    t_i.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 7.5),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 2.5)
    ]))
    elems.extend([t_i, Spacer(1, 10)])
    
    elems.append(Paragraph("<font size=6.5>Terms: Goods dispatched on challan basis. Not a tax invoice. Subject to Home Jurisdiction.</font>", normal))
    elems.append(Spacer(1, 30))
    
    sig = [[
        Paragraph("Receiver's Signature & Stamp", normal),
        Paragraph(f"For <b>{data.get('sender_name','')}</b><br/><br/><br/>Authorised Signatory", ParagraphStyle("R", parent=normal, alignment=2))
    ]]
    elems.append(Table(sig, colWidths=[270, 270]))
    doc.build(elems)

@app.route("/")
def home(): return send_from_directory(".", "index.html")

@app.route("/api/challans", methods=["GET"])
def get_c(): return jsonify(load_r())

@app.route("/api/challans", methods=["POST"])
def add_c():
    try:
        d = request.json
        r = load_r()
        
        existing_index = next((i for i, c in enumerate(r) if c.get("challan_no") == d.get("challan_no")), -1)
        
        if not d.get("challan_no"):
            d["challan_no"] = f"DC-{datetime.now().strftime('%Y%m%d')}-{len(r)+1:03d}"
        if not d.get("date"):
            d["date"] = datetime.now().strftime("%Y-%m-%d")
            
        fn = f"{d['challan_no'].replace('/','_')}.pdf"
        make_pdf(d, os.path.join(DATA_DIR, fn))
        d["pdf_path"] = f"/challans/{fn}"
        
        if existing_index >= 0:
            r[existing_index] = d
        else:
            r.append(d)
            
        save_r(r)
        return jsonify({"status":"success", "data": d})
    except Exception as e:
        return jsonify({"status":"error", "message": str(e)}), 500

@app.route("/api/challans/<path:challan_no>", methods=["DELETE"])
def delete_c(challan_no):
    req_pass = request.headers.get("X-Admin-Password", "")
    if req_pass != DELETE_PASSWORD:
        return jsonify({"status": "error", "message": "Incorrect password"}), 403

    r = load_r()
    r = [c for c in r if c.get("challan_no") != challan_no]
    save_r(r)
    
    fn = f"{challan_no.replace('/','_')}.pdf"
    file_path = os.path.join(DATA_DIR, fn)
    if os.path.exists(file_path):
        try: os.remove(file_path)
        except: pass
        
    return jsonify({"status": "success"})

@app.route("/challans/<path:f>")
def dl(f): return send_from_directory(DATA_DIR, f)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="0.0.0.0", port=port)
