from schema import (
    Schema,
    And,
    Use,
    Optional,
    Or,
    Regex,
    Forbidden,
    SchemaError,
)
import toml
import os
from rich.pretty import pretty_repr
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from string import Template

import logging

log = logging.getLogger("smatrix")

DEFAULT_ARRAY_EXEC_BODY = """

"""

LOAD_ENVIRONMENT = """
#!/bin/bash

while IFS= read -r -d $'\0' var
do
   export "$var"
done < job_environment
"""


def validate(input_file):
    SH_VAR_NAME = Regex(
        r"^[a-zA-Z_][a-zA-Z_0-9]+$",
        error="Not a valid Bash variable name: {}",
    )

    schema = Schema(
        And(
            Use(toml.load),
            {
                "general": {
                    "name": str,
                    "params": [str],
                    # the instance and root labels are both optional
                    Optional(
                        "instance_label", default="${MATRIX_JOB_ID}_${MATRIX_JOB_LABEL}"
                    ): str,
                    Optional("root_label", default="%Y%m%d_%H%M_$MATRIX_NAME"): str,
                },
                # each string key value should be accompanied by a corresponding string or dictionary of parameters
                "matrix": {
                    SH_VAR_NAME: [
                        Or(
                            str,  # it can either be a string value...
                            int,  # or an int...
                            # or a dictionary of string/int values
                            {SH_VAR_NAME: Or(str, int)},
                        )
                    ],
                },
                # We do pathing later, after all substitutions have been made
                Optional("symlinks"): {Optional(str): str},
                # Copying
                Optional("copies"): {
                    Optional(str): {
                        "path": str,
                        Optional("template", default=False): bool,
                    }
                },
                # the actual script to run
                "script": {
                    "slurm_exec": str,
                    Optional("load_env.sh", default=LOAD_ENVIRONMENT): str,
                    Optional(str): str,
                },
            },
        )
    )

    try:
        config = schema.validate(input_file)
        config["root_dir"] = get_root_directory(config)
        config["job_dir"] = config["root_dir"] / "jobs"

        log.info("Loaded config:\n%s", pretty_repr(config))
        return config
    except SchemaError as err:
        # handle bash variable name issue manually
        import re

        match = re.match(
            r"Key 'matrix' error:\nWrong key '(.+)' in {'", str(err), re.MULTILINE
        )
        if match:
            keyname = match.group(1)
            raise SchemaError(
                f"Matrix variable '{keyname}' must be a valid Bash variable name"
            )

        # otherwise, propagate
        raise err


def get_root_directory(config):
    envs = get_environment(config)
    label = template_envs(config["general"]["root_label"], envs)

    now = datetime.now()
    return Path(now.strftime(label)).resolve(strict=False)


def get_environment(config, state=dict(), id=None):
    flattened_state = dict()

    if state:
        job_labels = []
        for k, v in state.items():
            if isinstance(v, dict):
                v_repr = v.get(
                    "label",
                    next(
                        iter(v.values())
                    ),  # by default, return the first dictionary value
                )
                # flatten
                for k2, v2 in v.items():
                    flattened_state[f"{k}_{k2}"] = v2
            else:
                v_repr = str(v)
                flattened_state[k] = v
            job_labels.append(v_repr)
        job_label = "_".join(job_labels)
    else:
        job_label = None

    new_cfg = {
        **flattened_state,
        **{
            "MATRIX_NAME": config["general"]["name"],
            "MATRIX_JOB_ID": id,
            "MATRIX_JOB_LABEL": job_label,
        },
    }
    return new_cfg


def template_envs(s, envs):
    return Template(s).substitute(**envs)
