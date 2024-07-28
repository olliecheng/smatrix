from pathlib import Path
import subprocess
import re
import json
import logging

from rich.console import Console
from rich.table import Table

log = logging.getLogger("smatrix")

MAIN_EXECUTOR_HEADER = """#!/bin/bash
#SBATCH --export-file=jobs/%a/job_environment
#SBATCH --error=jobs/%a/slurm-%A.out
#SBATCH --output=jobs/%a/slurm-%A.out
#SBATCH --array=0-{count_m_1}
"""

MAIN_EXECUTOR_BODY = """
cd {root_dir}

echo $SLURM_JOB_ID > job_id

cd jobs/%a/

sh job_run.sh
"""


class SlurmException(Exception):
    pass


assert MAIN_EXECUTOR_BODY.startswith("\n")
assert MAIN_EXECUTOR_HEADER.endswith("\n")


def create_supplementary_files(cfg):
    parameters = "\n".join("#SBATCH " + x for x in cfg["general"]["params"])
    with open(cfg["root_dir"] / "executor.sh", "w") as f:
        f.write(
            MAIN_EXECUTOR_HEADER.format(count_m_1=cfg["count"] - 1, **cfg)
            + parameters
            + MAIN_EXECUTOR_BODY.format(**cfg)
        )


def execute_batch(cfg):
    result = subprocess.run(
        ["sbatch", cfg["root_dir"] / "executor.sh"],
        capture_output=True,
        text=True,
        check=True,
    )
    groups = re.match(r"^Submitted batch job (\d+)\n$", result.stdout, re.MULTILINE)
    if not groups:
        raise SlurmException(result.stdout + result.stderr)

    job_id = groups.group(1)
    return job_id


def ps(args):
    matrix_path = args.matrix_path
    if not matrix_path:
        # find it using path
        found = False
        matrix_path = None
        job_id = 0

        for job_f in Path(".").glob("**/job_id"):
            with open(job_f, "r") as f:
                try:
                    new_job_id = int(f.read())
                    if new_job_id > job_id:
                        job_id = new_job_id
                        matrix_path = job_f.parent
                except ValueError:
                    pass
        if not found:
            log.error(
                "Could not find valid job. Please manually provide one with '--job-id <JOB_ID>'. The job ID can be found in the job_id folder of the root directory."
            )
            return 1
    else:
        with open(matrix_path / Path("job_id"), "r") as f:
            job_id = int(f.read())

    result = subprocess.run(
        ["sacct", "-q", str(job_id), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    table = Table(title=f"Instances for matrix job {job_id}", expand=True)

    table.add_column("id")
    table.add_column("status")
    table.add_column("start")

    for job in data["jobs"]:
        id = job["array"]["task_id"]["number"]
        start = job["time"]["start"]
        status = " ".join(job["exit_code"]["status"])

        table.add_row(id, status, start)

    console = Console()
    console.print(table)
