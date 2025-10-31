// project_root.c
#define _GNU_SOURCE
#include <string.h>
#include <sys/stat.h>
#include <limits.h>
#include <libgen.h>
#include <stdio.h>

char *find_root(const char *start) {
    static char root[PATH_MAX];
    strncpy(root, start, sizeof(root));
    while (1) {
        struct stat st1, st2;
        char m1[PATH_MAX], m2[PATH_MAX];
        snprintf(m1, sizeof(m1), "%s/packy/modules", root);
        snprintf(m2, sizeof(m2), "%s/.nakurity", root);
        if (stat(m1, &st1) == 0 || stat(m2, &st2) == 0)
            return root;
        char *slash = strrchr(root, '/');
        if (!slash || slash == root) break;
        *slash = '\0';
    }
    return NULL;
}
