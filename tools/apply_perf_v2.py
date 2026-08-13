#!/usr/bin/env python3
from pathlib import Path


def replace_once(text, old, new, label):
    if old not in text:
        raise SystemExit(f"missing patch anchor: {label}")
    if text.count(old) != 1:
        raise SystemExit(f"non-unique patch anchor: {label} ({text.count(old)})")
    return text.replace(old, new, 1)


def replace_section(text, start, end, replacement, label):
    a = text.find(start)
    if a < 0:
        raise SystemExit(f"missing section start: {label}")
    b = text.find(end, a)
    if b < 0:
        raise SystemExit(f"missing section end: {label}")
    return text[:a] + replacement.rstrip() + "\n\n" + text[b:]


p = Path("src/cli.c")
s = p.read_text()

s = replace_once(s, '''typedef struct CompilerPerfOptions {
    int jobs;
    int unity;
    bool object_cache;
} CompilerPerfOptions;

static CompilerPerfOptions compiler_perf = {0, 0, true};
''', '''typedef struct CompilerPerfOptions {
    int jobs;
    int unity;              /* 0=off, -1=auto, >=2=fixed chunk size */
    bool object_cache;
    bool profile;
    bool fast_debug;
    bool adaptive_jobs;
    bool jobs_explicit;
    char linker[32];
} CompilerPerfOptions;

static CompilerPerfOptions compiler_perf = {0};

#include "perf_v2.h"
''', "performance options")

s = replace_section(s,
'''static int compiler_cpu_count(void) {''',
'''static int compiler_positive_int(''',
'''static int compiler_cpu_count(void) {
    return compiler_perf_cpu_count();
}''',
"cpu count")

s = replace_section(s,
'''static void compiler_perf_defaults(void) {''',
'''static char **compiler_filter_perf_options(''',
'''static void compiler_perf_defaults(void) {
    compiler_perf.jobs = compiler_default_jobs();
    compiler_perf.unity = 0;
    compiler_perf.object_cache = true;
    compiler_perf.profile = false;
    compiler_perf.fast_debug = false;
    compiler_perf.adaptive_jobs = false;
    compiler_perf.jobs_explicit = false;
    compiler_perf.linker[0] = '\0';

    const char *jobs = getenv("C_JOBS");
    if (jobs && *jobs) {
        compiler_perf.jobs = compiler_positive_int(jobs, "C_JOBS");
        compiler_perf.jobs_explicit = true;
    }
    const char *unity = getenv("C_UNITY");
    if (unity && *unity && strcmp(unity, "0")) {
        compiler_perf.unity = !strcmp(unity, "auto") ? -1 : compiler_positive_int(unity, "C_UNITY");
    }
    const char *cache = getenv("C_OBJECT_CACHE");
    if (cache && (!strcmp(cache, "0") || !strcmp(cache, "false") || !strcmp(cache, "off"))) compiler_perf.object_cache = false;
    const char *profile = getenv("C_PROFILE");
    if (profile && strcmp(profile, "0") && strcmp(profile, "false") && strcmp(profile, "off")) compiler_perf.profile = true;
    const char *fast_debug = getenv("C_FAST_DEBUG");
    if (fast_debug && strcmp(fast_debug, "0") && strcmp(fast_debug, "false") && strcmp(fast_debug, "off")) compiler_perf.fast_debug = true;
    const char *adaptive = getenv("C_ADAPTIVE_JOBS");
    if (adaptive && strcmp(adaptive, "0") && strcmp(adaptive, "false") && strcmp(adaptive, "off")) compiler_perf.adaptive_jobs = true;
    const char *linker = getenv("C_LINKER");
    if (linker && *linker) c__copy(compiler_perf.linker, sizeof(compiler_perf.linker), linker);
}''',
"performance defaults")

