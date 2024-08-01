from pathlib import Path
import subprocess
import re
import json
import logging
import copy

from rich.console import Console
from rich.table import Table
from rich.text import Text

log = logging.getLogger("smatrix")

MAIN_EXECUTOR_HEADER = """#!/bin/bash
#SBATCH --error=jobs/%a/slurm-%A.out
#SBATCH --output=jobs/%a/slurm-%A.out
#SBATCH --chdir={root_dir}
#SBATCH --array=0-{count_m_1}{concurrent}
"""

MAIN_EXECUTOR_BODY = """
set -e

cd {root_dir}
echo $SLURM_ARRAY_JOB_ID > job_id
cd jobs/$SLURM_ARRAY_TASK_ID/
source load_env.sh

sh job_run.sh
"""


class SlurmException(Exception):
    pass


assert MAIN_EXECUTOR_BODY.startswith("\n")
assert MAIN_EXECUTOR_HEADER.endswith("\n")


def create_supplementary_files(cfg):
    # parameters = "\n".join("#SBATCH " + x for x in cfg["general"]["params"])
    parameters = cfg["general"]["params"]

    if cfg["general"]["concurrent"]:
        concurrent = "%" + str(cfg["general"]["concurrent"])
    else:
        concurrent = ""

    with open(cfg["root_dir"] / "executor.sh", "w") as f:
        f.write(
            MAIN_EXECUTOR_HEADER.format(
                count_m_1=cfg["count"] - 1, concurrent=concurrent, **cfg
            )
            + parameters
            + MAIN_EXECUTOR_BODY.format(**cfg)
        )

    with open(cfg["root_dir"] / "matrix_config_snapshot.json", "w") as f:
        json.dump(cfg, f, default=str)


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


def find_loc_of_executing(args):
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
                    found = True
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
    return matrix_path, job_id


def ps(args):
    matrix_path, job_id = find_loc_of_executing(args)

    log.info(f"Using matrix at location {matrix_path}")

    result = subprocess.run(
        ["sacct", "-j", str(job_id), "--json"],
        capture_output=True,
        text=True,
        check=True,
    )
    data = json.loads(result.stdout)

    with open(matrix_path / "matrix_config_snapshot.json", "r") as f:
        cfg = json.load(f)

    jobs = []
    current_idx = 0
    for job in data["jobs"]:
        if job["array"]["task_id"]["set"]:
            current_idx = job["array"]["task_id"]["number"]
            jobs.append(job)
        else:
            for i in range(current_idx + 1, cfg["count"]):
                new_job = copy.deepcopy(job)
                new_job["array"]["task_id"]["set"] = True
                new_job["array"]["task_id"]["number"] = i

                jobs.append(new_job)

    table = Table(title=f"Instances for matrix job {job_id}", expand=True)

    table.add_column("id")
    table.add_column("status")
    table.add_column("start")

    for job in jobs:
        id = str(job["array"]["task_id"]["number"])
        start = str(job["time"]["start"])

        status_raw = " ".join(job["state"]["current"])
        # status_raw = job["state"]["current"]
        status = Text(status_raw)

        # add colour
        if "FAILED" in status_raw:
            status.stylize("bold red")
        elif "COMPLETED" in status_raw:
            status.stylize("bright_green")
        elif "RUNNING" in status_raw:
            status.stylize("magenta")

        table.add_row(id, status, start)

    console = Console()
    console.print(table)
