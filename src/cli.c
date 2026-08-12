#define C_DEP_CMAKE C_DEP_RESERVED
#define cmake_options compile_flags
#define main c_legacy_main
#include "main.c"
#undef main
#undef cmake_options
#undef C_DEP_CMAKE

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

    StrVec sources = {0}, objects = {0};
    for (size_t i = 0; i < d->source_patterns.count; ++i) {
        char pattern[PATH_MAX];
        path_join(pattern, root, d->source_patterns.items[i]);
        expand_pattern(pattern, &sources);
    }

    note("DEP", "%s", d->name);
    for (size_t i = 0; i < sources.count; ++i) {
        char obj[PATH_MAX];
        object_path(objdir, sources.items[i], obj);
        vec_push(&objects, obj);

        StrVec a = {0};
        vec_push(&a, opt->cc);
        compiler_push_standard(&a, sources.items[i]);
        vec_push(&a, opt->release ? "-O2" : "-O0");
        if (!opt->release) vec_push(&a, "-g");

        char root_inc[PATH_MAX + 3];
        snprintf(root_inc, sizeof(root_inc), "-I%s", root);
        vec_push(&a, root_inc);
        for (size_t j = 0; j < d->include_dirs.count; ++j) {
            char inc[PATH_MAX], arg[PATH_MAX + 3];
            path_join(inc, root, d->include_dirs.items[j]);
            snprintf(arg, sizeof(arg), "-I%s", inc);
            vec_push(&a, arg);
        }
        compiler_push_source_flags(&a, &d->compile_flags, sources.items[i]);
        vec_push(&a, "-c");
        vec_push(&a, sources.items[i]);
        vec_push(&a, "-o");
        vec_push(&a, obj);

        note("CC", "%s", sources.items[i]);
        if (run_process(&a, opt->verbose, NULL) != 0) die("dependency compile failed: %s", d->name);
        vec_free(&a);
    }

    StrVec ar = {0};
    vec_push(&ar, compiler_ar());
    vec_push(&ar, "rcs");
    vec_push(&ar, library);
    for (size_t i = 0; i < objects.count; ++i) vec_push(&ar, objects.items[i]);
    note("AR", "%s", library);
    if (run_process(&ar, opt->verbose, NULL) != 0) die("dependency archive failed: %s", d->name);
    vec_free(&ar);
    vec_free(&sources);
    vec_free(&objects);
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
            char library[PATH_MAX];
            compiler_dep_library(d, &states[idx], library);
            c__push(&ordered, library);
        }

        for (size_t i = 0; i < t->system_links.count; ++i) {
            char arg[C_MAX_NAME + 3];
            snprintf(arg, sizeof(arg), "-l%s", t->system_links.items[i]);
            c__push(&ordered, arg);
        }
#ifdef __APPLE__
        for (size_t i = 0; i < t->frameworks.count; ++i) {
            c__push(&ordered, "-framework");
            c__push(&ordered, t->frameworks.items[i]);
        }
#endif
        for (size_t i = 0; i < t->ldflags.count; ++i) c__push(&ordered, t->ldflags.items[i]);

        free_c_list(&t->system_links);
        free_c_list(&t->frameworks);
        free_c_list(&t->ldflags);
        t->ldflags = ordered;
    }

    for (size_t i = 0; i < b->dep_count; ++i) {
        if (b->deps[i].kind == C_DEP_SOURCE) b->deps[i].kind = C_DEP_HEADER_ONLY;
    }
}

