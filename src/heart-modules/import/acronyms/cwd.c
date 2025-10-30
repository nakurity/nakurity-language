// cwd.c
#define _GNU_SOURCE
#include <unistd.h>
#include <limits.h>
#include <stdio.h>

const char *resolve(const char *nh_path, const char *rest) {
    static char buf[PATH_MAX], cwd[PATH_MAX];
    getcwd(cwd, sizeof(cwd));
    snprintf(buf, sizeof(buf), "%s/%s", cwd, rest);
    return buf;
}
