from pathlib import Path
import subprocess
import re

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
        ["sbatch", cfg["root_dir"] / "executor.sh"], capture_output=True, text=True
    )
    groups = re.match(r"^Submitted batch job (\d+)\n$", result.stdout, re.MULTILINE)
    if not groups:
        raise SlurmException(result.stdout + result.stderr)

    job_id = groups.group(1)
    with open(cfg["root_dir"] / "job_id", "w") as f:
        f.write(str(job_id))


def ps(args):
    print("ps")
