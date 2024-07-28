from pathlib import Path

MAIN_EXECUTOR_HEADER = """#!/bin/bash
#SBATCH --export-file=jobs/%a/job_environment
#SBATCH --error=jobs/%a/slurm-%A.out
#SBATCH --output=jobs/%a/slurm-%A.out
#SBATCH --array=0-{count_m_1}
"""

MAIN_EXECUTOR_BODY = """
cd {root_dir}
cd jobs/%a/

sh job_run.sh
"""

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
