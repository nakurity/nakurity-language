; import.asm — NVM import binary (lazy resolver)
; Arch: x86_64, System V ABI, Linux
; Assemble: nasm -felf64 import.asm -o import.o
; Link: gcc import.o -o import
; Usage: ./import '<standardly-native.funcs.print()>'
; Behavior:
;   1) Parse angle spec: "<a.b.c()>"
;   2) Build base path: cwd/modules/a/b/c
;   3) Prefer c.nh: read export["..."] line and print inside content (without export[""])
;   4) Else fallback to c.so: print "cfd:/c.so:c"
;   5) Errors -> stderr + exit 1

BITS 64

%define SYS_write     1
%define SYS_open      2
%define SYS_close     3
%define SYS_execve    59
%define SYS_exit      60
%define SYS_getcwd    79
%define SYS_stat      4     ; legacy; use newfstatat (SYS_newfstatat=262) for robustness
%define SYS_read      0
%define O_RDONLY      0
%define O_CLOEXEC     02000000

section .data
  msg_err_nargs     db "Import error: expected 1 arg: '<ns.chain.name()>'", 10
  len_err_nargs     equ $-msg_err_nargs

  msg_err_parse     db "Import error: malformed angle spec", 10
  len_err_parse     equ $-msg_err_parse

  msg_err_missing   db "Import error: module not found (.nh/.so missing)", 10
  len_err_missing   equ $-msg_err_missing

  ; literals
  angle_l           db "<"
  angle_r           db ">"
  dot_ch            db "."
  lparen            db "("
  rparen            db ")"
  quote_ch          db '"'
  export_kw         db "export[",0
  cfd_prefix        db "cfd:/",0
  modules_dir       db "modules",0
  slash             db "/",0
  nh_ext            db ".nh",0
  so_ext            db ".so",0
  colon             db ":",0

section .bss
  ; buffers
  argv0_ptr         resq 1
  argv1_ptr         resq 1
  spec_buf          resb 1024
  spec_len          resq 1

  cwd_buf           resb 1024
  base_path_buf     resb 1024
  tmp_buf           resb 1024

  nh_path_buf       resb 1024
  so_path_buf       resb 1024

  nh_file_buf       resb 2048
  nh_read_len       resq 1

  export_out_buf    resb 1024
  out_len_q         resq 1

  end_name_buf      resb 256
  end_name_len_q    resq 1
  is_endfile_q      resq 1

section .text
global _start

; Minimal CRT: entry via _start (no libc)
_start:
  ; RSP points to argc, argv...
  ; Read argc
  mov rbx, [rsp]
  cmp rbx, 2
  je .args_ok
  ; write error and exit
  mov rdi, 2                ; stderr
  mov rsi, msg_err_nargs
  mov rdx, len_err_nargs
  mov rax, SYS_write
  syscall
  mov rdi, 1
  mov rax, SYS_exit
  syscall

.args_ok:
  ; argv[0] at [rsp+8], argv[1] at [rsp+16]
  mov rax, [rsp+16]
  mov [argv1_ptr], rax

  ; copy argv1 into spec_buf and compute length
  mov rsi, rax              ; src
  mov rdi, spec_buf         ; dst
  xor rcx, rcx              ; count
.copy_arg:
  mov al, byte [rsi]
  mov byte [rdi], al
  inc rsi
  inc rdi
  inc rcx
  cmp al, 0
  jne .copy_arg
  ; rcx includes null terminator, set length = rcx-1
  dec rcx
  mov [spec_len], rcx

  ; parse angle spec -> extract end_name, mark end-file flag if "()" present
  ; also check format <> balanced
  mov rsi, spec_buf
  mov rdx, [spec_len]
  call parse_angle_spec      ; end_name_buf, end_name_len_q, is_endfile_q ; also builds chain markers temporarily

  cmp rax, 0
  jne .parsed_ok
  ; error
  mov rdi, 2
  mov rsi, msg_err_parse
  mov rdx, len_err_parse
  mov rax, SYS_write
  syscall
  mov rdi, 1
  mov rax, SYS_exit
  syscall

