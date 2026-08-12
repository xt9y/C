#define C_DEP_CMAKE C_DEP_RESERVED
#define cmake_options compile_flags
#define main c_legacy_main
#include "main.c"
#undef main
#undef cmake_options
#undef C_DEP_CMAKE

#include <signal.h>
#include <spawn.h>

extern char **environ;

typedef struct CompilerPerfOptions {
    int jobs;
    int unity;
    bool object_cache;
} CompilerPerfOptions;

static CompilerPerfOptions compiler_perf = {0, 0, true};

static const char *compiler_ar(void) {
    const char *ar = getenv("AR");
    return (ar && *ar) ? ar : "ar";
}

static bool compiler_cpp_source(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return false;
    return !strcmp(ext, ".cpp") || !strcmp(ext, ".cc") || !strcmp(ext, ".cxx") || !strcmp(ext, ".mm");
}

static bool compiler_c_standard_flag(const char *flag) {
    return !strncmp(flag, "-std=c", 6) && strncmp(flag, "-std=c++", 8);
}

static bool compiler_cpp_standard_flag(const char *flag) {
    return !strncmp(flag, "-std=c++", 8) || !strncmp(flag, "-std=gnu++", 10);
}

static void compiler_push_standard(StrVec *a, const char *source) {
    vec_push(a, compiler_cpp_source(source) ? "-std=c++17" : "-std=c11");
}

static void compiler_push_source_flags(StrVec *a, const C_StringList *flags, const char *source) {
    bool cpp = compiler_cpp_source(source);
    for (size_t i = 0; i < flags->count; ++i) {
        const char *flag = flags->items[i];
        if (cpp && compiler_c_standard_flag(flag)) continue;
        if (!cpp && compiler_cpp_standard_flag(flag)) continue;
        vec_push(a, flag);
    }
}

static int compiler_cpu_count(void) {
    long n = sysconf(_SC_NPROCESSORS_ONLN);
    if (n < 1) n = 1;
    if (n > 32) n = 32;
    return (int)n;
}

static int compiler_positive_int(const char *s, const char *what) {
    if (!s || !*s) die("%s requires a positive integer", what);
    char *end = NULL;
    errno = 0;
    long n = strtol(s, &end, 10);
    if (errno || !end || *end || n < 1 || n > 1024) die("invalid %s: %s", what, s);
    return (int)n;
}

static void compiler_perf_defaults(void) {
    compiler_perf.jobs = compiler_cpu_count();
    compiler_perf.unity = 0;
    compiler_perf.object_cache = true;

    const char *jobs = getenv("C_JOBS");
    if (jobs && *jobs) compiler_perf.jobs = compiler_positive_int(jobs, "C_JOBS");
    const char *unity = getenv("C_UNITY");
    if (unity && *unity && strcmp(unity, "0")) compiler_perf.unity = compiler_positive_int(unity, "C_UNITY");
    const char *cache = getenv("C_OBJECT_CACHE");
    if (cache && (!strcmp(cache, "0") || !strcmp(cache, "false") || !strcmp(cache, "off"))) compiler_perf.object_cache = false;
}

static char **compiler_filter_perf_options(int argc, char **argv, int *out_argc) {
    char **out = calloc((size_t)argc + 1, sizeof(*out));
    if (!out) die("out of memory");
    int n = 0;
    bool forwarded = false;
    for (int i = 0; i < argc; ++i) {
        const char *arg = argv[i];
        if (i < 2 || forwarded) {
            out[n++] = argv[i];
            continue;
        }
        if (!strcmp(arg, "--")) {
            forwarded = true;
            out[n++] = argv[i];
            continue;
        }
        if (!strcmp(arg, "-j") || !strcmp(arg, "--jobs")) {
            if (i + 1 >= argc) die("%s requires a value", arg);
            compiler_perf.jobs = compiler_positive_int(argv[++i], "jobs");
            continue;
        }
        if (!strncmp(arg, "-j", 2) && arg[2]) {
            compiler_perf.jobs = compiler_positive_int(arg + 2, "jobs");
            continue;
        }
        if (!strncmp(arg, "--jobs=", 7)) {
            compiler_perf.jobs = compiler_positive_int(arg + 7, "jobs");
            continue;
        }
        if (!strcmp(arg, "--unity")) {
            compiler_perf.unity = 8;
            continue;
        }
        if (!strncmp(arg, "--unity=", 8)) {
            compiler_perf.unity = compiler_positive_int(arg + 8, "unity chunk size");
            continue;
        }
        if (!strcmp(arg, "--no-unity")) {
            compiler_perf.unity = 0;
            continue;
        }
        if (!strcmp(arg, "--no-object-cache")) {
            compiler_perf.object_cache = false;
            continue;
        }
        if (!strcmp(arg, "--object-cache")) {
            compiler_perf.object_cache = true;
            continue;
        }
        out[n++] = argv[i];
    }
    out[n] = NULL;
    *out_argc = n;
    return out;
}

static void compiler_print_command(StrVec *args) {
    fprintf(stderr, "  $ ");
    for (size_t i = 0; i < args->count; ++i) fprintf(stderr, "%s%s", i ? " " : "", args->items[i]);
    fputc('\n', stderr);
}

static int compiler_spawn(StrVec *args, bool verbose, pid_t *pid) {
    if (!args->count) return 0;
    if (verbose) compiler_print_command(args);
    int rc = posix_spawnp(pid, args->items[0], NULL, NULL, args->items, environ);
    if (rc != 0) {
        errno = rc;
        return -1;
    }
    return 0;
}

static int compiler_wait(pid_t pid) {
    int status = 0;
    while (waitpid(pid, &status, 0) < 0) {
        if (errno == EINTR) continue;
        return 1;
    }
    if (WIFEXITED(status)) return WEXITSTATUS(status);
    if (WIFSIGNALED(status)) return 128 + WTERMSIG(status);
    return 1;
}

static int compiler_run_process(StrVec *args, bool verbose) {
    pid_t pid = -1;
    if (compiler_spawn(args, verbose, &pid) != 0) {
        fprintf(stderr, "c: error: cannot start %s: %s\n", args->count ? args->items[0] : "process", strerror(errno));
        return 127;
    }
    return compiler_wait(pid);
}

typedef struct CompilerStamp {
    time_t sec;
    long nsec;
    off_t size;
    bool exists;
} CompilerStamp;

static bool compiler_stamp_equal(CompilerStamp a, CompilerStamp b) {
    return a.exists == b.exists && (!a.exists || (a.sec == b.sec && a.nsec == b.nsec && a.size == b.size));
}

