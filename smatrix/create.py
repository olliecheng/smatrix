from . import config
from . import instances
from . import slurm

import sys
import logging
import itertools
import os

log = logging.getLogger("smatrix")


def create(args):
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
    if args.start:
        job_id = slurm.execute_batch(cfg)
        with open(cfg["root_dir"] / "job_id", "w") as f:
            f.write(str(job_id))
        log.info(
            f"[bold yellow]Started matrix with job ID {job_id}[/]",
            extra={"markup": True},
        )
    else:
        log.warn(
            f"[bold red]Did not start the matrix, as the --start flag was not passed. You can manually start it using:[/]",
            extra={"markup": True},
        )
        log.warn(
            f"$ sbatch {cfg['root_dir']}/executor.sh",
            extra={"markup": True},
        )
