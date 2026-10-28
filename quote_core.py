"""Calculation, amount-in-words and PDF generation for Quotation Maker."""
import os
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.utils import ImageReader, simpleSplit
from reportlab.platypus import (BaseDocTemplate, Frame, KeepTogether, NextPageTemplate,
                                PageTemplate, Paragraph, Spacer, Table, TableStyle)


# ---------------------------------------------------------------- helpers
def num(x):
    try:
        return float(str(x).replace(",", "").strip() or 0)
    except ValueError:
        return 0.0


def money(n):
    """Indian digit grouping: 12,34,567.89"""
    n = round(float(n), 2)
    neg = n < 0
    s = f"{abs(n):.2f}"
    whole, dec = s.split(".")
    if len(whole) > 3:
        head, tail = whole[:-3], whole[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        whole = ",".join(parts) + "," + tail
    return ("-" if neg else "") + whole + "." + dec


def qty_fmt(n):
    n = num(n)
    return str(int(n)) if n == int(n) else f"{n:g}"


_ONES = ("Zero One Two Three Four Five Six Seven Eight Nine Ten Eleven Twelve Thirteen "
         "Fourteen Fifteen Sixteen Seventeen Eighteen Nineteen").split()
_TENS = "_ _ Twenty Thirty Forty Fifty Sixty Seventy Eighty Ninety".split()


def _below_100(n):
    return _ONES[n] if n < 20 else _TENS[n // 10] + (" " + _ONES[n % 10] if n % 10 else "")


def _below_1000(n):
    out = []
    if n >= 100:
        out.append(_ONES[n // 100] + " Hundred")
        n %= 100
    if n:
        out.append(_below_100(n))
    return " ".join(out)


def amount_in_words(amount):
    amount = round(abs(amount), 2)
    rupees, paise = int(amount), int(round((amount - int(amount)) * 100))
    if rupees == 0 and paise == 0:
        return "Indian Rupees Zero Only"
    parts = []
    for div, name in ((10000000, "Crore"), (100000, "Lakh"), (1000, "Thousand")):
        if rupees >= div:
            parts.append(_below_100(rupees // div) + " " + name)
            rupees %= div
    if rupees:
        parts.append(_below_1000(rupees))
    text = "Indian Rupees " + " ".join(parts) if parts else "Indian Rupees Zero"
    if paise:
        text += " and " + _below_100(paise) + " Paise"
    return text + " Only"


# ------------------------------------------------------------ calculation
def calc(q):
    gst = bool(q.get("gst_enabled"))
    inter = bool(q.get("interstate"))
    rows, sub = [], 0.0
    for it in q.get("items", []):
        gross = num(it.get("qty")) * num(it.get("rate"))
        net = round(gross * (1 - num(it.get("disc")) / 100), 2)
        rows.append(dict(it, net=net))
        sub += net
    sub = round(sub, 2)
    disc_total = min(num(q.get("discount_total")), sub)
    taxable_total = round(sub - disc_total, 2)
    factor = taxable_total / sub if sub else 0

    groups, order = {}, []
    if gst:
        for r in rows:
            key = (r.get("hsn", ""), num(r.get("gst")))
            if key not in groups:
                groups[key] = 0.0
                order.append(key)
            groups[key] += r["net"] * factor
    breakup = []
    for key in order:
        hsn, rate = key
        tv = round(groups[key], 2)
        if inter:
            t = round(tv * rate / 100, 2)
            breakup.append(dict(hsn=hsn, rate=rate, taxable=tv, cgst=0, sgst=0, igst=t, tax=t))
        else:
            c = round(tv * rate / 200, 2)
            breakup.append(dict(hsn=hsn, rate=rate, taxable=tv, cgst=c, sgst=c, igst=0, tax=round(2 * c, 2)))
    cgst = round(sum(b["cgst"] for b in breakup), 2)
    sgst = round(sum(b["sgst"] for b in breakup), 2)
    igst = round(sum(b["igst"] for b in breakup), 2)
    tax = round(cgst + sgst + igst, 2)
    extra = num(q.get("extra_amount"))
    raw = taxable_total + tax + extra
    total = float(round(raw)) if q.get("round_off", True) else round(raw, 2)
    return dict(rows=rows, subtotal=sub, discount_total=disc_total, taxable_total=taxable_total,
                breakup=breakup, cgst=cgst, sgst=sgst, igst=igst, tax=tax, extra=extra,
                round_off=round(total - raw, 2), total=total, words=amount_in_words(total))


# ----------------------------------------------------------------- PDF
THEMES = {
    "Royal Navy & Gold": dict(primary="#10264B", secondary="#1D4E89", accent="#C9A24B", tint="#EEF2F9", zebra="#F7F9FC"),
    "Emerald & Gold": dict(primary="#0B4F43", secondary="#168A6F", accent="#D4AF37", tint="#EAF5F1", zebra="#F5FAF8"),
    "Burgundy & Gold": dict(primary="#6B1B2E", secondary="#A3324A", accent="#D4AF37", tint="#F9EEF0", zebra="#FCF6F7"),
    "Royal Purple & Amber": dict(primary="#3A1F70", secondary="#6B3FC4", accent="#F5A623", tint="#F1ECFA", zebra="#F8F5FD"),
    "Ocean Teal & Coral": dict(primary="#0B4A5E", secondary="#1494A6", accent="#FF7F50", tint="#E8F5F7", zebra="#F4FAFB"),
    "Charcoal & Orange": dict(primary="#242B38", secondary="#4A5568", accent="#F28C28", tint="#EFF1F4", zebra="#F7F8FA"),
}
DEFAULT_THEME = "Royal Navy & Gold"


def _fonts():
    base = os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts")
    for reg, bold in (("segoeui.ttf", "segoeuib.ttf"), ("arial.ttf", "arialbd.ttf")):
        rp, bp = os.path.join(base, reg), os.path.join(base, bold)
        if os.path.exists(rp) and os.path.exists(bp):
            try:
                pdfmetrics.registerFont(TTFont("QM", rp))
                pdfmetrics.registerFont(TTFont("QM-B", bp))
                head = "QM-B"
                gp = os.path.join(base, "georgiab.ttf")
                if os.path.exists(gp):
                    pdfmetrics.registerFont(TTFont("QM-H", gp))
                    head = "QM-H"
                return "QM", "QM-B", head, "\u20b9"
            except Exception:
                pass
    return "Helvetica", "Helvetica-Bold", "Helvetica-Bold", "Rs. "


def _p(text, style):
    return Paragraph(escape(str(text if text is not None else "")).replace("\n", "<br/>"), style)


def make_pdf(q, company, path):
    R, B, H, SYM = _fonts()
    th = THEMES.get(q.get("theme"), THEMES[DEFAULT_THEME])
    P, S, A = (colors.HexColor(th[k]) for k in ("primary", "secondary", "accent"))
    TINT, ZEB = colors.HexColor(th["tint"]), colors.HexColor(th["zebra"])
    INK, MUTED, LINE = colors.HexColor("#1B2433"), colors.HexColor("#5B6678"), colors.HexColor("#CBD3DF")
    WHITE = colors.white
    c = calc(q)
    gst, inter = bool(q.get("gst_enabled")), bool(q.get("interstate"))
    pw, ph = A4
    W = pw - 24 * mm
    cname = company.get("name", "")

    def ps(name, **kw):
        base = dict(fontName=R, fontSize=8.5, leading=11.5, textColor=INK)
        base.update(kw)
        return ParagraphStyle(name, **base)

    st, stb = ps("st"), ps("stb", fontName=B)
    sr, srb = ps("sr", alignment=2), ps("srb", fontName=B, alignment=2)
    sc = ps("sc", alignment=1)
    sth = ps("sth", fontName=B, fontSize=8, textColor=WHITE, alignment=1)
    small = ps("sm", fontSize=7.8, leading=10.5, textColor=MUTED)
    lab = ps("lab", fontName=B, fontSize=7, leading=9, textColor=MUTED)

    # ---------- page decoration
    band = 37 * mm
    logo_path = company.get("logo", "")
    has_logo = bool(logo_path) and os.path.exists(logo_path)

    def footer(cv):
        cv.setStrokeColor(A)
        cv.setLineWidth(1)
        cv.line(12 * mm, 14 * mm, pw - 12 * mm, 14 * mm)
        cv.setFont(R, 7.5)
        cv.setFillColor(MUTED)
        bits = [x for x in (cname, company.get("phone"), company.get("email")) if x]
        cv.drawString(12 * mm, 9.5 * mm, "   |   ".join(bits))
        cv.drawRightString(pw - 12 * mm, 9.5 * mm, f"Page {cv.getPageNumber()}")
        cv.setFillColor(S)
        cv.setFont(H, 8.5)
        cv.drawCentredString(pw / 2, 17.5 * mm, "Thank you for your business!")

    def first_page(cv, doc):
        cv.saveState()
        cv.setFillColor(P)
        cv.rect(0, ph - band, pw, band, stroke=0, fill=1)
        poly = cv.beginPath()
        poly.moveTo(pw * 0.70, ph)
        poly.lineTo(pw, ph)
        poly.lineTo(pw, ph - band)
        poly.lineTo(pw * 0.60, ph - band)
        poly.close()
        cv.setFillColor(S)
        cv.drawPath(poly, stroke=0, fill=1)
        cv.setFillColor(A)
        cv.rect(0, ph - band - 2.2 * mm, pw, 2.2 * mm, stroke=0, fill=1)
        x = 12 * mm
        if has_logo:
            cv.setFillColor(WHITE)
            cv.roundRect(x, ph - band + 7 * mm, 44 * mm, 26 * mm, 3 * mm, stroke=0, fill=1)
            try:
                cv.drawImage(ImageReader(logo_path), x + 2 * mm, ph - band + 9 * mm, 40 * mm, 22 * mm,
                             preserveAspectRatio=True, anchor="c", mask="auto")
            except Exception:
                pass
            x += 50 * mm
        avail = pw * 0.62 - x - 4 * mm
        y = ph - 12 * mm
        cv.setFillColor(WHITE)
        cv.setFont(B, 15)
        for line in simpleSplit(cname, B, 15, avail)[:2]:
            cv.drawString(x, y, line)
            y -= 6.2 * mm
        cv.setFont(R, 8)
        cv.setFillColor(colors.HexColor("#D9E1EE"))
        addr = ", ".join(s.strip() for s in company.get("address", "").splitlines() if s.strip())
        for line in simpleSplit(addr, R, 8, avail)[:2]:
            cv.drawString(x, y, line)
            y -= 4 * mm
        extra = "   ".join(z for z in (("Ph: " + company["phone"]) if company.get("phone") else "",
                                       company.get("email", "")) if z)
        if extra:
            cv.drawString(x, y, extra)
            y -= 4 * mm
        if gst and company.get("gst"):
            cv.drawString(x, y, "GSTIN: " + company["gst"])
        cv.setFillColor(A)
        cv.setFont(H, 26)
        cv.drawRightString(pw - 12 * mm, ph - 19 * mm, "QUOTATION")
        cv.setFillColor(WHITE)
        cv.setFont(R, 9)
        cv.drawRightString(pw - 12 * mm, ph - 26 * mm, f"No. {q.get('number', '')}")
        footer(cv)
        cv.restoreState()

    def later_page(cv, doc):
        cv.saveState()
        cv.setFillColor(P)
        cv.rect(0, ph - 14 * mm, pw, 14 * mm, stroke=0, fill=1)
        cv.setFillColor(A)
        cv.rect(0, ph - 15.5 * mm, pw, 1.5 * mm, stroke=0, fill=1)
        cv.setFillColor(WHITE)
        cv.setFont(B, 10)
        cv.drawString(12 * mm, ph - 9 * mm, cname)
        cv.setFont(R, 9)
        cv.drawRightString(pw - 12 * mm, ph - 9 * mm, f"Quotation No. {q.get('number', '')}")
        footer(cv)
        cv.restoreState()

    doc = BaseDocTemplate(path, pagesize=A4, title=f"Quotation {q.get('number', '')}", author=cname)
    top1, top2 = band + 2.2 * mm + 4.5 * mm, 15.5 * mm + 6 * mm
    f1 = Frame(12 * mm, 18 * mm, W, ph - 18 * mm - top1, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    f2 = Frame(12 * mm, 18 * mm, W, ph - 18 * mm - top2, leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate("first", [f1], onPage=first_page),
                          PageTemplate("later", [f2], onPage=later_page)])
    story = [NextPageTemplate("later")]

    def section(title):
        t = Table([[Paragraph(title, ps("sec", fontName=B, fontSize=8, textColor=S))]], colWidths=[W])
        t.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.8, A), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 3)]))
        return t

    # ---------- summary tiles
    def tile(label, value, dark=False):
        l = ps("tl", fontName=B, fontSize=7, leading=9, textColor=colors.HexColor("#C9D3E6") if dark else MUTED)
        v = ps("tv", fontName=B, fontSize=11.5, leading=15, textColor=WHITE if dark else P)
        return [Paragraph(label, l), Paragraph(escape(str(value or "-")), v)]

    tiles = Table([[tile("QUOTATION NO.", q.get("number")), tile("DATE", q.get("date")),
                    tile("VALID UNTIL", q.get("validity")), tile("TOTAL AMOUNT", SYM + money(c["total"]), True)]],
                  colWidths=[W * 0.25] * 4)
    tiles.setStyle(TableStyle([("BACKGROUND", (0, 0), (2, 0), TINT), ("BACKGROUND", (3, 0), (3, 0), P),
                               ("LINEABOVE", (0, 0), (-1, 0), 2.5, A), ("LINEAFTER", (0, 0), (2, 0), 6, WHITE),
                               ("LEFTPADDING", (0, 0), (-1, -1), 9), ("TOPPADDING", (0, 0), (-1, -1), 7),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 7)]))
    story += [tiles, Spacer(1, 3 * mm)]

    # ---------- parties
    def party(label, d):
        lines = []
        if d.get("address"):
            lines.append(escape(d["address"]).replace("\n", "<br/>"))
        if d.get("phone"):
            lines.append("Phone: " + escape(d["phone"]))
        if d.get("email"):
            lines.append("E-mail: " + escape(d["email"]))
        if gst and d.get("gst"):
            lines.append("<b>GSTIN:</b> " + escape(d["gst"]))
        if d.get("pan"):
            lines.append("<b>PAN:</b> " + escape(d["pan"]))
        return [Paragraph(label, ps("pl", fontName=B, fontSize=7.5, textColor=S)), Spacer(1, 1.5 * mm),
                Paragraph(escape(d.get("name", "")), ps("pn", fontName=B, fontSize=10.5, leading=14, textColor=P)),
                Paragraph("<br/>".join(lines), st)]

    pt = Table([[party("QUOTATION FROM", company), "", party("BILL TO", q.get("client", {}))]],
               colWidths=[W * 0.485, W * 0.03, W * 0.485])
    pt.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), TINT), ("BACKGROUND", (2, 0), (2, 0), TINT),
                            ("LINEBEFORE", (0, 0), (0, 0), 3, A), ("LINEBEFORE", (2, 0), (2, 0), 3, A),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 9),
                            ("TOPPADDING", (0, 0), (-1, -1), 7), ("BOTTOMPADDING", (0, 0), (-1, -1), 8)]))
    story += [pt, Spacer(1, 3 * mm)]

    # ---------- other references
    ref = q.get("refs", {})
    pairs = [(k, v) for k, v in (("Buyer's Ref. / Order No.", ref.get("buyer_ref")),
                                 ("Terms of Payment", ref.get("payment")), ("Dispatched Through", ref.get("dispatch")),
                                 ("Destination", ref.get("destination")), ("Other References", ref.get("other"))) if v]
    if pairs:
        rows = []
        for i in range(0, len(pairs), 2):
            l = pairs[i]
            r = pairs[i + 1] if i + 1 < len(pairs) else ("", "")
            rows.append([_p(l[0], ps("rk", fontName=B, textColor=S)), _p(l[1], st),
                         _p(r[0], ps("rk2", fontName=B, textColor=S)), _p(r[1], st)])
        rt = Table(rows, colWidths=[W * 0.2, W * 0.3, W * 0.2, W * 0.3])
        rt.setStyle(TableStyle([("LINEBELOW", (0, 0), (-1, -1), 0.25, LINE), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                                ("LEFTPADDING", (0, 0), (-1, -1), 2)]))
        story += [rt, Spacer(1, 3 * mm)]

    # ---------- items
    if gst:
        hdr = ["Sl", "Description of Goods / Services", "HSN/SAC", "Qty", "Rate", "Per", "Disc%", "GST%", "Amount"]
        cw = [8, 54, 20, 13, 20, 11, 15, 14, 31]
    else:
        hdr = ["Sl", "Description of Goods / Services", "Qty", "Rate", "Per", "Disc%", "Amount"]
        cw = [8, 74, 16, 24, 14, 20, 30]
    cw = [x * mm * (186 / sum(cw)) for x in cw]
    data = [[Paragraph(h, sth) for h in hdr]]
    for i, r in enumerate(c["rows"], 1):
        line = [_p(i, sc), _p(r.get("desc"), st)]
        if gst:
            line.append(_p(r.get("hsn"), sc))
        line += [_p(qty_fmt(r.get("qty")), sr), _p(money(num(r.get("rate"))), sr), _p(r.get("per"), sc),
                 _p(f"{num(r.get('disc')):g}" if num(r.get("disc")) else "", sr)]
        if gst:
            line.append(_p(f"{num(r.get('gst')):g}", sr))
        line.append(_p(money(r["net"]), ps("amt", fontName=B, alignment=2)))
        data.append(line)
    it = Table(data, colWidths=cw, repeatRows=1)
    it.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), P), ("LINEBELOW", (0, 0), (-1, 0), 2, A),
                            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ZEB]),
                            ("LINEBELOW", (0, 1), (-1, -1), 0.25, LINE), ("LINEBELOW", (0, -1), (-1, -1), 1, P),
                            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    story += [it, Spacer(1, 3 * mm)]

    # ---------- words + totals
    tl = [("Sub Total", c["subtotal"])]
    if c["discount_total"]:
        tl.append(("Discount on Total", -c["discount_total"]))
    if gst:
        tl += [("IGST", c["igst"])] if inter else [("CGST", c["cgst"]), ("SGST / UTGST", c["sgst"])]
    if c["extra"]:
        tl.append((q.get("extra_label") or "Additional Charges", c["extra"]))
    if c["round_off"]:
        tl.append(("Round Off", c["round_off"]))
    td = [[_p(k, ps("tk", textColor=MUTED, alignment=2)),
           _p(("-" if v < 0 else "") + SYM + money(abs(v)), sr)] for k, v in tl]
    td.append([_p("TOTAL", ps("tt", fontName=B, textColor=WHITE, alignment=2, fontSize=10)),
               _p(SYM + money(c["total"]), ps("tv2", fontName=B, textColor=WHITE, alignment=2, fontSize=11))])
    tt = Table(td, colWidths=[W * 0.215, W * 0.235])
    tt.setStyle(TableStyle([("BACKGROUND", (0, -1), (-1, -1), P), ("LINEABOVE", (0, -1), (-1, -1), 2, A),
                            ("LINEBELOW", (0, 0), (-1, -2), 0.25, LINE), ("TOPPADDING", (0, 0), (-1, -1), 4),
                            ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
    left = [Paragraph("AMOUNT IN WORDS", lab),
            Paragraph(escape(c["words"]), ps("w", fontName=B, fontSize=9, leading=12.5, textColor=P))]
    if company.get("bank"):
        left += [Spacer(1, 3 * mm), Paragraph("BANK DETAILS", lab), _p(company["bank"], small)]
    wt = Table([[left, "", tt]], colWidths=[W * 0.52, W * 0.03, W * 0.45])
    wt.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, 0), TINT), ("LINEBEFORE", (0, 0), (0, 0), 3, A),
                            ("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (0, 0), 9),
                            ("TOPPADDING", (0, 0), (0, 0), 8), ("RIGHTPADDING", (2, 0), (2, 0), 0),
                            ("LEFTPADDING", (2, 0), (2, 0), 0), ("TOPPADDING", (2, 0), (2, 0), 0)]))
    story += [wt, Spacer(1, 4 * mm)]

    # ---------- GST break-up
    if gst and c["breakup"]:
        if inter:
            h = ["HSN/SAC", "Taxable Value", "IGST Rate", "IGST Amount", "Total Tax"]
            bd = [[Paragraph(x, sth) for x in h]]
            for r in c["breakup"]:
                bd.append([_p(r["hsn"], sc), _p(money(r["taxable"]), sr), _p(f"{r['rate']:g}%", sr),
                           _p(money(r["igst"]), sr), _p(money(r["tax"]), sr)])
            bd.append([_p("Total", stb), _p(money(c["taxable_total"]), srb), "", _p(money(c["igst"]), srb),
                       _p(money(c["tax"]), srb)])
            bw = [W * x for x in (0.2, 0.22, 0.16, 0.22, 0.2)]
        else:
            h = ["HSN/SAC", "Taxable Value", "CGST Rate", "CGST Amt", "SGST Rate", "SGST Amt", "Total Tax"]
            bd = [[Paragraph(x, sth) for x in h]]
            for r in c["breakup"]:
                bd.append([_p(r["hsn"], sc), _p(money(r["taxable"]), sr), _p(f"{r['rate'] / 2:g}%", sr),
                           _p(money(r["cgst"]), sr), _p(f"{r['rate'] / 2:g}%", sr), _p(money(r["sgst"]), sr),
                           _p(money(r["tax"]), sr)])
            bd.append([_p("Total", stb), _p(money(c["taxable_total"]), srb), "", _p(money(c["cgst"]), srb), "",
                       _p(money(c["sgst"]), srb), _p(money(c["tax"]), srb)])
            bw = [W * x for x in (0.15, 0.19, 0.11, 0.14, 0.11, 0.14, 0.16)]
        bt = Table(bd, colWidths=bw)
        bt.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, 0), S), ("BACKGROUND", (0, -1), (-1, -1), TINT),
                                ("LINEBELOW", (0, 1), (-1, -2), 0.25, LINE), ("LINEBELOW", (0, -1), (-1, -1), 1, S),
                                ("TOPPADDING", (0, 0), (-1, -1), 4), ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        story += [KeepTogether([section("GST BREAK-UP"), Spacer(1, 1.5 * mm), bt]), Spacer(1, 3 * mm)]

    # ---------- terms (left) + signatures (right)
    left = []
    if q.get("terms"):
        left += [Paragraph("TERMS &amp; CONDITIONS", ps("sec", fontName=B, fontSize=8, textColor=S)),
                 Spacer(1, 1.5 * mm), _p(q["terms"], ps("tm", fontSize=8, textColor=INK)), Spacer(1, 2 * mm)]
    left.append(Paragraph("<b>Declaration:</b> We declare that this quotation shows the actual price of the goods / "
                          "services described and that all particulars are true and correct.", small))
    sig = Table([[[Paragraph("Customer Seal &amp; Signature", small)],
                  [Paragraph(f"For <b>{escape(cname)}</b>", ps("fo", fontSize=8, alignment=2)), Spacer(1, 14 * mm),
                   Paragraph("Authorized Signatory", ps("as", fontName=B, fontSize=8, alignment=2, textColor=S))]]],
                colWidths=[W * 0.215, W * 0.255])
    sig.setStyle(TableStyle([("BOX", (0, 0), (-1, -1), 0.5, LINE), ("LINEAFTER", (0, 0), (0, 0), 0.5, LINE),
                             ("LINEABOVE", (0, 0), (-1, 0), 2, A), ("VALIGN", (0, 0), (-1, -1), "TOP"),
                             ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5)]))
    bottom = Table([[left, "", sig]], colWidths=[W * 0.51, W * 0.02, W * 0.47])
    bottom.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"), ("LEFTPADDING", (0, 0), (-1, -1), 0),
                                ("RIGHTPADDING", (0, 0), (-1, -1), 0), ("TOPPADDING", (0, 0), (-1, -1), 0)]))
    story.append(KeepTogether([bottom]))
    doc.build(story)
    return c