static int compiler_stamp_compare(CompilerStamp a, CompilerStamp b) {
    if (!a.exists || !b.exists) return a.exists ? 1 : b.exists ? -1 : 0;
    if (a.sec != b.sec) return a.sec > b.sec ? 1 : -1;
    if (a.nsec != b.nsec) return a.nsec > b.nsec ? 1 : -1;
    return 0;
}

static CompilerStamp compiler_stat_now(const char *path) {
    struct stat st;
    CompilerStamp out = {0};
    if (stat(path, &st) != 0) return out;
    out.exists = true;
    out.sec = st.st_mtime;
#ifdef __APPLE__
    out.nsec = st.st_mtimespec.tv_nsec;
#else
    out.nsec = st.st_mtim.tv_nsec;
#endif
    out.size = st.st_size;
    return out;
}

#define COMPILER_PATH_CACHE_SIZE 4096

typedef struct CompilerPathCacheEntry {
    uint64_t key;
    char *path;
    CompilerStamp stamp;
} CompilerPathCacheEntry;

static CompilerPathCacheEntry compiler_stat_cache[COMPILER_PATH_CACHE_SIZE];

static CompilerStamp compiler_cached_stamp(const char *path) {
    uint64_t key = hash_string(path);
    size_t slot = (size_t)(key % COMPILER_PATH_CACHE_SIZE);
    CompilerPathCacheEntry *e = &compiler_stat_cache[slot];
    if (e->path && e->key == key && !strcmp(e->path, path)) return e->stamp;
    free(e->path);
    e->path = xstrdup(path);
    e->key = key;
    e->stamp = compiler_stat_now(path);
    return e->stamp;
}

typedef struct CompilerHashCacheEntry {
    uint64_t key;
    char *path;
    CompilerStamp stamp;
    uint64_t hash;
    bool valid;
} CompilerHashCacheEntry;

static CompilerHashCacheEntry compiler_hash_cache[COMPILER_PATH_CACHE_SIZE];

static bool compiler_hash_file(const char *path, uint64_t *out) {
    CompilerStamp stamp = compiler_cached_stamp(path);
    if (!stamp.exists) return false;
    uint64_t key = hash_string(path);
    size_t slot = (size_t)(key % COMPILER_PATH_CACHE_SIZE);
    CompilerHashCacheEntry *e = &compiler_hash_cache[slot];
    if (e->valid && e->path && e->key == key && !strcmp(e->path, path) && compiler_stamp_equal(e->stamp, stamp)) {
        *out = e->hash;
        return true;
    }

    FILE *f = fopen(path, "rb");
    if (!f) return false;
    uint64_t h = 1469598103934665603ULL;
    unsigned char buf[32768];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f))) h = hash_update(h, buf, n);
    if (ferror(f)) { fclose(f); return false; }
    fclose(f);

    free(e->path);
    e->path = xstrdup(path);
    e->key = key;
    e->stamp = stamp;
    e->hash = h;
    e->valid = true;
    *out = h;
    return true;
}

static bool compiler_read_depfile(const char *path, StrVec *deps) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    if (fseek(f, 0, SEEK_END) != 0) { fclose(f); return false; }
    long end = ftell(f);
    if (end < 0) { fclose(f); return false; }
    rewind(f);
    char *buf = malloc((size_t)end + 1);
    if (!buf) { fclose(f); return false; }
    size_t got = fread(buf, 1, (size_t)end, f);
    fclose(f);
    if (got != (size_t)end) { free(buf); return false; }
    buf[end] = '\0';

    char *colon = strchr(buf, ':');
    if (!colon) { free(buf); return false; }
    char *p = colon + 1;
    while (*p) {
        while (*p == ' ' || *p == '\t' || *p == '\r' || *p == '\n' || (*p == '\\' && p[1] == '\n')) {
            if (*p == '\\' && p[1] == '\n') p += 2;
            else ++p;
        }
        if (!*p) break;
        char token[PATH_MAX];
        size_t len = 0;
        while (*p && *p != ' ' && *p != '\t' && *p != '\r' && *p != '\n') {
            if (*p == '\\' && p[1] == '\n') { p += 2; continue; }
            if (*p == '\\' && p[1]) ++p;
            if (len + 1 >= sizeof(token)) { free(buf); return false; }
            token[len++] = *p++;
        }
        token[len] = '\0';
        if (len) vec_push(deps, token);
    }
    free(buf);
    return deps->count != 0;
}

static bool compiler_depfile_fresh(const char *obj, const char *depfile, const char *src) {
    CompilerStamp object = compiler_stat_now(obj);
    if (!object.exists) return false;
    CompilerStamp source = compiler_cached_stamp(src);
    if (!source.exists || compiler_stamp_compare(source, object) > 0) return false;

    StrVec deps = {0};
    if (!compiler_read_depfile(depfile, &deps)) return false;
    bool fresh = true;
    for (size_t i = 0; i < deps.count; ++i) {
        CompilerStamp dep = compiler_cached_stamp(deps.items[i]);
        if (!dep.exists || compiler_stamp_compare(dep, object) > 0) { fresh = false; break; }
    }
    vec_free(&deps);
    return fresh;
}

static bool compiler_find_executable(const char *name, char out[PATH_MAX]) {
    if (!name || !*name) return false;
    if (strchr(name, '/')) {
        char resolved[PATH_MAX];
        if (realpath(name, resolved)) c__copy(out, PATH_MAX, resolved);
        else c__copy(out, PATH_MAX, name);
        return access(out, X_OK) == 0;
    }
    const char *path = getenv("PATH");
    if (!path) return false;
    char *copy = xstrdup(path);
    char *save = NULL;
    for (char *dir = strtok_r(copy, ":", &save); dir; dir = strtok_r(NULL, ":", &save)) {
        char candidate[PATH_MAX];
        path_join(candidate, *dir ? dir : ".", name);
        if (access(candidate, X_OK) == 0) {
            char resolved[PATH_MAX];
            if (realpath(candidate, resolved)) c__copy(out, PATH_MAX, resolved);
            else c__copy(out, PATH_MAX, candidate);
            free(copy);
            return true;
        }
    }
    free(copy);
    return false;
}

static uint64_t compiler_tool_identity(const char *tool) {
    char path[PATH_MAX];
    uint64_t h = hash_string(tool ? tool : "");
    if (!compiler_find_executable(tool, path)) return h;
    CompilerStamp st = compiler_stat_now(path);
    h = hash_update(h, path, strlen(path));
    h = hash_update(h, &st.sec, sizeof(st.sec));
    h = hash_update(h, &st.nsec, sizeof(st.nsec));
    h = hash_update(h, &st.size, sizeof(st.size));
    return h;
}

