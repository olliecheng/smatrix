import logging
import os
import csv
import time

from rich.console import Console
from rich.table import Table
from rich.style import Style
from rich.text import Text

from . import create
from . import config

log = logging.getLogger("smatrix")


def generate(args):
    shell_file = args.shell_file
    parameters = args.parameters
    name = args.name or time.strftime("%Y%m%d-%H%M")
    log.info(f"Creating a matrix job at directory '{name}' with parameters:")

    has_shebang = False
    start_commands = []
    with open(shell_file, "r") as f:
        shebang_line = f.readline()
        if shebang_line.startswith("#!"):
            has_shebang = True
        else:
            start_commands.append(shebang_line.rstrip())

        for line in f:
            if not line.startswith("#"):
                break

            start_commands.append(line.rstrip())

    params = []
    if parameters.endswith(".txt") or parameters.endswith(".csv"):
        params = read_csv(parameters, headers=args.headers)

    console = Console()
    table = Table(title="Parameters list")

    keys = params[0].keys()
    table.add_column("id", justify="right", style="bold cyan")
    for key in keys:
        table.add_column(f"${key}", justify="right")

    for idx, param in enumerate(params):
        table.add_row(str(idx), *map(str, param.values()))

    console.print(table)

    main_header = "\n".join(start_commands)
    log.info(
        f"Using SLURM parameters:\n[italic bright_black]{main_header}[/]",
        extra={"markup": True, "highlighter": None},
    )

    cfg = {
        "general": {
            "name": name,
            "root_label": name,
            "params": main_header,
            "instance_label": "${MATRIX_JOB_ID}",
            "concurrent": 0,
        },
        "matrix": params,
        "symlinks": dict(),
        "copies": dict(),
        "script": {"slurm_exec": open(shell_file, "r").read()},
    }
    cfg = config.interpret_config(cfg)

    create.create_from_cfg(args, cfg)


def read_csv(file, headers=False):
    with open(file, "r") as csvfile:
        est_header = csv.Sniffer().has_header(csvfile.read(1024))
        csvfile.seek(0)

        fieldnames = None
        first_row = ""
        if not headers:
            # create the fieldnames
            first_row = csvfile.readline()
            fieldnames = [
                str(x) for x in range(1, len(next(csv.reader([first_row]))) + 1)
            ]

            csvfile.seek(0)

        reader = csv.DictReader(csvfile, fieldnames=fieldnames)
        params = []

        for idx, row in enumerate(reader):
            if idx == 0 and not headers and est_header != headers:
                log.warn(
                    f"Your parameters file may have headers, but you have not provided the '--headers' flag. Parameters are currently being processed as if they do not contain headers.\nIf '{first_row.strip()}' is intended to be a header row, pass in the '--headers' flag. Otherwise, each column can be accessed using '$1' for the first column, '$2' for the second, and so on."
                )
            params.append(row)

        return params
