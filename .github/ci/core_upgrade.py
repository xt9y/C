from pathlib import Path

path = Path('src/cli.c')
s = path.read_text()


def replace_once(old: str, new: str) -> None:
    global s
    count = s.count(old)
    if count != 1:
        raise SystemExit(f'expected exactly one match, found {count}: {old[:120]!r}')
    s = s.replace(old, new, 1)


replace_once(
    '    bool adaptive_jobs;\n    bool jobs_explicit;\n    char linker[32];',
    '    bool adaptive_jobs;\n    bool jobs_explicit;\n    bool explain;\n    char linker[32];'
)
replace_once(
    '    compiler_perf.jobs_explicit = false;\n    compiler_perf.linker[0] = \'\\0\';',
    '    compiler_perf.jobs_explicit = false;\n    compiler_perf.explain = false;\n    compiler_perf.linker[0] = \'\\0\';'
)
replace_once(
    '    const char *linker = getenv("C_LINKER");\n    if (linker && *linker) c__copy(compiler_perf.linker, sizeof(compiler_perf.linker), linker);',
    '    const char *explain = getenv("C_EXPLAIN");\n    if (explain && strcmp(explain, "0") && strcmp(explain, "false") && strcmp(explain, "off")) compiler_perf.explain = true;\n    const char *linker = getenv("C_LINKER");\n    if (linker && *linker) c__copy(compiler_perf.linker, sizeof(compiler_perf.linker), linker);'
)
replace_once(
    '        if (!strcmp(arg, "--profile")) {\n            compiler_perf.profile = true;\n            continue;\n        }',
    '        if (!strcmp(arg, "--profile")) {\n            compiler_perf.profile = true;\n            continue;\n        }\n        if (!strcmp(arg, "--explain")) {\n            compiler_perf.explain = true;\n            continue;\n        }'
)
replace_once(
    '           !strcmp(arg, "--profile") || !strcmp(arg, "--fast-debug") ||',
    '           !strcmp(arg, "--profile") || !strcmp(arg, "--explain") || !strcmp(arg, "--fast-debug") ||'
)
replace_once(
    '    if (compiler_depfile_fresh(obj, depf, source)) {\n        vec_free(cmd);\n        return COMPILER_PREP_FRESH;\n    }',
    '    if (compiler_depfile_fresh(obj, depf, source)) {\n        if (compiler_perf.explain) note("WHY", "%s is fresh", source);\n        vec_free(cmd);\n        return COMPILER_PREP_FRESH;\n    }'
)
replace_once(
    '    if (compiler_object_cache_restore(key, obj, depf)) {\n        compiler_profile_cached(source);\n        vec_free(cmd);\n        return COMPILER_PREP_CACHE;\n    }',
    '    if (compiler_object_cache_restore(key, obj, depf)) {\n        if (compiler_perf.explain) note("WHY", "%s restored from object cache", source);\n        compiler_profile_cached(source);\n        vec_free(cmd);\n        return COMPILER_PREP_CACHE;\n    }'
)
replace_once(
    '    task->cmd = *cmd;\n    memset(cmd, 0, sizeof(*cmd));',
    '    if (compiler_perf.explain) note("WHY", "%s rebuild required (source/dependency/command changed or object missing)", source);\n    task->cmd = *cmd;\n    memset(cmd, 0, sizeof(*cmd));'
)

replace_once(
    '    if (ferror(in)) ok = false;\n    if (fclose(in) != 0) ok = false;\n    if (fclose(out) != 0) ok = false;\n    if (!ok || rename(temp, to) != 0) { unlink(temp); return false; }',
    '    if (ferror(in)) ok = false;\n    if (fflush(out) != 0) ok = false;\n    if (ok && fsync(fileno(out)) != 0) ok = false;\n    if (fclose(in) != 0) ok = false;\n    if (fclose(out) != 0) ok = false;\n    if (!ok || rename(temp, to) != 0) { unlink(temp); return false; }'
)
replace_once(
    '    fclose(f);\n    if (!valid) return false;\n    return compiler_clone_or_copy(cached_obj, obj) && compiler_clone_or_copy(cached_dep, depf);',
    '    fclose(f);\n    if (!valid) {\n        unlink(cached_obj);\n        unlink(cached_dep);\n        unlink(meta);\n        return false;\n    }\n    return compiler_clone_or_copy(cached_obj, obj) && compiler_clone_or_copy(cached_dep, depf);'
)

