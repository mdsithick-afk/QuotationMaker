"""Quotation Maker - premium Windows desktop app (Tkinter). GST is optional."""
import datetime
import json
import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:  # crisp text on Windows 10/11 high-DPI screens
    import ctypes
    ctypes.windll.shcore.SetProcessDpiAwareness(1)
except Exception:
    pass

from quote_core import DEFAULT_THEME, THEMES, calc, money, num
from quote_core import make_pdf as render_pdf

APP = "Quotation Maker"
FOLDER = "QuotationMaker"
SET_DIR = os.path.join(os.environ.get("APPDATA", os.path.expanduser("~")), FOLDER)
DOC_DIR = os.path.join(os.path.expanduser("~"), "Documents", FOLDER)
DATA_DIR, PDF_DIR = os.path.join(DOC_DIR, "Saved"), os.path.join(DOC_DIR, "PDF")
SETTINGS = os.path.join(SET_DIR, "settings.json")
for _d in (SET_DIR, DATA_DIR, PDF_DIR):
    os.makedirs(_d, exist_ok=True)

NAVY, NAVY2, GOLD, GOLD2 = "#10264B", "#1D4E89", "#C9A24B", "#D8B45E"
BG, WHITE, BORDER, MUTED, INK = "#F3F5FA", "#FFFFFF", "#D5DCE8", "#6B7690", "#1B2433"
F, FB = "Segoe UI", "Segoe UI Semibold"

DEFAULT_COMPANY = {"name": "", "address": "", "phone": "", "email": "", "gst": "", "pan": "", "logo": "",
                   "bank": "", "prefix": "QT-", "next": 1, "theme": DEFAULT_THEME,
                   "terms": "1. Prices are valid for 15 days from the quotation date.\n"
                            "2. Payment terms as agreed.\n3. Delivery as per mutual agreement."}


def load_company():
    try:
        with open(SETTINGS, encoding="utf-8") as f:
            return {**DEFAULT_COMPANY, **json.load(f)}
    except Exception:
        return dict(DEFAULT_COMPANY)


class Switch(tk.Canvas):
    """Small iOS-style toggle switch."""

    def __init__(self, master, variable, command=None, bg=NAVY):
        super().__init__(master, width=46, height=24, bg=bg, highlightthickness=0, cursor="hand2")
        self.var, self.cmd = variable, command
        self.bind("<Button-1>", self.toggle)
        self.draw()

    def draw(self):
        self.delete("all")
        on = self.var.get()
        col = GOLD if on else "#56627A"
        self.create_oval(1, 1, 23, 23, fill=col, outline=col)
        self.create_oval(23, 1, 45, 23, fill=col, outline=col)
        self.create_rectangle(12, 1, 34, 23, fill=col, outline=col)
        x = 34 if on else 12
        self.create_oval(x - 9, 3, x + 9, 21, fill="white", outline="white")

    def toggle(self, _e=None):
        self.var.set(not self.var.get())
        self.draw()
        if self.cmd:
            self.cmd()


