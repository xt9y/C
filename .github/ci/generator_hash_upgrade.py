from pathlib import Path

path = Path('src/cli.c')
s = path.read_text()
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
        if (input[0]) {
            if (!compiler_hash_file(input, &input_hash)) die("generated input not found or unreadable: %s", input);
        }
        uint64_t desired_hash_value = hash_string(command);
        desired_hash_value = hash_update(desired_hash_value, &input_hash, sizeof(input_hash));
        char desired_hash[17]; hash_u64_hex(desired_hash_value, desired_hash);

        uint64_t h = hash_string(t->name);
        h = hash_update(h, output, strlen(output));
        char key[17]; hash_u64_hex(h, key);
        char stamp[PATH_MAX]; path_join(stamp, state_root, key);
        FILE *sf = fopen(stamp, "r");
        char previous_state[17] = {0};
        char previous_output[17] = {0};
        if (!sf || fscanf(sf, "%16s %16s", previous_state, previous_output) != 2) need = true;
        if (sf) fclose(sf);
        if (strcmp(previous_state, desired_hash)) need = true;
        if (!need) {
            uint64_t current_output_hash = 0;
            char current_output[17];
            if (!compiler_hash_file(output, &current_output_hash)) need = true;
            else {
                hash_u64_hex(current_output_hash, current_output);
                if (strcmp(previous_output, current_output)) need = true;
            }
        }
'''
if s.count(old) != 1:
    raise SystemExit(f'expected one generator freshness block, found {s.count(old)}')
s = s.replace(old, new, 1)
old2 = '''        FILE *out = fopen(temp, "w");
        if (!out) die("cannot write generator state: %s", strerror(errno));
        if (fprintf(out, "%s\\n", command_hash) < 0 || fflush(out) != 0 || fsync(fileno(out)) != 0 || fclose(out) != 0) {
            unlink(temp); die("cannot persist generator state");
        }
'''
new2 = '''        uint64_t output_hash_value = 0;
        if (!compiler_hash_file(output, &output_hash_value)) die("cannot hash generated output: %s", output);
        char output_hash[17]; hash_u64_hex(output_hash_value, output_hash);
        FILE *out = fopen(temp, "w");
        if (!out) die("cannot write generator state: %s", strerror(errno));
        if (fprintf(out, "%s %s\\n", desired_hash, output_hash) < 0 || fflush(out) != 0 || fsync(fileno(out)) != 0 || fclose(out) != 0) {
            unlink(temp); die("cannot persist generator state");
        }
'''
if s.count(old2) != 1:
    raise SystemExit(f'expected one generator stamp block, found {s.count(old2)}')
path.write_text(s.replace(old2, new2, 1))
print('generator hashing hardening applied')