.parsed_ok:
  ; get cwd
  mov rdi, cwd_buf
  mov rsi, 1024
  mov rax, SYS_getcwd
  syscall
  ; rax = length or -1 on error; ignore for now, assume cwd_buf valid

  ; build base path: cwd/modules/<ns_chain...>/<end_name>
  call build_base_path

  ; try .nh
  call try_nh
  cmp rax, 1
  je .have_nh

  ; try .so
  call try_so
  cmp rax, 1
  je .have_so

  ; error missing
  mov rdi, 2
  mov rsi, msg_err_missing
  mov rdx, len_err_missing
  mov rax, SYS_write
  syscall
  mov rdi, 1
  mov rax, SYS_exit
  syscall

.have_nh:
  ; read .nh export[...] and emit interior string
  call read_nh_export
  cmp rax, 1
  jne .nh_read_fail

  ; print export_out_buf
  mov rdi, 1
  mov rsi, export_out_buf
  mov rdx, [out_len_q]
  mov rax, SYS_write
  syscall

  ; exit 0
  xor rdi, rdi
  mov rax, SYS_exit
  syscall

.nh_read_fail:
  ; fallback to .so synthesis if nh read failed (robust path)
  jmp .have_so

.have_so:
  ; construct "cfd:/<end_name>.so:<symbol>" where symbol=end_name
  call return_so_target
  ; print buffer
  mov rdi, 1
  mov rsi, export_out_buf
  mov rdx, [out_len_q]
  mov rax, SYS_write
  syscall
  xor rdi, rdi
  mov rax, SYS_exit
  syscall

; -------------------------------------------------------
; Helper: parse_angle_spec
; IN:  rsi=spec_ptr, rdx=spec_len
; OUT: rax=1 ok, 0 fail
;      end_name_buf filled, end_name_len_q set
;      is_endfile_q: 1 if ends with "()"
; Note: also strips leading '<' and trailing '>'
; -------------------------------------------------------
parse_angle_spec:
  ; validate first '<' and last '>'
  cmp rdx, 3
  jb .fail
  mov al, byte [rsi]
  cmp al, '<'
  jne .fail
  mov rcx, rdx
  dec rcx
  mov al, byte [rsi+rcx-1]
  cmp al, '>'
  jne .fail

  ; work window: content inside <>
  lea r8, [rsi+1]           ; start
  mov r9, rdx
  sub r9, 2                 ; length inside

  ; find last '.' (separates end_name)
  mov r10, 0
  mov r11, 0                ; index of last dot
  xor rax, rax
  mov rcx, 0
.find_last_dot:
  cmp rcx, r9
  jge .post_dot
  mov al, byte [r8+rcx]
  cmp al, '.'
  jne .cont_dot
  mov r11, rcx
.cont_dot:
  inc rcx
  jmp .find_last_dot

.post_dot:
  ; end_name begins at r11+1
  mov r12, r11
  inc r12
  ; copy until end to end_name_buf
  mov rdi, end_name_buf
  mov rsi, r8
  add rsi, r12
  mov rcx, 0
.copy_end_name:
  cmp rcx, r9
  jge .finish_copy_name
  ; index in whole '<...>' window is r12+rcx; bounds check
  mov r13, r12
  add r13, rcx
  cmp r13, r9
  jge .finish_copy_name
  mov al, byte [r8+r13]
  ; stop at ')' or '>' implicitly (we already removed '>')
  cmp al, ')'
  je .finish_copy_name
  ; also stop if '(' encountered (start of "()")
  cmp al, '('
  je .finish_copy_name
  mov byte [rdi+rcx], al
  inc rcx
  jmp .copy_end_name