s = replace_section(s,
'''static char **compiler_filter_perf_options(''',
'''static void compiler_print_command(''',
'''static char **compiler_filter_perf_options(int argc, char **argv, int *out_argc) {
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
            compiler_perf.jobs_explicit = true;
            continue;
        }
        if (!strncmp(arg, "-j", 2) && arg[2]) {
            compiler_perf.jobs = compiler_positive_int(arg + 2, "jobs");
            compiler_perf.jobs_explicit = true;
            continue;
        }
        if (!strncmp(arg, "--jobs=", 7)) {
            compiler_perf.jobs = compiler_positive_int(arg + 7, "jobs");
            compiler_perf.jobs_explicit = true;
            continue;
        }
        if (!strcmp(arg, "--unity")) {
            compiler_perf.unity = 8;
            continue;
        }
        if (!strncmp(arg, "--unity=", 8)) {
            const char *value = arg + 8;
            compiler_perf.unity = !strcmp(value, "auto") ? -1 : compiler_positive_int(value, "unity chunk size");
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
        if (!strcmp(arg, "--profile")) {
            compiler_perf.profile = true;
            continue;
        }
        if (!strcmp(arg, "--fast-debug")) {
            compiler_perf.fast_debug = true;
            continue;
        }
        if (!strcmp(arg, "--adaptive-jobs")) {
            compiler_perf.adaptive_jobs = true;
            continue;
        }
        if (!strcmp(arg, "--no-adaptive-jobs")) {
            compiler_perf.adaptive_jobs = false;
            continue;
        }
        if (!strcmp(arg, "--linker")) {
            if (i + 1 >= argc) die("--linker requires a value");
            c__copy(compiler_perf.linker, sizeof(compiler_perf.linker), argv[++i]);
            continue;
        }
        if (!strncmp(arg, "--linker=", 9)) {
            c__copy(compiler_perf.linker, sizeof(compiler_perf.linker), arg + 9);
            continue;
        }
        out[n++] = argv[i];
    }
    out[n] = NULL;
    *out_argc = n;
    return out;
}''',
"performance option filter")

old = '''    if (e->valid && e->path && e->key == key && !strcmp(e->path, path) && compiler_stamp_equal(e->stamp, stamp)) {
        *out = e->hash;
        return true;
    }

    FILE *f = fopen(path, "rb");
'''
new = '''    if (e->valid && e->path && e->key == key && !strcmp(e->path, path) && compiler_stamp_equal(e->stamp, stamp)) {
        *out = e->hash;
        return true;
    }
    uint64_t persistent = 0;
    if (compiler_persistent_hash_lookup(path, stamp.sec, stamp.nsec, stamp.size, &persistent)) {
        free(e->path);
        e->path = xstrdup(path);
        e->key = key;
        e->stamp = stamp;
        e->hash = persistent;
        e->valid = true;
        *out = persistent;
        return true;
    }

    FILE *f = fopen(path, "rb");
'''
s = replace_once(s, old, new, "persistent hash lookup")

old = '''    e->hash = h;
    e->valid = true;
    *out = h;
    return true;
}'''
new = '''    e->hash = h;
    e->valid = true;
    compiler_persistent_hash_store(path, stamp.sec, stamp.nsec, stamp.size, h);
    *out = h;
    return true;
}'''
s = replace_once(s, old, new, "persistent hash store")

s = replace_once(s,
'''    if (!compiler_read_depfile(depfile, &deps)) return false;''',
'''    if (!compiler_read_depfile_persistent(depfile, &deps)) return false;''',
"persistent dependency graph")

s = replace_once(s,
'''    return compiler_copy_atomic(cached_obj, obj) && compiler_copy_atomic(cached_dep, depf);''',
'''    return compiler_clone_or_copy(cached_obj, obj) && compiler_clone_or_copy(cached_dep, depf);''',
"clone cache restore")

s = replace_once(s,
'''    if (!compiler_copy_atomic(obj, cached_obj) || !compiler_copy_atomic(depf, cached_dep) || rename(temp_meta, meta) != 0) unlink(temp_meta);''',
'''    if (!compiler_clone_or_copy(obj, cached_obj) || !compiler_clone_or_copy(depf, cached_dep) || rename(temp_meta, meta) != 0) unlink(temp_meta);''',
"clone cache store")

s = replace_once(s,
'''    pid_t pid;
    bool active;
} CompilerTask;''',
'''    pid_t pid;
    bool active;
    double estimate_ms;
    double started_ms;
} CompilerTask;''',
"task timing fields")

