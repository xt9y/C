#include <errno.h>
#include <sched.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/wait.h>
#include <unistd.h>

#include "fuzz_support.h"
#include "cli_fuzz.c"

static bool fuzz_fs_ready = false;
static CompilerStamp fuzz_fs_source_stamp;
static CompilerStamp fuzz_fs_dep_stamp;
static char fuzz_fs_victim[PATH_MAX];
static char fuzz_fs_hash_meta[PATH_MAX];
static char fuzz_fs_dep_meta[PATH_MAX];
static char fuzz_fs_time_meta[PATH_MAX];

static const char fuzz_fs_guard[] = "C-FUZZ-GUARD\n";

static void fuzz_fs_assert_guard(void) {
    FILE *f = fopen(fuzz_fs_victim, "rb");
    if (!f) abort();
    char buf[64] = {0};
    size_t n = fread(buf, 1, sizeof(buf) - 1, f);
    fclose(f);
    if (n != sizeof(fuzz_fs_guard) - 1 || memcmp(buf, fuzz_fs_guard, n)) abort();
}

static void fuzz_fs_poison_temp(const char *destination) {
    char temp[PATH_MAX];
    int n = snprintf(temp, sizeof(temp), "%s.tmp.%ld", destination, (long)getpid());
    if (n < 0 || n >= (int)sizeof(temp)) abort();
    unlink(temp);
    if (symlink(fuzz_fs_victim, temp) != 0) abort();
}

static void fuzz_fs_init(void) {
    if (fuzz_fs_ready) return;
    if (setenv("C_CACHE_DIR", ".c-fuzz-fs-cache", 1) != 0) abort();

    char cwd[PATH_MAX];
    if (!getcwd(cwd, sizeof(cwd))) abort();
    path_join(fuzz_fs_victim, cwd, "victim.txt");
    if (!fuzz_write_file(fuzz_fs_victim, (const uint8_t *)fuzz_fs_guard, sizeof(fuzz_fs_guard) - 1)) abort();

    static const uint8_t source[] = "int fs_source(void) { return 1; }\n";
    static const uint8_t depfile[] = "build/fs.o: source.c include/fs.h\n";
    static const uint8_t header[] = "#define FS_HEADER 1\n";
    mkdir_p("include");
    if (!fuzz_write_file("source.c", source, sizeof(source) - 1)) abort();
    if (!fuzz_write_file("input.d", depfile, sizeof(depfile) - 1)) abort();
    if (!fuzz_write_file("include/fs.h", header, sizeof(header) - 1)) abort();

    fuzz_fs_source_stamp = compiler_stat_now("source.c");
    fuzz_fs_dep_stamp = compiler_stat_now("input.d");
    if (!fuzz_fs_source_stamp.exists || !fuzz_fs_dep_stamp.exists) abort();

    compiler_perf_cache_path("hash", "source.c", ".hash", fuzz_fs_hash_meta);
    compiler_perf_cache_path("deps", "input.d", ".deps", fuzz_fs_dep_meta);
    compiler_perf_cache_path("timings", "source.c", ".time", fuzz_fs_time_meta);
    fuzz_fs_ready = true;
}

static void fuzz_fs_symlink_writes(uint64_t value) {
    fuzz_fs_poison_temp(fuzz_fs_hash_meta);
    compiler_persistent_hash_store(
        "source.c",
        fuzz_fs_source_stamp.sec,
        fuzz_fs_source_stamp.nsec,
        fuzz_fs_source_stamp.size,
        value);
    fuzz_fs_assert_guard();

    StrVec deps = {0};
    vec_push(&deps, "source.c");
    vec_push(&deps, "include/fs.h");
    fuzz_fs_poison_temp(fuzz_fs_dep_meta);
    compiler_dep_cache_store("input.d", &deps);
    vec_free(&deps);
    fuzz_fs_assert_guard();

    fuzz_fs_poison_temp(fuzz_fs_time_meta);
    compiler_profile_reset();
    compiler_history_record("source.c", (double)(value % 100000ULL) / 100.0 + 0.01);
    fuzz_fs_assert_guard();

    static const uint8_t copy_data[] = "safe-copy\n";
    if (!fuzz_write_file("copy.in", copy_data, sizeof(copy_data) - 1)) abort();
    char copy_out[PATH_MAX];
    path_join(copy_out, ".", "copy.out");
    fuzz_fs_poison_temp(copy_out);
    if (!compiler_copy_atomic("copy.in", copy_out)) abort();
    fuzz_fs_assert_guard();
}