class ScrollFrame(tk.Frame):
    def __init__(self, master, bg=BG):
        super().__init__(master, bg=bg)
        self.canvas = tk.Canvas(self, bg=bg, highlightthickness=0)
        sb = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)
        self.inner = tk.Frame(self.canvas, bg=bg)
        self.win = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.inner.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(self.win, width=e.width))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title(APP)
        self.configure(bg=BG)
        w, h = 1220, 840
        self.geometry(f"{w}x{h}+{max((self.winfo_screenwidth() - w) // 2, 0)}+{max((self.winfo_screenheight() - h) // 2 - 20, 0)}")
        self.minsize(1050, 650)
        self.company = load_company()
        self.items, self.sel, self.v = [], None, {}
        self.gst_only = []
        self.gst_var, self.inter_var = tk.BooleanVar(value=False), tk.BooleanVar(value=False)
        self.round_var = tk.BooleanVar(value=True)
        self.theme_var = tk.StringVar(value=self.company.get("theme", DEFAULT_THEME))
        self.style_setup()
        self.build_header()
        self.status_lbl = tk.Label(self, text="", bg="#E6EBF4", fg=NAVY, anchor="w", font=(F, 9), padx=14, pady=5)
        self.status_lbl.pack(side="bottom", fill="x")
        self.body = tk.Frame(self, bg=BG)
        self.body.pack(fill="both", expand=True)
        self.pages = {"quote": ScrollFrame(self.body), "company": ScrollFrame(self.body)}
        self.build_quote(self.pages["quote"].inner)
        self.build_company(self.pages["company"].inner)
        self.bind_all("<MouseWheel>", self.on_wheel)
        self.current = "quote"
        self.new_quote()
        self.show("quote")
        if not self.company["name"]:
            self.show("company")
            self.status("Welcome! First fill in your company details and press Save.")

    # ------------------------------------------------------------ styling
    def style_setup(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("Q.TEntry", fieldbackground=WHITE, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER,
                    padding=6, foreground=INK)
        s.map("Q.TEntry", bordercolor=[("focus", GOLD)], lightcolor=[("focus", GOLD)], darkcolor=[("focus", GOLD)])
        s.configure("Q.TCombobox", fieldbackground=WHITE, background=WHITE, bordercolor=BORDER, lightcolor=BORDER,
                    darkcolor=BORDER, padding=5, arrowcolor=NAVY)
        s.map("Q.TCombobox", fieldbackground=[("readonly", WHITE)], bordercolor=[("focus", GOLD)])
        s.configure("Treeview", rowheight=30, font=(F, 10), background=WHITE, fieldbackground=WHITE,
                    foreground=INK, bordercolor=BORDER, lightcolor=BORDER, darkcolor=BORDER)
        s.configure("Treeview.Heading", background=NAVY, foreground="white", font=(FB, 10), relief="flat", padding=7)
        s.map("Treeview.Heading", background=[("active", NAVY2)])
        s.map("Treeview", background=[("selected", "#DCE6F7")], foreground=[("selected", NAVY)])

    def btn(self, parent, text, cmd, kind="ghost", big=False):
        bg, fg, hov = {"gold": (GOLD, NAVY, GOLD2), "navy": (NAVY, "white", NAVY2),
                       "ghost": ("#E6EBF4", NAVY, "#D5DDEC")}[kind]
        b = tk.Button(parent, text=text, command=cmd, bg=bg, fg=fg, activebackground=hov, activeforeground=fg,
                      relief="flat", bd=0, cursor="hand2", font=(FB, 12 if big else 10),
                      padx=24 if big else 16, pady=11 if big else 7)
        b.bind("<Enter>", lambda e: b.configure(bg=hov))
        b.bind("<Leave>", lambda e: b.configure(bg=bg))
        return b

    def card(self, parent, title):
        outer = tk.Frame(parent, bg=WHITE, highlightbackground=BORDER, highlightthickness=1)
        tk.Label(outer, text=title, bg=WHITE, fg=NAVY, font=(FB, 12)).pack(anchor="w", padx=16, pady=(12, 3))
        tk.Frame(outer, bg=GOLD, height=3, width=44).pack(anchor="w", padx=16)
        body = tk.Frame(outer, bg=WHITE)
        body.pack(fill="both", expand=True, padx=16, pady=(10, 14))
        return outer, body

    def status(self, msg, ok=True):
        self.status_lbl.configure(text="   " + msg, fg=NAVY if ok else "#B3261E")

    def on_wheel(self, e):
        w = self.winfo_containing(e.x_root, e.y_root)
        if isinstance(w, (ttk.Treeview, tk.Text)):
            return
        self.pages[self.current].canvas.yview_scroll(int(-e.delta / 120), "units")

    # ------------------------------------------------------------- header
    def build_header(self):
        h = tk.Frame(self, bg=NAVY)
        h.pack(fill="x")
        left = tk.Frame(h, bg=NAVY)
        left.pack(side="left", padx=22, pady=10)
        t = tk.Frame(left, bg=NAVY)
        t.pack(anchor="w")
        tk.Label(t, text="Quotation ", bg=NAVY, fg="white", font=(FB, 19)).pack(side="left")
        tk.Label(t, text="Maker", bg=NAVY, fg=GOLD, font=(FB, 19)).pack(side="left")
        tk.Label(left, text="Professional quotations in seconds", bg=NAVY, fg="#9FB0CF", font=(F, 9)).pack(anchor="w")
        nav = tk.Frame(h, bg=NAVY)
        nav.pack(side="left", padx=30)
        self.nav = {}
        for key, text in (("quote", "Quotation"), ("company", "My Company")):
            b = tk.Button(nav, text=text, relief="flat", bd=0, bg=NAVY, activebackground=NAVY, cursor="hand2",
                          font=(FB, 11), padx=14, pady=6, command=lambda k=key: self.show(k))
            b.pack(side="left", padx=2)
            self.nav[key] = b
        right = tk.Frame(h, bg=NAVY)
        right.pack(side="right", padx=22)
        self.gst_group = tk.Frame(right, bg=NAVY)
        self.gst_group.grid(row=0, column=0, padx=10)
        tk.Label(self.gst_group, text="GST", bg=NAVY, fg="white", font=(FB, 10)).pack(side="left", padx=(0, 8))
        Switch(self.gst_group, self.gst_var, self.apply_gst).pack(side="left")
        self.inter_group = tk.Frame(right, bg=NAVY)
        self.inter_group.grid(row=0, column=1, padx=10)
        tk.Label(self.inter_group, text="Inter-state (IGST)", bg=NAVY, fg="white", font=(FB, 10)).pack(side="left", padx=(0, 8))
        Switch(self.inter_group, self.inter_var, self.refresh).pack(side="left")
        tk.Frame(self, bg=GOLD, height=3).pack(fill="x")

    def show(self, key):
        self.current = key
        for k, p in self.pages.items():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, b in self.nav.items():
            b.configure(fg=GOLD if k == key else "#B8C4DC", font=(FB, 11) if k == key else (F, 11))

    # ------------------------------------------------------ form helpers
    def sv(self, key, value=""):
        self.v[key] = tk.StringVar(value=value)
        return self.v[key]

    def field(self, parent, label, key, row, gst=False, width=None):
        l = tk.Label(parent, text=label, bg=WHITE, fg=MUTED, font=(F, 9))
        e = ttk.Entry(parent, textvariable=self.sv(key), style="Q.TEntry", font=(F, 10), **({"width": width} if width else {}))
        l.grid(row=row, column=0, sticky="w", padx=(0, 10), pady=3)
        e.grid(row=row, column=1, sticky="we", pady=3)
        if gst:
            self.gst_only += [l, e]
        return e

    def textbox(self, parent, label, row, height=3):
        tk.Label(parent, text=label, bg=WHITE, fg=MUTED, font=(F, 9)).grid(row=row, column=0, sticky="nw", padx=(0, 10), pady=4)
        t = tk.Text(parent, height=height, font=(F, 10), wrap="word", relief="flat", bd=0, padx=6, pady=5,
                    highlightthickness=1, highlightbackground=BORDER, highlightcolor=GOLD, fg=INK)
        t.grid(row=row, column=1, sticky="we", pady=3)
        return t

    @staticmethod
    def get(t):
        return t.get("1.0", "end").strip()

    @staticmethod
    def put(t, s):
        t.delete("1.0", "end")
        t.insert("1.0", s or "")

    # ---------------------------------------------------- company page
    def build_company(self, root):
        root.columnconfigure(0, weight=1)
        pad = tk.Frame(root, bg=BG)
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        pad.columnconfigure(0, weight=1)
        pad.columnconfigure(1, weight=1)
        c = self.company
        self.cfield = {}
        a, ab = self.card(pad, "Business profile")
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ab.columnconfigure(1, weight=1)
        rows = [("Company name", "name"), ("Phone", "phone"), ("E-mail", "email"),
                ("GST number (printed only when GST is ON)", "gst"), ("PAN (optional)", "pan")]
        for r, (lbl, k) in enumerate(rows):
            tk.Label(ab, text=lbl, bg=WHITE, fg=MUTED, font=(F, 9)).grid(row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            var = tk.StringVar(value=str(c.get(k, "")))
            ttk.Entry(ab, textvariable=var, style="Q.TEntry", font=(F, 10)).grid(row=r, column=1, sticky="we", pady=3)
            self.cfield[k] = var
        self.c_addr = self.textbox(ab, "Address", len(rows), height=4)
        self.put(self.c_addr, c["address"])
        b, bb = self.card(pad, "Branding & defaults")
        b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        bb.columnconfigure(1, weight=1)
        tk.Label(bb, text="Logo (PNG / JPG)", bg=WHITE, fg=MUTED, font=(F, 9)).grid(row=0, column=0, sticky="w", pady=3)
        self.cfield["logo"] = tk.StringVar(value=c.get("logo", ""))
        lf = tk.Frame(bb, bg=WHITE)
        lf.grid(row=0, column=1, sticky="we")
        lf.columnconfigure(0, weight=1)
        ttk.Entry(lf, textvariable=self.cfield["logo"], style="Q.TEntry", font=(F, 10)).grid(row=0, column=0, sticky="we")
        self.btn(lf, "Browse", self.pick_logo).grid(row=0, column=1, padx=(6, 0))
        for r, (lbl, k) in enumerate([("Quotation prefix", "prefix"), ("Next quotation number", "next")], 1):
            tk.Label(bb, text=lbl, bg=WHITE, fg=MUTED, font=(F, 9)).grid(row=r, column=0, sticky="w", pady=3)
            var = tk.StringVar(value=str(c.get(k, "")))
            ttk.Entry(bb, textvariable=var, style="Q.TEntry", font=(F, 10)).grid(row=r, column=1, sticky="we", pady=3)
            self.cfield[k] = var
        self.c_bank = self.textbox(bb, "Bank details (optional)", 3, height=3)
        self.put(self.c_bank, c["bank"])
        self.c_terms = self.textbox(bb, "Default terms & conditions", 4, height=5)
        self.put(self.c_terms, c["terms"])
        bar = tk.Frame(pad, bg=BG)
        bar.grid(row=1, column=0, columnspan=2, sticky="e", pady=14)
        self.btn(bar, "Save company details", self.save_company, "gold", big=True).pack()

    def pick_logo(self):
        p = filedialog.askopenfilename(filetypes=[("Images", "*.png *.jpg *.jpeg")])
        if p:
            self.cfield["logo"].set(p)

    def save_company(self):
        for k, var in self.cfield.items():
            self.company[k] = var.get().strip()
        try:
            self.company["next"] = max(int(self.company["next"]), 1)
        except ValueError:
            self.company["next"] = 1
        self.company["address"] = self.get(self.c_addr)
        self.company["bank"] = self.get(self.c_bank)
        self.company["terms"] = self.get(self.c_terms)
        self.write_settings()
        self.status("Company details saved.")
        if self.items == [] and not self.get(self.terms):
            self.put(self.terms, self.company["terms"])
        self.show("quote")

    def write_settings(self):
        with open(SETTINGS, "w", encoding="utf-8") as f:
            json.dump(self.company, f, indent=2)

    # --------------------------------------------------- quotation page
    def build_quote(self, root):
        pad = tk.Frame(root, bg=BG)
        pad.pack(fill="both", expand=True, padx=24, pady=18)
        pad.columnconfigure(0, weight=1, uniform="c")
        pad.columnconfigure(1, weight=1, uniform="c")

        a, ab = self.card(pad, "Quotation details")
        a.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        ab.columnconfigure(1, weight=1)
        for r, (l, k) in enumerate([("Quotation No.", "number"), ("Date", "date"), ("Valid until", "validity"),
                                    ("Buyer's Ref / Order No.", "buyer_ref"), ("Payment terms", "payment"),
                                    ("Dispatched through", "dispatch"), ("Destination", "destination"),
                                    ("Other references", "other")]):
            self.field(ab, l, k, r)

        b, bb = self.card(pad, "Customer (Bill to)")
        b.grid(row=0, column=1, sticky="nsew", padx=(8, 0))
        bb.columnconfigure(1, weight=1)
        self.field(bb, "Customer name", "c_name", 0)
        self.c_address = self.textbox(bb, "Address", 1, height=3)
        self.field(bb, "Phone", "c_phone", 2)
        self.field(bb, "E-mail", "c_email", 3)
        self.field(bb, "GST number", "c_gst", 4, gst=True)
        self.field(bb, "PAN (optional)", "c_pan", 5)

        ic, ib = self.card(pad, "Items")
        ic.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=14)
        ib.columnconfigure(0, weight=1)
        heads = [("Description", "i_desc", 36), ("HSN/SAC", "i_hsn", 10), ("Qty", "i_qty", 7), ("Rate", "i_rate", 11),
                 ("Per", "i_per", 6), ("Disc %", "i_disc", 7), ("GST %", "i_gst", 7)]
        self.item_entries = []
        for col, (lbl, key, w) in enumerate(heads):
            l = tk.Label(ib, text=lbl, bg=WHITE, fg=MUTED, font=(F, 9))
            e = ttk.Entry(ib, textvariable=self.sv(key), style="Q.TEntry", font=(F, 10), width=w)
            l.grid(row=0, column=col, sticky="w", padx=3)
            e.grid(row=1, column=col, sticky="we", padx=3, pady=(0, 8))
            e.bind("<Return>", lambda ev: self.add_item())
            if key in ("i_hsn", "i_gst"):
                self.gst_only += [l, e]
        bf = tk.Frame(ib, bg=WHITE)
        bf.grid(row=1, column=len(heads), padx=(8, 0), pady=(0, 8))
        self.btn(bf, "Add item", self.add_item, "gold").pack(side="left")
        self.btn(bf, "Update", self.update_item).pack(side="left", padx=6)
        self.btn(bf, "Remove", self.del_item).pack(side="left")

        cols = ("sl", "desc", "hsn", "qty", "rate", "per", "disc", "gst", "amount")
        tf = tk.Frame(ib, bg=WHITE)
        tf.grid(row=2, column=0, columnspan=len(heads) + 1, sticky="nsew")
        tf.columnconfigure(0, weight=1)
        self.tree = ttk.Treeview(tf, columns=cols, show="headings", height=7, selectmode="browse")
        for k, h, w in (("sl", "Sl", 40), ("desc", "Description", 360), ("hsn", "HSN/SAC", 90), ("qty", "Qty", 70),
                        ("rate", "Rate", 110), ("per", "Per", 60), ("disc", "Disc %", 70), ("gst", "GST %", 70),
                        ("amount", "Amount", 130)):
            self.tree.heading(k, text=h)
            self.tree.column(k, width=w, anchor="w" if k == "desc" else "center")
        self.tree.tag_configure("odd", background="#F6F8FC")
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        tc, tb = self.card(pad, "Terms & conditions")
        tc.grid(row=2, column=0, sticky="nsew", padx=(0, 8))
        tb.columnconfigure(0, weight=1)
        self.terms = tk.Text(tb, height=8, font=(F, 10), wrap="word", relief="flat", bd=0, padx=6, pady=5,
                             highlightthickness=1, highlightbackground=BORDER, highlightcolor=GOLD, fg=INK)
        self.terms.grid(row=0, column=0, sticky="nsew")

        sc, sbd = self.card(pad, "Summary & style")
        sc.grid(row=2, column=1, sticky="nsew", padx=(8, 0))
        sbd.columnconfigure(1, weight=1)
        self.field(sbd, "Discount on total", "disc_total", 0)
        self.field(sbd, "Extra charge name", "extra_label", 1)
        self.field(sbd, "Extra charge amount", "extra_amount", 2)
        for k in ("disc_total", "extra_label", "extra_amount"):
            self.v[k].trace_add("write", lambda *a: self.refresh())
        tk.Checkbutton(sbd, text="Round off total to nearest rupee", variable=self.round_var, command=self.refresh,
                       bg=WHITE, activebackground=WHITE, fg=INK, font=(F, 9), selectcolor=WHITE).grid(
            row=3, column=0, columnspan=2, sticky="w", pady=2)
        tk.Label(sbd, text="PDF colour theme", bg=WHITE, fg=MUTED, font=(F, 9)).grid(row=4, column=0, sticky="w", pady=3)
        ttk.Combobox(sbd, textvariable=self.theme_var, values=list(THEMES), state="readonly",
                     style="Q.TCombobox", font=(F, 10)).grid(row=4, column=1, sticky="we", pady=3)
        tot = tk.Frame(sbd, bg=NAVY)
        tot.grid(row=5, column=0, columnspan=2, sticky="we", pady=(10, 0))
        self.sub_lbl = tk.Label(tot, bg=NAVY, fg="#B8C4DC", font=(F, 9), anchor="e", justify="right")
        self.sub_lbl.pack(fill="x", padx=14, pady=(8, 0))
        self.total_lbl = tk.Label(tot, bg=NAVY, fg=GOLD, font=(FB, 20), anchor="e")
        self.total_lbl.pack(fill="x", padx=14, pady=(0, 8))

        bar = tk.Frame(pad, bg=BG)
        bar.grid(row=3, column=0, columnspan=2, sticky="we", pady=(14, 0))
        self.btn(bar, "New quotation", self.new_quote).pack(side="left")
        self.btn(bar, "Open saved...", self.open_quote).pack(side="left", padx=8)
        self.btn(bar, "PDF folder", lambda: os.startfile(PDF_DIR)).pack(side="left")
        self.btn(bar, "Save & create PDF", self.create_pdf, "gold", big=True).pack(side="right")

    # -------------------------------------------------------- GST on/off
    def apply_gst(self):
        on = self.gst_var.get()
        for w in self.gst_only:
            w.grid() if on else w.grid_remove()
        if on:
            self.inter_group.grid()
            self.tree.configure(displaycolumns=("sl", "desc", "hsn", "qty", "rate", "per", "disc", "gst", "amount"))
        else:
            self.inter_group.grid_remove()
            self.inter_var.set(False)
            self.tree.configure(displaycolumns=("sl", "desc", "qty", "rate", "per", "disc", "amount"))
        self.refresh()
        self.status("GST is ON - CGST/SGST/IGST will be shown." if on else "GST is OFF - no GST details will appear.")

    # ------------------------------------------------------------- items
    def read_item(self):
        g = lambda k: self.v[k].get().strip()
        if not g("i_desc"):
            self.status("Enter the item description.", False)
            return None
        for key, label, lo, hi in (("i_qty", "Quantity", 0.0001, None), ("i_rate", "Rate", 0, None),
                                   ("i_disc", "Discount %", 0, 100), ("i_gst", "GST %", 0, 100)):
            raw = g(key).replace(",", "")
            if raw:
                try:
                    val = float(raw)
                except ValueError:
                    self.status(f"{label} must be a number.", False)
                    return None
                if val < lo or (hi is not None and val > hi):
                    self.status(f"{label} is out of range.", False)
                    return None
        return {"desc": g("i_desc"), "hsn": g("i_hsn"), "qty": g("i_qty") or "1", "rate": g("i_rate") or "0",
                "per": g("i_per") or "Nos", "disc": g("i_disc") or "0", "gst": g("i_gst") or "0"}

    def clear_item(self):
        for k in ("i_desc", "i_hsn", "i_qty", "i_rate", "i_per", "i_disc", "i_gst"):
            self.v[k].set("")
        self.sel = None

    def add_item(self):
        it = self.read_item()
        if it:
            self.items.append(it)
            self.clear_item()
            self.refresh()
            self.status("Item added.")

    def update_item(self):
        if self.sel is None:
            self.status("Click an item in the table first, edit it above, then press Update.", False)
            return
        it = self.read_item()
        if it:
            self.items[self.sel] = it
            self.clear_item()
            self.refresh()
            self.status("Item updated.")

    def del_item(self):
        if self.sel is None:
            self.status("Click an item in the table first.", False)
            return
        del self.items[self.sel]
        self.clear_item()
        self.refresh()
        self.status("Item removed.")

    def on_select(self, _e=None):
        s = self.tree.selection()
        if not s:
            return
        self.sel = self.tree.index(s[0])
        it = self.items[self.sel]
        for k, f in (("i_desc", "desc"), ("i_hsn", "hsn"), ("i_qty", "qty"), ("i_rate", "rate"),
                     ("i_per", "per"), ("i_disc", "disc"), ("i_gst", "gst")):
            self.v[k].set(it.get(f, ""))

    # ------------------------------------------------------- data <-> form
    def collect(self):
        g = lambda k: self.v[k].get().strip()
        return {"gst_enabled": self.gst_var.get(), "interstate": self.inter_var.get(), "theme": self.theme_var.get(),
                "number": g("number"), "date": g("date"), "validity": g("validity"),
                "refs": {"buyer_ref": g("buyer_ref"), "payment": g("payment"), "dispatch": g("dispatch"),
                         "destination": g("destination"), "other": g("other")},
                "client": {"name": g("c_name"), "address": self.get(self.c_address), "phone": g("c_phone"),
                           "email": g("c_email"), "gst": g("c_gst"), "pan": g("c_pan")},
                "items": self.items, "discount_total": g("disc_total"), "extra_label": g("extra_label"),
                "extra_amount": g("extra_amount"), "terms": self.get(self.terms), "round_off": self.round_var.get()}

    def load(self, q):
        self.gst_var.set(q.get("gst_enabled", False))
        self.inter_var.set(q.get("interstate", False))
        self.round_var.set(q.get("round_off", True))
        self.theme_var.set(q.get("theme") if q.get("theme") in THEMES else DEFAULT_THEME)
        for k in ("number", "date", "validity"):
            self.v[k].set(q.get(k, ""))
        r, c = q.get("refs", {}), q.get("client", {})
        for k in ("buyer_ref", "payment", "dispatch", "destination", "other"):
            self.v[k].set(r.get(k, ""))
        for k, src in (("c_name", "name"), ("c_phone", "phone"), ("c_email", "email"), ("c_gst", "gst"),
                       ("c_pan", "pan")):
            self.v[k].set(c.get(src, ""))
        self.put(self.c_address, c.get("address", ""))
        self.items = list(q.get("items", []))
        self.v["disc_total"].set(q.get("discount_total", ""))
        self.v["extra_label"].set(q.get("extra_label", ""))
        self.v["extra_amount"].set(q.get("extra_amount", ""))
        self.put(self.terms, q.get("terms", ""))
        self.clear_item()
        self.inter_var.set(bool(q.get("interstate", False)) and bool(q.get("gst_enabled", False)))
        self.apply_gst()
        for w in self.inter_group.winfo_children():
            if isinstance(w, Switch):
                w.draw()
        for w in self.gst_group.winfo_children():
            if isinstance(w, Switch):
                w.draw()

    def new_quote(self):
        today = datetime.date.today()
        fmt = lambda d: d.strftime("%d-%m-%Y")
        self.load({"gst_enabled": False, "number": f"{self.company['prefix']}{int(self.company['next']):04d}",
                   "date": fmt(today), "validity": fmt(today + datetime.timedelta(days=15)),
                   "terms": self.company["terms"], "theme": self.company.get("theme", DEFAULT_THEME),
                   "round_off": True, "items": []})
        self.show("quote")

    def refresh(self):
        c = calc(self.collect())
        self.tree.delete(*self.tree.get_children())
        for i, r in enumerate(c["rows"], 1):
            self.tree.insert("", "end", tags=("odd",) if i % 2 == 0 else (),
                             values=(i, r["desc"], r.get("hsn", ""), r["qty"], money(num(r["rate"])),
                                     r.get("per", ""), r.get("disc", ""), r.get("gst", ""), money(r["net"])))
        txt = f"Sub total {money(c['subtotal'])}"
        if c["discount_total"]:
            txt += f"   |   Discount -{money(c['discount_total'])}"
        if self.gst_var.get():
            txt += f"   |   GST {money(c['tax'])}"
        self.sub_lbl.configure(text=txt)
        self.total_lbl.configure(text="Total  \u20b9 " + money(c["total"]))

    # --------------------------------------------------- save / open / pdf
    def create_pdf(self):
        q = self.collect()
        if not self.company["name"]:
            self.show("company")
            self.status("Please fill in your company details first.", False)
            return
        if not q["client"]["name"]:
            self.status("Enter the customer name.", False)
            return
        if not q["items"]:
            self.status("Add at least one item.", False)
            return
        safe = "".join(ch for ch in q["number"] if ch.isalnum() or ch in "-_") or "quotation"
        pdf = os.path.join(PDF_DIR, safe + ".pdf")
        try:
            render_pdf(q, self.company, pdf)
        except PermissionError:
            messagebox.showerror(APP, "This PDF is open in another program. Close it and try again.")
            return
        except Exception as exc:
            messagebox.showerror(APP, f"Could not create the PDF:\n{exc}")
            return
        with open(os.path.join(DATA_DIR, safe + ".json"), "w", encoding="utf-8") as f:
            json.dump(q, f, indent=2)
        self.company["theme"] = q["theme"]
        if q["number"] == f"{self.company['prefix']}{int(self.company['next']):04d}":
            self.company["next"] = int(self.company["next"]) + 1
            self.cfield["next"].set(str(self.company["next"]))
        self.write_settings()
        self.status(f"Saved: {pdf}")
        try:
            os.startfile(pdf)
        except Exception:
            pass

    def open_quote(self):
        p = filedialog.askopenfilename(initialdir=DATA_DIR, filetypes=[("Saved quotation", "*.json")])
        if p:
            try:
                with open(p, encoding="utf-8") as f:
                    self.load(json.load(f))
                self.show("quote")
                self.status("Quotation loaded.")
            except Exception as exc:
                messagebox.showerror(APP, f"Could not open the file:\n{exc}")


if __name__ == "__main__":
    App().mainloop()
