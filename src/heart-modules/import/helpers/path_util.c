// path_util.c
#define _GNU_SOURCE
#include <unistd.h>
#include <sys/stat.h>
#include <string.h>
#include <limits.h>

int file_exists_helper(const char *path) {
    struct stat st;
    return stat(path, &st) == 0;
}

const char *get_cwd_helper(void) {
    static char cwd[PATH_MAX];
    if (!getcwd(cwd, sizeof(cwd))) strcpy(cwd, ".");
    return cwd;
}
