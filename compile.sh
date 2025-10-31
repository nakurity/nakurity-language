# Set base directories and create them
BASE_DIR="packy"
MODULES_DIR="$BASE_DIR/modules/standardly-native/funcs"
HEADERS="$BASE_DIR/modules/headerly-native/import"
HELPERS="$BASE_DIR/modules/headerly-native/helpers"
ACRONYMS="$BASE_DIR/modules/headerly-native/acronyms"
RUNTIME_DIR="$BASE_DIR/runtime/heart-modules"

mkdir -p "packy/namespaces"
mkdir -p "$MODULES_DIR" "$RUNTIME_DIR" "$ACRONYMS" "$HEADERS" "$HELPERS"

# # Enables recursive globbing
# shopt -s globstar

# # Iterate over all C files
# for file in **/*.c; do
#   # Skip directories
#   if [[ -f "$file" ]]; then
#     # Extract the directory path of the current file
#     file_dir=$(dirname "$file")
    
#     # Determine the output directory based on the file's original location
#     # All files inside packy/modules/standardly-native/funcs will go to that directory
#     if [[ "$file_dir" == "$MODULES_DIR" ]]; then
#       output_dir="$MODULES_DIR"
#     # All other files will go to packy/runtime/heart-modules
#     else
#       output_dir="$RUNTIME_DIR"
#     fi

#     # Extract the filename without the extension
#     base_name=$(basename "$file" .c)
    
#     # Construct the full output path
#     output_path="$output_dir/$base_name"
    
#     # Compile each C file into the designated output directory
#     gcc -std=gnu11 -O2 -ldl "$file" -o "$output_path"
    
#     # Optional: Print a message to show what was compiled
#     echo "Compiled '$file' to '$output_path'"
#   fi
# done

# # Restores the default globbing behavior
# shopt -u globstar

cp src/base-modules/standardly-native/funcs/print.nh packy/modules/standardly-native/funcs/print.nh

gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/helpers/find_root.c -o packy/modules/headerly-native/helpers/find_root.so
gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/acronyms/cfd.c -o packy/modules/headerly-native/acronyms/cfd.so
gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/acronyms/cwd.c -o packy/modules/headerly-native/acronyms/cwd.so
gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/helpers/acronym_resolver.c -o packy/modules/headerly-native/helpers/acronym_resolver.so
gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/helpers/path_util.c -o packy/modules/headerly-native/helpers/path_util.so
gcc -std=gnu11 -O2 -fPIC -ldl -shared src/heart-modules/import/helpers/read_export.c -o packy/modules/headerly-native/helpers/read_export.so

gcc -std=gnu11 -g -O0 -fPIC -ldl src/heart-modules/import.c -o packy/namespaces/@import

nasm -f elf64 -F dwarf -g src/base-modules/standardly-native/funcs/print.asm -o packy/modules/standardly-native/funcs/print.o
ld packy/modules/standardly-native/funcs/print.o -o packy/modules/standardly-native/funcs/print.so
cp packy/modules/standardly-native/funcs/print.so ./print

gcc -std=c11 -O2 -l vcpkg/packages/jansson_x64-linux/include/jansson.h -o packy/modules/standardly-native/funcs.so src/base-modules/standardly-native/funcs.c
cp src/base-modules/standardly-native/funcs.nh packy/modules/standardly-native/funcs.nh