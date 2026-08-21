#include <stdint.h>
#include <errno.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

static void fuzz_check_lock(const LockFile *lock) {
    if (lock->count > C_MAX_DEPS) abort();
    for (size_t i = 0; i < lock->count; ++i) {
        const LockEntry *e = &lock->entries[i];
        if (!memchr(e->name, '\0', sizeof(e->name))) abort();
        if (!memchr(e->url, '\0', sizeof(e->url))) abort();
        if (!memchr(e->requested, '\0', sizeof(e->requested))) abort();
        if (!memchr(e->resolved, '\0', sizeof(e->resolved))) abort();
    }
}

static bool fuzz_lock_equal(const LockFile *a, const LockFile *b) {
    if (a->count != b->count) return false;
    for (size_t i = 0; i < a->count; ++i) {
        if (strcmp(a->entries[i].name, b->entries[i].name)) return false;
        if (strcmp(a->entries[i].url, b->entries[i].url)) return false;
        if (strcmp(a->entries[i].requested, b->entries[i].requested)) return false;
        if (strcmp(a->entries[i].resolved, b->entries[i].resolved)) return false;
    }
    return true;
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 1024 * 1024) return 0;
    if (!fuzz_write_file("c.lock", data, size)) return 0;

    /* load_lock() intentionally rejects malformed CLI input through
       c__fatal()/exit().  libFuzzer treats any direct exit as a crash, so run
       the parser in a child.  Ordinary non-zero exits are expected rejection;
       signals still mean a real crash and are escalated to the parent. */
    pid_t pid = fork();
    if (pid < 0) {
        unlink("c.lock");
        return 0;
    }
    if (pid == 0) {
        LockFile first;
        load_lock(&first);
        fuzz_check_lock(&first);

        if (first.count) {
            save_lock(&first);
            LockFile second;
            load_lock(&second);
            fuzz_check_lock(&second);
            if (!fuzz_lock_equal(&first, &second)) abort();
        }
        _exit(0);
    }

    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) continue;
        unlink("c.lock");
        return 0;
    }
    unlink("c.lock");
    if (WIFSIGNALED(status)) abort();
    return 0;
}
