import argparse
import toml
import logging
import sys
from rich.logging import RichHandler

from . import create
from . import default
from . import slurm

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler()],
)
log = logging.getLogger("smatrix")

top_parser = argparse.ArgumentParser(
    description="Batch create slurm jobs, with more flexibility than --array"
)
subparsers = top_parser.add_subparsers(required=True)

create_parser = subparsers.add_parser("create")
create_parser.add_argument(
    "config", type=str, help="The .json file to configure smatrix"
)
create_parser.add_argument(
    "--start",
    action="store_true",
    help="Start any jobs, after the file structure has been created. Identical to running `sbatch executor.sh` from the root folder, or `smatrix start`.",
)
create_parser.set_defaults(func=create.create)

ps_parser = subparsers.add_parser("ps", description="See status of started job matrix")
ps_parser.add_argument(
    "--matrix-path",
    type=int,
    required=False,
    help="The path of the matrix which has been started",
)
ps_parser.set_defaults(func=slurm.ps)

default_parser = subparsers.add_parser(
    "default", description="Provides a default configuration file."
)
default_parser.add_argument("file", type=str, help="The .json path to output to")
default_parser.set_defaults(func=default.create_default)

top_parser.add_argument(
    "--verbose",
    action="store_true",
    help="Show debug logs",
)


def main():
    args = top_parser.parse_args()
    if args.verbose:
        log.setLevel("DEBUG")

    sys.exit(args.func(args))
