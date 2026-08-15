#!/usr/bin/env python3

import subprocess

import benchmark_curve as curve


def choose_ranges(candidates, targets, total):
    """Choose increasing real rebuild sizes without requiring every target."""
    by_count = {}
    for item in candidates:
        _, index, count, _ = item
        if not 4 < count < total:
            continue
        current = by_count.get(count)
        if current is None or index < current[1]:
            by_count[count] = item

    available = sorted(by_count.values(), key=lambda item: item[2])
    selected = []
    previous_count = 4

    for position, target in enumerate(targets):
        eligible = [item for item in available if item[2] > previous_count]
        if not eligible:
            break

        chosen = min(
            eligible,
            key=lambda item: (abs(item[2] - target), item[2], item[1]),
        )

        # Sparse real SDL history is valid. If the closest available point is
        # already closer to the next target, skip this target instead of
        # failing or consuming the next point.
        if position + 1 < len(targets):
            midpoint = (target + targets[position + 1]) / 2.0
            if chosen[2] > midpoint:
                continue

        selected.append((target, chosen))
        previous_count = chosen[2]

    return selected


def select_ranges(repo, deps, sources):
    commits = subprocess.check_output(
        [
            "git",
            "rev-list",
            "--first-parent",
            f"--max-count={curve.HISTORY_LIMIT}",
            curve.CHANGE,
        ],
        cwd=repo,
        text=True,
    ).splitlines()
    try:
        anchor = commits.index(curve.BASE)
    except ValueError as exc:
        raise RuntimeError("anchor base is not in endpoint first-parent history") from exc

    candidates = []
    large_at = None
    for index in range(anchor + 1, len(commits)):
        revision = commits[index]
        changed = curve.changed_paths(repo, revision)
        count = curve.predicted(deps, changed)
        if 4 < count < len(deps):
            candidates.append((revision, index, count, len(changed)))
            if count >= max(curve.TARGETS) and large_at is None:
                large_at = index
        if large_at is not None and index >= large_at + 60:
            break

    # A fixed endpoint build graph can only use bases that still contain all
    # endpoint source files. Check every real candidate, not only the closest
    # 30, then adapt to whichever rebuild sizes SDL history actually offers.
    compatible_candidates = [
        item for item in candidates if curve.compatible(repo, item[0], sources)
    ]
    chosen = choose_ranges(compatible_candidates, curve.TARGETS, len(deps))

    if len(chosen) < 3:
        available = sorted({item[2] for item in compatible_candidates})
        raise RuntimeError(
            "not enough compatible SDL history points for a scaling curve; "
            f"available rebuilt-TU predictions: {available}"
        )

    chosen_targets = {target for target, _ in chosen}
    for target in curve.TARGETS:
        if target not in chosen_targets:
            print(f"curve target={target} skipped: no suitable real SDL range")

    selected = []
    for target, item in chosen:
        revision, _, count, files = item
        selected.append(
            {
                "target_tus": target,
                "base": revision,
                "predicted_tus": count,
                "predicted_changed_files": files,
                "change_stats": curve.range_change_stats(repo, revision),
            }
        )
    return selected
