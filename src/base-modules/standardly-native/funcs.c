// lazy_fn.c
// Improved lazy "fn" registry for Nakurity integration.
// Goals / changes vs previous draft:
// - Safer command building and escaping.
// - Resolver helper that can call the provided `import` helper (C binary) or any
//   resolver that returns an executable command string.
// - Cleaner popen usage and robust temporary-file fallback for stdin piping.
// - Explicit API designed to be callable from Python via ctypes (compile as shared lib):
//     gcc -shared -fPIC -std=c11 -O2 -o liblazyfn.so lazy_fn.c
//   Python usage (ctypes example):
//     lib = ctypes.CDLL('./liblazyfn.so')
//     lib.define_fn(c_name, c_params, c_body)
//     lib.install_resolver(resolver_fn_ptr, None)  # optional
//     lib.call_fn(...)
// - Adds cleanup, thread-safety note (NOT thread-safe — add locking externally if needed).

#define _GNU_SOURCE
#define _POSIX_C_SOURCE 200809L

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdarg.h>
#include <errno.h>
#include <unistd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>

// ----------------------
// Types & API surface
// ----------------------
typedef struct LazyFn {
    char *name;
    char *params;
    char *body;
    int resolved;
    char *resolved_cmd;
    struct LazyFn *next;
} LazyFn;

typedef char *(*fn_resolver_t)(const char *func_name, const char *params, const char *body, void *ctx);

static LazyFn *registry_head = NULL;
static fn_resolver_t global_resolver = NULL;
static void *global_resolver_ctx = NULL;

// ---------- utility ----------
static char *xstrdup(const char *s) {
    if (!s) return NULL;
    size_t n = strlen(s);
    char *r = malloc(n+1);
    if (!r) return NULL;
    memcpy(r, s, n+1);
    return r;
}

static int file_exists(const char *path) {
    struct stat st;
    if (!path) return 0;
    return stat(path, &st) == 0;
}

static LazyFn *find_fn(const char *name) {
    for (LazyFn *it = registry_head; it; it = it->next) {
        if (it->name && strcmp(it->name, name) == 0) return it;
    }
    return NULL;
}

// Shell-escape a single argument into a newly malloc'd string.
// Uses single-quote wrapping and handles embedded single quotes safely.
static char *shell_escape_arg(const char *s) {
    if (!s) return xstrdup("''");
    // worst-case each char could expand to 4 (for ' -> '\''), allocate conservatively
    size_t len = strlen(s);
    size_t cap = len * 4 + 4;
    char *out = malloc(cap);
    if (!out) return NULL;
    char *p = out;
    *p++ = '\'';
    for (size_t i = 0; i < len; ++i) {
        if (s[i] == '\'') {
            // append '\'' (4 chars) sequence
            strcpy(p, "'\\''");
            p += 4;
        } else {
            *p++ = s[i];
        }
    }
    *p++ = '\'';
    *p = '\0';
    return out;
}

// Build a command string: resolved_cmd plus escaped args. Returns malloc'd string.
static char *build_command_with_args(const char *resolved_cmd, int argc, const char **argv) {
    if (!resolved_cmd) return NULL;
    // start with resolved_cmd length
    size_t cap = strlen(resolved_cmd) + 1;
    // estimate extra
    for (int i = 0; i < argc; ++i) cap += strlen(argv[i] ? argv[i] : "") * 4 + 4 + 1;
    char *cmd = malloc(cap);
    if (!cmd) return NULL;
    strcpy(cmd, resolved_cmd);
    for (int i = 0; i < argc; ++i) {
        char *esc = shell_escape_arg(argv[i] ? argv[i] : "");
        if (!esc) { free(cmd); return NULL; }
        strcat(cmd, " ");
        strcat(cmd, esc);
        free(esc);
    }
    return cmd;
}

