import argparse
import toml
import itertools
from wat import wat
from rich.console import Console
from rich import inspect
import sys

import logging
from rich.logging import RichHandler

import os

from . import instances
from . import config
from . import slurm

FORMAT = "%(message)s"
logging.basicConfig(
    level="INFO",
    format=FORMAT,
    datefmt="[%X]",
    handlers=[RichHandler()],
)
log = logging.getLogger("smatrix")

parser = argparse.ArgumentParser(
    description="Batch create slurm jobs, with more flexibility than --array"
)
parser.add_argument("config", type=str, help="The .json file to configure smatrix")
parser.add_argument(
    "--dry-run",
    action="store_true",
    help="Create the file structure, but do not start any jobs.",
)
parser.add_argument(
    "--verbose",
    action="store_true",
    help="Show debug logs",
)


def main():
    args = parser.parse_args()
    dry_run = args.dry_run
    if args.verbose:
        log.setLevel("DEBUG")

    if dry_run:
        log.warn(
            f"[bold yellow]smatrix is running in dry run mode. No jobs will be started, but all files will be created.[/]",
            extra={"markup": True},
        )

    log.info(f"Creating matrix from '{args.config}'")

    try:
        with open(args.config, "r") as config_file:
            cfg = config.validate(config_file)
    except Exception as err:
        log.error(
            "[bold red]Failed to load config file:[/bold red]\n%s",
            err,
            extra={"markup": True},
        )
        sys.exit(1)

    cfg["dry_run"] = dry_run
    log.info(f"Using root directory '{cfg['root_dir']}'")

    # will make jobs and root dir (as job dir is a subdirectory)
    os.makedirs(cfg["job_dir"], exist_ok=False)

    # create iteration matrix
    # NB: as this requires Python ^3.6, dict key order is preserved
    keys = cfg["matrix"].keys()
    values = cfg["matrix"].values()
    matrix = [
        (id, dict(zip(keys, inst)))
        for id, inst in enumerate(itertools.product(*values))
    ]
    cfg["count"] = len(matrix)

    for id, state in matrix:
        inst = instances.Instance(state, cfg, id)
        inst.update_filesystem()
        inst.write_files()

        # create symlink
        os.symlink(inst.dir, cfg["job_dir"] / str(inst.id))

    slurm.create_supplementary_files(cfg)
