import sys

if __package__:
    from . import cli
else:
    from pathlib import Path

    HERE = Path(__file__).resolve().parents[0]
    sys.path[:] = [str(HERE.parents[0])] + [p for p in sys.path if Path(p).resolve() != HERE]
    import stay_safe.cli as cli

if __name__ == "__main__":
    sys.exit(cli.main())