replace_once(
    '        compiler_append_target_compile_flags(&a, t, b, states, source);\n        vec_push(&a, "-c"); vec_push(&a, source); vec_push(&a, "-o"); vec_push(&a, obj);',
    '        compiler_append_target_compile_flags(&a, t, b, states, source);\n        if (t->kind == C_TARGET_SHARED_LIBRARY) vec_push(&a, "-fPIC");\n        vec_push(&a, "-c"); vec_push(&a, source); vec_push(&a, "-o"); vec_push(&a, obj);'
)
replace_once(
    '    char outname[C_MAX_NAME + 4]; snprintf(outname, sizeof(outname), "%s%s", t->name, t->kind == C_TARGET_STATIC_LIBRARY ? ".a" : "");\n    path_join(output, profile_dir, outname);',
    '''    char outname[C_MAX_NAME + 16];
    if (t->kind == C_TARGET_STATIC_LIBRARY) snprintf(outname, sizeof(outname), "%s.a", t->name);
    else if (t->kind == C_TARGET_SHARED_LIBRARY) {
#ifdef __APPLE__
        snprintf(outname, sizeof(outname), "lib%s.dylib", t->name);
#else
        snprintf(outname, sizeof(outname), "lib%s.so", t->name);
#endif
    } else snprintf(outname, sizeof(outname), "%s", t->name);
    path_join(output, profile_dir, outname);'''
)
replace_once(
    '''        } else {
            StrVec a = {0}; vec_push(&a, opt->cc); compiler_append_linker(&a); for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states); vec_push(&a, "-o"); vec_push(&a, output);
            note("LINK", "%s", output); double link_started = compiler_perf_now_ms(); if (compiler_run_process(&a, opt->verbose) != 0) die("link failed"); link_ms = compiler_perf_now_ms() - link_started; vec_free(&a);
        }''',
    '''        } else {
            StrVec a = {0}; vec_push(&a, opt->cc); compiler_append_linker(&a);
            if (t->kind == C_TARGET_SHARED_LIBRARY) {
#ifdef __APPLE__
                vec_push(&a, "-dynamiclib");
#else
                vec_push(&a, "-shared");
#endif
            }
            for (size_t i = 0; i < objects.count; ++i) vec_push(&a, objects.items[i]);
            append_link_flags(&a, t, b, states); vec_push(&a, "-o"); vec_push(&a, output);
            note("LINK", "%s", output); double link_started = compiler_perf_now_ms(); if (compiler_run_process(&a, opt->verbose) != 0) die("link failed"); link_ms = compiler_perf_now_ms() - link_started; vec_free(&a);
        }'''
)