static uint64_t compiler_command_cache_hash(const StrVec *cmd, const char *source) {
    uint64_t h = 1469598103934665603ULL;
    uint64_t tool = compiler_tool_identity(cmd->count ? cmd->items[0] : "");
    h = hash_update(h, &tool, sizeof(tool));
    h = hash_update(h, source, strlen(source));
    uint64_t source_hash = 0;
    if (compiler_hash_file(source, &source_hash)) h = hash_update(h, &source_hash, sizeof(source_hash));

    for (size_t i = 1; i < cmd->count; ++i) {
        const char *arg = cmd->items[i];
        if (!strcmp(arg, "-o") || !strcmp(arg, "-MF")) { if (i + 1 < cmd->count) ++i; continue; }
        if (!strcmp(arg, "-c") || !strcmp(arg, source)) continue;
        h = hash_update(h, arg, strlen(arg));
        const char zero = '\0';
        h = hash_update(h, &zero, 1);
    }

    static const char *envs[] = {
        "CPATH", "C_INCLUDE_PATH", "CPLUS_INCLUDE_PATH", "OBJC_INCLUDE_PATH",
        "SDKROOT", "MACOSX_DEPLOYMENT_TARGET"
    };
    for (size_t i = 0; i < C_ARRAY_LEN(envs); ++i) {
        const char *v = getenv(envs[i]);
        if (v) h = hash_update(h, v, strlen(v));
    }
    return h;
}

static void compiler_object_cache_paths(const char key[17], char obj[PATH_MAX], char dep[PATH_MAX], char meta[PATH_MAX]) {
    char cache[PATH_MAX], root[PATH_MAX], shard[3], dir[PATH_MAX];
    cache_root(cache);
    path_join(root, cache, "objects");
    shard[0] = key[0]; shard[1] = key[1]; shard[2] = '\0';
    path_join(dir, root, shard);
    mkdir_p(dir);
    snprintf(obj, PATH_MAX, "%s/%s.o", dir, key);
    snprintf(dep, PATH_MAX, "%s/%s.d", dir, key);
    snprintf(meta, PATH_MAX, "%s/%s.meta", dir, key);
}

static bool compiler_copy_atomic(const char *from, const char *to) {
    char temp[PATH_MAX];
    if (snprintf(temp, sizeof(temp), "%s.tmp.%ld", to, (long)getpid()) >= (int)sizeof(temp)) return false;
    FILE *in = fopen(from, "rb");
    if (!in) return false;
    FILE *out = fopen(temp, "wb");
    if (!out) { fclose(in); return false; }
    unsigned char buf[32768];
    size_t n;
    bool ok = true;
    while ((n = fread(buf, 1, sizeof(buf), in))) {
        if (fwrite(buf, 1, n, out) != n) { ok = false; break; }
    }
    if (ferror(in)) ok = false;
    if (fclose(in) != 0) ok = false;
    if (fclose(out) != 0) ok = false;
    if (!ok || rename(temp, to) != 0) { unlink(temp); return false; }
    return true;
}

static bool compiler_object_cache_restore(const char key[17], const char *obj, const char *depf) {
    if (!compiler_perf.object_cache) return false;
    char cached_obj[PATH_MAX], cached_dep[PATH_MAX], meta[PATH_MAX];
    compiler_object_cache_paths(key, cached_obj, cached_dep, meta);
    if (!file_exists(cached_obj) || !file_exists(cached_dep) || !file_exists(meta)) return false;

    FILE *f = fopen(meta, "r");
    if (!f) return false;
    char line[PATH_MAX + 64];
    if (!fgets(line, sizeof(line), f) || strcmp(line, "c-object-cache-v1\n")) { fclose(f); return false; }
    bool valid = true;
    while (fgets(line, sizeof(line), f)) {
        char *tab = strchr(line, '\t');
        if (!tab) { valid = false; break; }
        *tab++ = '\0';
        char *nl = strpbrk(tab, "\r\n");
        if (nl) *nl = '\0';
        char *end = NULL;
        unsigned long long expected = strtoull(line, &end, 16);
        uint64_t actual = 0;
        if (!end || *end || !compiler_hash_file(tab, &actual) || actual != (uint64_t)expected) { valid = false; break; }
    }
    fclose(f);
    if (!valid) return false;
    return compiler_copy_atomic(cached_obj, obj) && compiler_copy_atomic(cached_dep, depf);
}

static void compiler_object_cache_store(const char key[17], const char *obj, const char *depf) {
    if (!compiler_perf.object_cache || !file_exists(obj) || !file_exists(depf)) return;
    StrVec deps = {0};
    if (!compiler_read_depfile(depf, &deps)) return;

    char cached_obj[PATH_MAX], cached_dep[PATH_MAX], meta[PATH_MAX];
    compiler_object_cache_paths(key, cached_obj, cached_dep, meta);
    char temp_meta[PATH_MAX];
    if (snprintf(temp_meta, sizeof(temp_meta), "%s.tmp.%ld", meta, (long)getpid()) >= (int)sizeof(temp_meta)) { vec_free(&deps); return; }
    FILE *f = fopen(temp_meta, "w");
    if (!f) { vec_free(&deps); return; }
    fputs("c-object-cache-v1\n", f);
    bool ok = true;
    for (size_t i = 0; i < deps.count; ++i) {
        uint64_t h = 0;
        if (!compiler_hash_file(deps.items[i], &h)) { ok = false; break; }
        if (fprintf(f, "%016llx\t%s\n", (unsigned long long)h, deps.items[i]) < 0) { ok = false; break; }
    }
    if (fclose(f) != 0) ok = false;
    if (!ok) { unlink(temp_meta); vec_free(&deps); return; }
    if (!compiler_copy_atomic(obj, cached_obj) || !compiler_copy_atomic(depf, cached_dep) || rename(temp_meta, meta) != 0) unlink(temp_meta);
    vec_free(&deps);
}

typedef struct CompilerTask {
    StrVec cmd;
    char *source;
    char *obj;
    char *depf;
    char key[17];
    pid_t pid;
    bool active;
} CompilerTask;

static void compiler_task_free(CompilerTask *t) {
    vec_free(&t->cmd);
    free(t->source);
    free(t->obj);
    free(t->depf);
    memset(t, 0, sizeof(*t));
}

