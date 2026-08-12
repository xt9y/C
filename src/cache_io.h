#ifndef C_CACHE_IO_H
#define C_CACHE_IO_H

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

/*
 * build.c is compiled with ~/.cache/c/scripts on its include path. Older
 * versions copied cbuild.h into that directory, which allowed stale or
 * interrupted copies to become the header used by every project. Keep the
 * include location, but make it a symlink to the canonical header instead.
 */
static char c_cbuild_source[PATH_MAX];

static int c_is_cached_build_header(const char *path) {
    static const char suffix[] = "/scripts/cbuild.h";
    if (!path) return 0;
    size_t n = strlen(path);
    size_t s = sizeof(suffix) - 1;
    return n >= s && !strcmp(path + n - s, suffix);
}

static int c_is_cbuild_header(const char *path) {
    if (!path) return 0;
    const char *base = strrchr(path, '/');
    base = base ? base + 1 : path;
    return !strcmp(base, "cbuild.h");
}

static FILE *c_direct_header_fopen(const char *path, const char *mode) {
    if (!path || !mode) {
        errno = EINVAL;
        return NULL;
    }

    /* Remember the exact source selected by write_embedded_header(). */
    if (!strcmp(mode, "rb") && c_is_cbuild_header(path) &&
        !c_is_cached_build_header(path)) {
        char resolved[PATH_MAX];
        if (realpath(path, resolved)) {
            int n = snprintf(c_cbuild_source, sizeof(c_cbuild_source), "%s", resolved);
            if (n < 0 || n >= (int)sizeof(c_cbuild_source)) {
                c_cbuild_source[0] = '\0';
                errno = ENAMETOOLONG;
                return NULL;
            }
        }
    }

    /*
     * copy_file() still opens the scripts path for writing. Replace that write
     * with a symlink to the real header, and give copy_file() a scratch stream
     * for the bytes it was going to duplicate. No cached header contents are
     * created.
     */
    if (!strcmp(mode, "wb") && c_is_cached_build_header(path)) {
        if (!c_cbuild_source[0]) {
            errno = ENOENT;
            return NULL;
        }

        if (unlink(path) != 0 && errno != ENOENT) return NULL;
        if (symlink(c_cbuild_source, path) != 0) return NULL;

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
