# tokenizer.py - lib/ klasorune koy
# AYIKLAMA MAKİNESİ - add, x1, loop:, , gibi ifadeleri birbirinden ayırır.
import ply.lex as lex
from lib.machinecodeconst import MachineCodeConst
mcc = MachineCodeConst()

# 1. TOKEN LİSTESİ
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
t_COMMA  = r','
t_COLUMN = r':'
t_LPAREN = r'\('
t_RPAREN = r'\)'
t_ignore = ' \t\r'

# 3. Fonksiyonel Kurallar

def t_DIRECTIVE(t):
    # DÜZELTİLDİ: globl, extern, external eklendi
    r'\.(data|text|word|byte|org|end|space|globl|global|extern|external|bss)'
    return t

def t_REGISTER(t):
    r'x[0-9][0-9]?'
    return t

def t_IMMEDIATE(t):
    r'[+-]?[0-9]+'
    return t

def t_OPCODE(t):
    r'[a-zA-Z_][a-zA-Z_0-9]*'
    if t.value in mcc.ALL_INSTR:
        t.type = "OPCODE"
    else:
        t.type = "LABEL"
    return t

def t_COMMENT(t):
    r'\#.*'
    pass

def t_NEWLINE(t):
    r'\n+'
    t.lexer.lineno += len(t.value)
    return t

def t_error(t):
    print(f"Hatalı Karakter Tespit Edildi: '{t.value[0]}' - Satır: {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()

def reset_lineno():
    lexer.lineno = 1

if __name__ == '__main__':
    lex.runmain()