typedef enum CompilerPrepareResult {
    COMPILER_PREP_FRESH = 0,
    COMPILER_PREP_CACHE = 1,
    COMPILER_PREP_BUILD = 2
} CompilerPrepareResult;

static CompilerPrepareResult compiler_prepare_task(CompilerTask *task, StrVec *cmd, const char *source, const char *obj, const char *depf) {
    if (compiler_depfile_fresh(obj, depf, source)) {
        vec_free(cmd);
        return COMPILER_PREP_FRESH;
    }

    uint64_t h = compiler_command_cache_hash(cmd, source);
    char key[17];
    hash_u64_hex(h, key);
    if (compiler_object_cache_restore(key, obj, depf)) {
        vec_free(cmd);
        return COMPILER_PREP_CACHE;
    }

    task->cmd = *cmd;
    memset(cmd, 0, sizeof(*cmd));
    task->source = xstrdup(source);
    task->obj = xstrdup(obj);
    task->depf = xstrdup(depf);
    c__copy(task->key, sizeof(task->key), key);
    return COMPILER_PREP_BUILD;
}

static void compiler_cancel_tasks(CompilerTask *tasks, size_t count) {
    for (size_t i = 0; i < count; ++i) if (tasks[i].active) kill(tasks[i].pid, SIGTERM);
    for (size_t i = 0; i < count; ++i) if (tasks[i].active) { compiler_wait(tasks[i].pid); tasks[i].active = false; }
}

static size_t compiler_execute_tasks(CompilerTask *tasks, size_t count, const Options *opt, const char *error_message) {
    if (!count) return 0;
    size_t next = 0, finished = 0, running = 0;
    size_t limit = (size_t)(compiler_perf.jobs < 1 ? 1 : compiler_perf.jobs);
    if (limit > count) limit = count;

    while (finished < count) {
        while (next < count && running < limit) {
            note("CC", "%s", tasks[next].source);
            if (compiler_spawn(&tasks[next].cmd, opt->verbose, &tasks[next].pid) != 0) {
                compiler_cancel_tasks(tasks, count);
                die("cannot start compiler for %s: %s", tasks[next].source, strerror(errno));
            }
            tasks[next].active = true;
            ++running;
            ++next;
        }

        int status = 0;
        pid_t done;
        do { done = waitpid(-1, &status, 0); } while (done < 0 && errno == EINTR);
        if (done < 0) {
            compiler_cancel_tasks(tasks, count);
            die("waitpid: %s", strerror(errno));
        }

        CompilerTask *task = NULL;
        for (size_t i = 0; i < count; ++i) if (tasks[i].active && tasks[i].pid == done) { task = &tasks[i]; break; }
        if (!task) continue;
        task->active = false;
        --running;
        ++finished;
        int rc = WIFEXITED(status) ? WEXITSTATUS(status) : WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1;
        if (rc != 0) {
            compiler_cancel_tasks(tasks, count);
            die("%s: %s", error_message, task->source);
        }
        compiler_object_cache_store(task->key, task->obj, task->depf);
    }
    return count;
}

static int compiler_language_kind(const char *path) {
    const char *ext = strrchr(path, '.');
    if (!ext) return 0;
    if (!strcmp(ext, ".mm")) return 3;
    if (!strcmp(ext, ".m")) return 2;
    if (!strcmp(ext, ".cpp") || !strcmp(ext, ".cc") || !strcmp(ext, ".cxx")) return 1;
    return 0;
}

static const char *compiler_unity_extension(int kind) {
    if (kind == 3) return ".mm";
    if (kind == 2) return ".m";
    if (kind == 1) return ".cpp";
    return ".c";
}

static void compiler_write_unity_file(const char *path, StrVec *sources, size_t *indices, size_t count, const char *root_prefix) {
    if (file_exists(path)) return;
    FILE *f = fopen(path, "w");
    if (!f) die("cannot write unity source %s", path);
    fputs("/* generated by c --unity */\n", f);
    for (size_t i = 0; i < count; ++i) {
        const char *src = sources->items[indices[i]];
        fputs("#include \"", f);
        if (src[0] != '/' && root_prefix) fputs(root_prefix, f);
        for (const char *p = src; *p; ++p) {
            if (*p == '\\' || *p == '"') fputc('\\', f);
            fputc(*p, f);
        }
        fputs("\"\n", f);
    }
    if (fclose(f) != 0) die("cannot finish unity source %s", path);
}

static void compiler_make_unity_sources(StrVec *sources, const char *unity_dir, const char *root_prefix, StrVec *out) {
    if (compiler_perf.unity <= 1 || sources->count <= 1) {
        for (size_t i = 0; i < sources->count; ++i) vec_push(out, sources->items[i]);
        return;
    }
    mkdir_p(unity_dir);
    size_t chunk_size = (size_t)compiler_perf.unity;
    for (int kind = 0; kind < 4; ++kind) {
        size_t *indices = calloc(sources->count, sizeof(*indices));
        if (!indices) die("out of memory");
        size_t n = 0;
        for (size_t i = 0; i < sources->count; ++i) if (compiler_language_kind(sources->items[i]) == kind) indices[n++] = i;
        for (size_t start = 0, chunk = 0; start < n; start += chunk_size, ++chunk) {
            size_t count = n - start;
            if (count > chunk_size) count = chunk_size;
            if (count == 1) {
                vec_push(out, sources->items[indices[start]]);
                continue;
            }
            char name[64], path[PATH_MAX];
            snprintf(name, sizeof(name), "unity-%d-%zu%s", kind, chunk, compiler_unity_extension(kind));
            path_join(path, unity_dir, name);
            compiler_write_unity_file(path, sources, indices + start, count, root_prefix);
            vec_push(out, path);
        }
        free(indices);
    }
}

static void compiler_dep_root(const C_Dependency *d, const DepState *state, char out[PATH_MAX]) {
    if (d->subdir[0]) path_join(out, state->source, d->subdir);
    else c__copy(out, PATH_MAX, state->source);
}

static void compiler_dep_library(const C_Dependency *d, const DepState *state, char out[PATH_MAX]) {
    char name[C_MAX_NAME + 8];
    snprintf(name, sizeof(name), "lib%s.a", d->name);
    path_join(out, state->package, name);
}

