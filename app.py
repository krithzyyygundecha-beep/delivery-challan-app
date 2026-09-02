import os, json, webbrowser
from datetime import datetime
from threading import Timer
from flask import Flask, request, jsonify, send_from_directory
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

app = Flask(__name__, static_folder=".", static_url_path="")
DATA_DIR = os.path.join(os.path.dirname(__file__), "challans")
os.makedirs(DATA_DIR, exist_ok=True)
REC_FILE = os.path.join(DATA_DIR, "records.json")

def load_r():
    if os.path.exists(REC_FILE):
        try:
            with open(REC_FILE, "r", encoding="utf-8") as f: return json.load(f)
        except: return []
    return []

def save_r(data):
    with open(REC_FILE, "w", encoding="utf-8") as f: json.dump(data, f, indent=2)

def make_pdf(data, path):
    doc = SimpleDocTemplate(path, pagesize=A4, rightMargin=25, leftMargin=25, topMargin=25, bottomMargin=25)
    s = getSampleStyleSheet()
    normal = s["Normal"]
    normal.fontSize = 8
    normal.leading = 10
    
    elems = [
        Paragraph("<b>DELIVERY CHALLAN</b>", ParagraphStyle("T", parent=s["Heading1"], alignment=1, fontSize=14)),
        Paragraph("<font size=8 color=gray>Issued under Rule 55 of CGST / SGST Rules</font>", ParagraphStyle("S", alignment=1, spaceAfter=10))
    ]
    
    is_interstate = (data.get("sender_state", "").strip().lower() != data.get("receiver_state", "").strip().lower())
    
    hd = [
        [Paragraph(f"<b>Consignor (Sender):</b><br/>{data.get('sender_name','')}<br/>{data.get('sender_address','')}<br/>State: {data.get('sender_state','')}<br/>GSTIN: {data.get('sender_gstin','')}", normal),
         Paragraph(f"<b>Challan No:</b> {data.get('challan_no','')}<br/><b>Date:</b> {data.get('date','')}<br/><b>Reason:</b> {data.get('reason','')}", normal)],
        [Paragraph(f"<b>Consignee (Recipient):</b><br/>{data.get('receiver_name','')}<br/>{data.get('receiver_address','')}<br/>State: {data.get('receiver_state','')}<br/>GSTIN/PAN: {data.get('receiver_gstin','')}", normal),
         Paragraph(f"<b>Vehicle / Docket:</b> {data.get('vehicle_no','')}<br/><b>Place of Supply:</b> {data.get('receiver_state','')}", normal)]
    ]
    t_h = Table(hd, colWidths=[275, 270])
    t_h.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('INNERGRID', (0,0), (-1,-1), 0.5, colors.grey),
        ('VALIGN', (0,0), (-1,-1), 'TOP'),
        ('PADDING', (0,0), (-1,-1), 4)
    ]))
    elems.extend([t_h, Spacer(1, 10)])
    
    if is_interstate:
        headers = ["Sr.", "Description", "HSN", "Qty", "Net Wt", "Rate (₹)", "Taxable (₹)", "IGST (₹)", "Total (₹)"]
        col_w = [25, 120, 55, 35, 50, 60, 70, 65, 65]
    else:
        headers = ["Sr.", "Description", "HSN", "Qty", "Net Wt", "Rate (₹)", "Taxable (₹)", "CGST (₹)", "SGST (₹)", "Total (₹)"]
        col_w = [22, 110, 50, 30, 45, 55, 63, 55, 55, 60]

    rows = [headers]
    tot_taxable = 0
    tot_cgst = 0
    tot_sgst = 0
    tot_igst = 0
    tot_grand = 0

    for i, itm in enumerate(data.get("items", []), 1):
        taxable = float(itm.get("value", 0) or 0)
        tot_taxable += taxable
        
        if is_interstate:
            igst = float(itm.get("igst", 0) or 0)
            tot_igst += igst
            item_tot = taxable + igst
            tot_grand += item_tot
            rows.append([
                str(i), itm.get("description",""), itm.get("hsn",""), str(itm.get("qty","")),
                str(itm.get("net_wt","")), f"{float(itm.get('rate',0)):.2f}", f"{taxable:.2f}",
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
                str(itm.get("net_wt","")), f"{float(itm.get('rate',0)):.2f}", f"{taxable:.2f}",
                f"{cgst:.2f}", f"{sgst:.2f}", f"{item_tot:.2f}"
            ])

    if is_interstate:
        rows.append(["", "Total", "", "", "", "", f"{tot_taxable:.2f}", f"{tot_igst:.2f}", f"{tot_grand:.2f}"])
    else:
        rows.append(["", "Total", "", "", "", "", f"{tot_taxable:.2f}", f"{tot_cgst:.2f}", f"{tot_sgst:.2f}", f"{tot_grand:.2f}"])

    t_i = Table(rows, colWidths=col_w)
    t_i.setStyle(TableStyle([
        ('BOX', (0,0), (-1,-1), 1, colors.black),
        ('GRID', (0,0), (-1,-2), 0.5, colors.grey),
        ('BACKGROUND', (0,0), (-1,0), colors.whitesmoke),
        ('ALIGN', (0,0), (-1,-1), 'CENTER'),
        ('ALIGN', (1,1), (1,-1), 'LEFT'),
        ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
        ('FONTNAME', (0,-1), (-1,-1), 'Helvetica-Bold'),
        ('FONTSIZE', (0,0), (-1,-1), 8),
        ('LINEABOVE', (0,-1), (-1,-1), 1, colors.black),
        ('PADDING', (0,0), (-1,-1), 3)
    ]))
    elems.extend([t_i, Spacer(1, 20)])
    
    elems.append(Paragraph("<font size=7>Terms: Goods dispatched on challan basis. This is not a tax invoice. Subject to Mumbai Jurisdiction.</font>", normal))
    elems.append(Spacer(1, 35))
    
    sig = [[
        Paragraph("Receiver's Signature & Stamp", normal),
        Paragraph(f"For <b>{data.get('sender_name','')}</b><br/><br/>Authorised Signatory", ParagraphStyle("R", parent=normal, alignment=2))
    ]]
    elems.append(Table(sig, colWidths=[270, 270]))
    doc.build(elems)

@app.route("/")
def home(): return send_from_directory(".", "index.html")

@app.route("/api/challans", methods=["GET"])
def get_c(): return jsonify(load_r())

@app.route("/api/challans", methods=["POST"])
def add_c():
    d = request.json
    r = load_r()
    if not d.get("challan_no"): d["challan_no"] = f"DC-{datetime.now().strftime('%Y%m%d')}-{len(r)+1:03d}"
    if not d.get("date"): d["date"] = datetime.now().strftime("%d-%m-%Y")
    fn = f"{d['challan_no'].replace('/','_')}.pdf"
    make_pdf(d, os.path.join(DATA_DIR, fn))
    d["pdf_path"] = f"/challans/{fn}"
    r.append(d)
    save_r(r)
    return jsonify({"status":"success", "data": d})

@app.route("/challans/<path:f>")
def dl(f): return send_from_directory(DATA_DIR, f)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    Timer(1.2, lambda: webbrowser.open(f"http://127.0.0.1:{port}")).start()
    app.run(host="0.0.0.0", port=port)
