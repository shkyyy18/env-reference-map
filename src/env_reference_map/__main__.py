from . import core
from .common import main


def cli():
    return main(core, "env-reference-map")


if __name__ == "__main__":
    raise SystemExit(cli())
