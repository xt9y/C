from pathlib import Path

p = Path('src/cli.c')
s = p.read_text()
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
        uint64_t state_hash = hash_string(command);
        if (input[0]) {
            if (!file_exists(input)) die("generated input not found: %s", input);
            uint64_t input_hash = 0;
            if (!compiler_hash_file(input, &input_hash)) die("cannot hash generated input: %s", input);
            state_hash = hash_update(state_hash, &input_hash, sizeof(input_hash));
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
        char state_hex[17]; hash_u64_hex(state_hash, state_hex);
        if (strcmp(previous, state_hex)) need = true;
'''
if s.count(old) != 1:
    raise SystemExit(f'expected one generator freshness block, found {s.count(old)}')
s = s.replace(old, new, 1)
s = s.replace('fprintf(out, "%s\\n", command_hash)', 'fprintf(out, "%s\\n", state_hex)', 1)
p.write_text(s)