static void compiler_build_dependency(const C_Dependency *d, const Options *opt, DepState *state) {
    if (d->kind != C_DEP_SOURCE) return;
    if (!d->source_patterns.count) die("source dependency %s has no sources; use c_dep_sources()", d->name);

    char library[PATH_MAX];
    compiler_dep_library(d, state, library);
    if (file_exists(library)) {
        note("CACHED", "%s", d->name);
        return;
    }

    mkdir_p(state->package);
    char objdir[PATH_MAX];
    path_join(objdir, state->package, ".objs");
    mkdir_p(objdir);
    char root[PATH_MAX];
    compiler_dep_root(d, state, root);

    StrVec sources = {0}, compile_sources = {0}, objects = {0};
    for (size_t i = 0; i < d->source_patterns.count; ++i) {
        char pattern[PATH_MAX];
        path_join(pattern, root, d->source_patterns.items[i]);
        expand_pattern(pattern, &sources);
    }
    char unity_dir[PATH_MAX];
    path_join(unity_dir, state->package, ".unity");
    compiler_make_unity_sources(&sources, unity_dir, "", &compile_sources);

    CompilerTask *tasks = calloc(compile_sources.count, sizeof(*tasks));
    if (!tasks) die("out of memory");
    size_t task_count = 0, cache_hits = 0;
    note("DEP", "%s", d->name);

    for (size_t i = 0; i < compile_sources.count; ++i) {
        const char *source = compile_sources.items[i];
        char obj[PATH_MAX], depf[PATH_MAX];
        object_path(objdir, source, obj);
        if (strlen(obj) + 3 >= sizeof(depf)) die("object path too long: %s", obj);
        c__copy(depf, sizeof(depf), obj); strcat(depf, ".d");
        vec_push(&objects, obj);

        StrVec a = {0};
        vec_push(&a, opt->cc);
        compiler_push_standard(&a, source);
        vec_push(&a, opt->release ? "-O2" : "-O0");
        if (!opt->release) vec_push(&a, "-g");
        vec_push(&a, "-MMD"); vec_push(&a, "-MF"); vec_push(&a, depf);
        char root_inc[PATH_MAX + 3]; snprintf(root_inc, sizeof(root_inc), "-I%s", root); vec_push(&a, root_inc);
        for (size_t j = 0; j < d->include_dirs.count; ++j) {
            char inc[PATH_MAX], arg[PATH_MAX + 3];
            path_join(inc, root, d->include_dirs.items[j]);
            snprintf(arg, sizeof(arg), "-I%s", inc); vec_push(&a, arg);
        }
        compiler_push_source_flags(&a, &d->compile_flags, source);
        vec_push(&a, "-c"); vec_push(&a, source); vec_push(&a, "-o"); vec_push(&a, obj);

        CompilerPrepareResult prep = compiler_prepare_task(&tasks[task_count], &a, source, obj, depf);
        if (prep == COMPILER_PREP_BUILD) ++task_count;
        else if (prep == COMPILER_PREP_CACHE) ++cache_hits;
    }
    if (cache_hits) note("CACHED", "%zu object%s", cache_hits, cache_hits == 1 ? "" : "s");
    compiler_execute_tasks(tasks, task_count, opt, "dependency compile failed");
    for (size_t i = 0; i < task_count; ++i) compiler_task_free(&tasks[i]);
    free(tasks);

    StrVec ar = {0};
    vec_push(&ar, compiler_ar()); vec_push(&ar, "rcs"); vec_push(&ar, library);
    for (size_t i = 0; i < objects.count; ++i) vec_push(&ar, objects.items[i]);
    note("AR", "%s", library);
    if (compiler_run_process(&ar, opt->verbose) != 0) die("dependency archive failed: %s", d->name);
    vec_free(&ar); vec_free(&sources); vec_free(&compile_sources); vec_free(&objects);
}

static void compiler_prepare_target_links(C_Build *b, DepState states[]) {
    for (size_t ti = 0; ti < b->target_count; ++ti) {
        C_Target *t = &b->targets[ti];
        C_StringList ordered = {0};
        for (size_t i = 0; i < t->dep_count; ++i) {
            C_Dependency *d = t->deps[i];
            if (d->kind != C_DEP_SOURCE) continue;
            ptrdiff_t idx = d - b->deps;
            if (idx < 0 || (size_t)idx >= b->dep_count) die("target %s has invalid dependency", t->name);
            char library[PATH_MAX]; compiler_dep_library(d, &states[idx], library); c__push(&ordered, library);
        }
        for (size_t i = 0; i < t->system_links.count; ++i) {
            char arg[C_MAX_NAME + 3]; snprintf(arg, sizeof(arg), "-l%s", t->system_links.items[i]); c__push(&ordered, arg);
        }
#ifdef __APPLE__
        for (size_t i = 0; i < t->frameworks.count; ++i) { c__push(&ordered, "-framework"); c__push(&ordered, t->frameworks.items[i]); }
#endif
        for (size_t i = 0; i < t->ldflags.count; ++i) c__push(&ordered, t->ldflags.items[i]);
        free_c_list(&t->system_links); free_c_list(&t->frameworks); free_c_list(&t->ldflags); t->ldflags = ordered;
    }
    for (size_t i = 0; i < b->dep_count; ++i) if (b->deps[i].kind == C_DEP_SOURCE) b->deps[i].kind = C_DEP_HEADER_ONLY;
}

static void compiler_resolve_all(C_Build *b, const Options *opt, DepState states[]) {
    LockFile lock; load_lock(&lock);
    for (size_t i = 0; i < b->dep_count; ++i) {
        C_Dependency *d = &b->deps[i];
        if (d->kind == C_DEP_RESERVED) die("external build-system dependencies are not supported; use c_dep_source()");
        resolve_dependency(d, opt, &lock, &states[i], false);
        compiler_build_dependency(d, opt, &states[i]);
    }
    save_lock(&lock);
    compiler_prepare_target_links(b, states);
}

static void compiler_append_target_compile_flags(StrVec *a, const C_Target *t, C_Build *b, DepState states[], const char *source) {
    for (size_t i = 0; i < t->includes.count; ++i) { char x[PATH_MAX + 3]; snprintf(x, sizeof(x), "-I%s", t->includes.items[i]); vec_push(a, x); }
    for (size_t i = 0; i < t->defines.count; ++i) { char x[PATH_MAX + 3]; snprintf(x, sizeof(x), "-D%s", t->defines.items[i]); vec_push(a, x); }
    compiler_push_source_flags(a, &t->cflags, source);
    for (size_t i = 0; i < t->dep_count; ++i) {
        C_Dependency *d = t->deps[i];
        ptrdiff_t dep_index = d - b->deps;
        if (dep_index < 0 || (size_t)dep_index >= b->dep_count) die("target %s has invalid dependency", t->name);
        DepState *s = &states[dep_index];
        char root[PATH_MAX];
        if (d->subdir[0]) path_join(root, s->source, d->subdir); else c__copy(root, sizeof(root), s->source);
        if (d->include_dirs.count == 0) { char x[PATH_MAX + 3]; snprintf(x, sizeof(x), "-I%s", root); vec_push(a, x); }
        else for (size_t j = 0; j < d->include_dirs.count; ++j) {
            char inc[PATH_MAX], x[PATH_MAX + 3]; path_join(inc, root, d->include_dirs.items[j]); snprintf(x, sizeof(x), "-I%s", inc); vec_push(a, x);
        }
    }
}