s = replace_once(s,
'''    if (compiler_object_cache_restore(key, obj, depf)) {
        vec_free(cmd);
        return COMPILER_PREP_CACHE;
    }''',
'''    if (compiler_object_cache_restore(key, obj, depf)) {
        compiler_profile_cached(source);
        vec_free(cmd);
        return COMPILER_PREP_CACHE;
    }''',
"profile cache hits")

s = replace_once(s,
'''    c__copy(task->key, sizeof(task->key), key);
    return COMPILER_PREP_BUILD;''',
'''    c__copy(task->key, sizeof(task->key), key);
    task->estimate_ms = compiler_source_estimate(source);
    return COMPILER_PREP_BUILD;''',
"task estimates")

s = replace_once(s,
'''    size_t next = 0, finished = 0, running = 0;
    size_t limit = (size_t)(compiler_perf.jobs < 1 ? 1 : compiler_perf.jobs);
    if (limit > count) limit = count;
''',
'''    for (size_t i = 0; i < count; ++i) {
        for (size_t j = i + 1; j < count; ++j) {
            if (tasks[j].estimate_ms > tasks[i].estimate_ms) {
                CompilerTask tmp = tasks[i];
                tasks[i] = tasks[j];
                tasks[j] = tmp;
            }
        }
    }
    size_t next = 0, finished = 0, running = 0;
    size_t limit = (size_t)compiler_adaptive_jobs(compiler_perf.jobs);
    if (limit < 1) limit = 1;
    if (limit > count) limit = count;
''',
"longest-job-first scheduler")

s = replace_once(s,
'''            tasks[next].active = true;
            ++running;''',
'''            tasks[next].active = true;
            tasks[next].started_ms = compiler_perf_now_ms();
            ++running;''',
"task start timing")

s = replace_once(s,
'''        if (rc != 0) {
            compiler_cancel_tasks(tasks, count);
            die("%s: %s", error_message, task->source);
        }
        compiler_object_cache_store(task->key, task->obj, task->depf);''',
'''        if (rc != 0) {
            compiler_cancel_tasks(tasks, count);
            die("%s: %s", error_message, task->source);
        }
        compiler_history_record(task->source, compiler_perf_now_ms() - task->started_ms);
        compiler_object_cache_store(task->key, task->obj, task->depf);''',
"task timing history")

s = replace_section(s,
'''static void compiler_make_unity_sources(''',
'''static void compiler_dep_root(''',
'''static void compiler_make_unity_sources(StrVec *sources, const char *unity_dir, const char *root_prefix, StrVec *out) {
    int mode = compiler_perf.unity;
    if (mode == 0 || mode == 1 || sources->count <= 1) {
        for (size_t i = 0; i < sources->count; ++i) vec_push(out, sources->items[i]);
        return;
    }
    mkdir_p(unity_dir);
    for (int kind = 0; kind < 4; ++kind) {
        size_t *indices = calloc(sources->count, sizeof(*indices));
        if (!indices) die("out of memory");
        size_t n = 0;
        for (size_t i = 0; i < sources->count; ++i) if (compiler_language_kind(sources->items[i]) == kind) indices[n++] = i;
        size_t start = 0, chunk = 0;
        while (start < n) {
            size_t count = 0;
            if (mode == -1) {
                size_t max_count = (size_t)compiler_unity_auto_mode(sources);
                double cost = 0.0;
                while (start + count < n && count < max_count) {
                    cost += compiler_source_estimate(sources->items[indices[start + count]]);
                    ++count;
                    if (count >= 2 && cost >= 600.0) break;
                }
            } else {
                count = n - start;
                if (count > (size_t)mode) count = (size_t)mode;
            }
            if (count == 0) count = 1;
            if (count == 1) {
                vec_push(out, sources->items[indices[start]]);
                start += count;
                ++chunk;
                continue;
            }
            uint64_t membership = compiler_unity_membership_hash(sources, indices + start, count);
            char member_hex[17], name[96], path[PATH_MAX];
            hash_u64_hex(membership, member_hex);
            snprintf(name, sizeof(name), "unity-%d-%zu-%s%s", kind, chunk, member_hex, compiler_unity_extension(kind));
            path_join(path, unity_dir, name);
            compiler_write_unity_file(path, sources, indices + start, count, root_prefix);
            vec_push(out, path);
            start += count;
            ++chunk;
        }
        free(indices);
    }
}''',
"smart unity")

