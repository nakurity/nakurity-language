// import.c
// Core import logic with lazy helper loading (hardened + debug)
// Build: gcc -std=gnu11 -O2 -ldl -o import import.c
// For stronger diagnostics build with: gcc -g -O0 -fsanitize=address,undefined -ldl -o import_dbg import.c

#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <limits.h>
#include <sys/stat.h>
#include <dlfcn.h>
#include <errno.h>
#include <stdarg.h>

static const char *MSG_ERR_NARGS   = "Import error: expected 1 arg: '<ns.chain.name()>'\n";
static const char *MSG_ERR_PARSE   = "Import error: malformed angle spec\n";
static const char *MSG_ERR_MISSING = "Import error: module not found (.nh/.so missing)\n";

#ifndef DEBUG
#define DEBUG 0
#endif

static void logf(const char *fmt, ...) {
#if DEBUG
    va_list ap;
    va_start(ap, fmt);
    fprintf(stderr, "[import-debug] ");
    vfprintf(stderr, fmt, ap);
    fprintf(stderr, "\n");
    va_end(ap);
#endif
}

static int file_exists(const char *path) {
    struct stat st;
    if (!path) return 0;
    return (stat(path, &st) == 0);
}

// ------------------------------
// Dynamic loader for helpers
// ------------------------------
// Returns NULL on any failure and does not exit()
// Caller must not assume handle lifetime beyond this call unless they change this API
// ------------------------------
static void *load_helper_symbol(const char *name, const char *symbol) {
    if (!name || !symbol) return NULL;
    char path[PATH_MAX];
    if (snprintf(path, sizeof(path),
                 "packy/modules/headerly-native/helpers/%s.so", name) >= (int)sizeof(path)) {
        fprintf(stderr, "loader path overflow for helper '%s'\n", name);
        return NULL;
    }

    logf("attempting dlopen(%s)", path);
    void *handle = dlopen(path, RTLD_LAZY | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "dlopen failed for %s: %s\n", path, dlerror());
        return NULL;
    }

    dlerror(); // clear
    void *sym = dlsym(handle, symbol);
    char *d = dlerror();
    if (d != NULL || !sym) {
        fprintf(stderr, "dlsym failed for %s -> %s: %s\n", path, symbol, d ? d : "symbol NULL");
        dlclose(handle);
        return NULL;
    }

    // Note: we intentionally dlclose(handle) NOT performed here so that symbol remains valid on some systems.
    // If you prefer to dlclose immediately, you must platform-check or copy function pointer safely.
    return sym;
}

// ------------------------------
// parse_angle_spec
// - spec must be of form "<a.b.c.func()>" or "<a.b.module>" etc.
// - extracts last identifier into end_name (safe copy)
// - sets is_func if trailing "()"
// ------------------------------
static int parse_angle_spec(const char *spec, size_t len,
                            char *end_name, size_t cap,
                            int *is_func)
{
    if (!spec || !end_name || cap == 0 || !is_func) return 0;
    if (len < 3) return 0;
    if (spec[0] != '<' || spec[len - 1] != '>') return 0;

    const char *inside = spec + 1;
    size_t inside_len = len - 2;
    if (inside_len == 0) return 0;

    ssize_t last_dot = -1;
    for (size_t i = 0; i < inside_len; ++i) {
        if (inside[i] == '.') last_dot = (ssize_t)i;
    }

    size_t start = (last_dot >= 0) ? (size_t)(last_dot + 1) : 0;
    size_t w = 0;

    // copy until '(' or ')' or '.' (terminators) or end
    for (size_t i = start; i < inside_len && w + 1 < cap; ++i) {
        char c = inside[i];
        if (c == '(' || c == ')' || c == '.') break;
        // optionally validate identifier chars (alnum + '-' + '_')
        if (!( (c >= '0' && c <= '9') ||
               (c >= 'A' && c <= 'Z') ||
               (c >= 'a' && c <= 'z') ||
               c == '_' || c == '-' )) {
            // treat unexpected char as terminator
            break;
        }
        end_name[w++] = c;
    }
    end_name[w] = '\0';

    // safety: ensure we actually captured something reasonable
    if (w == 0) return 0;

    *is_func = 0;
    if (inside_len >= 2) {
        // check last two characters inside for "()"
        if (inside[inside_len - 2] == '(' && inside[inside_len - 1] == ')') *is_func = 1;
    }

    logf("parse: end_name='%s', is_func=%d, last_dot=%zd", end_name, *is_func, last_dot);
    return 1;
}