.finish_copy_name:
  mov byte [rdi+rcx], 0
  mov [end_name_len_q], rcx

  ; detect trailing "()"
  ; check last two bytes in window: ... '(' ')'
  ; we scan from the end
  mov r14, r9
  cmp r14, 2
  jb .no_endfile
  mov al, byte [r8+r14-2]
  cmp al, '('
  jne .no_endfile
  mov al, byte [r8+r14-1]
  cmp al, ')'
  jne .no_endfile
  mov qword [is_endfile_q], 1
  jmp .ok

.no_endfile:
  mov qword [is_endfile_q], 0

.ok:
  mov rax, 1
  ret
.fail:
  xor rax, rax
  ret

; -------------------------------------------------------
; Helper: build_base_path = cwd_buf + "/modules" + each ns segment + "/" + end_name
; We reconstruct chain by splitting on '.' and stopping before end_name.
; OUT: base_path_buf contains cwd/modules/<ns...>/<end_name_without()>
; -------------------------------------------------------
build_base_path:
  ; start with cwd_buf
  ; write cwd to base_path_buf
  mov rsi, cwd_buf
  mov rdi, base_path_buf
  call str_copy

  ; append '/'
  mov rsi, slash
  call str_cat_cstr

  ; append "modules"
  mov rsi, modules_dir
  call str_cat_cstr

  ; append '/'
  mov rsi, slash
  call str_cat_cstr

  ; now append namespace chain (inside spec, before last dot)
  ; reuse the inside window r8/r9 from parsing? Not stored—so reparse minimally:
  ; Reuse spec_buf: split between '<' and '>' then iterate chars until last '.'
  ; find last dot again
  mov rsi, spec_buf
  mov rdx, [spec_len]
  lea r8, [rsi+1]
  mov r9, rdx
  sub r9, 2
  ; find last dot index in window
  xor rcx, rcx
  mov r11, 0
.bd_find_last_dot:
  cmp rcx, r9
  jge .bd_have_last
  mov al, byte [r8+rcx]
  cmp al, '.'
  jne .bd_cont
  mov r11, rcx
.bd_cont:
  inc rcx
  jmp .bd_find_last_dot
.bd_have_last:
  ; iterate from start to r11, splitting on '.'
  xor rcx, rcx
  mov r15, 0                ; token start
.bd_loop:
  cmp rcx, r11
  jg .bd_done_chain
  mov al, byte [r8+rcx]
  cmp al, '.'
  jne .bd_adv
  ; append token [r15..rcx-1]
  mov rsi, tmp_buf
  mov rdi, rsi
  mov rbx, 0
.copy_token:
  cmp r15, rcx
  jge .token_copied
  mov dl, byte [r8+r15]
  mov byte [rdi], dl
  inc rdi
  inc r15
  inc rbx
  jmp .copy_token
.token_copied:
  mov byte [rdi], 0
  ; cat token
  mov rsi, tmp_buf
  mov rdi, base_path_buf
  call str_cat_cstr
  ; append '/'
  mov rsi, slash
  mov rdi, base_path_buf
  call str_cat_cstr
  ; advance token start to rcx+1
  inc rcx
  mov r15, rcx
  jmp .bd_loop
.bd_adv:
  inc rcx
  jmp .bd_loop

.bd_done_chain:
  ; append final token before last dot (if any)
  cmp r15, r11
  jge .bd_after_chain
  mov rsi, tmp_buf
  mov rdi, rsi
  ; copy [r15..r11-1]
  mov rcx, r15
.bd_copy_lastseg:
  cmp rcx, r11
  jge .bd_lastseg_copied
  mov al, byte [r8+rcx]
  mov byte [rdi], al
  inc rdi
  inc rcx
  jmp .bd_copy_lastseg
.bd_lastseg_copied:
  mov byte [rdi], 0
  mov rsi, tmp_buf
  mov rdi, base_path_buf
  call str_cat_cstr
  mov rsi, slash
  call str_cat_cstr

