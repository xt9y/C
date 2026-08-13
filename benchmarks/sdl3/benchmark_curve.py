#!/usr/bin/env python3

import json
import subprocess
import tempfile
from pathlib import Path

import benchmark_impl as impl
import benchmark_stats as stats

TARGETS = (8, 16, 32, 64, 128, 192)
RUNS = 3
HISTORY_LIMIT = 600
BASE = stats.BASE
CHANGE = stats.CHANGE


def repo_sources(meta, sdl):
    root = sdl.resolve()
    out = []
    for _, _, source in impl.static_entries(meta / "compile_commands.json"):
        try:
            out.append(str(source.resolve().relative_to(root)))
        except ValueError:
            pass
    return sorted(set(out))


def dependency_sets(build, sdl):
    text = subprocess.check_output(
        ["ninja", "-C", str(build), "-t", "deps"], text=True
    )
    root = sdl.resolve()
    result = []
    current = None
    for line in text.splitlines():
        if line and not line[0].isspace():
            target = line.split(":", 1)[0]
            current = set() if "SDL3-static.dir" in target and target.endswith(".o") else None
            if current is not None:
                result.append(current)
            continue
        if current is None:
            continue
        dep = line.strip()
        if not dep:
            continue
        try:
            current.add(str(Path(dep).resolve().relative_to(root)))
        except (ValueError, OSError):
            pass
    return [item for item in result if item]


def changed_paths(repo, base):
    text = subprocess.check_output(
        ["git", "diff", "--name-only", base, CHANGE, "--"],
        cwd=repo,
        text=True,
    )
    return {line for line in text.splitlines() if line}


def predicted(dep_sets, changed):
    return sum(bool(deps & changed) for deps in dep_sets)


def compatible(repo, revision, sources):
    text = subprocess.check_output(
        ["git", "ls-tree", "-r", "--name-only", revision],
        cwd=repo,
        text=True,
    )
    present = set(text.splitlines())
    return all(path in present for path in sources)


def select_ranges(repo, deps, sources):
    commits = subprocess.check_output(
        ["git", "rev-list", "--first-parent", f"--max-count={HISTORY_LIMIT}", CHANGE],
        cwd=repo,
        text=True,
    ).splitlines()
    try:
        anchor = commits.index(BASE)
    except ValueError as exc:
        raise RuntimeError("anchor base is not in endpoint first-parent history") from exc

    candidates = []
    large_at = None
    for index in range(anchor + 1, len(commits)):
        revision = commits[index]
        changed = changed_paths(repo, revision)
        count = predicted(deps, changed)
        if 4 < count < len(deps):
            candidates.append((revision, index, count, len(changed)))
            if count >= max(TARGETS) and large_at is None:
                large_at = index
        if large_at is not None and index >= large_at + 60:
            break

    selected = []
    prev_index = anchor
    prev_count = 4
    for target in TARGETS:
        ranked = sorted(
            (
                item for item in candidates
                if item[1] > prev_index and item[2] > prev_count
            ),
            key=lambda item: (abs(item[2] - target), item[1]),
        )
        chosen = next(
            (item for item in ranked[:30] if compatible(repo, item[0], sources)),
            None,
        )
        if chosen is None:
            raise RuntimeError(f"no compatible SDL history range near {target} TUs")
        revision, index, count, files = chosen
        selected.append({
            "target_tus": target,
            "base": revision,
            "predicted_tus": count,
            "predicted_changed_files": files,
            "change_stats": stats.change_stats(repo, revision, CHANGE),
        })
        prev_index = index
        prev_count = count
    return selected


def profile_range(repo, command, base, *, cwd=None, env=None):
    samples = []
    for _ in range(RUNS):
        impl.checkout(repo, base)
        impl.run(command, cwd=cwd, env=env, quiet=True)
        stats.checkout_with_gap(repo, CHANGE)
        samples.append(stats.profiled(command, cwd=cwd, env=env))
    return stats.summarize(samples)


def actual_rebuilt(repo, command, base, root, *, marker=None, cwd=None, env=None):
    impl.checkout(repo, base)
    impl.run(command, cwd=cwd, env=env, quiet=True)
    before = stats.object_snapshot(root, marker=marker)
    stats.checkout_with_gap(repo, CHANGE)
    impl.run(command, cwd=cwd, env=env, quiet=True)
    after = stats.object_snapshot(root, marker=marker)
    return len(stats.changed_objects(before, after))


def main():
    jobs = int(__import__("os").environ.get("BENCH_JOBS", 2))
    impl.run(["make"], cwd=stats.ROOT, quiet=True)

    with tempfile.TemporaryDirectory(prefix="c-sdl3-curve-") as directory:
        work = Path(directory)
        sdl = work / "SDL"
        impl.run(["git", "clone", "--quiet", impl.SDL_REPO, str(sdl)])
        impl.checkout(sdl, CHANGE)

        meta = work / "meta"
        impl.run(stats.cmake_args(sdl, meta), quiet=True)
        cproj = work / "cproj"
        source_count, _ = impl.generate_build_c(meta, cproj, sdl)
        sources = repo_sources(meta, sdl)

        impl.run(impl.cmake_build_cmd(meta, jobs), quiet=True)
        deps = dependency_sets(meta, sdl)
        if len(deps) != source_count:
            raise RuntimeError(
                f"Ninja dependency map has {len(deps)} TUs; expected {source_count}"
            )

        ranges = select_ranges(sdl, deps, sources)
        for point in ranges:
            info = point["change_stats"]
            print(
                f"curve target={point['target_tus']} "
                f"predicted={point['predicted_tus']} "
                f"commits={info['commits']} files={info['files_changed']} "
                f"base={point['base'][:8]}"
            )

        ninja_build = work / "ninja"
        impl.checkout(sdl, CHANGE)
        impl.run(stats.cmake_args(sdl, ninja_build), quiet=True)
        ninja_cmd = impl.cmake_build_cmd(ninja_build, jobs)
        impl.run(ninja_cmd, quiet=True)

        c_cache = work / "c-cache"
        c_env = stats.c_env(c_cache)
        c_cmd = stats.c_cmd(jobs)
        impl.run(c_cmd, cwd=cproj, env=c_env, quiet=True)

        points = []
        for point in ranges:
            base = point["base"]
            ninja_profile = profile_range(sdl, ninja_cmd, base)
            ninja_tus = actual_rebuilt(
                sdl, ninja_cmd, base, ninja_build, marker="SDL3-static.dir"
            )
            c_profile = profile_range(
                sdl, c_cmd, base, cwd=cproj, env=c_env
            )
            c_tus = actual_rebuilt(
                sdl, c_cmd, base, cproj / "build", cwd=cproj, env=c_env
            )
            if c_tus != ninja_tus:
                raise RuntimeError(
                    f"unfair curve point {point['target_tus']}: "
                    f"c rebuilt {c_tus}, Ninja rebuilt {ninja_tus}"
                )
            points.append({
                **point,
                "rebuilt_tus": c_tus,
                "c": c_profile,
                "cmake_ninja": ninja_profile,
            })
            print(
                f"curve actual={c_tus} "
                f"c={c_profile['wall_ms']:.1f}ms "
                f"ninja={ninja_profile['wall_ms']:.1f}ms"
            )

        result = {
            "endpoint": CHANGE,
            "source_count": source_count,
            "jobs": jobs,
            "runs_per_point": RUNS,
            "targets": list(TARGETS),
            "points": points,
        }
        print("CURVE_JSON=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
