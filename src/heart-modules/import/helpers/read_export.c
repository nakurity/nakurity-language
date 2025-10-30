// nh_export_reader.c
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

int read_export(const char *path, char *out, size_t cap) {
    FILE *f = fopen(path, "rb");
    if (!f) return 0;

    char *buf = malloc(8192);
    if (!buf) { fclose(f); return 0; }
    size_t n = fread(buf, 1, 8192, f);
    fclose(f);

    if (n == 0) { free(buf); return 0; }

    const char *kw = "export[\"";
    char *p = strstr(buf, kw);
    if (!p) { free(buf); return 0; }
    p += strlen(kw);
    char *q = strchr(p, '"');
    if (!q) { free(buf); return 0; }

    size_t len = q - p;
    if (len >= cap) len = cap - 1;
    memcpy(out, p, len);
    out[len] = '\0';
    free(buf);
    return 1;
}
