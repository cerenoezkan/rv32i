.globl ADD_FUNC

.text

ADD_FUNC:
    add  x12, x10, x11
    andi x12, x12, 63
    jalr x0, x1, 0