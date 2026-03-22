from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m talaragworker")
    parser.add_argument("--mode", choices=("run", "doctor"), default="run")
    args = parser.parse_args()

    if args.mode == "doctor":
        from talaragworker.doctor import doctor

        raise SystemExit(doctor())

    from talaragworker.worker import run

    run()


if __name__ == "__main__":
    main()
