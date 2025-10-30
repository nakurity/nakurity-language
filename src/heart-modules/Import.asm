; import.asm — nvm asm for @import
; Convention:
;  - ENTRY: _main
;  - ARGS:
;      arg0: raw import spec string, e.g. "<standardly-native.funcs.print()>"
;  - EXPORTS:
;      _resolve: resolves an import and returns a handle or path

.section .text

_global _main
_main:
  ; read arg0
  CALL read_arg0            ; puts pointer/len in R0/R1
  CALL parse_angle_spec     ; parses into ns_chain, end_name, mode flags
  ; ns_chain: ["standardly-native","funcs"]
  ; end_name: "print"
  ; mode: "end-file" if () present

  ; build candidate paths
  CALL build_base_path      ; cwd/modules/<ns_chain...>/<end_name>

  ; try .nh first
  CALL try_nh               ; returns FOUND flag in R2, path in R3
  CMP R2, #1
  BEQ .FOUND_NH

  ; fallback .so
  CALL try_so               ; returns FOUND flag in R2, path in R3
  CMP R2, #1
  BEQ .FOUND_SO

  ; fallback error
  CALL emit_import_error
  RET

.FOUND_NH:
  ; read .nh and return export target string, e.g. export["cfd:/print.so:print"]
  CALL read_nh_export       ; places export target in R4
  CALL return_export_target ; returns R4 upward to runtime
  RET

.FOUND_SO:
  ; return path + symbol default to file stem
  CALL default_symbol_from_name ; "print"
  CALL return_so_target         ; returns "cfd:/print.so:print"
  RET

; ------------- helpers (pseudo) -------------

read_arg0:
  ; platform ABI, load first argument into registers
  RET

parse_angle_spec:
  ; parse "<a.b.c()>" into chain ["a","b"], end "c", end-file flag true
  RET

build_base_path:
  ; cwd/modules/a/b/c
  RET

try_nh:
  ; check {base}.nh existence, set flags and path
  RET

try_so:
  ; check {base}.so existence, set flags and path
  RET

read_nh_export:
  ; read the file and extract string inside export["..."]
  RET

emit_import_error:
  ; print meaningful error to stderr/log
  RET

return_export_target:
  ; pass string to caller (interpreter or compiler)
  RET

default_symbol_from_name:
  RET

return_so_target:
  RET
