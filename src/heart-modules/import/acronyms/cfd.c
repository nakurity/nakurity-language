// cfd.c
#define _GNU_SOURCE
#include <libgen.h>
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <limits.h>

const char *resolve(const char *nh_path, const char *rest) {
    static char buf[PATH_MAX];
    char tmp[PATH_MAX];
    strncpy(tmp, nh_path, sizeof(tmp));
    snprintf(buf, sizeof(buf), "%s/%s", dirname(tmp), rest);
    return buf;
}
