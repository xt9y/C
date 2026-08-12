#ifndef C_CACHE_IO_H
#define C_CACHE_IO_H

#ifndef _POSIX_C_SOURCE
#define _POSIX_C_SOURCE 200809L
#endif

#include <errno.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include <unistd.h>

#ifndef PATH_MAX
#define PATH_MAX 4096
#endif

typedef struct C_AtomicFile {
    FILE *file;
    char temp[PATH_MAX];
    char target[PATH_MAX];
} C_AtomicFile;

static C_AtomicFile c_atomic_files[4];
static unsigned long c_atomic_sequence;

static int c_is_cached_build_header(const char *path) {
    static const char suffix[] = "/scripts/cbuild.h";
    if (!path) return 0;
    size_t n = strlen(path);
    size_t s = sizeof(suffix) - 1;
    return n >= s && !strcmp(path + n - s, suffix);
}

static FILE *c_atomic_fopen(const char *path, const char *mode) {
    if (!mode || strcmp(mode, "wb") || !c_is_cached_build_header(path)) {
        return fopen(path, mode);
    }

    C_AtomicFile *slot = NULL;
    for (size_t i = 0; i < sizeof(c_atomic_files) / sizeof(c_atomic_files[0]); ++i) {
        if (!c_atomic_files[i].file) {
            slot = &c_atomic_files[i];
            break;
        }
    }
    if (!slot) {
        errno = EMFILE;
        return NULL;
    }

    if (snprintf(slot->target, sizeof(slot->target), "%s", path) >= (int)sizeof(slot->target) ||
        snprintf(slot->temp, sizeof(slot->temp), "%s.tmp.%ld.%lu",
                 path, (long)getpid(), ++c_atomic_sequence) >= (int)sizeof(slot->temp)) {
        slot->target[0] = '\0';
        slot->temp[0] = '\0';
        errno = ENAMETOOLONG;
        return NULL;
    }

    slot->file = fopen(slot->temp, mode);
    if (!slot->file) {
        slot->target[0] = '\0';
        slot->temp[0] = '\0';
    }
    return slot->file;
}

static int c_atomic_fclose(FILE *file) {
    C_AtomicFile *slot = NULL;
    for (size_t i = 0; i < sizeof(c_atomic_files) / sizeof(c_atomic_files[0]); ++i) {
        if (c_atomic_files[i].file == file) {
            slot = &c_atomic_files[i];
            break;
        }
    }

    if (!slot) return fclose(file);

    int rc = fclose(file);
    slot->file = NULL;
    if (rc == 0) {
        if (rename(slot->temp, slot->target) != 0) {
            rc = EOF;
            unlink(slot->temp);
        }
    } else {
        unlink(slot->temp);
    }
    slot->temp[0] = '\0';
    slot->target[0] = '\0';
    return rc;
}

#define fopen c_atomic_fopen
#define fclose c_atomic_fclose

#endif
