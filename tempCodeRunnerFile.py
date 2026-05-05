import tkinter as tk
from tkinter import filedialog, messagebox, scrolledtext, ttk
import os
import sys
import io

# Mevcut modülleri içe aktarıyoruz
from lib.parser import parse_input, reset_lineno
from lib.object_writer import write_object_file
from linker import link

VERSION = "1.0 - Academic Edition (Final)"

# Terminal çıktılarını GUI'ye yönlendirmek için yardımcı sınıf
class TerminalToGUI:
    def __init__(self, text_widget):
        self.text_widget = text_widget

    def write(self, string):
        self.text_widget.insert(tk.END, string)
        self.text_widget.see(tk.END)

    def flush(self):
        pass

class RVI_Ultimate_GUI:
    def __init__(self, root):
        self.root = root
        self.root.title(f"RVI: RV32I Linker System - {VERSION}")
        self.root.geometry("1000x750")
        self.root.configure(bg="#f4f4f9")
        
        self.files_to_process = []
        self.setup_ui()

    def setup_ui(self):
        # --- ÜST PANEL (BANNER) ---
        banner = tk.Frame(self.root, bg="#2c3e50", height=80)
        banner.pack(fill=tk.X)
        
        tk.Label(banner, text="RVI LINKER & ASSEMBLER SYSTEM", fg="#ecf0f1", bg="#2c3e50", 
                 font=('Segoe UI', 18, 'bold')).pack(pady=10)

        # --- KONTROL PANELİ ---
        ctrl_frame = tk.Frame(self.root, bg="#f4f4f9")
        ctrl_frame.pack(pady=15)

        tk.Button(ctrl_frame, text="📁 .asm Dosyaları Ekle", command=self.select_files, 
                  bg="#3498db", fg="white", font=('Segoe UI', 10, 'bold'), 
                  relief=tk.FLAT, padx=20, pady=8).grid(row=0, column=0, padx=10)

        tk.Button(ctrl_frame, text="🚀 Derle ve Linkle (Run)", command=self.run_process, 
                  bg="#27ae60", fg="white", font=('Segoe UI', 10, 'bold'), 
                  relief=tk.FLAT, padx=20, pady=8).grid(row=0, column=1, padx=10)

        tk.Button(ctrl_frame, text="🧹 Sistemi Temizle", command=self.clear_all, 
                  bg="#e74c3c", fg="white", font=('Segoe UI', 10, 'bold'), 
                  relief=tk.FLAT, padx=20, pady=8).grid(row=0, column=2, padx=10)

        # --- SEKMELİ ANA GÖVDE ---
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill=tk.BOTH, expand=True, padx=20, pady=10)

        # Sekme 1: Teknik İşlem Günlüğü (Terminal gibi davranır)
        self.tab_log = tk.Frame(self.notebook)
        self.txt_log = scrolledtext.ScrolledText(self.tab_log, bg="#1e1e1e", fg="#00ff00", 
                                               font=('Consolas', 10), insertbackground="white")
        self.txt_log.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.tab_log, text=" 📝 Teknik İşlem Günlüğü ")

        # Sekme 2: Global Sembol Tablosu
        self.tab_sym = tk.Frame(self.notebook)
        columns = ("Label", "Address", "Status")
        self.tree_sym = ttk.Treeview(self.tab_sym, columns=columns, show='headings')
        self.tree_sym.heading("Label", text="Sembol (Etiket)")
        self.tree_sym.heading("Address", text="Bellek Adresi (Hex)")
        self.tree_sym.heading("Status", text="Durum")
        self.tree_sym.column("Label", anchor=tk.CENTER)
        self.tree_sym.column("Address", anchor=tk.CENTER)
        self.tree_sym.column("Status", anchor=tk.CENTER)
        self.tree_sym.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.tab_sym, text=" 🔍 Global Sembol Tablosu ")

        # Sekme 3: Final HEX Çıktısı
        self.tab_hex = tk.Frame(self.notebook)
        self.txt_hex = scrolledtext.ScrolledText(self.tab_hex, bg="white", fg="#2c3e50", 
                                               font=('Courier New', 12, 'bold'))
        self.txt_hex.pack(fill=tk.BOTH, expand=True)
        self.notebook.add(self.tab_hex, text=" 💾 Final HEX (FPGA) ")

    def log(self, msg):
        self.txt_log.insert(tk.END, msg + "\n")
        self.txt_log.see(tk.END)
        self.root.update_idletasks()

    def select_files(self):
        files = filedialog.askopenfilenames(filetypes=[("Assembly Files", "*.asm")])
        if files:
            for f in files:
                if f not in self.files_to_process:
                    self.files_to_process.append(f)
                    self.log(f"[DOSYA EKLENDİ] {os.path.basename(f)}")

    def clear_all(self):
        self.files_to_process = []
        self.txt_log.delete('1.0', tk.END)
        self.txt_hex.delete('1.0', tk.END)
        for item in self.tree_sym.get_children():
            self.tree_sym.delete(item)
        self.log("Sistem sıfırlandı. Yeni projeler için hazır.")

    def run_process(self):
        if not self.files_to_process:
            messagebox.showwarning("Uyarı", "İşlem yapılacak .asm dosyası bulunamadı!")
            return

        self.txt_log.delete('1.0', tk.END)
        self.txt_hex.delete('1.0', tk.END)
        for item in self.tree_sym.get_children():
            self.tree_sym.delete(item)

        # Terminal çıktılarını yakalamaya başla
        old_stdout = sys.stdout
        sys.stdout = TerminalToGUI(self.txt_log)

        try:
            print("="*70)
            print(" RVI RV32I LINKER & ASSEMBLER - AKADEMİK ANALİZ RAPORU")
            print("="*70)
            
            obj_files = []
            
            # --- 1. ADIM: ASSEMBLE ---
            print("\n>>> ASSEMBLE AŞAMASI BAŞLADI")
            for asm_file in self.files_to_process:
                print(f"İşleniyor: {os.path.basename(asm_file)}...")
                res = parse_input(asm_file, hex=True)
                obj_file = write_object_file(asm_file, res['text'], res['data'], res['symbols'], res['relocations'])
                obj_files.append(obj_file)

            # --- 2. ADIM: LINKING ---
            print("\n>>> LINKING AŞAMASI BAŞLADI (Relocation Çözülüyor)")
            output_hex = "output.hex"
            merged_symbols = link(object_files=obj_files, output_path=output_hex, hex_mode=True)
            
            # Sembol Tablosunu Doldur
            for sym, addr in merged_symbols.items():
                self.tree_sym.insert("", tk.END, values=(sym, f"0x{addr:04X}", "RESOLVED"))

            # --- 3. ADIM: FINAL ÇIKTI ---
            with open(output_hex, 'r') as hf:
                hex_content = hf.read()
                self.txt_hex.insert(tk.END, hex_content)
            
            print("\n[BAŞARILI] Linkleme tamamlandı. Final adreslemeler yapıldı.")
            print(f"Toplam Program Uzunluğu: {len(hex_content.splitlines()) * 4} Byte")
            
            messagebox.showinfo("Başarılı", "Linkleme başarıyla tamamlandı!")

        except Exception as e:
            print(f"\n[HATA] {str(e)}")
            messagebox.showerror("Sistem Hatası", str(e))
        
        finally:
            # Terminali normale döndür
            sys.stdout = old_stdout

if __name__ == "__main__":
    root = tk.Tk()
    app = RVI_Ultimate_GUI(root)
    root.mainloop()