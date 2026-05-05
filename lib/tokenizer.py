# AYIKLAMA MAKİNESİ - add, x1, loop:, , gibi ifadeleri birbirinden ayırır. 
import ply.lex as lex
from lib.machinecodeconst import MachineCodeConst

mcc = MachineCodeConst()

# 1. TOKEN LİSTESİ: 
#Program bir kelime gördüğünde ona bu listeden bir isim takmak zorundadır.
#Sen add yazarsan program ona OPCODE etiketi yapıştırır. x1 yazarsan REGISTER etiketi yapıştırır.
tokens = (
    'DIRECTIVE', 
    'OPCODE',    
    'LABEL',     
    'REGISTER',  
    'COMMA',     
    'IMMEDIATE', 
    'NEWLINE',   
    'COLUMN',
    'LPAREN',    
    'RPAREN'     
)

# 2. REGEX TANIMLARI - Basit Kurallar
#Bunlar tek karakterlik basit eşleşmelerdir.
#r harfi "Raw String" demektir, yani "içerideki karakteri olduğu gibi gör" der.
t_COMMA = r',' 
t_COLUMN = r':'
t_LPAREN = r'\(' 
t_RPAREN = r'\)' 
t_ignore = ' \t\r' #Boşluk, tab, ve carriage return karakterlerini görmezden gelir. Yani bunları kelime olarak tanımaz, sadece kelimeleri birbirinden ayırmak için kullanır.

# 3. Fonksiyonel Kurallar (Kelime Tanıma)

def t_DIRECTIVE(t): #(Yol Göstericiler)
    r'\.(data|text|word|byte|org|end|space|global|extern)' #Başında nokta (.) olan kelimeleri yakalar.
    return t

def t_REGISTER(t):
    r'x[0-9][0-9]?' #Mantık: x harfiyle başlayan ve peşinden 1 veya 2 rakam gelen her şeyi yakalar (x0, x1, x31 gibi).
    return t

def t_IMMEDIATE(t):
    r'[+-]?[0-9]+' #Mantık: Başında artı veya eksi olabilen ([+-]?), en az bir rakamdan oluşan ([0-9]+) tam sayıları yakalar.
    return t

def t_OPCODE(t): #Opcode vs Label Ayrımı (En Önemli Yer!)
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    # Hash Table Kontrolü
    if t.value in mcc.ALL_INSTR: #Opcode Table'a (yani mcc.ALL_INSTR listesine) bakıyor.
        t.type = "OPCODE"
    else:
        t.type = "LABEL" 
    return t
#Hata ve Yorum Satırları:
def t_COMMENT(t):
    r'\#.*' # # işaretinden sonra satır sonuna kadar ne yazılırsa yazılsın program bunu çöpe atar.
    pass

def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

def t_error(t):
    # Hata yakalama
    print(f"Hatalı Karakter Tespit Edildi: '{t.value[0]}' - Satır: {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()

def reset_lineno():
    lexer.lineno = 1

if __name__ == '__main__':
    lex.runmain()