static void compiler_resolve_all(C_Build *b, const Options *opt, DepState states[]) {
    LockFile lock;
    load_lock(&lock);
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
    for (size_t i = 0; i < t->includes.count; ++i) {
        char x[PATH_MAX + 3];
        snprintf(x, sizeof(x), "-I%s", t->includes.items[i]);
        vec_push(a, x);
    }
    for (size_t i = 0; i < t->defines.count; ++i) {
        char x[PATH_MAX + 3];
        snprintf(x, sizeof(x), "-D%s", t->defines.items[i]);
        vec_push(a, x);
    }
    compiler_push_source_flags(a, &t->cflags, source);
    for (size_t i = 0; i < t->dep_count; ++i) {
        C_Dependency *d = t->deps[i];
        ptrdiff_t dep_index = d - b->deps;
        if (dep_index < 0 || (size_t)dep_index >= b->dep_count) die("target %s has invalid dependency", t->name);
        DepState *s = &states[dep_index];
        char root[PATH_MAX];
        if (d->subdir[0]) path_join(root, s->source, d->subdir);
        else c__copy(root, sizeof(root), s->source);
        if (d->include_dirs.count == 0) {
            char x[PATH_MAX + 3];
            snprintf(x, sizeof(x), "-I%s", root);
            vec_push(a, x);
        } else {
            for (size_t j = 0; j < d->include_dirs.count; ++j) {
                char inc[PATH_MAX], x[PATH_MAX + 3];
                path_join(inc, root, d->include_dirs.items[j]);
                snprintf(x, sizeof(x), "-I%s", inc);
                vec_push(a, x);
            }
        }
    }
}

static char *compiler_build_target(C_Build *b, C_Target *t, DepState states[], const Options *opt) {
    StrVec sources = {0}, objects = {0};
    expand_sources(t, b, states, &sources);
    if (sources.count == 0) die("target %s has no sources", t->name);
    uint64_t sig = target_signature(t, b, states, opt, &sources);
    char sighex[17]; hash_u64_hex(sig, sighex);
    char objdir[PATH_MAX]; path_join(objdir, "build/.objs", sighex); mkdir_p(objdir);
    char cwd[PATH_MAX]; if (!getcwd(cwd, sizeof(cwd))) die("getcwd failed");
    FILE *db = fopen("compile_commands.json", "w");
    bool first = true;
    if (db) fprintf(db, "[\n");

    size_t compiled = 0;
    for (size_t i = 0; i < sources.count; ++i) {
        char obj[PATH_MAX], depf[PATH_MAX];
        object_path(objdir, sources.items[i], obj);
        if (strlen(obj) + 3 >= sizeof(depf)) die("object path too long: %s", obj);
        c__copy(depf, sizeof(depf), obj);
        strcat(depf, ".d");
        vec_push(&objects, obj);

        StrVec a = {0};
        vec_push(&a, opt->cc);
        compiler_push_standard(&a, sources.items[i]);
        vec_push(&a, opt->release ? "-O2" : "-O0");
        if (!opt->release) vec_push(&a, "-g");
        vec_push(&a, "-MMD");
        vec_push(&a, "-MF");
        vec_push(&a, depf);
        compiler_append_target_compile_flags(&a, t, b, states, sources.items[i]);
        vec_push(&a, "-c");
        vec_push(&a, sources.items[i]);
        vec_push(&a, "-o");
        vec_push(&a, obj);

        if (db) write_compile_command(db, &first, &a, sources.items[i], cwd);
        if (!depfile_fresh(obj, depf, sources.items[i])) {
            note("CC", "%s", sources.items[i]);
            if (run_process(&a, opt->verbose, NULL) != 0) die("compile failed");
            compiled++;
        }
        vec_free(&a);
    }
    if (db) {
        fprintf(db, "\n]\n");
        fclose(db);
    }

    char profile_dir[PATH_MAX];
    path_join(profile_dir, "build", opt->release ? "release" : "debug");
    mkdir_p(profile_dir);
    char *output = malloc(PATH_MAX);
    if (!output) die("out of memory");
    char outname[C_MAX_NAME + 4];
    snprintf(outname, sizeof(outname), "%s%s", t->name, t->kind == C_TARGET_STATIC_LIBRARY ? ".a" : "");
    path_join(output, profile_dir, outname);
    bool relink = !file_exists(output);
    time_t outt = mtime_of(output);
    for (size_t i = 0; i < objects.count; ++i) if (mtime_of(objects.items[i]) > outt) relink = true;

    if (relink || compiled) {
        if (t->kind == C_TARGET_STATIC_LIBRARY) {
            StrVec a = {0};
            vec_push(&a, compiler_ar());
            vec_push(&a, "rcs");
            vec_push(&a, output);
            for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            note("AR", "%s", output);
            if (run_process(&a, opt->verbose, NULL) != 0) die("archive failed");
            vec_free(&a);
        } else {
            StrVec a = {0};
            vec_push(&a, opt->cc);
            for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states);
            vec_push(&a, "-o");
            vec_push(&a, output);
            note("LINK", "%s", output);
            if (run_process(&a, opt->verbose, NULL) != 0) die("link failed");
            vec_free(&a);
        }
    } else {
        note("CACHED", "%s", t->name);
    }

    vec_free(&sources);
    vec_free(&objects);
    return output;
}

