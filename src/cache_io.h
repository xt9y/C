#ifndef C_CACHE_IO_H
#define C_CACHE_IO_H

#ifndef _XOPEN_SOURCE
#define _XOPEN_SOURCE 700
#endif

#ifdef __APPLE__
#ifndef _DARWIN_C_SOURCE
#define _DARWIN_C_SOURCE
#endif
#endif

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
 * main.c historically copied cbuild.h to <cache>/scripts/cbuild.h and then
 * compiled build.c with that directory on the include path. Keep the old core
 * ABI untouched, but make that cached header purely virtual:
 *
 *   - writes to <cache>/scripts/cbuild.h are discarded;
 *   - reads of that path (used for the build-script cache hash) read the
 *     canonical cbuild.h instead;
 *   - the compiler invocation for build.c receives the canonical include dir.
 *
 * Therefore no cached cbuild.h file or symlink is created, while changes to
 * the real header still invalidate the compiled build.c module.
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
    ssize_t exe_len = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
    if (exe_len <= 0) return 0;
    exe[exe_len] = '\0';
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
    /* The header installed/built beside the running c executable wins. */
    if (c_header_beside_binary(out)) return 1;

#ifdef CBUILD_HEADER_PATH
    if (c_copy_readable_path(CBUILD_HEADER_PATH, out)) return 1;
#endif

    /* Development fallback only. */
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

static int c_canonical_include(char out[PATH_MAX]) {
    if (!c_canonical_header(out)) return 0;
    char *slash = strrchr(out, '/');
    if (!slash) {
        errno = EINVAL;
        return 0;
    }
    *slash = '\0';
    return 1;
}

static FILE *c_direct_header_fopen(const char *path, const char *mode) {
    if (!path || !mode) {
        errno = EINVAL;
        return NULL;
    }

    if (c_is_cached_build_header(path)) {
        if (!strcmp(mode, "wb")) {
            /* Remove leftovers from older c versions and discard the copy. */
            if (unlink(path) != 0 && errno != ENOENT) return NULL;
            return tmpfile();
        }

        if (!strcmp(mode, "rb")) {
            char canonical[PATH_MAX];
            if (!c_canonical_header(canonical)) return NULL;
            return fopen(canonical, mode);
        }
    }

    return fopen(path, mode);
}

static int c_build_script_argv(char *const argv[]) {
    if (!argv) return 0;
    for (size_t i = 0; argv[i]; ++i) {
        if (!strcmp(argv[i], "build.c")) return 1;
    }
    return 0;
}

static int c_direct_header_execvp(const char *file, char *const argv[]) {
    if (!c_build_script_argv(argv)) return execvp(file, argv);

    char include_dir[PATH_MAX];
    if (!c_canonical_include(include_dir)) return execvp(file, argv);

    char include_arg[PATH_MAX + 3];
    int n = snprintf(include_arg, sizeof(include_arg), "-I%s", include_dir);
    if (n < 0 || n >= (int)sizeof(include_arg)) {
        errno = ENAMETOOLONG;
        return -1;
    }

    char *rewritten[256];
    size_t count = 0;
    int replaced = 0;
    while (argv[count]) {
        if (count + 2 >= sizeof(rewritten) / sizeof(rewritten[0])) {
            errno = E2BIG;
            return -1;
        }
        rewritten[count] = argv[count];
        if (!replaced && argv[count][0] == '-' && argv[count][1] == 'I' &&
            strstr(argv[count] + 2, "/scripts")) {
            rewritten[count] = include_arg;
            replaced = 1;
        }
        ++count;
    }

    if (!replaced) rewritten[count++] = include_arg;
    rewritten[count] = NULL;
    return execvp(file, rewritten);
}

#define fopen c_direct_header_fopen
#define execvp c_direct_header_execvp

#endif