.bd_after_chain:
  ; append end_name
  mov rsi, end_name_buf
  mov rdi, base_path_buf
  call str_cat_cstr
  ret

; -------------------------------------------------------
; try_nh: create base+".nh" in nh_path_buf and test existence
; OUT: rax=1 if exists, else 0
; -------------------------------------------------------
try_nh:
  ; nh_path_buf = base_path_buf + ".nh"
  mov rsi, base_path_buf
  mov rdi, nh_path_buf
  call str_copy
  mov rsi, nh_ext
  mov rdi, nh_path_buf
  call str_cat_cstr

  ; open read-only
  mov rax, SYS_open
  mov rdi, nh_path_buf
  mov rsi, O_RDONLY
  mov rdx, 0
  syscall
  cmp rax, 0
  jl .nh_missing
  ; found: close and return 1
  mov rbx, rax
  mov rax, SYS_close
  mov rdi, rbx
  syscall
  mov rax, 1
  ret
.nh_missing:
  xor rax, rax
  ret

; -------------------------------------------------------
; try_so: base+".so" existence
; OUT: rax=1 if exists
; -------------------------------------------------------
try_so:
  mov rsi, base_path_buf
  mov rdi, so_path_buf
  call str_copy
  mov rsi, so_ext
  mov rdi, so_path_buf
  call str_cat_cstr

  mov rax, SYS_open
  mov rdi, so_path_buf
  mov rsi, O_RDONLY
  mov rdx, 0
  syscall
  cmp rax, 0
  jl .so_missing
  mov rbx, rax
  mov rax, SYS_close
  mov rdi, rbx
  syscall
  mov rax, 1
  ret
.so_missing:
  xor rax, rax
  ret