static char *compiler_build_target(C_Build *b, C_Target *t, DepState states[], const Options *opt) {
    StrVec sources = {0}, compile_sources = {0}, objects = {0};
    expand_sources(t, b, states, &sources);
    if (sources.count == 0) die("target %s has no sources", t->name);
    uint64_t sig = target_signature(t, b, states, opt, &sources);
    uint64_t tool = compiler_tool_identity(opt->cc);
    sig = hash_update(sig, &tool, sizeof(tool));
    sig = hash_update(sig, &compiler_perf.unity, sizeof(compiler_perf.unity));
    char sighex[17]; hash_u64_hex(sig, sighex);
    char objdir[PATH_MAX]; path_join(objdir, "build/.objs", sighex); mkdir_p(objdir);
    char unity_root[PATH_MAX], unity_dir[PATH_MAX];
    path_join(unity_root, "build", ".unity"); path_join(unity_dir, unity_root, sighex);
    compiler_make_unity_sources(&sources, unity_dir, "../../../", &compile_sources);

    char cwd[PATH_MAX]; if (!getcwd(cwd, sizeof(cwd))) die("getcwd failed");
    FILE *db = fopen("compile_commands.json", "w"); bool first = true; if (db) fprintf(db, "[\n");
    CompilerTask *tasks = calloc(compile_sources.count, sizeof(*tasks));
    if (!tasks) die("out of memory");
    size_t task_count = 0, cache_hits = 0;

    for (size_t i = 0; i < compile_sources.count; ++i) {
        const char *source = compile_sources.items[i];
        char obj[PATH_MAX], depf[PATH_MAX];
        object_path(objdir, source, obj);
        if (strlen(obj) + 3 >= sizeof(depf)) die("object path too long: %s", obj);
        c__copy(depf, sizeof(depf), obj); strcat(depf, ".d"); vec_push(&objects, obj);

        StrVec a = {0};
        vec_push(&a, opt->cc); compiler_push_standard(&a, source);
        vec_push(&a, opt->release ? "-O2" : "-O0"); if (!opt->release) vec_push(&a, "-g");
        vec_push(&a, "-MMD"); vec_push(&a, "-MF"); vec_push(&a, depf);
        compiler_append_target_compile_flags(&a, t, b, states, source);
        vec_push(&a, "-c"); vec_push(&a, source); vec_push(&a, "-o"); vec_push(&a, obj);
        if (db) write_compile_command(db, &first, &a, source, cwd);

        CompilerPrepareResult prep = compiler_prepare_task(&tasks[task_count], &a, source, obj, depf);
        if (prep == COMPILER_PREP_BUILD) ++task_count;
        else if (prep == COMPILER_PREP_CACHE) ++cache_hits;
    }
    if (db) { fprintf(db, "\n]\n"); fclose(db); }
    if (cache_hits) note("CACHED", "%zu object%s", cache_hits, cache_hits == 1 ? "" : "s");
    size_t compiled = compiler_execute_tasks(tasks, task_count, opt, "compile failed");
    for (size_t i = 0; i < task_count; ++i) compiler_task_free(&tasks[i]);
    free(tasks);

    char profile_dir[PATH_MAX]; path_join(profile_dir, "build", opt->release ? "release" : "debug"); mkdir_p(profile_dir);
    char *output = malloc(PATH_MAX); if (!output) die("out of memory");
    char outname[C_MAX_NAME + 4]; snprintf(outname, sizeof(outname), "%s%s", t->name, t->kind == C_TARGET_STATIC_LIBRARY ? ".a" : "");
    path_join(output, profile_dir, outname);
    bool relink = !file_exists(output); time_t outt = mtime_of(output);
    for (size_t i = 0; i < objects.count; ++i) if (mtime_of(objects.items[i]) > outt) relink = true;

    if (relink || compiled || cache_hits) {
        if (t->kind == C_TARGET_STATIC_LIBRARY) {
            StrVec a = {0}; vec_push(&a, compiler_ar()); vec_push(&a, "rcs"); vec_push(&a, output);
            for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            note("AR", "%s", output); if (compiler_run_process(&a, opt->verbose) != 0) die("archive failed"); vec_free(&a);
        } else {
            StrVec a = {0}; vec_push(&a, opt->cc); for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states); vec_push(&a, "-o"); vec_push(&a, output);
            note("LINK", "%s", output); if (compiler_run_process(&a, opt->verbose) != 0) die("link failed"); vec_free(&a);
        }
    } else note("CACHED", "%s", t->name);

    vec_free(&sources); vec_free(&compile_sources); vec_free(&objects); return output;
}

static void compiler_cmd_build_or_run(const Options *opt, bool run) {
    C_Build *b = alloc_build(); load_build(opt, b);
    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);
    C_Target *t = select_target(b, opt); char *output = compiler_build_target(b, t, states, opt);
    if (run) {
        if (t->kind != C_TARGET_EXECUTABLE && t->kind != C_TARGET_TEST) die("target %s is not executable", t->name);
        note("RUN", "%s", output);
        StrVec a = {0}; char exec[PATH_MAX];
        if (output[0] == '/') snprintf(exec, sizeof(exec), "%s", output); else snprintf(exec, sizeof(exec), "./%s", output);
        vec_push(&a, exec); for (int i = 0; i < opt->run_argc; ++i) vec_push(&a, opt->run_argv[i]);
        int rc = compiler_run_process(&a, opt->verbose); vec_free(&a); free(output); free_build(b); exit(rc);
    }
    free(output); free_build(b);
}

