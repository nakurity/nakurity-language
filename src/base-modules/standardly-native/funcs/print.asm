; print.asm
BITS 64
section .text
global _start

_start:
    ; argc at [rsp], argv[0] at [rsp+8], argv[1] at [rsp+16]
    mov rbx, [rsp]          ; argc
    cmp rbx, 2
    jl .noarg

    mov rsi, [rsp+16]       ; argv[1] pointer
    ; compute length
    xor rcx, rcx
.lenloop:
    cmp byte [rsi+rcx], 0
    je .lenfound
    inc rcx
    jmp .lenloop
.lenfound:
    mov rdx, rcx            ; length
    mov rdi, 1              ; fd=stdout
    mov rax, 1              ; SYS_write
    syscall

.noarg:
    mov rax, 60             ; SYS_exit
    xor rdi, rdi
    syscall