s = replace_once(s,
'''        vec_push(&a, opt->release ? "-O2" : "-O0");
        if (!opt->release) vec_push(&a, "-g");''',
'''        if (opt->release) vec_push(&a, "-O2");
        else if (compiler_perf.fast_debug) { vec_push(&a, "-O1"); vec_push(&a, "-g1"); }
        else { vec_push(&a, "-O0"); vec_push(&a, "-g"); }''',
"dependency fast debug")

s = replace_section(s,
'''static void compiler_resolve_all(''',
'''static void compiler_append_target_compile_flags(''',
'''static void compiler_resolve_all(C_Build *b, const Options *opt, DepState states[]) {
    LockFile lock;
    load_lock(&lock);
    for (size_t i = 0; i < b->dep_count; ++i) {
        C_Dependency *d = &b->deps[i];
        if (d->kind == C_DEP_RESERVED) die("external build-system dependencies are not supported; use c_dep_source()");
        resolve_dependency(d, opt, &lock, &states[i], false);
    }
    save_lock(&lock);

    size_t source_indices[C_MAX_DEPS];
    size_t source_count = 0;
    for (size_t i = 0; i < b->dep_count; ++i) if (b->deps[i].kind == C_DEP_SOURCE) source_indices[source_count++] = i;
    int total_jobs = compiler_adaptive_jobs(compiler_perf.jobs);
    if (source_count <= 1 || total_jobs <= 1) {
        for (size_t i = 0; i < source_count; ++i) {
            size_t idx = source_indices[i];
            compiler_build_dependency(&b->deps[idx], opt, &states[idx]);
        }
    } else {
        size_t worker_limit = source_count < (size_t)total_jobs ? source_count : (size_t)total_jobs;
        pid_t pids[C_MAX_DEPS] = {0};
        size_t dep_for_pid[C_MAX_DEPS] = {0};
        size_t next = 0, running = 0, finished = 0;
        int jobs_per_dep = total_jobs / (int)worker_limit;
        if (jobs_per_dep < 1) jobs_per_dep = 1;
        while (finished < source_count) {
            while (next < source_count && running < worker_limit) {
                size_t idx = source_indices[next];
                pid_t pid = fork();
                if (pid < 0) die("fork dependency build: %s", strerror(errno));
                if (pid == 0) {
                    compiler_perf.jobs = jobs_per_dep;
                    compiler_perf.adaptive_jobs = false;
                    compiler_build_dependency(&b->deps[idx], opt, &states[idx]);
                    fflush(NULL);
                    _exit(0);
                }
                pids[next] = pid;
                dep_for_pid[next] = idx;
                ++next;
                ++running;
            }
            int status = 0;
            pid_t done;
            do { done = waitpid(-1, &status, 0); } while (done < 0 && errno == EINTR);
            if (done < 0) die("waitpid dependency build: %s", strerror(errno));
            size_t slot = source_count;
            for (size_t i = 0; i < next; ++i) if (pids[i] == done) { slot = i; break; }
            if (slot == source_count) continue;
            pids[slot] = 0;
            --running;
            ++finished;
            int rc = WIFEXITED(status) ? WEXITSTATUS(status) : WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1;
            if (rc != 0) die("dependency build failed: %s", b->deps[dep_for_pid[slot]].name);
        }
    }
    compiler_prepare_target_links(b, states);
}''',
"parallel dependencies")

s = replace_once(s,
'''    uint64_t sig = target_signature(t, b, states, opt, &sources);
    uint64_t tool = compiler_tool_identity(opt->cc);
    sig = hash_update(sig, &tool, sizeof(tool));
    sig = hash_update(sig, &compiler_perf.unity, sizeof(compiler_perf.unity));''',
'''    compiler_profile_reset();
    int unity_mode = t->unity_chunk ? t->unity_chunk : compiler_perf.unity;
    uint64_t sig = target_signature(t, b, states, opt, &sources);
    uint64_t tool = compiler_tool_identity(opt->cc);
    sig = hash_update(sig, &tool, sizeof(tool));
    sig = hash_update(sig, &unity_mode, sizeof(unity_mode));
    sig = hash_update(sig, &compiler_perf.fast_debug, sizeof(compiler_perf.fast_debug));
    sig = hash_update(sig, compiler_perf.linker, strlen(compiler_perf.linker));''',
"target performance signature")