static void compiler_cmd_build_or_run(const Options *opt, bool run) {
    C_Build *b = alloc_build();
    load_build(opt, b);
    DepState states[C_MAX_DEPS] = {0};
    compiler_resolve_all(b, opt, states);
    C_Target *t = select_target(b, opt);
    char *output = compiler_build_target(b, t, states, opt);

    if (run) {
        if (t->kind != C_TARGET_EXECUTABLE && t->kind != C_TARGET_TEST) die("target %s is not executable", t->name);
        note("RUN", "%s", output);
        StrVec a = {0};
        char exec[PATH_MAX];
        if (output[0] == '/') snprintf(exec, sizeof(exec), "%s", output);
        else snprintf(exec, sizeof(exec), "./%s", output);
        vec_push(&a, exec);
        for (int i = 0; i < opt->run_argc; ++i) vec_push(&a, opt->run_argv[i]);
        int rc = run_process(&a, opt->verbose, NULL);
        vec_free(&a);
        free(output);
        free_build(b);
        exit(rc);
    }

    free(output);
    free_build(b);
}

static void compiler_cmd_test(const Options *opt) {
    C_Build *b = alloc_build();
    load_build(opt, b);
    DepState states[C_MAX_DEPS] = {0};
    compiler_resolve_all(b, opt, states);
    size_t tests = 0;

    for (size_t i = 0; i < b->target_count; ++i) {
        C_Target *t = &b->targets[i];
        if (t->kind != C_TARGET_TEST) continue;
        if (opt->target_name && strcmp(t->name, opt->target_name)) continue;
        ++tests;
        char *output = compiler_build_target(b, t, states, opt);
        note("TEST", "%s", t->name);
        StrVec a = {0};
        char exec[PATH_MAX];
        snprintf(exec, sizeof(exec), "./%s", output);
        vec_push(&a, exec);
        int rc = run_process(&a, opt->verbose, NULL);
        vec_free(&a);
        free(output);
        if (rc != 0) die("test failed: %s", t->name);
    }

    if (!tests) die("no test targets defined; use c_test() in build.c");
    note("PASS", "%zu test target%s", tests, tests == 1 ? "" : "s");
    free_build(b);
}

static void compiler_cmd_doctor(const Options *opt) {
    struct utsname u;
    uname(&u);
    printf("c %s\n\n", C_VERSION);
    printf("Platform   %s %s\n", u.sysname, u.machine);
    printf("Compiler   %s%s\n", opt->cc, command_exists(opt->cc) ? "" : "  [missing]");
    printf("Archiver   %s%s\n", compiler_ar(), command_exists(compiler_ar()) ? "" : "  [missing]");
    printf("Git        %s\n", command_exists("git") ? "ok" : "missing");
    char cache[PATH_MAX];
    cache_root(cache);
    printf("Cache      %s\n", cache);
}

static int compiler_dispatch(int argc, char **argv) {
    Options opt = parse_options(argc, argv);
    if (!strcmp(opt.command, "build")) { compiler_cmd_build_or_run(&opt, false); return 0; }
    if (!strcmp(opt.command, "run")) { compiler_cmd_build_or_run(&opt, true); return 0; }
    if (!strcmp(opt.command, "test")) { compiler_cmd_test(&opt); return 0; }
    if (!strcmp(opt.command, "doctor")) { compiler_cmd_doctor(&opt); return 0; }
    return c_legacy_main(argc, argv);
}

static bool cli_is_command(const char *s) {
    static const char *commands[] = {
        "init", "build", "run", "fetch", "update", "deps", "test",
        "clean", "cache", "doctor", "help", "--help", "-h",
        "version", "--version"
    };
    for (size_t i = 0; i < C_ARRAY_LEN(commands); ++i) {
        if (!strcmp(s, commands[i])) return true;
    }
    return false;
}

