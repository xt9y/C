#ifndef C_CACHE_IO_H
#define C_CACHE_IO_H

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <limits.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#ifdef __APPLE__
#include <mach-o/dyld.h>
#endif

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

/*
 * main.c still asks copy_file() to populate ~/.cache/c/scripts/cbuild.h.
 * Never let that path own header bytes. Replace it with a symlink to the
 * canonical header that belongs to the running c executable.
 */
static int c_is_cached_build_header(const char *path) {
    static const char suffix[] = "/scripts/cbuild.h";
    if (!path) return 0;
    size_t n = strlen(path);
    size_t s = sizeof(suffix) - 1;
    return n >= s && !strcmp(path + n - s, suffix);
}

static int c_copy_readable_path(const char *path, char out[PATH_MAX]) {
    if (!path || !*path || access(path, R_OK) != 0) return 0;
    int n = snprintf(out, PATH_MAX, "%s", path);
    if (n < 0 || n >= PATH_MAX) {
        errno = ENAMETOOLONG;
        return 0;
    }
    return 1;
}

static int c_header_beside_binary(char out[PATH_MAX]) {
    char exe[PATH_MAX];
#ifdef __APPLE__
    uint32_t size = (uint32_t)sizeof(exe);
    if (_NSGetExecutablePath(exe, &size) != 0) return 0;
#else
    ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (n <= 0) return 0;
    exe[n] = '\0';
#endif

    char *slash = strrchr(exe, '/');
    if (!slash) return 0;
    *slash = '\0';

    char candidate[PATH_MAX];
    int n = snprintf(candidate, sizeof(candidate), "%s/../include/cbuild.h", exe);
    if (n < 0 || n >= (int)sizeof(candidate)) {
        errno = ENAMETOOLONG;
        return 0;
    }
    return c_copy_readable_path(candidate, out);
}

static int c_canonical_header(char out[PATH_MAX]) {
    /* Installed/development layout is authoritative. */
    if (c_header_beside_binary(out)) return 1;

#ifdef CBUILD_HEADER_PATH
    /* Build-time fallback for unusual executable layouts. */
    if (c_copy_readable_path(CBUILD_HEADER_PATH, out)) return 1;
#endif

    /* Preserve C_INCLUDE_DIR only as a last-resort compatibility override. */
    const char *inc = getenv("C_INCLUDE_DIR");
    if (inc && *inc) {
        char candidate[PATH_MAX];
        int n = snprintf(candidate, sizeof(candidate), "%s/cbuild.h", inc);
        if (n >= 0 && n < (int)sizeof(candidate) &&
            c_copy_readable_path(candidate, out)) return 1;
    }

    errno = ENOENT;
    return 0;
}

static FILE *c_direct_header_fopen(const char *path, const char *mode) {
    if (!path || !mode) {
        errno = EINVAL;
        return NULL;
    }

    if (!strcmp(mode, "wb") && c_is_cached_build_header(path)) {
        char source[PATH_MAX];
        if (!c_canonical_header(source)) return NULL;
        if (!strcmp(source, path)) {
            errno = ELOOP;
            return NULL;
        }

        if (unlink(path) != 0 && errno != ENOENT) return NULL;
        if (symlink(source, path) != 0) return NULL;

        /* copy_file() may continue writing, but those bytes go nowhere. */
        FILE *scratch = tmpfile();
        if (!scratch) {
            int saved = errno;
            unlink(path);
            errno = saved;
            return NULL;
        }
        return scratch;
    }

    return fopen(path, mode);
}

#define fopen c_direct_header_fopen

#endif
