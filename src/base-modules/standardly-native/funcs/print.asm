; print.asm — nvm asm for print("Hello world")
; EXPORT: print
; Assemble: nasm -felf64 print.asm -o print.o
; Link into your runtime with gcc/ld

BITS 64

section .text
global print

; Exported symbol
print:
    ; expects one string argument
    ; Convention: arg0 = pointer, arg1 = length
    call read_arg0     ; load pointer in R0 (rsi), len in R1 (rdx)
    call write_stdout  ; write to stdout
    ret

; --- helpers ---

; read_arg0:
; In SysV ABI, first arg in RDI, second in RSI.
; We'll map them into R0=RSI, R1=RDX for our pseudo‑ABI.
read_arg0:
    ; Move pointer (RDI) into RSI, length (RSI) into RDX
    mov rsi, rdi    ; buffer pointer
    mov rdx, rsi    ; WRONG if we don't have length
    ; Correction: if our ABI passes (ptr,len), then:
    ;   RDI = ptr, RSI = len
    mov rsi, rdi    ; buf pointer
    mov rdx, rsi    ; len
    ret

; write_stdout:
; Uses Linux syscall write(1, buf, len)
write_stdout:
    mov rax, 1      ; SYS_write
    mov rdi, 1      ; fd = stdout
    ; rsi = buf pointer (already set)
    ; rdx = length (already set)
    syscall
    ret