// ------------------------------
// build_base_path
// - build path like: <cwd>/packy/modules/<token1>/<token2>/.../<end_name>
// - tokens come from the inside portion up to last dot (exclusive)
// - safer tokenization and bounds checks
// ------------------------------
static int build_base_path(const char *spec, size_t len,
                           const char *end_name, char *out, size_t cap)
{
    if (!spec || !end_name || !out || cap == 0) return 0;

    char cwd[PATH_MAX];
    if (!getcwd(cwd, sizeof(cwd))) {
        // fallback
        strncpy(cwd, ".", sizeof(cwd));
        cwd[sizeof(cwd)-1] = '\0';
    }

    if (len < 2) return 0;
    const char *inside = spec + 1;
    size_t inside_len = len - 2;
    if (inside_len == 0) return 0;

    // find last dot position inside (index)
    ssize_t last_dot = -1;
    for (size_t i = 0; i < inside_len; ++i)
        if (inside[i] == '.') last_dot = (ssize_t)i;

    // start with base prefix
    if (snprintf(out, cap, "%s/packy/modules", cwd) >= (int)cap) return 0;

    // if there are path tokens before the final dot, append them as directories
    if (last_dot > 0) {
        size_t tok_start = 0;
        for (size_t i = 0; i <= (size_t)last_dot; ++i) {
            // split tokens on dots or when we hit last_dot
            if (i == (size_t)last_dot || inside[i] == '.') {
                size_t tok_len = i - tok_start;
                if (tok_len > 0) {
                    // ensure we have space for '/' + token + '\0'
                    size_t used = strlen(out);
                    if (used + 1 + tok_len + 1 >= cap) return 0; // +1 for '/', +1 for '\0'
                    // append '/'
                    strncat(out, "/", cap - strlen(out) - 1);
                    // append token
                    strncat(out, inside + tok_start, tok_len);
                }
                tok_start = i + 1;
            }
        }
    }

    // finally append '/' + end_name
    size_t used = strlen(out);
    if (used + 1 + strlen(end_name) + 1 >= cap) return 0;
    strncat(out, "/", cap - strlen(out) - 1);
    strncat(out, end_name, cap - strlen(out) - 1);

    logf("built base path: %s", out);
    return 1;
}

int main(int argc, char **argv) {
    // basic guard
    if (argc != 2) {
        fputs(MSG_ERR_NARGS, stderr);
        return 1;
    }

    const char *spec = argv[1];
    if (!spec) {
        fputs(MSG_ERR_PARSE, stderr);
        return 1;
    }

    size_t len = strlen(spec);
    if (len == 0 || len >= PATH_MAX*2) { // arbitrary large limit guard
        fputs(MSG_ERR_PARSE, stderr);
        return 1;
    }

    char end_name[128];
    int is_func = 0;
    if (!parse_angle_spec(spec, len, end_name, sizeof(end_name), &is_func)) {
        fputs(MSG_ERR_PARSE, stderr);
        return 1;
    }

    char base[PATH_MAX];
    memset(base, 0, sizeof(base));
    if (!build_base_path(spec, len, end_name, base, sizeof(base))) {
        fprintf(stderr, "Import error: path construction failed or would overflow.\n");
        return 1;
    }

    // compose nh and so paths safely
    char nh_path[PATH_MAX];
    char so_path[PATH_MAX];
    if (snprintf(nh_path, sizeof(nh_path), "%s.nh", base) >= (int)sizeof(nh_path) ||
        snprintf(so_path, sizeof(so_path), "%s.so", base) >= (int)sizeof(so_path)) {
        fprintf(stderr, "Import error: path overflow when making nh/so paths\n");
        return 1;
    }

    logf("nh_path='%s' so_path='%s'", nh_path, so_path);

    // try .nh first (preferred)
    if (file_exists(nh_path)) {
        // zero-initialize read buffer
        char buf[4096];
        memset(buf, 0, sizeof(buf));

        // lazy-load nh_export_reader -> function signature: int read_export(const char *, char *, size_t)
        typedef int (*read_export_t)(const char *, char *, size_t);
        void *sym = load_helper_symbol("read_export", "read_export");
        if (!sym) {
            fprintf(stderr, "missing nh_export_reader helper or symbol\n");
            // don't segfault — treat as failure to load helper
            return 1;
        }
        read_export_t read_export = (read_export_t)sym;

        int rc = 0;
        // protect against misbehaving helper by checking return value and keeping buffer bounds
        rc = read_export(nh_path, buf, sizeof(buf));
        if (rc == 0) {
            // helper reports failure
            fprintf(stderr, "nh_export_reader failed to read %s\n", nh_path);
            return 1;
        }
        // ensure NUL-termination
        buf[sizeof(buf)-1] = '\0';

        // lazy-load acronym_resolver if available, but do NOT require it
        typedef void (*resolve_acronyms_t)(const char *, char *, size_t, const char *);
        void *sym2 = load_helper_symbol("acronym_resolver", "resolve_acronyms");
        if (sym2) {
            resolve_acronyms_t resolve_acronyms = (resolve_acronyms_t)sym2;
            // call with careful params; assume resolver will not overflow dst if size param is correct
            resolve_acronyms(buf, buf, sizeof(buf), nh_path);
            buf[sizeof(buf)-1] = '\0';
        } else {
            logf("acronym_resolver helper not present; skipping");
        }

        // print outcome safely
        printf("%s\n", buf);
        return 0;
    }

    // try .so
    if (file_exists(so_path)) {
        // convention output
        // protect end_name length
        if (strlen(end_name) >= 1024) {
            fprintf(stderr, "Import error: name too long\n");
            return 1;
        }
        printf("%s.so:%s\n", end_name, end_name);
        return 0;
    }

    fputs(MSG_ERR_MISSING, stderr);
    return 1;
}