// If registry_json != NULL, we will provide it on stdin to the command.
// We run the command via /bin/sh -c '<cmd>' so that redirection and piping work.
static int run_command_capture_stdout(const char *cmdline, const char *registry_json, char **out_str) {
    if (!cmdline) return -1;
    *out_str = NULL;

    // Build final shell invocation. If registry_json present, wrap with cat - | <cmd>
    size_t final_cap = strlen(cmdline) + 128;
    char *final_cmd = malloc(final_cap);
    if (!final_cmd) return -1;

    if (registry_json && registry_json[0] != '\0') {
        // We ensure the command is invoked via sh -c "cat - | <cmd>"
        // Escape double-quotes in cmdline just in case by using single-quote wrapping for the outer sh -c
        // But since cmdline may contain single quotes, easiest robust route is to write registry to a temp file
        // and run: sh -c '<cmd> < /tmp/tmpfile'
        char tmpname[] = "/tmp/lazyfn_registry_XXXXXX";
        int fd = mkstemp(tmpname);
        if (fd == -1) { free(final_cmd); return -1; }
        ssize_t w = write(fd, registry_json, strlen(registry_json));
        (void)w;
        close(fd);
        // final command: sh -c '<cmdline> < /tmp/tmpname'
        size_t need = strlen("sh -c ''") + strlen(cmdline) + strlen(" < ") + strlen(tmpname) + 10;
        if (need > final_cap) {
            char *tmp = realloc(final_cmd, need + 1);
            if (!tmp) { unlink(tmpname); free(final_cmd); return -1; }
            final_cmd = tmp; final_cap = need + 1;
        }
        snprintf(final_cmd, final_cap, "sh -c '%s < %s'", cmdline, tmpname);

        // open for reading
        FILE *fp = popen(final_cmd, "r");
        if (!fp) { unlink(tmpname); free(final_cmd); return -1; }

        // read all output
        char buf[4096]; size_t outcap = 0, outlen = 0;
        while (1) {
            size_t n = fread(buf, 1, sizeof(buf), fp);
            if (n == 0) break;
            if (outlen + n + 1 > outcap) {
                outcap = (outlen + n + 1) * 2 + 1;
                char *tmpout = realloc(*out_str, outcap);
                if (!tmpout) { free(*out_str); *out_str = NULL; pclose(fp); unlink(tmpname); free(final_cmd); return -1; }
                *out_str = tmpout;
            }
            memcpy(*out_str + outlen, buf, n);
            outlen += n;
        }
        if (*out_str) (*out_str)[outlen] = '\0';
        pclose(fp);
        unlink(tmpname);
        free(final_cmd);
        return 0;
    } else {
        // no registry; run directly
        size_t need = strlen("sh -c ''") + strlen(cmdline) + 4;
        if (need > final_cap) {
            char *tmp = realloc(final_cmd, need + 1);
            if (!tmp) { free(final_cmd); return -1; }
            final_cmd = tmp; final_cap = need + 1;
        }
        snprintf(final_cmd, final_cap, "sh -c '%s'", cmdline);
        FILE *fp = popen(final_cmd, "r");
        if (!fp) { free(final_cmd); return -1; }
        char buf[4096]; size_t outcap = 0, outlen = 0;
        while (1) {
            size_t n = fread(buf, 1, sizeof(buf), fp);
            if (n == 0) break;
            if (outlen + n + 1 > outcap) {
                outcap = (outlen + n + 1) * 2 + 1;
                char *tmpout = realloc(*out_str, outcap);
                if (!tmpout) { free(*out_str); *out_str = NULL; pclose(fp); free(final_cmd); return -1; }
                *out_str = tmpout;
            }
            memcpy(*out_str + outlen, buf, n);
            outlen += n;
        }
        if (*out_str) (*out_str)[outlen] = '\0';
        pclose(fp);
        free(final_cmd);
        return 0;
    }
}

// ----------------------
// Public API
// ----------------------

// install_resolver: set global resolver callback (NULL to unset)
void install_resolver(fn_resolver_t resolver, void *ctx) {
    global_resolver = resolver;
    global_resolver_ctx = ctx;
}

