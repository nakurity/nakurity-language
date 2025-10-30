; print.asm — nvm asm for print("Hello world")
; EXPORT: print
.section .text

_export print
print:
  ; expects one string argument
  CALL read_arg0    ; load pointer/len in R0/R1
  CALL write_stdout ; actually write bytes
  RET

; --- helpers ---
read_arg0:
  ; ABI-dependent argument load
  RET

write_stdout:
  ; system call to write to stdout using R0 ptr and R1 len
  RET