s = replace_once(s,
'''    path_join(unity_root, "build", ".unity"); path_join(unity_dir, unity_root, sighex);
    compiler_make_unity_sources(&sources, unity_dir, "../../../", &compile_sources);''',
'''    path_join(unity_root, "build", ".unity"); path_join(unity_dir, unity_root, sighex);
    int saved_unity = compiler_perf.unity;
    compiler_perf.unity = unity_mode;
    compiler_make_unity_sources(&sources, unity_dir, "../../../", &compile_sources);
    compiler_perf.unity = saved_unity;''',
"per-target unity")

s = replace_once(s,
'''        vec_push(&a, opt->cc); compiler_push_standard(&a, source);
        vec_push(&a, opt->release ? "-O2" : "-O0"); if (!opt->release) vec_push(&a, "-g");''',
'''        vec_push(&a, opt->cc); compiler_push_standard(&a, source);
        if (opt->release) vec_push(&a, "-O2");
        else if (compiler_perf.fast_debug) { vec_push(&a, "-O1"); vec_push(&a, "-g1"); }
        else { vec_push(&a, "-O0"); vec_push(&a, "-g"); }''',
"target fast debug")

s = replace_once(s,
'''    bool relink = !file_exists(output); time_t outt = mtime_of(output);''',
'''    bool relink = !file_exists(output); time_t outt = mtime_of(output);
    double link_ms = 0.0;''',
"link timer declaration")

s = replace_once(s,
'''            note("AR", "%s", output); if (compiler_run_process(&a, opt->verbose) != 0) die("archive failed"); vec_free(&a);''',
'''            note("AR", "%s", output); double link_started = compiler_perf_now_ms(); if (compiler_run_process(&a, opt->verbose) != 0) die("archive failed"); link_ms = compiler_perf_now_ms() - link_started; vec_free(&a);''',
"archive profiling")

s = replace_once(s,
'''            StrVec a = {0}; vec_push(&a, opt->cc); for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states); vec_push(&a, "-o"); vec_push(&a, output);
            note("LINK", "%s", output); if (compiler_run_process(&a, opt->verbose) != 0) die("link failed"); vec_free(&a);''',
'''            StrVec a = {0}; vec_push(&a, opt->cc); compiler_append_linker(&a); for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states); vec_push(&a, "-o"); vec_push(&a, output);
            note("LINK", "%s", output); double link_started = compiler_perf_now_ms(); if (compiler_run_process(&a, opt->verbose) != 0) die("link failed"); link_ms = compiler_perf_now_ms() - link_started; vec_free(&a);''',
"linker selection and profiling")

s = replace_once(s,
'''    vec_free(&sources); vec_free(&compile_sources); vec_free(&objects); return output;''',
'''    compiler_profile_report(t->name, link_ms);
    vec_free(&sources); vec_free(&compile_sources); vec_free(&objects); return output;''',
"profile report")

