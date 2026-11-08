"""Compose Chagatai's one-root render models from a fresh structure cook."""
from argparse import ArgumentParser
import json
from pathlib import Path

from compose_buildings import ART, compose_asset, stock_game


def main():
    parser = ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("previous_catalog", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    args.output.mkdir()
    game = stock_game.current()
    listed = game.archiver.run(["list", str(args.archive), "--verify"])
    if not listed["archive"]["verification"]["verified"]:
        raise ValueError("Invalid model cook archive")
    source = args.output / "readback"
    game.archiver.run(["extract", str(args.archive), str(source), "--filter", ART])
    rows = json.loads(args.previous_catalog.read_bytes())
    results = []
    for row in rows:
        asset = row["asset"]
        if asset in ("melee", "ranged"):
            # Remove the two-state age program that failed to load. Retain
            # the first playable appearance and its construction/ruin meshes.
            age = "m1" if asset == "melee" else "r2"
            states = {
                "healthy": ("healthy", "preview", "targeting", *(f"damage_{i}" for i in range(1, 6))),
                **{f"{age}_frame{i:02}": tuple(f"construct_{j:02}" for j in range(i, i + 25, 5))
                   for i in (0, 25, 50, 75)},
                f"{age}_ruins": ("ruins",),
            }
            result = compose_asset(asset, source, args.output / "art", None, states=states)
            result["state_groups"] = {"healthy": list(states["healthy"])}
            result["stage_aliases"] = {stage: stage.removeprefix(age + "_") for stage in states}
        else:
            from compose_buildings import STATES
            keys = [name.removeprefix(asset + "_") for name in row["states"]]
            groups = STATES | {f"damage_{i}": (f"damage_{i}",) for i in range(1, 6)}
            result = compose_asset(asset, source, args.output / "art", None,
                                   states={key: groups[key] for key in keys})
        results.append(result)
    (args.output / "buildings.json").write_text(json.dumps(results, indent=2) + "\n", encoding="utf-8")
    print(f"Composed {len(results)} one-root building models")


if __name__ == "__main__":
    main()
