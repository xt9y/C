from pathlib import Path


def replace_once(path: Path, old: str, new: str) -> None:
    s = path.read_text()
    n = s.count(old)
    if n != 1:
        raise SystemExit(f'{path}: expected one match, got {n}: {old[:100]!r}')
    path.write_text(s.replace(old, new, 1))

h = Path('include/cbuild.h')
replace_once(h,
'''    C_StringList system_links;
    C_StringList frameworks;
    C_Dependency *deps[C_MAX_DEPS];''',
'''    C_StringList system_links;
    C_StringList frameworks;
    C_StringList generated_outputs;
    C_StringList generated_inputs;
    C_StringList generated_commands;
    C_Dependency *deps[C_MAX_DEPS];''')
replace_once(h,
'''static inline void c_warnings_strict(C_Target *t) {
    if (!t) c__fatal("c_warnings_strict received a null target");
    c__push(&t->cflags, "-Wall");
    c__push(&t->cflags, "-Wextra");
    c__push(&t->cflags, "-Wpedantic");
}

static inline void c_link_target''',
'''static inline void c_warnings_strict(C_Target *t) {
    if (!t) c__fatal("c_warnings_strict received a null target");
    c__push(&t->cflags, "-Wall");
    c__push(&t->cflags, "-Wextra");
    c__push(&t->cflags, "-Wpedantic");
}

/*
 * Declare a generated source/output. `command` is executed by /bin/sh when
 * output is missing, input is newer, or the command itself changed. Passing
 * NULL/empty input creates a command-only generated output. The output is
 * automatically added to the target's source list.
 */
static inline void c_generate(C_Target *t, const char *output, const char *input, const char *command) {
    if (!t) c__fatal("c_generate received a null target");
    if (!output || !output[0]) c__fatal("c_generate output is empty");
    if (!command || !command[0]) c__fatal("c_generate command is empty");
    c__push(&t->generated_outputs, output);
    c__push(&t->generated_inputs, input ? input : "");
    c__push(&t->generated_commands, command);
    c__push(&t->sources, output);
}

static inline void c_link_target''')

main = Path('src/main.c')
replace_once(main,
'''        free_c_list(&t->system_links);
        free_c_list(&t->frameworks);
    }''',
'''        free_c_list(&t->system_links);
        free_c_list(&t->frameworks);
        free_c_list(&t->generated_outputs);
        free_c_list(&t->generated_inputs);
        free_c_list(&t->generated_commands);
    }''')

cli = Path('src/cli.c')
replace_once(cli,
'''static char *compiler_build_target(C_Build *b, C_Target *t, DepState states[], const Options *opt) {
    StrVec sources = {0}, compile_sources = {0}, objects = {0};
    expand_sources(t, b, states, &sources);''',
'''static void compiler_run_generators(C_Target *t, const Options *opt) {
    if (t->generated_outputs.count != t->generated_inputs.count ||
        t->generated_outputs.count != t->generated_commands.count)
        die("target %s has an invalid generated-source description", t->name);
    if (!t->generated_outputs.count) return;

    char state_root[PATH_MAX];
    path_join(state_root, "build", ".generated");
    mkdir_p(state_root);

    for (size_t i = 0; i < t->generated_outputs.count; ++i) {
        const char *output = t->generated_outputs.items[i];
        const char *input = t->generated_inputs.items[i];
        const char *command = t->generated_commands.items[i];
        bool need = !file_exists(output);
        if (!need && input[0]) {
            if (!file_exists(input)) die("generated input not found: %s", input);
            if (mtime_of(input) > mtime_of(output)) need = true;
        }

        uint64_t h = hash_string(t->name);
        h = hash_update(h, output, strlen(output));
        char key[17]; hash_u64_hex(h, key);
        char stamp[PATH_MAX]; path_join(stamp, state_root, key);
        FILE *sf = fopen(stamp, "r");
        char previous[4096] = {0};
        if (!sf || !fgets(previous, sizeof(previous), sf)) need = true;
        if (sf) fclose(sf);
        previous[strcspn(previous, "\\r\\n")] = '\\0';
        char command_hash[17]; hash_u64_hex(hash_string(command), command_hash);
        if (strcmp(previous, command_hash)) need = true;

        if (!need) {
            if (compiler_perf.explain) note("WHY", "%s generator is fresh", output);
            continue;
        }

        char parent[PATH_MAX]; c__copy(parent, sizeof(parent), output);
        char *slash = strrchr(parent, '/');
        if (slash) { *slash = '\\0'; if (parent[0]) mkdir_p(parent); }
        note("GEN", "%s", output);
        StrVec a = {0}; vec_push(&a, "sh"); vec_push(&a, "-c"); vec_push(&a, command);
        if (compiler_run_process(&a, opt->verbose) != 0) { vec_free(&a); die("generator failed for %s", output); }
        vec_free(&a);
        if (!file_exists(output)) die("generator did not produce %s", output);

        char temp[PATH_MAX];
        if (snprintf(temp, sizeof(temp), "%s.tmp.%ld", stamp, (long)getpid()) >= (int)sizeof(temp))
            die("generator stamp path too long");
        FILE *out = fopen(temp, "w");
        if (!out) die("cannot write generator state: %s", strerror(errno));
        if (fprintf(out, "%s\\n", command_hash) < 0 || fflush(out) != 0 || fsync(fileno(out)) != 0 || fclose(out) != 0) {
            unlink(temp); die("cannot persist generator state");
        }
        if (rename(temp, stamp) != 0) { unlink(temp); die("cannot install generator state: %s", strerror(errno)); }
    }
}

static char *compiler_build_target(C_Build *b, C_Target *t, DepState states[], const Options *opt) {
    StrVec sources = {0}, compile_sources = {0}, objects = {0};
    compiler_run_generators(t, opt);
    expand_sources(t, b, states, &sources);''')

print('generated-source upgrade applied')