s = replace_section(s,
'''static void compiler_cmd_test(''',
'''static void compiler_cmd_doctor(''',
'''static void compiler_cmd_test(const Options *opt) {
    C_Build *b = alloc_build(); load_build(opt, b);
    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);
    C_Target *targets[C_MAX_TARGETS] = {0};
    char *outputs[C_MAX_TARGETS] = {0};
    size_t tests = 0;
    for (size_t i = 0; i < b->target_count; ++i) {
        C_Target *t = &b->targets[i];
        if (t->kind != C_TARGET_TEST || (opt->target_name && strcmp(t->name, opt->target_name))) continue;
        targets[tests] = t;
        outputs[tests] = compiler_build_target(b, t, states, opt);
        ++tests;
    }
    if (!tests) die("no test targets defined; use c_test() in build.c");

    pid_t pids[C_MAX_TARGETS] = {0};
    bool active[C_MAX_TARGETS] = {0};
    size_t next = 0, running = 0, finished = 0;
    size_t limit = (size_t)compiler_adaptive_jobs(compiler_perf.jobs);
    if (limit < 1) limit = 1;
    if (limit > tests) limit = tests;
    while (finished < tests) {
        while (next < tests && running < limit) {
            note("TEST", "%s", targets[next]->name);
            StrVec a = {0}; char exec[PATH_MAX];
            snprintf(exec, sizeof(exec), "./%s", outputs[next]);
            vec_push(&a, exec);
            if (compiler_spawn(&a, opt->verbose, &pids[next]) != 0) die("cannot start test: %s", targets[next]->name);
            vec_free(&a);
            active[next] = true;
            ++next; ++running;
        }
        int status = 0; pid_t done;
        do { done = waitpid(-1, &status, 0); } while (done < 0 && errno == EINTR);
        if (done < 0) die("waitpid test: %s", strerror(errno));
        size_t slot = tests;
        for (size_t i = 0; i < tests; ++i) if (active[i] && pids[i] == done) { slot = i; break; }
        if (slot == tests) continue;
        active[slot] = false; --running; ++finished;
        int rc = WIFEXITED(status) ? WEXITSTATUS(status) : WIFSIGNALED(status) ? 128 + WTERMSIG(status) : 1;
        if (rc != 0) {
            for (size_t i = 0; i < tests; ++i) if (active[i]) kill(pids[i], SIGTERM);
            die("test failed: %s", targets[slot]->name);
        }
    }
    for (size_t i = 0; i < tests; ++i) free(outputs[i]);
    note("PASS", "%zu test target%s", tests, tests == 1 ? "" : "s");
    free_build(b);
}''',
"parallel tests")

s = replace_section(s,
'''static void compiler_cmd_doctor(''',
'''static int compiler_dispatch(''',
'''static void compiler_cmd_doctor(const Options *opt) {
    struct utsname u; uname(&u);
    printf("c %s\n\n", C_VERSION);
    printf("Platform   %s %s\n", u.sysname, u.machine);
    printf("Compiler   %s%s\n", opt->cc, command_exists(opt->cc) ? "" : "  [missing]");
    printf("Archiver   %s%s\n", compiler_ar(), command_exists(compiler_ar()) ? "" : "  [missing]");
    printf("Git        %s\n", command_exists("git") ? "ok" : "missing");
    printf("CPUs       %d\n", compiler_cpu_count());
    printf("Jobs       %d%s\n", compiler_perf.jobs, compiler_perf.jobs_explicit ? " (explicit)" : " (half CPUs default)");
    printf("Adaptive   %s\n", compiler_perf.adaptive_jobs ? "on" : "off");
    printf("Obj cache  %s\n", compiler_perf.object_cache ? "on" : "off");
    printf("Unity      %s", compiler_perf.unity ? "on" : "off");
    if (compiler_perf.unity == -1) printf(" (auto)");
    else if (compiler_perf.unity > 1) printf(" (chunk %d)", compiler_perf.unity);
    putchar('\n');
    printf("Fast debug %s\n", compiler_perf.fast_debug ? "on" : "off");
    const char *linker = compiler_selected_linker();
    printf("Linker     %s\n", linker ? linker : compiler_perf.linker[0] ? compiler_perf.linker : "system default");
    char cache[PATH_MAX]; cache_root(cache); printf("Cache      %s\n", cache);
}

static int compiler_watch_build_once(const Options *opt) {
    pid_t pid = fork();
    if (pid < 0) die("fork watch build: %s", strerror(errno));
    if (pid == 0) {
        compiler_cmd_build_or_run(opt, false);
        fflush(NULL);
        _exit(0);
    }
    return compiler_wait(pid);
}

static void compiler_cmd_watch(const Options *opt) {
    int rc = compiler_watch_build_once(opt);
    uint64_t fingerprint = compiler_watch_fingerprint();
    note("WATCH", "waiting for changes%s", rc == 0 ? "" : " (last build failed)");
    for (;;) {
        compiler_watch_sleep();
        uint64_t next = compiler_watch_fingerprint();
        if (next == fingerprint) continue;
        fingerprint = next;
        note("WATCH", "change detected");
        rc = compiler_watch_build_once(opt);
        note("WATCH", "waiting for changes%s", rc == 0 ? "" : " (last build failed)");
    }
}''',
"doctor and watch")

