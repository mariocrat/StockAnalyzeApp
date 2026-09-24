"""Deprecated Phase A entrypoint. Do not import or execute any test targets."""

import sys


def main():
    print("Deprecated: run_phase_a_tests.py no longer executes tests. "
          "Use an explicitly approved Python executable with "
          "-I -B tests/run_isolated_tests.py --all (Python only), "
          "or pass explicit guarded module names to that runner.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
