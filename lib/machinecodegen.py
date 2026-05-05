# -*MachineCodeConst içinde tanımladığımız tüm o hammadde bitlerini (Opcode, Funct3, vb.) alıp, onları doğru kutucuklara yerleştiren ve son 32 bitlik ürünü çıkaran yer*-
#Bu dosya, string halindeki komut parçalarını (tokens), bit seviyesinde uç uca ekleyerek (concatenation) devasa bir 0-1 zinciri oluşturur.
from lib.cprint import cprint as cp
from lib.machinecodeconst import MachineCodeConst

class MachineCodeGenerator:
    CONST = MachineCodeConst()

    def __init__(self):
        pass

    def get_bin_register(self, r):
        # x10 -> 10 -> 01010 (5 bit binary)Neden 5 bit? Çünkü $2^5 = 32$. RISC-V'de tam 32 tane register (x0'dan x31'e) vardır. Bu yüzden 5 bit her register'ı temsil etmek için yeterlidir.
        r_number = r[1:] #(Baştaki x harfini atar)
        try:
            r_val = int(r_number)
        except ValueError:
            cp.cprint_fail(f"Hata: Register ismi anlaşılamadı: {r}")
            exit(1)
        return format(r_val, '05b') # 10 sayısını 5 bitlik binary yapar: "01010"

    def op_lui(self, tokens):
        bin_opcode = self.CONST.BOP_LUI
        bin_rd = self.get_bin_register(tokens['rd'])
        imm = tokens['imm']
        bin_str = imm + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'rd': bin_rd, 'imm': imm}

    def op_jal(self, tokens):
        bin_opcode = self.CONST.BOP_JAL
        bin_rd = self.get_bin_register(tokens['rd'])
        imm = tokens['imm']
        bin_str = imm + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'rd': bin_rd, 'imm': imm}

    def op_jalr(self, tokens):
        opcode = tokens['opcode']
        funct = self.CONST.FUNCT3_JALR[opcode]
        bin_opcode = self.CONST.BOP_JALR
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rd = self.get_bin_register(tokens['rd'])
        imm = tokens['imm']
        bin_str = imm + bin_rs1 + funct + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'funct': funct, 'rs1': bin_rs1, 'rd': bin_rd, 'imm': imm}

    def op_branch(self, tokens):
        opcode = tokens['opcode']
        funct3 = self.CONST.FUNCT3_BRANCH[opcode]
        bin_opcode = self.CONST.BOP_BRANCH
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rs2 = self.get_bin_register(tokens['rs2'])
        imm_12_10_5, imm_4_1_11 = tokens['imm'] #Aynı Store gibi, atlanacak yerin mesafesi (imm) burada da parçalanmıştır
        bin_str = imm_12_10_5 + bin_rs2 + bin_rs1 + funct3 + imm_4_1_11 + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'funct': funct3, 'rs1': bin_rs1, 'rs2': bin_rs2}

    def op_load(self, tokens):
        opcode = tokens['opcode']
        funct3 = self.CONST.FUNCT3_LOAD[opcode]
        bin_opcode = self.CONST.BOP_LOAD
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rd = self.get_bin_register(tokens['rd'])
        imm = tokens['imm']
        bin_str = imm + bin_rs1 + funct3 + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'funct': funct3, 'rs1': bin_rs1, 'rd': bin_rd}

    def op_store(self, tokens):
        opcode = tokens['opcode']
        funct3 = self.CONST.FUNCT3_STORE[opcode]
        bin_opcode = self.CONST.BOP_STORE
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rs2 = self.get_bin_register(tokens['rs2'])
        imm_11_5, imm_4_0 = tokens['imm'] # Sayı ikiye ayrılmış geliyor Donanım Verimliliği için (12 bitlik sayı, 7 bit ve 5 bit olarak iki parçaya bölünür)
        bin_str = imm_11_5 + bin_rs2 + bin_rs1 + funct3 + imm_4_0 + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'rs1': bin_rs1, 'rs2': bin_rs2}

    def op_arithi(self, tokens):
        opcode = tokens['opcode']
        funct3 = self.CONST.FUNCT3_ARITHI[opcode]
        bin_opcode = self.CONST.BOP_ARITHI
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rd = self.get_bin_register(tokens['rd'])
        imm = tokens['imm']
        bin_str = imm + bin_rs1 + funct3 + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'funct3': funct3, 'rd': bin_rd}

    def op_arith(self, tokens):
        ## Bitleri şu sırayla birleştirir: 
        # [funct7] + [rs2] + [rs1] + [funct3] + [rd] + [opcode]
        opcode = tokens['opcode']
        funct3 = self.CONST.FUNCT3_ARITH[opcode]
        funct7 = self.CONST.FUNCT7_ARITH[opcode]
        bin_opcode = self.CONST.BOP_ARITH
        bin_rs1 = self.get_bin_register(tokens['rs1'])
        bin_rs2 = self.get_bin_register(tokens['rs2'])
        bin_rd = self.get_bin_register(tokens['rd'])
        bin_str = funct7 + bin_rs2 + bin_rs1 + funct3 + bin_rd + bin_opcode
        return bin_str, {'opcode': bin_opcode, 'funct3': funct3, 'rs1': bin_rs1, 'rd': bin_rd}

    def convert_to_binary(self, tokens): #Gelen komutun adına bakar ve onu ilgili paketleme istasyonuna gönderir.
        try:
            opcode = tokens['opcode']
        except KeyError:
            return None

        # SADELEŞTİRİLMİŞ KONTROLLER
        #Bu kısım, opcode'un hangi gruba ait olduğunu hızlıca bulur ve ilgili fonksiyona gönderir. Örneğin, opcode add ise, o INSTR_BOP_ARITH grubundadır, o zaman op_arith fonksiyonuna gönderilir.
        if opcode in self.CONST.INSTR_BOP_LUI: return self.op_lui(tokens)
        elif opcode in self.CONST.INSTR_BOP_JAL: return self.op_jal(tokens)
        elif opcode in self.CONST.INSTR_BOP_JALR: return self.op_jalr(tokens)
        elif opcode in self.CONST.INSTR_BOP_BRANCH: return self.op_branch(tokens)
        elif opcode in self.CONST.INSTR_BOP_LOAD: return self.op_load(tokens)
        elif opcode in self.CONST.INSTR_BOP_STORE: return self.op_store(tokens)
        elif opcode in self.CONST.INSTR_BOP_ARITHI: return self.op_arithi(tokens)
        elif opcode in self.CONST.INSTR_BOP_ARITH: return self.op_arith(tokens)
        else:
            cp.cprint_fail(f"Hata: {opcode} desteklenmiyor.")
            return None

mcg = MachineCodeGenerator()