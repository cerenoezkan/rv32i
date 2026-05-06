import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import time
import threading

try:
    from lib.parser import parse_input
    from linker import link
    MODULES_LOADED = True
except ImportError:
    MODULES_LOADED = False

VERSION = "2.0 · Academic Edition"

# ─── RENK PALETİ ────────────────────────────────────────────────────────────
BG_DEEP    = "#0a0c10"
BG_PANEL   = "#0f1117"
BG_CARD    = "#141720"
BG_HOVER   = "#1c2030"
BORDER     = "#1e2540"
BORDER_LIT = "#2a3560"
ACCENT     = "#00d4ff"
ACCENT2    = "#7c3aed"
SUCCESS    = "#00e676"
WARNING    = "#ffab00"
DANGER     = "#ff1744"
TEXT_PRI   = "#e8ecf8"
TEXT_SEC   = "#7a8ab0"
TEXT_DIM   = "#3d4a6a"
GLOW       = "#00d4ff33"

# ─── KONSOL AKISI ────────────────────────────────────────────────────────────
class GUIStream:
    def __init__(self, callback):
        self.callback = callback
    def write(self, s):
        self.callback(s)
    def flush(self):
        pass

# ─── PARLAYAN DÜĞME ──────────────────────────────────────────────────────────
class GlowButton(tk.Canvas):
    def __init__(self, parent, text, command, color=ACCENT, width=180, height=40, **kwargs):
        super().__init__(parent, width=width, height=height,
                         bg=BG_PANEL, highlightthickness=0, cursor="hand2")
        self.command = command
        self.color   = color
        self.txt     = text
        self.w       = width
        self.h       = height
        self._draw(False)
        self.bind("<Enter>",    self._on_enter)
        self.bind("<Leave>",    self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _hex_alpha(self, hex_color, alpha):
        r = int(hex_color[1:3], 16)
        g = int(hex_color[3:5], 16)
        b = int(hex_color[5:7], 16)
        return f"#{int(r*alpha):02x}{int(g*alpha):02x}{int(b*alpha):02x}"

    def _draw(self, hover):
        self.delete("all")
        w, h = self.w, self.h
        fill  = self._hex_alpha(self.color, 0.18 if hover else 0.08)
        bord  = self.color if hover else self._hex_alpha(self.color, 0.5)
        self.create_rectangle(2, 2, w-2, h-2, fill=fill, outline=bord, width=1)
        cl = 8
        self.create_line(2, 2, 2+cl, 2, fill=self.color, width=2)
        self.create_line(2, 2, 2, 2+cl, fill=self.color, width=2)
        self.create_line(w-2, h-2, w-2-cl, h-2, fill=self.color, width=2)
        self.create_line(w-2, h-2, w-2, h-2-cl, fill=self.color, width=2)
        fc = TEXT_PRI if hover else TEXT_SEC
        self.create_text(w//2, h//2, text=self.txt, fill=fc,
                         font=("Courier New", 9, "bold"))

    def _on_enter(self, e): self._draw(True)
    def _on_leave(self, e): self._draw(False)
    def _on_click(self, e):
        self._draw(False)
        if self.command:
            self.command()

# ─── DOSYA KARTI ─────────────────────────────────────────────────────────────
class FileCard(tk.Frame):
    def __init__(self, parent, filename, on_remove, **kwargs):
        super().__init__(parent, bg=BG_CARD, **kwargs)
        self.configure(relief="flat", bd=0)

        indicator = tk.Canvas(self, width=3, bg=ACCENT, highlightthickness=0)
        indicator.pack(side=tk.LEFT, fill=tk.Y)

        inner = tk.Frame(self, bg=BG_CARD, padx=10, pady=8)
        inner.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        tk.Label(inner, text="⬡", fg=ACCENT, bg=BG_CARD,
                 font=("Courier New", 12)).pack(side=tk.LEFT, padx=(0, 8))
        tk.Label(inner, text=filename, fg=TEXT_PRI, bg=BG_CARD,
                 font=("Courier New", 9, "bold")).pack(side=tk.LEFT)

        close = tk.Label(self, text="✕", fg=TEXT_DIM, bg=BG_CARD,
                         font=("Courier New", 9), cursor="hand2", padx=10)
        close.pack(side=tk.RIGHT)
        close.bind("<Button-1>", lambda e: on_remove(self))
        close.bind("<Enter>", lambda e: close.config(fg=DANGER))
        close.bind("<Leave>", lambda e: close.config(fg=TEXT_DIM))

# ─── ANA UYGULAMA ─────────────────────────────────────────────────────────────
class RVI_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title("RVI · RV32I Linker & Assembler System")
        self.root.geometry("1100x780")
        self.root.configure(bg=BG_DEEP)
        self.root.minsize(900, 650)

        self.files_to_process = []
        self.file_cards       = {}
        self._blink_state     = True

        self._build_ui()
        self._start_blink()

    # ── UI İNŞASI ──────────────────────────────────────────────────────────────
    def _build_ui(self):
        self._build_header()
        self._build_body()
        self._build_statusbar()

    def _build_header(self):
        hdr = tk.Frame(self.root, bg=BG_PANEL, height=70)
        hdr.pack(fill=tk.X)
        hdr.pack_propagate(False)

        left = tk.Frame(hdr, bg=BG_PANEL)
        left.pack(side=tk.LEFT, padx=24, fill=tk.Y)

        logo = tk.Canvas(left, width=36, height=36, bg=BG_PANEL, highlightthickness=0)
        logo.pack(side=tk.LEFT, pady=17, padx=(0, 12))
        logo.create_polygon(18,2, 34,10, 34,26, 18,34, 2,26, 2,10,
                            fill="", outline=ACCENT, width=1.5)
        logo.create_text(18, 18, text="RV", fill=ACCENT, font=("Courier New", 9, "bold"))

        title_block = tk.Frame(left, bg=BG_PANEL)
        title_block.pack(side=tk.LEFT, fill=tk.Y, pady=14)
        tk.Label(title_block, text="RVI LINKER SYSTEM",
                 fg=TEXT_PRI, bg=BG_PANEL,
                 font=("Courier New", 14, "bold")).pack(anchor="w")
        tk.Label(title_block, text=f"RV32I · {VERSION}",
                 fg=TEXT_SEC, bg=BG_PANEL,
                 font=("Courier New", 8)).pack(anchor="w")

        mid = tk.Frame(hdr, bg=BG_PANEL)
        mid.pack(side=tk.LEFT, expand=True)
        self.status_dot = tk.Canvas(mid, width=10, height=10, bg=BG_PANEL,
                                    highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self._dot_id = self.status_dot.create_oval(1,1,9,9, fill=ACCENT, outline="")
        self.status_label = tk.Label(mid, text="HAZIR",
                                     fg=ACCENT, bg=BG_PANEL,
                                     font=("Courier New", 8, "bold"))
        self.status_label.pack(side=tk.LEFT)

        right = tk.Frame(hdr, bg=BG_PANEL)
        right.pack(side=tk.RIGHT, padx=20, fill=tk.Y)

        for txt, cmd, col in [
            ("[ + ] DOSYA EKLE",     self.select_files, ACCENT),
            ("[ ▶ ] DERLE & LINKLE", self.run_process,  SUCCESS),
            ("[ ✕ ] TEMİZLE",        self.clear_all,    DANGER),
        ]:
            btn = GlowButton(right, txt, cmd, color=col, width=165, height=36)
            btn.pack(side=tk.LEFT, padx=6, pady=17)

        sep = tk.Canvas(self.root, height=1, bg=BORDER, highlightthickness=0)
        sep.pack(fill=tk.X)

    def _build_body(self):
        body = tk.Frame(self.root, bg=BG_DEEP)
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=12)
        body.columnconfigure(0, weight=1, minsize=260)
        body.columnconfigure(1, weight=3)
        body.rowconfigure(0, weight=1)

        # ── SOL PANEL ────────────────────────────────────────────────────
        left_col = tk.Frame(body, bg=BG_PANEL, bd=0)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 10))

        self._section_label(left_col, "DOSYA YÖNETİCİSİ")

        self.files_frame = tk.Frame(left_col, bg=BG_PANEL)
        self.files_frame.pack(fill=tk.BOTH, expand=True, padx=8, pady=4)

        self.empty_label = tk.Label(
            self.files_frame,
            text="─── Dosya yok ───\n.asm eklemek için\nyukarıdaki butonu kullanın",
            fg=TEXT_DIM, bg=BG_PANEL,
            font=("Courier New", 8), justify="center"
        )
        self.empty_label.pack(expand=True)

        stats_frame = tk.Frame(left_col, bg=BG_CARD, pady=8)
        stats_frame.pack(fill=tk.X, padx=8, pady=8)
        self._draw_stat_divider(stats_frame)
        self.stat_files  = self._stat_item(stats_frame, "DOSYA", "0")
        self._draw_stat_divider(stats_frame)
        self.stat_status = self._stat_item(stats_frame, "DURUM", "BEKLE")
        self._draw_stat_divider(stats_frame)

        # ── SAĞ PANEL ─────────────────────────────────────────────────────
        right_col = tk.Frame(body, bg=BG_PANEL)
        right_col.grid(row=0, column=1, sticky="nsew")

        self._section_label(right_col, "ÇIKTI PANELİ")

        tab_bar = tk.Frame(right_col, bg=BG_PANEL)
        tab_bar.pack(fill=tk.X, padx=8)

        self.tab_content = tk.Frame(right_col, bg=BG_DEEP)
        self.tab_content.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._tabs    = {}
        self._cur_tab = None

        for tab_id, label in [
            ("log", "◈  İŞLEM GÜNLÜĞÜ"),
            ("sym", "◈  SEMBOL TABLOSU"),
            ("hex", "◈  FINAL HEX"),
        ]:
            btn = tk.Label(tab_bar, text=label, fg=TEXT_DIM, bg=BG_PANEL,
                           font=("Courier New", 8, "bold"), padx=16, pady=8,
                           cursor="hand2")
            btn.pack(side=tk.LEFT)
            btn.bind("<Button-1>", lambda e, t=tab_id: self._switch_tab(t))
            btn.bind("<Enter>",  lambda e, b=btn: b.config(fg=TEXT_SEC)
                     if b != self._tabs.get(self._cur_tab, {}).get("btn") else None)
            btn.bind("<Leave>",  lambda e, t2=tab_id, b=btn:
                     b.config(fg=ACCENT if t2 == self._cur_tab else TEXT_DIM))
            self._tabs[tab_id] = {"btn": btn}

        # LOG sekmesi
        log_frame = tk.Frame(self.tab_content, bg=BG_DEEP)
        self.txt_log = tk.Text(log_frame, bg=BG_DEEP, fg=SUCCESS,
                               font=("Courier New", 9),
                               insertbackground=ACCENT, bd=0,
                               selectbackground=ACCENT2, relief="flat",
                               wrap=tk.WORD, padx=12, pady=10)
        log_scroll = tk.Scrollbar(log_frame, command=self.txt_log.yview,
                                  bg=BG_CARD, troughcolor=BG_DEEP,
                                  activebackground=ACCENT, bd=0)
        self.txt_log.config(yscrollcommand=log_scroll.set)
        log_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self._tabs["log"]["frame"] = log_frame
        self._setup_log_tags()

        # SEMBOL TABLOSU sekmesi
        sym_frame = tk.Frame(self.tab_content, bg=BG_DEEP)
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Custom.Treeview",
                         background=BG_DEEP, foreground=TEXT_PRI,
                         fieldbackground=BG_DEEP, rowheight=30,
                         font=("Courier New", 9), borderwidth=0)
        style.configure("Custom.Treeview.Heading",
                         background=BG_CARD, foreground=ACCENT,
                         font=("Courier New", 9, "bold"),
                         borderwidth=0, relief="flat")
        style.map("Custom.Treeview",
                  background=[("selected", ACCENT2)],
                  foreground=[("selected", TEXT_PRI)])

        # Sütunlara "Kaynak Dosya" eklendi
        cols = ("Symbol", "Address", "Scope", "Source", "Status")
        self.tree = ttk.Treeview(sym_frame, columns=cols, show="headings",
                                  style="Custom.Treeview")
        for col, w in [("Symbol", 180), ("Address", 130), ("Scope", 90),
                        ("Source", 160), ("Status", 100)]:
            self.tree.heading(col, text=col.upper())
            self.tree.column(col, anchor="center", width=w)
        sym_scroll = ttk.Scrollbar(sym_frame, command=self.tree.yview)
        self.tree.config(yscrollcommand=sym_scroll.set)
        sym_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.tree.pack(fill=tk.BOTH, expand=True)
        self._tabs["sym"]["frame"] = sym_frame

        # HEX sekmesi
        hex_frame = tk.Frame(self.tab_content, bg=BG_DEEP)
        self.txt_hex = tk.Text(hex_frame, bg=BG_DEEP, fg=ACCENT,
                               font=("Courier New", 10, "bold"),
                               insertbackground=ACCENT, bd=0,
                               selectbackground=ACCENT2, relief="flat",
                               padx=12, pady=10)
        hex_scroll = tk.Scrollbar(hex_frame, command=self.txt_hex.yview,
                                  bg=BG_CARD, troughcolor=BG_DEEP,
                                  activebackground=ACCENT, bd=0)
        self.txt_hex.config(yscrollcommand=hex_scroll.set)
        hex_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.txt_hex.pack(fill=tk.BOTH, expand=True)
        self._tabs["hex"]["frame"] = hex_frame

        self._switch_tab("log")

    def _build_statusbar(self):
        sep = tk.Canvas(self.root, height=1, bg=BORDER, highlightthickness=0)
        sep.pack(fill=tk.X)

        bar = tk.Frame(self.root, bg=BG_PANEL, height=28)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="RVI v2.0  ·  PicoRV32 / RV32I  ·  FPGA Linker System",
                 fg=TEXT_DIM, bg=BG_PANEL,
                 font=("Courier New", 7)).pack(side=tk.LEFT, padx=16, pady=6)

        self.bar_msg = tk.Label(bar, text="Sistem hazır.",
                                fg=TEXT_DIM, bg=BG_PANEL,
                                font=("Courier New", 7))
        self.bar_msg.pack(side=tk.RIGHT, padx=16, pady=6)

    # ── YARDIMCI UI ────────────────────────────────────────────────────────────
    def _section_label(self, parent, text):
        frm = tk.Frame(parent, bg=BG_PANEL)
        frm.pack(fill=tk.X, padx=8, pady=(10, 6))
        tk.Canvas(frm, width=3, height=14, bg=ACCENT,
                  highlightthickness=0).pack(side=tk.LEFT)
        tk.Label(frm, text=f"  {text}", fg=TEXT_SEC, bg=BG_PANEL,
                 font=("Courier New", 7, "bold")).pack(side=tk.LEFT)

    def _draw_stat_divider(self, parent):
        tk.Frame(parent, bg=BORDER, width=1).pack(side=tk.LEFT, fill=tk.Y, pady=4)

    def _stat_item(self, parent, label, value):
        frm = tk.Frame(parent, bg=BG_CARD, padx=14, pady=4)
        frm.pack(side=tk.LEFT, expand=True)
        val_lbl = tk.Label(frm, text=value, fg=ACCENT, bg=BG_CARD,
                           font=("Courier New", 16, "bold"))
        val_lbl.pack()
        tk.Label(frm, text=label, fg=TEXT_DIM, bg=BG_CARD,
                 font=("Courier New", 6, "bold")).pack()
        return val_lbl

    def _setup_log_tags(self):
        self.txt_log.tag_config("header",  foreground=ACCENT,   font=("Courier New", 9, "bold"))
        self.txt_log.tag_config("success", foreground=SUCCESS)
        self.txt_log.tag_config("error",   foreground=DANGER)
        self.txt_log.tag_config("warn",    foreground=WARNING)
        self.txt_log.tag_config("info",    foreground=TEXT_SEC)
        self.txt_log.tag_config("dim",     foreground=TEXT_DIM)

    def _switch_tab(self, tab_id):
        for tid, data in self._tabs.items():
            data["frame"].pack_forget()
            data["btn"].config(fg=TEXT_DIM)
        self._cur_tab = tab_id
        self._tabs[tab_id]["frame"].pack(fill=tk.BOTH, expand=True)
        self._tabs[tab_id]["btn"].config(fg=ACCENT)

    def _start_blink(self):
        def blink():
            while True:
                color = ACCENT if self._blink_state else BG_PANEL
                try:
                    self.status_dot.itemconfig(self._dot_id, fill=color)
                except:
                    break
                self._blink_state = not self._blink_state
                time.sleep(1.2)
        t = threading.Thread(target=blink, daemon=True)
        t.start()

    # ── DOSYA İŞLEMLERİ ────────────────────────────────────────────────────────
    def select_files(self):
        files = filedialog.askopenfilenames(
            title="Assembly Dosyaları Seç",
            filetypes=[("Assembly Files", "*.asm"), ("All Files", "*.*")]
        )
        for f in files:
            if f not in self.files_to_process:
                self.files_to_process.append(f)
                self._add_file_card(f)
        self._update_stats()

    def _add_file_card(self, filepath):
        self.empty_label.pack_forget()
        name = os.path.basename(filepath)
        card = FileCard(self.files_frame, name, self._remove_card)
        card.pack(fill=tk.X, pady=2)
        self.file_cards[filepath] = card
        self._log(f"[+] Dosya eklendi: {name}", "info")

    def _remove_card(self, card_widget):
        for path, card in list(self.file_cards.items()):
            if card == card_widget:
                self.files_to_process.remove(path)
                del self.file_cards[path]
                card.destroy()
                break
        if not self.files_to_process:
            self.empty_label.pack(expand=True)
        self._update_stats()

    def _update_stats(self):
        self.stat_files.config(text=str(len(self.files_to_process)))

    def clear_all(self):
        self.files_to_process = []
        for card in self.file_cards.values():
            card.destroy()
        self.file_cards = {}
        self.empty_label.pack(expand=True)
        self.txt_log.delete("1.0", tk.END)
        self.txt_hex.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._update_stats()
        self.stat_status.config(text="BEKLE", fg=TEXT_SEC)
        self.bar_msg.config(text="Sistem sıfırlandı.")
        self._log("Sistem sıfırlandı. Yeni proje için hazır.", "dim")

    # ── LOG ────────────────────────────────────────────────────────────────────
    def _log(self, msg, tag="success"):
        ts = time.strftime("%H:%M:%S")
        self.txt_log.insert(tk.END, f"[{ts}] ", "dim")
        self.txt_log.insert(tk.END, msg + "\n", tag)
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    def _log_raw(self, text):
        self.txt_log.insert(tk.END, text, "info")
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    # ── ANA İŞLEM ──────────────────────────────────────────────────────────────
    def run_process(self):
        if not self.files_to_process:
            messagebox.showwarning("Uyarı", "İşlem yapılacak .asm dosyası bulunamadı!")
            return

        if not MODULES_LOADED:
            messagebox.showerror("Modül Hatası",
                "lib.parser / linker modülleri bulunamadı.")
            return

        self._switch_tab("log")
        self.txt_log.delete("1.0", tk.END)
        self.txt_hex.delete("1.0", tk.END)
        for item in self.tree.get_children():
            self.tree.delete(item)

        self.stat_status.config(text="ÇALIŞIYOR", fg=WARNING)
        self.bar_msg.config(text="İşlem devam ediyor...")

        old_stdout = sys.stdout
        sys.stdout = GUIStream(self._log_raw)

        try:
            self._log("─" * 60, "dim")
            self._log("  RVI RV32I LINKER — İŞLEM RAPORU", "header")
            self._log("─" * 60, "dim")

            obj_files = []

            # ── ASSEMBLE AŞAMASI ──────────────────────────────────────────
            self._log("\n▶ ASSEMBLE AŞAMASI", "header")
            for asm_file in self.files_to_process:
                name = os.path.basename(asm_file)
                self._log(f"  Derleniyor: {name}", "info")

                res = parse_input(asm_file)

                obj_file = os.path.splitext(asm_file)[0] + ".o"
                obj_files.append(obj_file)

                exports = res.get('exports', [])
                imports = res.get('imports', [])
                self._log(f"  ✓ {name} → {os.path.basename(obj_file)}", "success")
                if exports:
                    self._log(f"    exports: {exports}", "info")
                if imports:
                    self._log(f"    imports: {imports}", "info")
                if res['relocations']:
                    syms = [r['symbol'] for r in res['relocations']]
                    self._log(f"    relocations: {syms}", "warn")

            # ── LINKING AŞAMASI ───────────────────────────────────────────
            self._log("\n▶ LINKING AŞAMASI", "header")
            output_hex = os.path.join(
                os.path.dirname(self.files_to_process[0]), "output.hex"
            )

            # link() artık üç değer döndürüyor:
            # global_symbols, all_symbols (lokal dahil), symbol_scopes
            global_symbols, all_symbols, symbol_scopes = link(
                object_files=obj_files,
                output_path=output_hex,
                hex_mode=True
            )

            # ── SEMBOL TABLOSU ────────────────────────────────────────────
            # all_symbols: tüm semboller (lokal + global)
            # symbol_scopes: {sym: ('GLOBAL'/'LOCAL', kaynak_dosya)}
            self._switch_tab("sym")
            for item in self.tree.get_children():
                self.tree.delete(item)

            # Önce GLOBAL semboller, sonra LOCAL semboller (sıralı görünüm)
            def sort_key(sym):
                scope, _ = symbol_scopes.get(sym, ('LOCAL', ''))
                return (0 if scope == 'GLOBAL' else 1, sym)

            for sym in sorted(all_symbols.keys(), key=sort_key):
                addr  = all_symbols[sym]
                scope, src_file = symbol_scopes.get(sym, ('LOCAL', '?'))
                status = "RESOLVED" if scope == 'GLOBAL' else "LOCAL"
                self.tree.insert("", tk.END,
                                 values=(sym, f"0x{addr:08X}", scope, src_file, status))

            # ── HEX ÇIKTI ─────────────────────────────────────────────────
            with open(output_hex, 'r') as hf:
                hex_content = hf.read()
            self.txt_hex.delete("1.0", tk.END)
            self.txt_hex.insert(tk.END, hex_content)
            self._switch_tab("hex")

            instr_lines = [l for l in hex_content.splitlines()
                           if l and not l.startswith('//') and not l.startswith('@')]
            byte_count  = len(instr_lines) * 4

            self._log(f"\n✓ Linkleme başarıyla tamamlandı.", "success")
            self._log(f"  Program boyutu  : {byte_count} Byte ({len(instr_lines)} komut)", "info")
            self._log(f"  Toplam sembol   : {len(all_symbols)} ({len(global_symbols)} global, "
                      f"{len(all_symbols) - len(global_symbols)} lokal)", "info")
            self._log(f"  Global semboller: {list(global_symbols.keys())}", "info")
            self._log(f"  Çıktı dosyası   : {output_hex}", "info")

            self.stat_status.config(text="TAMAM", fg=SUCCESS)
            self.bar_msg.config(
                text=f"Linkleme tamamlandı · {len(instr_lines)} komut · "
                     f"{len(all_symbols)} sembol ({len(global_symbols)} global)"
            )
            messagebox.showinfo("Başarılı",
                f"Linkleme tamamlandı!\n"
                f"Komut sayısı   : {len(instr_lines)}\n"
                f"Toplam sembol  : {len(all_symbols)}\n"
                f"Global sembol  : {len(global_symbols)}\n"
                f"Çıktı          : {os.path.basename(output_hex)}")

        except Exception as e:
            self._switch_tab("log")
            self._log(f"\n✕ HATA: {str(e)}", "error")
            self.stat_status.config(text="HATA", fg=DANGER)
            self.bar_msg.config(text=f"Hata: {str(e)[:80]}")
            messagebox.showerror("Sistem Hatası", str(e))

        finally:
            sys.stdout = old_stdout


if __name__ == "__main__":
    root = tk.Tk()
    app = RVI_GUI(root)
    root.mainloop()