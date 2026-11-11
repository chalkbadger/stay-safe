"""Run stay-safe as `python3 -m stay_safe`, or as `python3 stay_safe` from the checkout (issue #48).

Python compiles this whole file before running it as a script, so it must parse on older Pythons, such as 3.9.
"""
import sys

if __package__:
    from . import cli
else:
    # `python3 stay_safe` runs this file outside its package. Put the checkout folder, rather than this one, first on
    # the path, as `python3 -m stay_safe` from the checkout does, then import the package by name, so its version
    # check in __init__.py runs before anything that needs Python 3.11.
    from pathlib import Path

    HERE = Path(__file__).resolve().parents[0]
    sys.path[:] = [str(HERE.parents[0])] + [p for p in sys.path if Path(p).resolve() != HERE]
    import stay_safe.cli as cli

if __name__ == "__main__":
    sys.exit(cli.main())
