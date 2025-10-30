; print.asm — NVM asm for print("Hello world")
; EXPORT: print
; Arch: x86_64, System V ABI, Linux

BITS 64

section .text
global print

print:
    ; SysV: RDI=buf, RSI=len
    mov rsi, rdi    ; buf pointer into rsi
    mov rdx, rsi    ; WRONG in your draft
    ret