; -------------------------------------------------------
; read_nh_export: read first line with export["..."] and emit interior
; OUT: rax=1 ok; export_out_buf filled; out_len_q set (includes newline)
; -------------------------------------------------------
read_nh_export:
  ; open nh_path_buf
  mov rax, SYS_open
  mov rdi, nh_path_buf
  mov rsi, O_RDONLY
  mov rdx, 0
  syscall
  cmp rax, 0
  jl .read_fail
  mov rbx, rax    ; fd

  ; read file into nh_file_buf
  mov rax, SYS_read
  mov rdi, rbx
  mov rsi, nh_file_buf
  mov rdx, 2048
  syscall
  cmp rax, 0
  jle .read_close_fail
  mov [nh_read_len], rax

  ; close
  mov rax, SYS_close
  mov rdi, rbx
  syscall

  ; scan for export["
  mov rsi, nh_file_buf
  mov rdx, [nh_read_len]
  call scan_export_line      ; rax=1 if found, rdi points to start inside quotes, rcx=len
  cmp rax, 1
  jne .read_fail

  ; copy interior to export_out_buf and add newline
  mov rsi, rdi
  mov rdi, export_out_buf
  mov rbx, rcx               ; len inside quotes
  call mem_copy_len
  ; add newline
  mov byte [export_out_buf+rbx], 10
  mov rbx, rbx
  inc rbx
  mov [out_len_q], rbx
  mov rax, 1
  ret

.read_close_fail:
  ; close on fail
  mov rax, SYS_close
  mov rdi, rbx
  syscall
.read_fail:
  xor rax, rax
  ret

; -------------------------------------------------------
; scan_export_line: find export["..."] pattern and length inside quotes
; IN: rsi=buf, rdx=len
; OUT: rax=1 ok, rdi=ptr start, rcx=len
; -------------------------------------------------------
scan_export_line:
  mov r8, rsi
  mov r9, rdx
  mov r10, 0
.loop_find_export:
  cmp r10, r9
  jge .not_found
  ; match "export["
  ; naive scan: when 'e' matches, compare the sequence
  mov al, byte [r8+r10]
  cmp al, 'e'
  jne .cont_scan
  ; compare export[
  mov r11, 0
.check_kw:
  mov bl, byte [export_kw + r11]
  cmp bl, 0
  je .kw_ok
  mov dl, byte [r8+r10+r11]
  cmp dl, bl
  jne .cont_scan
  inc r11
  jmp .check_kw
.kw_ok:
  ; next must be '"' (opening)
  mov dl, byte [r8+r10+r11]
  cmp dl, '"'
  jne .cont_scan
  ; find closing '"'
  mov r12, r10
  add r12, r11
  inc r12                 ; point to char after opening "
  mov r13, r12
.find_close_quote:
  cmp r13, r9
  jge .not_found
  mov dl, byte [r8+r13]
  cmp dl, '"'
  je .have_quote
  inc r13
  jmp .find_close_quote
.have_quote:
  ; interior begins at r12, length = r13 - r12
  mov rdi, r8
  add rdi, r12
  mov rcx, r13
  sub rcx, r12
  mov rax, 1
  ret

.cont_scan:
  inc r10
  jmp .loop_find_export

.not_found:
  xor rax, rax
  ret

; -------------------------------------------------------
; return_so_target: "cfd:/<end_name>.so:<end_name>\n"
; OUT: export_out_buf, out_len_q, rax=1
; -------------------------------------------------------
return_so_target:
  ; copy "cfd:/"
  mov rsi, cfd_prefix
  mov rdi, export_out_buf
  call str_copy

  ; append end_name
  mov rsi, end_name_buf
  mov rdi, export_out_buf
  call str_cat_cstr

  ; append ".so"
  mov rsi, so_ext
  mov rdi, export_out_buf
  call str_cat_cstr

  ; append ":"
  mov rsi, colon
  mov rdi, export_out_buf
  call str_cat_cstr

  ; append symbol=end_name
  mov rsi, end_name_buf
  mov rdi, export_out_buf
  call str_cat_cstr

  ; add newline and compute length
  ; compute length until 0
  mov rsi, export_out_buf
  call strlen
  ; rax=len
  mov byte [export_out_buf+rax], 10
  inc rax
  mov [out_len_q], rax
  mov rax, 1
  ret

; -------------------------------------------------------
; String helpers
; -------------------------------------------------------

; str_copy: copy zero-terminated RSI -> RDI
str_copy:
  mov rcx, 0
.sc_loop:
  mov al, byte [rsi+rcx]
  mov byte [rdi+rcx], al
  inc rcx
  cmp al, 0
  jne .sc_loop
  ret

; str_cat_cstr: append zero-terminated RSI to end of RDI buffer
str_cat_cstr:
  ; find end of RDI
  mov rax, 0
  mov rbx, rdi
  call strlen_rdi            ; len in rax
  add rbx, rax               ; rbx = end
  ; copy RSI to rbx
  mov rcx, 0
.scc_loop:
  mov al, byte [rsi+rcx]
  mov byte [rbx+rcx], al
  inc rcx
  cmp al, 0
  jne .scc_loop
  ret

; strlen: RSI points to cstr, returns len in RAX (not counting null)
strlen:
  mov rax, 0
.sl_loop:
  mov dl, byte [rsi+rax]
  cmp dl, 0
  je .sl_done
  inc rax
  jmp .sl_loop
.sl_done:
  ret

; strlen_rdi: RDI points to cstr, returns len in RAX
strlen_rdi:
  mov rax, 0
.sld_loop:
  mov dl, byte [rdi+rax]
  cmp dl, 0
  je .sld_done
  inc rax
  jmp .sld_loop
.sld_done:
  ret

; mem_copy_len: copy RBX bytes from RSI to RDI
mem_copy_len:
  test rbx, rbx
  jz .mcl_done
  mov rcx, rbx
.mcl_loop:
  mov al, byte [rsi]
  mov byte [rdi], al
  inc rsi
  inc rdi
  loop .mcl_loop
.mcl_done:
  ret