s = replace_once(s,
'''    if (!strcmp(opt.command, "build")) compiler_cmd_build_or_run(&opt, false);
    else if (!strcmp(opt.command, "run")) compiler_cmd_build_or_run(&opt, true);
    else if (!strcmp(opt.command, "test")) compiler_cmd_test(&opt);
    else if (!strcmp(opt.command, "doctor")) compiler_cmd_doctor(&opt);''',
'''    if (!strcmp(opt.command, "build")) compiler_cmd_build_or_run(&opt, false);
    else if (!strcmp(opt.command, "run")) compiler_cmd_build_or_run(&opt, true);
    else if (!strcmp(opt.command, "watch")) compiler_cmd_watch(&opt);
    else if (!strcmp(opt.command, "test")) compiler_cmd_test(&opt);
    else if (!strcmp(opt.command, "doctor")) compiler_cmd_doctor(&opt);''',
"watch dispatch")

s = replace_once(s,
'''        "init", "build", "run", "fetch", "update", "deps", "test",''',
'''        "init", "build", "run", "watch", "fetch", "update", "deps", "test",''',
"watch command list")

s = replace_once(s,
'''    return !strcmp(s, "init") || !strcmp(s, "build") || !strcmp(s, "run") || !strcmp(s, "fetch") || !strcmp(s, "update") || !strcmp(s, "test") || !strcmp(s, "clean") || !strcmp(s, "cache");''',
'''    return !strcmp(s, "init") || !strcmp(s, "build") || !strcmp(s, "run") || !strcmp(s, "watch") || !strcmp(s, "fetch") || !strcmp(s, "update") || !strcmp(s, "test") || !strcmp(s, "clean") || !strcmp(s, "cache");''',
"watch action list")

s = replace_once(s,
'''    return (!strncmp(arg, "-j", 2) && arg[2]) || !strncmp(arg, "--jobs=", 7) ||
           !strcmp(arg, "--unity") || !strncmp(arg, "--unity=", 8) || !strcmp(arg, "--no-unity") ||
           !strcmp(arg, "--object-cache") || !strcmp(arg, "--no-object-cache");''',
'''    return (!strncmp(arg, "-j", 2) && arg[2]) || !strncmp(arg, "--jobs=", 7) ||
           !strcmp(arg, "--unity") || !strncmp(arg, "--unity=", 8) || !strcmp(arg, "--no-unity") ||
           !strcmp(arg, "--object-cache") || !strcmp(arg, "--no-object-cache") ||
           !strcmp(arg, "--profile") || !strcmp(arg, "--fast-debug") ||
           !strcmp(arg, "--adaptive-jobs") || !strcmp(arg, "--no-adaptive-jobs") ||
           !strncmp(arg, "--linker=", 9);''',
"CLI performance flags")

s = replace_once(s,
'''        if ((!strcmp(argv[i], "--cc") || cli_jobs_option(argv[i])) && i + 1 < argc) ++i;''',
'''        if ((!strcmp(argv[i], "--cc") || !strcmp(argv[i], "--linker") || cli_jobs_option(argv[i])) && i + 1 < argc) ++i;''',
"CLI flag value skip")

s = replace_once(s,
'''        if ((!strcmp(arg, "--cc") || cli_jobs_option(arg)) && i + 1 < argc) { ++i; continue; }''',
'''        if ((!strcmp(arg, "--cc") || !strcmp(arg, "--linker") || cli_jobs_option(arg)) && i + 1 < argc) { ++i; continue; }''',
"CLI target value skip")

s = replace_once(s,
'''    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "test")) fprintf(stderr, " %s[%s]%s", dim, cli_has_flag(argc, argv, "--release", "-Drelease") ? "release" : "debug", reset);''',
'''    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "watch") || !strcmp(command, "test")) fprintf(stderr, " %s[%s]%s", dim, cli_has_flag(argc, argv, "--release", "-Drelease") ? "release" : "debug", reset);''',
"watch heading")

s = replace_once(s,
'''    if (!strcmp(kind, "PASS")) return "pass";
    if (!strcmp(kind, "CLEAN")) return "clean";''',
'''    if (!strcmp(kind, "PASS")) return "pass";
    if (!strcmp(kind, "WATCH")) return "watch";
    if (!strcmp(kind, "CLEAN")) return "clean";''',
"watch step name")