marker = '    compiler_profile_report(t->name, link_ms);\n    vec_free(&sources); vec_free(&compile_sources); vec_free(&objects); return output;\n}\n\nstatic void compiler_cmd_build_or_run(const Options *opt, bool run) {'
replacement = '''    compiler_profile_report(t->name, link_ms);
    vec_free(&sources); vec_free(&compile_sources); vec_free(&objects); return output;
}

static size_t compiler_target_index(C_Build *b, C_Target *t) {
    if (!b || !t) die("invalid target graph");
    ptrdiff_t idx = t - b->targets;
    if (idx < 0 || (size_t)idx >= b->target_count) die("target dependency does not belong to this build");
    return (size_t)idx;
}

static void compiler_append_target_link_closure(C_Build *b, C_Target *owner, C_Target *dep,
                                                char *graph_outputs[], bool seen[]) {
    size_t idx = compiler_target_index(b, dep);
    if (seen[idx]) return;
    seen[idx] = true;
    if (dep->kind != C_TARGET_STATIC_LIBRARY && dep->kind != C_TARGET_SHARED_LIBRARY)
        die("target %s links non-library target %s", owner->name, dep->name);
    if (!graph_outputs[idx]) die("internal target graph error for %s", dep->name);
    c__push(&owner->ldflags, graph_outputs[idx]);
    for (size_t i = 0; i < dep->target_dep_count; ++i)
        compiler_append_target_link_closure(b, owner, dep->target_deps[i], graph_outputs, seen);
}

static char *compiler_build_target_graph(C_Build *b, C_Target *t, DepState states[], const Options *opt,
                                         unsigned char graph_state[], char *graph_outputs[]) {
    size_t idx = compiler_target_index(b, t);
    if (graph_state[idx] == 1) die("cyclic target dependency involving %s", t->name);
    if (graph_state[idx] == 2) return xstrdup(graph_outputs[idx]);
    graph_state[idx] = 1;
    for (size_t i = 0; i < t->target_dep_count; ++i) {
        char *dep_output = compiler_build_target_graph(b, t->target_deps[i], states, opt, graph_state, graph_outputs);
        free(dep_output);
    }
    bool seen[C_MAX_TARGETS] = {0};
    for (size_t i = 0; i < t->target_dep_count; ++i)
        compiler_append_target_link_closure(b, t, t->target_deps[i], graph_outputs, seen);
    graph_outputs[idx] = compiler_build_target(b, t, states, opt);
    graph_state[idx] = 2;
    return xstrdup(graph_outputs[idx]);
}

static void compiler_free_graph_outputs(C_Build *b, char *graph_outputs[]) {
    for (size_t i = 0; i < b->target_count; ++i) free(graph_outputs[i]);
}

static void compiler_cmd_build_or_run(const Options *opt, bool run) {'''
replace_once(marker, replacement)

replace_once(
    '    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);\n    C_Target *t = select_target(b, opt); char *output = compiler_build_target(b, t, states, opt);',
    '    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);\n    unsigned char graph_state[C_MAX_TARGETS] = {0}; char *graph_outputs[C_MAX_TARGETS] = {0};\n    C_Target *t = select_target(b, opt); char *output = compiler_build_target_graph(b, t, states, opt, graph_state, graph_outputs);'
)
replace_once(
    '        int rc = compiler_run_process(&a, opt->verbose); vec_free(&a); free(output); free_build(b); exit(rc);\n    }\n    free(output); free_build(b);',
    '        int rc = compiler_run_process(&a, opt->verbose); vec_free(&a); free(output); compiler_free_graph_outputs(b, graph_outputs); free_build(b); exit(rc);\n    }\n    free(output); compiler_free_graph_outputs(b, graph_outputs); free_build(b);'
)

replace_once(
    '    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);\n    C_Target *targets[C_MAX_TARGETS] = {0};',
    '    DepState states[C_MAX_DEPS] = {0}; compiler_resolve_all(b, opt, states);\n    unsigned char graph_state[C_MAX_TARGETS] = {0}; char *graph_outputs[C_MAX_TARGETS] = {0};\n    C_Target *targets[C_MAX_TARGETS] = {0};'
)
replace_once(
    '        outputs[tests] = compiler_build_target(b, t, states, opt);',
    '        outputs[tests] = compiler_build_target_graph(b, t, states, opt, graph_state, graph_outputs);'
)
replace_once(
    '    for (size_t i = 0; i < tests; ++i) free(outputs[i]);\n    note("PASS", "%zu test target%s", tests, tests == 1 ? "" : "s");\n    free_build(b);',
    '    for (size_t i = 0; i < tests; ++i) free(outputs[i]);\n    compiler_free_graph_outputs(b, graph_outputs);\n    note("PASS", "%zu test target%s", tests, tests == 1 ? "" : "s");\n    free_build(b);'
)

path.write_text(s)
print('core upgrade applied')
