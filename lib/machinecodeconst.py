#OPCODE TABLE
class MachineCodeConst:
    # --- 1. KOMUT TANIMLARI (En Temel 15 Komut) ---
    #Bu kısımda,sol taraftaki değişken isimlerini) biz oluşturduk, ama sağ taraftaki değerleri ('add', 'lui', 'beq') resmi RISC-V standartlarına göre seçtik.
    INSTR_LUI   = 'lui'
    INSTR_JAL   = 'jal'
    INSTR_JALR  = 'jalr'
    INSTR_BEQ   = 'beq'
    INSTR_BNE   = 'bne'
    INSTR_BLT   = 'blt'
    INSTR_LW    = 'lw'
    INSTR_SW    = 'sw'
    INSTR_ADDI  = 'addi'
    INSTR_ANDI  = 'andi'
    INSTR_ADD   = 'add'
    INSTR_SUB   = 'sub'
    INSTR_AND   = 'and'
    INSTR_OR    = 'or'
    INSTR_XOR   = 'xor'

    # Tüm desteklenen komutlar listesi 
    #Bu liste, opcode tanımlarken ve opcode'ları tanımlarken referans olarak kullanılır. Örneğin, tokenizer'da bir kelime gördüğümüzde bu listede mi diye bakarız. Eğer varsa OPCODE etiketi yapıştırırız, yoksa LABEL etiketi yapıştırırız.
    ALL_INSTR = [
        INSTR_LUI, INSTR_JAL, INSTR_JALR, INSTR_BEQ, INSTR_BNE, 
        INSTR_BLT, INSTR_LW, INSTR_SW, INSTR_ADDI, INSTR_ANDI, 
        INSTR_ADD, INSTR_SUB, INSTR_AND, INSTR_OR, INSTR_XOR
    ]

    # --- 2. TİPLERİNE GÖRE GRUPLAMA ---
    #RISC-V'de her komutun bir türü vardır (R, I, S, SB, U, UJ gibi). Bu gruplama, opcode ve funct değerlerini tanımlarken bize yardımcı olur.
    INSTR_TYPE_U  = [INSTR_LUI]#(Büyük Sayı ve Uzak Atlama) U tipi komutlar, büyük sayılarla veya uzak atlamalarla çalışır. Örneğin LUI komutu, bir register'a 20 bitlik büyük bir sayı yükler. Bu tür komutlarda genellikle sadece bir register (rd) ve büyük bir immediate (imm) bulunur.
    INSTR_TYPE_UJ = [INSTR_JAL] #(Uzak Atlama) UJ tipi komutlar, uzak atlamalar yaparken kullanılır. Örneğin JAL komutu, bir register'a (rd) o anki adrese imm kadar ekleyerek atlama yapar. Bu tür komutlarda genellikle bir register (rd) ve büyük bir immediate (imm) bulunur.
    INSTR_TYPE_S  = [INSTR_SW] #(Store Tipi) Belleğe veri yazarken kullanılır. rs2'deki değeri rs1'deki adrese yazar. Örneğin sw x5, 8(x10) komutunda, x5'teki değeri alır, x10'daki adrese 8 ekler, ve sonucu o adrese yazar.Bir "Hedef Register (rd)" yoktur, çünkü sonuç bir register'a değil RAM'e yazılır. Bu yüzden 12 bitlik sayı ikiye bölünerek paketlenir.
    INSTR_TYPE_SB = [INSTR_BEQ, INSTR_BNE, INSTR_BLT] #(Branch/Dallanma Tipi) Koşullu dallanma yaparken kullanılır. rs1 ve rs2'deki değerleri karşılaştırır, eğer şart sağlanıyorsa o anki adrese imm (12 bitlik sayı) kadar ekleyerek atlama yapar. Örneğin beq x5, x6, LOOP komutunda, x5 ve x6'yı karşılaştırır, eğer eşitse o anki adrese imm kadar ekleyerek LOOP etiketine atlar. Bir "Hedef Register (rd)" yoktur, çünkü sonuç bir register'a değil RAM'e yazılır. Bu yüzden 12 bitlik sayı ikiye bölünerek paketlenir.
    INSTR_TYPE_I  = [INSTR_ADDI, INSTR_ANDI, INSTR_JALR, INSTR_LW] #(Immediate Tipi) Bir register ve bir küçük sayı (12 bitlik) ile çalışır.rs1'i al, üstüne imm (sayıyı) ekle, sonucu rd'ye yaz.
    INSTR_TYPE_R  = [INSTR_ADD, INSTR_SUB, INSTR_AND, INSTR_OR, INSTR_XOR] #(Register Tipi)sadece register'larla çalışır. Sayı (immediate) içermez. 3 tane register adresi (rd, rs1, rs2) + funct3 + funct7

    #R: Sadece Register.
    #I: Register + Sayı.
    #S: Hafızaya Kaydet.
    #SB: Şartlı Atlama.
    #U/UJ: Büyük Sayı/Uzak Atlama.

    # --- 3. BINARY OPCODE'LAR (Hash Table Değerleri)evrensel ---
    BOP_LUI    = '0110111' #lui Büyük bir sayıyı register'ın üst kısmına koy
    BOP_JAL    = '1101111' #jal Uzak atlama yap, o anki adrese imm kadar ekleyerek rd'ye atla
    BOP_JALR   = '1100111' #jalr Uzak atlama yap, rs1'deki adrese imm ekleyerek rd'ye atla
    BOP_BRANCH = '1100011' #beq, bne, blt
    BOP_LOAD   = '0000011' #lw Hafızadan (RAM) işlemciye veri getir
    BOP_STORE  = '0100011' #sw İşlemcideki veriyi hafızaya (RAM) yaz
    BOP_ARITHI = '0010011' #addi, andi
    BOP_ARITH  = '0110011' #add, sub, and, or, xor 

    # Tip-Opcode Eşleşmesi
    #Bu kısım olmasaydı, her komut için devasa bir if-else bloğu yazman gerekirdi
    #Assembler bir satırı okuduğunda (örneğin add), önce onun hangi grupta olduğunu bulur. Bu bölüm sayesinde program şunları öğrenir:
    #"add komutu mu geldi? O zaman o INSTR_BOP_ARITH grubundadır."
    #"INSTR_BOP_ARITH grubunun Opcode'u neydi? Hemen yukarı bak: 0110011."
    INSTR_BOP_LUI    = [INSTR_LUI]
    INSTR_BOP_JAL    = [INSTR_JAL]
    INSTR_BOP_JALR   = [INSTR_JALR]
    INSTR_BOP_BRANCH = INSTR_TYPE_SB #beq, bne ve blt komutlarının hepsi (SB tipi) aslında aynı Opcode'u (1100011) paylaşır. Hepsini tek tek yazmak yerine grubu direkt eşitle
    INSTR_BOP_LOAD   = [INSTR_LW] #Şu an sadece lw desteklediğimiz için tek elemanlı bir liste oldu.
    INSTR_BOP_STORE  = INSTR_TYPE_S
    INSTR_BOP_ARITHI = [INSTR_ADDI, INSTR_ANDI] #İçinde "I" (Immediate) olan aritmetik komutları bu gruba topladın.
    INSTR_BOP_ARITH  = INSTR_TYPE_R #add, sub, and, or, xor komutlarının hepsinin Opcode'u aynıdır (0110111)

    # --- 4. FUNCT DEĞERLERİ (O(1) Hash Table Yapısı) ---
    #RISC-V'de her komut 32 bittir. Yer tasarrufu yapmak için birçok komut aynı Opcode'u paylaşır.
    FUNCT3_ARITHI = { INSTR_ADDI: '000', INSTR_ANDI: '111' }
    FUNCT3_JALR   = { INSTR_JALR: '000' }
    FUNCT3_LOAD   = { INSTR_LW: '010' }
    FUNCT3_STORE  = { INSTR_SW: '010' }
    FUNCT3_BRANCH = { INSTR_BEQ: '000', INSTR_BNE: '001', INSTR_BLT: '100' }
    FUNCT3_ARITH  = { 
        INSTR_ADD: '000', INSTR_SUB: '000', INSTR_AND: '111', 
        INSTR_OR: '110', INSTR_XOR: '100'
    }
    FUNCT7_ARITH  = { 
        INSTR_ADD: '0000000', INSTR_SUB: '0100000', INSTR_AND: '0000000', 
        INSTR_OR: '0000000', INSTR_XOR: '0000000'
    }