static void compiler_cmd_test(const Options *opt) {
    C_Build *b = alloc_build(); load_build(opt, b);
    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states); size_t tests = 0;
    for (size_t i = 0; i < b->target_count; ++i) {
        C_Target *t = &b->targets[i];
        if (t->kind != C_TARGET_TEST || (opt->target_name && strcmp(t->name, opt->target_name))) continue;
        ++tests; char *output = compiler_build_target(b, t, states, opt); note("TEST", "%s", t->name);
        StrVec a = {0}; char exec[PATH_MAX]; snprintf(exec, sizeof(exec), "./%s", output); vec_push(&a, exec);
        int rc = compiler_run_process(&a, opt->verbose); vec_free(&a); free(output); if (rc != 0) die("test failed: %s", t->name);
    }
    if (!tests) die("no test targets defined; use c_test() in build.c");
    note("PASS", "%zu test target%s", tests, tests == 1 ? "" : "s"); free_build(b);
}

static void compiler_cmd_doctor(const Options *opt) {
    struct utsname u; uname(&u);
    printf("c %s\n\n", C_VERSION);
    printf("Platform   %s %s\n", u.sysname, u.machine);
    printf("Compiler   %s%s\n", opt->cc, command_exists(opt->cc) ? "" : "  [missing]");
    printf("Archiver   %s%s\n", compiler_ar(), command_exists(compiler_ar()) ? "" : "  [missing]");
    printf("Git        %s\n", command_exists("git") ? "ok" : "missing");
    printf("Jobs       %d\n", compiler_perf.jobs);
    printf("Obj cache  %s\n", compiler_perf.object_cache ? "on" : "off");
    printf("Unity      %s", compiler_perf.unity > 1 ? "on" : "off");
    if (compiler_perf.unity > 1) printf(" (chunk %d)", compiler_perf.unity);
    putchar('\n');
    char cache[PATH_MAX]; cache_root(cache); printf("Cache      %s\n", cache);
}

static int compiler_dispatch(int argc, char **argv) {
    compiler_perf_defaults();
    int filtered_argc = 0;
    char **filtered_argv = compiler_filter_perf_options(argc, argv, &filtered_argc);
    Options opt = parse_options(filtered_argc, filtered_argv);
    int rc = 0;
    if (!strcmp(opt.command, "build")) compiler_cmd_build_or_run(&opt, false);
    else if (!strcmp(opt.command, "run")) compiler_cmd_build_or_run(&opt, true);
    else if (!strcmp(opt.command, "test")) compiler_cmd_test(&opt);
    else if (!strcmp(opt.command, "doctor")) compiler_cmd_doctor(&opt);
    else rc = c_legacy_main(filtered_argc, filtered_argv);
    free(filtered_argv);
    return rc;
}

static bool cli_is_command(const char *s) {
    static const char *commands[] = {
        "init", "build", "run", "fetch", "update", "deps", "test",
        "clean", "cache", "doctor", "help", "--help", "-h",
        "version", "--version"
    };
    for (size_t i = 0; i < C_ARRAY_LEN(commands); ++i) if (!strcmp(s, commands[i])) return true;
    return false;
}

static bool cli_is_version_or_help(const char *s) {
    return !strcmp(s, "help") || !strcmp(s, "--help") || !strcmp(s, "-h") || !strcmp(s, "version") || !strcmp(s, "--version");
}

static bool cli_is_action(const char *s) {
    return !strcmp(s, "init") || !strcmp(s, "build") || !strcmp(s, "run") || !strcmp(s, "fetch") || !strcmp(s, "update") || !strcmp(s, "test") || !strcmp(s, "clean") || !strcmp(s, "cache");
}

static bool cli_jobs_option(const char *arg) {
    return !strcmp(arg, "-j") || !strcmp(arg, "--jobs");
}

static bool cli_perf_option(const char *arg) {
    return (!strncmp(arg, "-j", 2) && arg[2]) || !strncmp(arg, "--jobs=", 7) ||
           !strcmp(arg, "--unity") || !strncmp(arg, "--unity=", 8) || !strcmp(arg, "--no-unity") ||
           !strcmp(arg, "--object-cache") || !strcmp(arg, "--no-object-cache");
}

static bool cli_has_flag(int argc, char **argv, const char *a, const char *b) {
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--")) break;
        if (!strcmp(argv[i], a) || (b && !strcmp(argv[i], b))) return true;
        if ((!strcmp(argv[i], "--cc") || cli_jobs_option(argv[i])) && i + 1 < argc) ++i;
    }
    return false;
}

static const char *cli_target(int argc, char **argv) {
    for (int i = 2; i < argc; ++i) {
        const char *arg = argv[i];
        if (!strcmp(arg, "--")) break;
        if (!strcmp(arg, "--release") || !strcmp(arg, "-Drelease") || !strcmp(arg, "-v") || !strcmp(arg, "--verbose") || cli_perf_option(arg)) continue;
        if ((!strcmp(arg, "--cc") || cli_jobs_option(arg)) && i + 1 < argc) { ++i; continue; }
        if (arg[0] != '-') return arg;
    }
    return NULL;
}

static bool cli_color(void) {
    const char *term = getenv("TERM");
    return isatty(STDERR_FILENO) && !getenv("NO_COLOR") && (!term || strcmp(term, "dumb"));
}

static const char *cli_style(bool color, const char *code) { return color ? code : ""; }

static double cli_now_ms(void) {
    struct timespec ts = {0};
    if (clock_gettime(CLOCK_MONOTONIC, &ts) != 0) return 0.0;
    return (double)ts.tv_sec * 1000.0 + (double)ts.tv_nsec / 1000000.0;
}

static const char *cli_step_name(const char *kind) {
    if (!strcmp(kind, "CONFIG")) return "configure";
    if (!strcmp(kind, "FETCH")) return "fetch";
    if (!strcmp(kind, "UPDATE")) return "update";
    if (!strcmp(kind, "DEP")) return "dependency";
    if (!strcmp(kind, "CC")) return "compile";
    if (!strcmp(kind, "AR")) return "archive";
    if (!strcmp(kind, "LINK")) return "link";
    if (!strcmp(kind, "CACHED")) return "cached";
    if (!strcmp(kind, "RUN")) return "run";
    if (!strcmp(kind, "DONE")) return "done";
    if (!strcmp(kind, "TEST")) return "test";
    if (!strcmp(kind, "PASS")) return "pass";
    if (!strcmp(kind, "CLEAN")) return "clean";
    if (!strcmp(kind, "INIT")) return "init";
    return NULL;
}

static bool cli_parse_note(const char *line, char kind[8], const char **message) {
    size_t n = strlen(line);
    if (n < 10 || line[0] != ' ' || line[1] != ' ' || line[9] != ' ') return false;
    memcpy(kind, line + 2, 7); kind[7] = '\0';
    for (int i = 6; i >= 0 && kind[i] == ' '; --i) kind[i] = '\0';
    if (!cli_step_name(kind)) return false;
    *message = line + 10; return true;
}