// define_fn: copy name/params/body into registry
int define_fn(const char *name, const char *params, const char *body) {
    if (!name) return -1;
    if (find_fn(name)) return -1; // already exists
    LazyFn *f = malloc(sizeof(LazyFn));
    if (!f) return -1;
    memset(f, 0, sizeof(*f));
    f->name = xstrdup(name);
    f->params = xstrdup(params ? params : "");
    f->body = xstrdup(body ? body : "");
    f->resolved = 0;
    f->resolved_cmd = NULL;
    f->next = registry_head;
    registry_head = f;
    return 0;
}

// resolve_fn: call global_resolver if set, otherwise try a default resolution path
static int resolve_fn(LazyFn *f) {
    if (!f) return -1;
    if (f->resolved) return 0;
    char *cmd = NULL;
    if (global_resolver) {
        cmd = global_resolver(f->name, f->params, f->body, global_resolver_ctx);
        if (!cmd) return -1;
    } else {
        // default resolver: try to call ./import '<body-or-angle-spec>' if body looks like angle <...>
        // Fallback: write body to temp file and run `nakurity` on it.
        // Detect angle spec
        if (f->body && f->body[0] == '<') {
            // call import helper
            size_t need = strlen("./import ") + strlen(f->body) + 8;
            cmd = malloc(need);
            if (!cmd) return -1;
            // quote argument safely by single-quoting and replacing single quotes
            // simple approach: use printf style with %s because import expects a single arg
            char *escaped = shell_escape_arg(f->body);
            if (!escaped) { free(cmd); return -1; }
            snprintf(cmd, need, "./import %s", escaped);
            free(escaped);
        } else {
            // write body to temp .npp and run nakurity on it
            char tmpname[] = "/tmp/nfn_XXXXXX.npp";
            int fd = mkstemp(tmpname);
            if (fd == -1) return -1;
            // A conservative wrapper — adapt to your bytecode layout
            dprintf(fd, ":file %s\n:start-bytecode\n<module [%s]>\n:end-bytecode\n", f->name, f->body ? f->body : "");
            close(fd);
            size_t need = strlen("nakurity ") + strlen(tmpname) + 8;
            cmd = malloc(need);
            if (!cmd) { unlink(tmpname); return -1; }
            snprintf(cmd, need, "nakurity %s", tmpname);
            // Note: temp file remains; resolver could remove it after first run if desired.
        }
    }
    f->resolved_cmd = cmd;
    f->resolved = 1;
    return 0;
}

// call_fn: invoke a function by name with argv; registry_json optionally piped to stdin.
// returned_stdout allocated with malloc and must be free()d by caller.
int call_fn(const char *name, int argc, const char **argv, const char *registry_json, char **returned_stdout) {
    if (!name) return -1;
    LazyFn *f = find_fn(name);
    if (!f) return -1;
    if (!f->resolved) {
        if (resolve_fn(f) != 0) return -1;
    }
    if (!f->resolved_cmd) return -1;

    char *cmdline = build_command_with_args(f->resolved_cmd, argc, argv ? argv : NULL);
    if (!cmdline) return -1;

    char *out = NULL;
    int rc = run_command_capture_stdout(cmdline, registry_json, &out);
    free(cmdline);
    if (rc != 0) {
        if (out) free(out);
        return -1;
    }
    if (returned_stdout) *returned_stdout = out; else if (out) free(out);
    return 0;
}

// Free registry and associated memory. Call on shutdown.
void free_registry(void) {
    LazyFn *it = registry_head;
    while (it) {
        LazyFn *next = it->next;
        if (it->name) free(it->name);
        if (it->params) free(it->params);
        if (it->body) free(it->body);
        if (it->resolved_cmd) free(it->resolved_cmd);
        free(it);
        it = next;
    }
    registry_head = NULL;
}

