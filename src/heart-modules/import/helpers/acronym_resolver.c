#define _GNU_SOURCE
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <dlfcn.h>
#include <limits.h>
#include <unistd.h>
#include <libgen.h>
#include <sys/stat.h>

typedef const char *(*acronym_func_t)(const char *nh_path, const char *rest);

static void *load_module(const char *name) {
    static char path[PATH_MAX];
    snprintf(path, sizeof(path), "packy/modules/headerly-native/acronyms/%s.so", name);
    void *handle = dlopen(path, RTLD_LAZY | RTLD_LOCAL);
    if (!handle) {
        fprintf(stderr, "[lazy-acronym] failed to load %s: %s\n", path, dlerror());
        return NULL;
    }
    return handle;
}

static acronym_func_t get_func(const char *name) {
    static struct { const char *key; void *handle; acronym_func_t func; } cache[8];
    for (int i = 0; i < 8; i++) {
        if (cache[i].key && strcmp(cache[i].key, name) == 0)
            return cache[i].func;
        if (!cache[i].key) {
            cache[i].key = strdup(name);
            cache[i].handle = load_module(name);
            if (!cache[i].handle) return NULL;
            cache[i].func = (acronym_func_t)dlsym(cache[i].handle, "resolve");
            if (!cache[i].func) {
                fprintf(stderr, "[lazy-acronym] missing symbol in %s\n", name);
                dlclose(cache[i].handle);
                cache[i].key = NULL;
                return NULL;
            }
            return cache[i].func;
        }
    }
    fprintf(stderr, "[lazy-acronym] cache full\n");
    return NULL;
}

void resolve_acronyms(const char *src, char *dst, size_t dstlen, const char *nh_path) {
    const char *s = src;
    char *out = dst;
    size_t rem = dstlen;

    while (*s && rem > 1) {
        if (strncmp(s, "cfd:/", 5) == 0) {
            acronym_func_t fn = get_func("cfd");
            if (fn) {
                const char *val = fn(nh_path, s + 5);
                size_t n = snprintf(out, rem, "%s", val);
                out += n; rem -= n;
            }
            break;
        } else if (strncmp(s, "cwd:/", 5) == 0) {
            acronym_func_t fn = get_func("cwd");
            if (fn) {
                const char *val = fn(nh_path, s + 5);
                size_t n = snprintf(out, rem, "%s", val);
                out += n; rem -= n;
            }
            break;
        } else if (strncmp(s, "root:/", 6) == 0) {
            acronym_func_t fn = get_func("find_root");
            if (fn) {
                const char *val = fn(nh_path, s + 6);
                size_t n = snprintf(out, rem, "%s", val);
                out += n; rem -= n;
            }
            break;
        } else {
            *out++ = *s++;
            rem--;
        }
    }
    *out = '\0';
}