static void cli_heading(const char *command, int argc, char **argv) {
    if (!cli_is_action(command)) return;
    bool color = cli_color(); const char *bold = cli_style(color, "\x1b[1m"); const char *dim = cli_style(color, "\x1b[2m"); const char *reset = cli_style(color, "\x1b[0m");
    const char *target = cli_target(argc, argv);
    fprintf(stderr, "%s%s%s", bold, command, reset);
    if (target && strcmp(command, "cache")) fprintf(stderr, " %s", target);
    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "test")) fprintf(stderr, " %s[%s]%s", dim, cli_has_flag(argc, argv, "--release", "-Drelease") ? "release" : "debug", reset);
    fputc('\n', stderr);
}

static void cli_step(const char *kind, const char *message) {
    bool color = cli_color(); const char *dim = cli_style(color, "\x1b[2m"); const char *cyan = cli_style(color, "\x1b[36m"); const char *green = cli_style(color, "\x1b[32m"); const char *reset = cli_style(color, "\x1b[0m");
    const char *name = cli_step_name(kind); const char *style = (!strcmp(kind, "CACHED")) ? dim : (!strcmp(kind, "PASS") || !strcmp(kind, "DONE")) ? green : cyan;
    fprintf(stderr, "%s  ├─%s %s%-10s%s %s", dim, reset, style, name, reset, message);
    size_t n = strlen(message); if (!n || message[n - 1] != '\n') fputc('\n', stderr);
}

static void cli_finish(int rc, double elapsed_ms) {
    bool color = cli_color(); const char *dim = cli_style(color, "\x1b[2m"); const char *green = cli_style(color, "\x1b[32m"); const char *red = cli_style(color, "\x1b[31m"); const char *reset = cli_style(color, "\x1b[0m");
    if (rc == 0) fprintf(stderr, "%s  └─%s %ssuccess%s %s%.0f ms%s\n", dim, reset, green, reset, dim, elapsed_ms, reset);
    else fprintf(stderr, "%s  └─%s %sfailed%s %s(exit %d, %.0f ms)%s\n", dim, reset, red, reset, dim, rc, elapsed_ms, reset);
}

static bool cli_quiet_stdout(const char *command, const char *target) {
    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "fetch") || !strcmp(command, "update") || !strcmp(command, "test") || !strcmp(command, "clean") || !strcmp(command, "init")) return true;
    return !strcmp(command, "cache") && target && !strcmp(target, "clean");
}

static int cli_run_segment(int argc, char **argv) {
    const char *command = argc > 1 ? argv[1] : "help"; const char *target = cli_target(argc, argv);
    bool action = cli_is_action(command); bool verbose = cli_has_flag(argc, argv, "-v", "--verbose"); bool quiet = cli_quiet_stdout(command, target); bool show_program_output = false;
    double started = cli_now_ms(); if (action) cli_heading(command, argc, argv);

    int fds[2]; if (pipe(fds) != 0) { perror("pipe"); return 1; }
    pid_t pid = fork(); if (pid < 0) { perror("fork"); close(fds[0]); close(fds[1]); return 1; }
    if (pid == 0) {
        close(fds[0]); if (dup2(fds[1], STDOUT_FILENO) < 0) _exit(127); close(fds[1]); setvbuf(stdout, NULL, _IONBF, 0);
        int rc = compiler_dispatch(argc, argv); fflush(NULL); _exit(rc);
    }

    close(fds[1]); FILE *stream = fdopen(fds[0], "r"); if (!stream) { close(fds[0]); waitpid(pid, NULL, 0); return 1; }
    char *line = NULL; size_t cap = 0;
    while (getline(&line, &cap, stream) >= 0) {
        char kind[8]; const char *message = NULL;
        if (cli_parse_note(line, kind, &message)) { if (action) cli_step(kind, message); else fputs(line, stdout); if (!strcmp(kind, "RUN") || !strcmp(kind, "TEST")) show_program_output = true; continue; }
        if (!quiet || verbose || show_program_output) { fputs(line, stdout); fflush(stdout); }
    }
    free(line); fclose(stream);
    int status = 0; while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    int rc = WIFEXITED(status) ? WEXITSTATUS(status) : WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1;
    if (action) cli_finish(rc, cli_now_ms() - started);

    if (rc == 0 && cli_is_version_or_help(command) && (!strcmp(command, "help") || !strcmp(command, "--help") || !strcmp(command, "-h"))) {
        fputs("\nchaining:\n  c clean build run\n  c fetch build test\n\nperformance:\n  -j N / -jN / --jobs=N    parallel compiler jobs (default: CPU count)\n  --unity[=N]              optional unity chunks (default chunk: 8)\n  --no-object-cache        disable the persistent global object cache\n\nenvironment:\n  C_JOBS=N                 default parallel job count\n  C_UNITY=N                default unity chunk size\n  C_OBJECT_CACHE=0         disable global object caching\n\nCommands run left-to-right and stop on the first failure.\nArguments after `--` belong to `c run` and end the command chain.\n", stdout);
    }
    return rc;
}

static bool cli_cache_clean_argument(int start, int i, char **argv) {
    return i == start + 1 && !strcmp(argv[start], "cache") && !strcmp(argv[i], "clean");
}

int main(int argc, char **argv) {
    if (argc < 2) return cli_run_segment(argc, argv);
    int start = 1; bool first_action = true;
    while (start < argc) {
        int end = argc; bool forwarded_args = false;
        for (int i = start + 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--")) { forwarded_args = true; break; }
            if (cli_is_command(argv[i]) && !cli_cache_clean_argument(start, i, argv)) { end = i; break; }
        }
        if (forwarded_args) end = argc;
        int seg_argc = 1 + (end - start); char **seg_argv = calloc((size_t)seg_argc + 1, sizeof(*seg_argv));
        if (!seg_argv) { fputs("c: error: out of memory\n", stderr); return 1; }
        seg_argv[0] = argv[0]; for (int i = start; i < end; ++i) seg_argv[1 + i - start] = argv[i];
        bool segment_action = seg_argc > 1 && cli_is_action(seg_argv[1]);
        if (segment_action && !first_action) fputc('\n', stderr); if (segment_action) first_action = false;
        int rc = cli_run_segment(seg_argc, seg_argv); free(seg_argv); if (rc != 0) return rc;
        if (end >= argc) break; start = end;
    }
    return 0;
}
