# One-shot repair for generated-source content invalidation.
from pathlib import Path

p = Path('src/cli.c')
s = p.read_text()
needle = '''static bool compiler_read_depfile(const char *path, StrVec *deps) {'''
helper = '''static bool compiler_hash_file_uncached(const char *path, uint64_t *out) {
    FILE *f = fopen(path, "rb");
    if (!f) return false;
    uint64_t h = 1469598103934665603ULL;
    unsigned char buf[32768];
    size_t n;
    while ((n = fread(buf, 1, sizeof(buf), f))) h = hash_update(h, buf, n);
    if (ferror(f)) { fclose(f); return false; }
    if (fclose(f) != 0) return false;
    *out = h;
    return true;
}

static bool compiler_read_depfile(const char *path, StrVec *deps) {'''
if s.count(needle) != 1:
    raise SystemExit(f'helper insertion match count: {s.count(needle)}')
s = s.replace(needle, helper, 1)
old = '''        bool need = !file_exists(output);
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
'''
new = '''        bool need = !file_exists(output);
        uint64_t input_hash = 0;
        if (input[0] && !compiler_hash_file_uncached(input, &input_hash))
            die("generated input not found or unreadable: %s", input);
        uint64_t desired_state = hash_string(command);
        desired_state = hash_update(desired_state, &input_hash, sizeof(input_hash));
        char desired_hex[17]; hash_u64_hex(desired_state, desired_hex);

        uint64_t h = hash_string(t->name);
        h = hash_update(h, output, strlen(output));
        char key[17]; hash_u64_hex(h, key);
        char stamp[PATH_MAX]; path_join(stamp, state_root, key);
        FILE *sf = fopen(stamp, "r");
        char previous_state[17] = {0};
        char previous_output[17] = {0};
        if (!sf || fscanf(sf, "%16s %16s", previous_state, previous_output) != 2) need = true;
        if (sf) fclose(sf);
        if (strcmp(previous_state, desired_hex)) need = true;
        if (!need) {
            uint64_t output_hash = 0;
            char output_hex[17];
            if (!compiler_hash_file_uncached(output, &output_hash)) need = true;
            else {
                hash_u64_hex(output_hash, output_hex);
                if (strcmp(previous_output, output_hex)) need = true;
            }
        }
'''
if s.count(old) != 1:
    raise SystemExit(f'generator freshness match count: {s.count(old)}')
s = s.replace(old, new, 1)
old2 = '''        FILE *out = fopen(temp, "w");
        if (!out) die("cannot write generator state: %s", strerror(errno));
        if (fprintf(out, "%s\\n", command_hash) < 0 || fflush(out) != 0 || fsync(fileno(out)) != 0 || fclose(out) != 0) {
            unlink(temp); die("cannot persist generator state");
        }
'''
new2 = '''        uint64_t generated_hash = 0;
        if (!compiler_hash_file_uncached(output, &generated_hash)) die("cannot hash generated output: %s", output);
        char generated_hex[17]; hash_u64_hex(generated_hash, generated_hex);
        FILE *out = fopen(temp, "w");
        if (!out) die("cannot write generator state: %s", strerror(errno));
        if (fprintf(out, "%s %s\\n", desired_hex, generated_hex) < 0 || fflush(out) != 0 || fsync(fileno(out)) != 0 || fclose(out) != 0) {
            unlink(temp); die("cannot persist generator state");
        }
'''
if s.count(old2) != 1:
    raise SystemExit(f'generator state write match count: {s.count(old2)}')
s = s.replace(old2, new2, 1)
p.write_text(s)
print('generated source content invalidation repair applied')
