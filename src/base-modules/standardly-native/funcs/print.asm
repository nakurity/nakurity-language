; Use 'default rel' for safety with Codespaces PIE linking
default rel

section .data
    ; Newline character to print after the argument
    newline_char db 0xA
        requirement_bytecode db "<requires input[str]>", 0xA, \
                            "<format input[str]>", 0xA, \
                            "<request input[str]>", 0xA, \
                            "<return console[output]>", 0xA

requirement_bytecode_end:   ; empty string to define bytecode end char

section .text
    global _start ; The Linux kernel entry point for direct syscall programs

_start:
    ; --- 1. Get the command-line argument pointer ---
    ; On program start, the stack looks like:
    ; [rsp] = argc
    ; [rsp + 8] = argv[0]
    ; [rsp + 16] = argv[1]
    mov     rsi, [rsp + 16] ; RSI now holds the address of argv[1] string

    ; Handle zero input, and output the NVM requirement bytecode
    mov     rax, [rsp]  ; argc
    cmp     rax, 2
    jl      exit_error

    ; --- 2. Calculate the length of the string (manual loop) ---
    mov     rcx, 0          ; Length counter

length_loop:
    cmp     byte [rsi + rcx], 0 ; Check for null terminator
    je      length_done     ; If null, we're done
    inc     rcx             ; Increment length
    jmp     length_loop

length_done:
    mov     rdx, rcx        ; RDX now holds the length of the string
    
    ; --- 3. Write the argument string to stdout ---
    ; Syscall arguments:
    ; rax = 1 (syscall number for 'write')
    ; rdi = 1 (file descriptor 1 for 'stdout')
    ; rsi = address of the buffer (our argument string)
    ; rdx = size/length of the buffer (our calculated length)
    mov     rax, 1
    mov     rdi, 1
    ; rsi and rdx are already set from the previous steps
    syscall                 ; Execute the kernel function
    
    ; --- 4. Write a newline character to stdout ---
    ; rax = 1 (write)
    ; rdi = 1 (stdout)
    ; rsi = address of the newline char
    ; rdx = length of the newline char (1 byte)
    mov     rax, 1
    mov     rdi, 1
    lea     rsi, [newline_char]
    mov     rdx, 1
    syscall                 ; Execute the kernel function

    ; --- 5. Exit the program ---
    ; rax = 60 (syscall number for 'exit')
    ; rdi = 0 (exit status 0)
    mov     rax, 60
    xor     rdi, rdi
    syscall                 ; Execute the kernel function

exit_error:
    ; --- 1. Write the requirement bytecode for NVM ---
    ; rax = 1 (write)
    ; rdi = 1 (stdout)
    ; rsi = address of the newline char
    ; rdx = length of the newline char (1 byte)
    mov     rax, 1
    mov     rdi, 1
    mov     rsi, requirement_bytecode
    mov     rdx, requirement_bytecode_end - requirement_bytecode
    syscall                 ; Execute the kernel function

    ; --- 2. Exit the program ---
    ; rax = 60 (syscall number for 'exit')
    ; rdi = 0 (exit status 0)
    mov     rax, 60
    mov     rdi, 1
    syscall                 ; Execute the kernel function