static bool cli_is_version_or_help(const char *s) {
    return !strcmp(s, "help") || !strcmp(s, "--help") || !strcmp(s, "-h") ||
           !strcmp(s, "version") || !strcmp(s, "--version");
}

static bool cli_is_action(const char *s) {
    return !strcmp(s, "init") || !strcmp(s, "build") || !strcmp(s, "run") ||
           !strcmp(s, "fetch") || !strcmp(s, "update") || !strcmp(s, "test") ||
           !strcmp(s, "clean") || !strcmp(s, "cache");
}

static bool cli_has_flag(int argc, char **argv, const char *a, const char *b) {
    for (int i = 2; i < argc; ++i) {
        if (!strcmp(argv[i], "--")) break;
        if (!strcmp(argv[i], a) || (b && !strcmp(argv[i], b))) return true;
        if (!strcmp(argv[i], "--cc") && i + 1 < argc) ++i;
    }
    return false;
}

static const char *cli_target(int argc, char **argv) {
    for (int i = 2; i < argc; ++i) {
        const char *arg = argv[i];
        if (!strcmp(arg, "--")) break;
        if (!strcmp(arg, "--release") || !strcmp(arg, "-Drelease") ||
            !strcmp(arg, "-v") || !strcmp(arg, "--verbose")) continue;
        if (!strcmp(arg, "--cc") && i + 1 < argc) { ++i; continue; }
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
    memcpy(kind, line + 2, 7);
    kind[7] = '\0';
    for (int i = 6; i >= 0 && kind[i] == ' '; --i) kind[i] = '\0';
    if (!cli_step_name(kind)) return false;
    *message = line + 10;
    return true;
}

static void cli_heading(const char *command, int argc, char **argv) {
    if (!cli_is_action(command)) return;
    bool color = cli_color();
    const char *bold = cli_style(color, "\x1b[1m");
    const char *dim = cli_style(color, "\x1b[2m");
    const char *reset = cli_style(color, "\x1b[0m");
    const char *target = cli_target(argc, argv);
    fprintf(stderr, "%s%s%s", bold, command, reset);
    if (target && strcmp(command, "cache")) fprintf(stderr, " %s", target);
    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "test")) {
        fprintf(stderr, " %s[%s]%s", dim, cli_has_flag(argc, argv, "--release", "-Drelease") ? "release" : "debug", reset);
    }
    fputc('\n', stderr);
}

static void cli_step(const char *kind, const char *message) {
    bool color = cli_color();
    const char *dim = cli_style(color, "\x1b[2m");
    const char *cyan = cli_style(color, "\x1b[36m");
    const char *green = cli_style(color, "\x1b[32m");
    const char *reset = cli_style(color, "\x1b[0m");
    const char *name = cli_step_name(kind);
    const char *style = (!strcmp(kind, "CACHED")) ? dim : (!strcmp(kind, "PASS") || !strcmp(kind, "DONE")) ? green : cyan;
    fprintf(stderr, "%s  ├─%s %s%-10s%s %s", dim, reset, style, name, reset, message);
    size_t n = strlen(message);
    if (!n || message[n - 1] != '\n') fputc('\n', stderr);
}

static void cli_finish(int rc, double elapsed_ms) {
    bool color = cli_color();
    const char *dim = cli_style(color, "\x1b[2m");
    const char *green = cli_style(color, "\x1b[32m");
    const char *red = cli_style(color, "\x1b[31m");
    const char *reset = cli_style(color, "\x1b[0m");
    if (rc == 0) fprintf(stderr, "%s  └─%s %ssuccess%s %s%.0f ms%s\n", dim, reset, green, reset, dim, elapsed_ms, reset);
    else fprintf(stderr, "%s  └─%s %sfailed%s %s(exit %d, %.0f ms)%s\n", dim, reset, red, reset, dim, rc, elapsed_ms, reset);
}

