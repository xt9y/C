#!/usr/bin/env python3

import json
import subprocess
import tempfile
import time
from pathlib import Path

import benchmark_curve as legacy
import benchmark_impl as impl
import benchmark_stats as stats
from curve_selector import choose_ranges


TARGETS = legacy.TARGETS
RUNS = legacy.RUNS
HISTORY_LIMIT = legacy.HISTORY_LIMIT
BASE = legacy.BASE
CHANGE = legacy.CHANGE


def modified_paths(repo, base):
    """Paths modified in both revisions; additions/deletions stay at endpoint."""
    text = subprocess.check_output(
        ["git", "diff", "--name-only", "--diff-filter=M", base, CHANGE, "--"],
        cwd=repo,
        text=True,
    )
    return sorted({line for line in text.splitlines() if line})


def select_ranges(repo, deps):
    commits = subprocess.check_output(
        [
            "git",
            "rev-list",
            "--first-parent",
            f"--max-count={HISTORY_LIMIT}",
            CHANGE,
        ],
        cwd=repo,
        text=True,
    ).splitlines()
    try:
        anchor = commits.index(BASE)
    except ValueError as exc:
        raise RuntimeError("anchor base is not in endpoint first-parent history") from exc

    candidates = []
    large_at = None
    paths_by_revision = {}
    for index in range(anchor + 1, len(commits)):
        revision = commits[index]
        paths = modified_paths(repo, revision)
        paths_by_revision[revision] = paths
        count = legacy.predicted(deps, set(paths))
        if 4 < count < len(deps):
            candidates.append((revision, index, count, len(paths)))
            if count >= max(TARGETS) and large_at is None:
                large_at = index
        if large_at is not None and index >= large_at + 60:
            break

    chosen = choose_ranges(candidates, TARGETS, len(deps))
    chosen_targets = {target for target, _ in chosen}
    for target in TARGETS:
        if target not in chosen_targets:
            print(f"curve target={target} skipped: no suitable real SDL modified-file range")

    if not chosen:
        print("curve warning: no extra historical points found; baseline and clean points remain valid")
        return []

    selected = []
    for target, item in chosen:
        revision, _, count, _ = item
        paths = paths_by_revision[revision]
        selected.append(
            {
                "target_tus": target,
                "base": revision,
                "predicted_tus": count,
                "applied_files": len(paths),
                "applied_paths": paths,
                "change_stats": legacy.range_change_stats(repo, revision),
            }
        )
    return selected


def reset_endpoint(repo):
    impl.run(
        ["git", "reset", "--hard", "--quiet", CHANGE],
        cwd=repo,
        quiet=True,
    )


def set_historical_state(repo, base, paths):
    # Keep the endpoint commit/build graph checked out. Only files that were
    # modified in both revisions receive their real historical contents.
    reset_endpoint(repo)
    if paths:
        impl.run(
            ["git", "checkout", "--quiet", base, "--", *paths],
            cwd=repo,
            quiet=True,
        )


def restore_endpoint_paths(repo, paths):
    # Object-change accounting is mtime based, so make the content transition
    # unambiguously newer even on coarse filesystems.
    time.sleep(1.05)
    if paths:
        impl.run(
            ["git", "checkout", "--quiet", CHANGE, "--", *paths],
            cwd=repo,
            quiet=True,
        )


def profile_range(repo, command, point, root, *, marker=None, cwd=None, env=None):
    samples = []
    rebuilt = None
    paths = point["applied_paths"]
    base = point["base"]

    try:
        for index in range(RUNS):
            set_historical_state(repo, base, paths)
            impl.run(command, cwd=cwd, env=env, quiet=True)
            before = stats.object_snapshot(root, marker=marker) if index == 0 else None

            restore_endpoint_paths(repo, paths)
            samples.append(stats.profiled(command, cwd=cwd, env=env))

            if before is not None:
                after = stats.object_snapshot(root, marker=marker)
                rebuilt = len(stats.changed_objects(before, after))
    except subprocess.CalledProcessError as exc:
        print(
            f"curve target={point['target_tus']} skipped: historical file state "
            f"does not build with this fixed endpoint graph ({exc.returncode})"
        )
        return None
    finally:
        reset_endpoint(repo)

    if rebuilt is None:
        return None
    return stats.summarize(samples), rebuilt


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

        impl.run(impl.cmake_build_cmd(meta, jobs), quiet=True)
        deps = legacy.dependency_sets(meta, sdl)
        if len(deps) != source_count:
            raise RuntimeError(
                f"Ninja dependency map has {len(deps)} TUs; expected {source_count}"
            )

        ranges = select_ranges(sdl, deps)
        for point in ranges:
            info = point["change_stats"]
            print(
                f"curve target={point['target_tus']} "
                f"predicted={point['predicted_tus']} "
                f"commits={info['commits']} applied_files={point['applied_files']} "
                f"base={point['base'][:8]}"
            )

        ninja_build = work / "ninja"
        reset_endpoint(sdl)
        impl.run(stats.cmake_args(sdl, ninja_build), quiet=True)
        ninja_cmd = impl.cmake_build_cmd(ninja_build, jobs)
        impl.run(ninja_cmd, quiet=True)

        c_cache = work / "c-cache"
        c_env = stats.c_env(c_cache)
        c_cmd = stats.c_cmd(jobs)
        impl.run(c_cmd, cwd=cproj, env=c_env, quiet=True)

        points = []
        for point in ranges:
            ninja = profile_range(
                sdl,
                ninja_cmd,
                point,
                ninja_build,
                marker="SDL3-static.dir",
            )
            if ninja is None:
                continue

            c_result = profile_range(
                sdl,
                c_cmd,
                point,
                cproj / "build",
                cwd=cproj,
                env=c_env,
            )
            if c_result is None:
                continue

            ninja_profile, ninja_tus = ninja
            c_profile, c_tus = c_result
            if c_tus != ninja_tus:
                print(
                    f"curve target={point['target_tus']} skipped: unfair rebuild counts "
                    f"c={c_tus} ninja={ninja_tus}"
                )
                continue

            points.append(
                {
                    **point,
                    "rebuilt_tus": c_tus,
                    "c": c_profile,
                    "cmake_ninja": ninja_profile,
                }
            )
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
            "history_mode": "fixed endpoint tree with real historical modified-file contents",
            "points": points,
        }
        print("CURVE_JSON=" + json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