static void fuzz_fs_concurrent_hashes(const uint8_t *data, size_t size) {
    unsigned workers = 2u + (unsigned)(fuzz_u64(data, size) % 3ULL);
    uint64_t values[4] = {0};
    pid_t pids[4] = {0};

    for (unsigned i = 0; i < workers; ++i) {
        values[i] = fuzz_u64(data + (size > i ? i : size), size > i ? size - i : 0) ^
                    (0x9e3779b97f4a7c15ULL * (uint64_t)(i + 1));
        pid_t pid = fork();
        if (pid < 0) abort();
        if (pid == 0) {
            compiler_persistent_hash_store(
                "source.c",
                fuzz_fs_source_stamp.sec,
                fuzz_fs_source_stamp.nsec,
                fuzz_fs_source_stamp.size,
                values[i]);
            compiler_history_record("source.c", (double)(i + 1));
            _exit(0);
        }
        pids[i] = pid;
    }

    for (unsigned i = 0; i < workers; ++i) {
        int status = 0;
        while (waitpid(pids[i], &status, 0) < 0 && errno == EINTR) {}
        if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) abort();
    }

    uint64_t observed = 0;
    if (!compiler_persistent_hash_lookup(
            "source.c",
            fuzz_fs_source_stamp.sec,
            fuzz_fs_source_stamp.nsec,
            fuzz_fs_source_stamp.size,
            &observed)) abort();
    bool matched = false;
    for (unsigned i = 0; i < workers; ++i) if (observed == values[i]) matched = true;
    if (!matched) abort();

    double history = compiler_history_read("source.c");
    if (!(history > 0.0)) abort();
    fuzz_fs_assert_guard();
}

static void fuzz_fs_symlink_race(uint64_t value) {
    char temp[PATH_MAX];
    int n = snprintf(temp, sizeof(temp), "%s.tmp.%ld", fuzz_fs_hash_meta, (long)getpid());
    if (n < 0 || n >= (int)sizeof(temp)) abort();

    int start_pipe[2];
    if (pipe(start_pipe) != 0) abort();
    pid_t attacker = fork();
    if (attacker < 0) abort();
    if (attacker == 0) {
        close(start_pipe[1]);
        char token = 0;
        ssize_t got;
        do { got = read(start_pipe[0], &token, 1); } while (got < 0 && errno == EINTR);
        close(start_pipe[0]);
        if (got != 1) _exit(2);

        unsigned attacks = 256u + (unsigned)(value & 255ULL);
        for (unsigned i = 0; i < attacks; ++i) {
            if (unlink(temp) != 0 && errno != ENOENT) _exit(3);
            if (symlink(fuzz_fs_victim, temp) != 0 && errno != EEXIST) _exit(4);
            sched_yield();
        }
        _exit(0);
    }

    close(start_pipe[0]);
    char token = 'x';
    ssize_t sent;
    do { sent = write(start_pipe[1], &token, 1); } while (sent < 0 && errno == EINTR);
    close(start_pipe[1]);
    if (sent != 1) abort();

    unsigned stores = 16u + (unsigned)(value & 15ULL);
    for (unsigned i = 0; i < stores; ++i) {
        compiler_persistent_hash_store(
            "source.c",
            fuzz_fs_source_stamp.sec,
            fuzz_fs_source_stamp.nsec,
            fuzz_fs_source_stamp.size,
            value + i);
        sched_yield();
    }

    int status = 0;
    while (waitpid(attacker, &status, 0) < 0 && errno == EINTR) {}
    if (!WIFEXITED(status) || WEXITSTATUS(status) != 0) abort();

    if (unlink(temp) != 0 && errno != ENOENT) abort();
    uint64_t final_value = value ^ 0xd1b54a32d192ed03ULL;
    compiler_persistent_hash_store(
        "source.c",
        fuzz_fs_source_stamp.sec,
        fuzz_fs_source_stamp.nsec,
        fuzz_fs_source_stamp.size,
        final_value);

    fuzz_fs_assert_guard();
    uint64_t observed = 0;
    if (!compiler_persistent_hash_lookup(
            "source.c",
            fuzz_fs_source_stamp.sec,
            fuzz_fs_source_stamp.nsec,
            fuzz_fs_source_stamp.size,
            &observed) || observed != final_value) abort();
}

int LLVMFuzzerTestOneInput(const uint8_t *data, size_t size) {
    if (size > 512) return 0;
    fuzz_fs_init();
    uint64_t value = fuzz_u64(data, size);
    fuzz_fs_symlink_writes(value);
    fuzz_fs_concurrent_hashes(data, size);
    fuzz_fs_symlink_race(value);
    return 0;
}