static bool cli_quiet_stdout(const char *command, const char *target) {
    if (!strcmp(command, "build") || !strcmp(command, "run") || !strcmp(command, "fetch") ||
        !strcmp(command, "update") || !strcmp(command, "test") || !strcmp(command, "clean") ||
        !strcmp(command, "init")) return true;
    return !strcmp(command, "cache") && target && !strcmp(target, "clean");
}

static int cli_run_segment(int argc, char **argv) {
    const char *command = argc > 1 ? argv[1] : "help";
    const char *target = cli_target(argc, argv);
    bool action = cli_is_action(command);
    bool verbose = cli_has_flag(argc, argv, "-v", "--verbose");
    bool quiet = cli_quiet_stdout(command, target);
    bool show_program_output = false;
    double started = cli_now_ms();
    if (action) cli_heading(command, argc, argv);

    int fds[2];
    if (pipe(fds) != 0) { perror("pipe"); return 1; }
    pid_t pid = fork();
    if (pid < 0) { perror("fork"); close(fds[0]); close(fds[1]); return 1; }

    if (pid == 0) {
        close(fds[0]);
        if (dup2(fds[1], STDOUT_FILENO) < 0) _exit(127);
        close(fds[1]);
        setvbuf(stdout, NULL, _IONBF, 0);
        int rc = compiler_dispatch(argc, argv);
        fflush(NULL);
        _exit(rc);
    }

    close(fds[1]);
    FILE *stream = fdopen(fds[0], "r");
    if (!stream) { close(fds[0]); waitpid(pid, NULL, 0); return 1; }

    char *line = NULL;
    size_t cap = 0;
    while (getline(&line, &cap, stream) >= 0) {
        char kind[8];
        const char *message = NULL;
        if (cli_parse_note(line, kind, &message)) {
            if (action) cli_step(kind, message); else fputs(line, stdout);
            if (!strcmp(kind, "RUN") || !strcmp(kind, "TEST")) show_program_output = true;
            continue;
        }
        if (!quiet || verbose || show_program_output) { fputs(line, stdout); fflush(stdout); }
    }
    free(line);
    fclose(stream);

    int status = 0;
    while (waitpid(pid, &status, 0) < 0 && errno == EINTR) {}
    int rc = 1;
    if (WIFEXITED(status)) rc = WEXITSTATUS(status);
    else if (WIFSIGNALED(status)) rc = 128 + WTERMSIG(status);
    if (action) cli_finish(rc, cli_now_ms() - started);

    if (rc == 0 && cli_is_version_or_help(command) && (!strcmp(command, "help") || !strcmp(command, "--help") || !strcmp(command, "-h"))) {
        fputs("\nchaining:\n  c clean build run\n  c fetch build test\n\nCommands run left-to-right and stop on the first failure.\nArguments after `--` belong to `c run` and end the command chain.\n", stdout);
    }
    return rc;
}

static bool cli_cache_clean_argument(int start, int i, char **argv) {
    return i == start + 1 && !strcmp(argv[start], "cache") && !strcmp(argv[i], "clean");
}

int main(int argc, char **argv) {
    if (argc < 2) return cli_run_segment(argc, argv);
    int start = 1;
    bool first_action = true;
    while (start < argc) {
        int end = argc;
        bool forwarded_args = false;
        for (int i = start + 1; i < argc; ++i) {
            if (!strcmp(argv[i], "--")) { forwarded_args = true; break; }
            if (cli_is_command(argv[i]) && !cli_cache_clean_argument(start, i, argv)) { end = i; break; }
        }
        if (forwarded_args) end = argc;

        int seg_argc = 1 + (end - start);
        char **seg_argv = calloc((size_t)seg_argc + 1, sizeof(*seg_argv));
        if (!seg_argv) { fputs("c: error: out of memory\n", stderr); return 1; }
        seg_argv[0] = argv[0];
        for (int i = start; i < end; ++i) seg_argv[1 + i - start] = argv[i];

        bool segment_action = seg_argc > 1 && cli_is_action(seg_argv[1]);
        if (segment_action && !first_action) fputc('\n', stderr);
        if (segment_action) first_action = false;
        int rc = cli_run_segment(seg_argc, seg_argv);
        free(seg_argv);
        if (rc != 0) return rc;
        if (end >= argc) break;
        start = end;
    }
    return 0;
}