s = replace_once(s,
'''    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "fetch") || !strcmp(command, "update") || !strcmp(command, "test") || !strcmp(command, "clean") || !strcmp(command, "init")) return true;''',
'''    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "watch") || !strcmp(command, "fetch") || !strcmp(command, "update") || !strcmp(command, "test") || !strcmp(command, "clean") || !strcmp(command, "init")) return true;''',
"watch quiet output")

s = replace_once(s,
'''performance:\n  -j N / -jN / --jobs=N    parallel compiler jobs (default: CPU count)\n  --unity[=N]              optional unity chunks (default chunk: 8)\n  --no-object-cache        disable the persistent global object cache\n\nenvironment:\n  C_JOBS=N                 default parallel job count\n  C_UNITY=N                default unity chunk size\n  C_OBJECT_CACHE=0         disable global object caching\n''',
'''performance:\n  -j N / -jN / --jobs=N    parallel jobs (default: half available CPUs)\n  --adaptive-jobs          reduce jobs when the machine is already busy\n  --unity[=N|auto]         optional fixed or history-balanced unity chunks\n  --profile                show cache/build timings and slowest files\n  --fast-debug             use -O1 -g1 for faster debug compiles\n  --linker=NAME|auto       select mold/lld/another compiler-driver linker\n  --no-object-cache        disable the persistent global object cache\n\nwatch:\n  c watch [target]         keep the build process warm and rebuild on changes\n\nenvironment:\n  C_JOBS=N                 default parallel job count\n  C_ADAPTIVE_JOBS=1        adaptive load-aware job limiting\n  C_UNITY=N|auto           default unity mode\n  C_OBJECT_CACHE=0         disable global object caching\n  C_PROFILE=1              enable build timing reports\n  C_FAST_DEBUG=1           enable faster debug compilation\n  C_LINKER=NAME|auto       linker selection\n''',
"help performance text")

# Keep the two existing compact statements readable and warning-free.
s = s.replace('''        if (segment_action && !first_action) fputc('\\n', stderr); if (segment_action) first_action = false;''', '''        if (segment_action && !first_action) fputc('\\n', stderr);
        if (segment_action) first_action = false;''')
s = s.replace('''        if (end >= argc) break; start = end;''', '''        if (end >= argc) break;
        start = end;''')

p.write_text(s)

# Public per-target unity controls.
p = Path("include/cbuild.h")
s = p.read_text()
s = replace_once(s,
'''    C_Dependency *deps[C_MAX_DEPS];
    size_t dep_count;
} C_Target;''',
'''    C_Dependency *deps[C_MAX_DEPS];
    size_t dep_count;
    int unity_chunk;  /* 0=inherit CLI, 1=off, -1=auto, >=2=fixed chunk */
} C_Target;''',
"public target unity field")
s = replace_once(s,
'''static inline void c_framework(C_Target *t, const char *name) { if (t) c__push(&t->frameworks, name); }
''',
'''static inline void c_framework(C_Target *t, const char *name) { if (t) c__push(&t->frameworks, name); }
static inline void c_unity(C_Target *t, int chunk_size) { if (t) t->unity_chunk = chunk_size > 1 ? chunk_size : 1; }
static inline void c_unity_auto(C_Target *t) { if (t) t->unity_chunk = -1; }
static inline void c_no_unity(C_Target *t) { if (t) t->unity_chunk = 1; }
''',
"public target unity API")
p.write_text(s)

# API baseline must exercise every newly public function.
p = Path("tests/api_baseline.sh")
s = p.read_text()
s = replace_once(s,
'''    c_framework(app, "Foundation");
''',
'''    c_framework(app, "Foundation");
    c_unity(app, 8);
    c_unity_auto(lib);
    c_no_unity(test);
''',
"API baseline unity")
p.write_text(s)

# Make the advanced module part of the normal rebuild dependency list.
p = Path("Makefile")
s = p.read_text()
s = replace_once(s,
'''$(TARGET): src/cli.c src/main.c src/cache_io.h include/cbuild.h''',
'''$(TARGET): src/cli.c src/main.c src/cache_io.h src/perf_v2.h include/cbuild.h''',
"Makefile perf module")
p.write_text(s)