// ----------------------
// Convenience small resolver you can compile-in for testing.
// This resolver writes body to a temp file and returns a malloc'd command string.
// ----------------------
char *example_resolver_write_temp(const char *func_name, const char *params, const char *body, void *ctx) {
    (void)params; (void)ctx;
    char tmpname[] = "/tmp/nfn_XXXXXX.npp";
    int fd = mkstemp(tmpname);
    if (fd == -1) return NULL;
    dprintf(fd, ":file %s\n:start-bytecode\n<module [%s]>\n:end-bytecode\n", func_name ? func_name : "anon", body ? body : "");
    close(fd);
    size_t need = strlen("nakurity ") + strlen(tmpname) + 1;
    char *cmd = malloc(need + 1);
    if (!cmd) { unlink(tmpname); return NULL; }
    snprintf(cmd, need + 1, "nakurity %s", tmpname);
    return cmd;
}

#include <ctype.h>
#include <jansson.h>  // or cJSON if you prefer

int main(int argc, char **argv) {
    if (argc == 1) {
        // Probe mode — print requirement declarations for NVM
        printf("<requires registry[lazy-fn-registry]>\n");
        printf("<requires format[stdin-json]>\n");
        printf("<return format[stdout-json]>\n");
        return 0;
    }

    // Execution mode: read JSON from stdin
    char *input = NULL;
    size_t len = 0;
    ssize_t nread = getdelim(&input, &len, '\0', stdin);
    if (nread <= 0) {
        fprintf(stderr, "lazy_fn: no JSON input\n");
        return 1;
    }

    json_error_t jerr;
    json_t *root = json_loads(input, 0, &jerr);
    free(input);
    if (!root) {
        fprintf(stderr, "lazy_fn: invalid JSON (%s)\n", jerr.text);
        return 1;
    }

    // expected: { "func": "name", "args": ["a","b"], "registry": {...} }
    const char *func = json_string_value(json_object_get(root, "func"));
    json_t *args = json_object_get(root, "args");

    if (!func) {
        json_decref(root);
        printf("{\"status\":\"false\",\"output\":\"missing func\"}\n");
        return 0;
    }

    LazyFn *entry = find_fn(func);
    if (!entry || !entry->resolved_cmd) {
        json_decref(root);
        printf("{\"status\":\"pending\",\"registry\":[]}\n");
        return 0;
    }

    // Construct command
    size_t total = strlen(entry->resolved_cmd) + 128;
    for (size_t i = 0; i < json_array_size(args); i++) {
        total += strlen(json_string_value(json_array_get(args, i))) + 3;
    }
    char *cmd = malloc(total);
    snprintf(cmd, total, "%s", entry->resolved_cmd);
    for (size_t i = 0; i < json_array_size(args); i++) {
        const char *a = json_string_value(json_array_get(args, i));
        strcat(cmd, " ");
        strcat(cmd, a);
    }

    // Execute and capture
    FILE *fp = popen(cmd, "r");
    if (!fp) {
        printf("{\"status\":\"false\",\"output\":\"exec failed\"}\n");
        free(cmd);
        json_decref(root);
        return 0;
    }
    char out[4096]; size_t r = fread(out, 1, sizeof(out)-1, fp);
    out[r] = '\0';
    pclose(fp);
    free(cmd);
    json_decref(root);

    // Return result
    printf("{\"status\":\"true\",\"output\":%s}\n", json_dumps(json_string(out), JSON_ENCODE_ANY));
    return 0;
}

#ifdef DEMO_MAIN
int main(void) {
    install_resolver(example_resolver_write_temp, NULL);
    define_fn("greet", "(name)", "print('Hello, ' + name)");
    const char *args[] = {"Niwatori"};
    char *out = NULL;
    int rc = call_fn("greet", 1, args, NULL, &out);
    if (rc == 0) {
        printf("CALL OUTPUT:\n%s\n", out ? out : "(no output)");
        free(out);
    } else {
        fprintf(stderr, "call failed\n");
    }
    free_registry();
    return 0;
}
#endif

// End of file
