from rich.pretty import pretty_repr
from rich.console import Console
import logging
from pathlib import Path
import glob
import os
import shutil

from . import config

log = logging.getLogger("smatrix")


class Instance:
    def __init__(self, state, cfg, id):
        self.state = state
        self.cfg = cfg
        self.id = id

        # 0 when the job hasn't started yet
        self.slurm_id = 0

        self.dry_run = self.cfg["dry_run"]

        self.env = config.get_environment(cfg, state, id)

        # create subdirectory folder
        self.dir = self.cfg["root_dir"] / Path(
            config.template_envs(self.cfg["general"]["instance_label"], self.env)
        )

        print("")
        log.info(
            "[yellow]Instance %d has state: %s[/]",
            self.id,
            self.state,
            extra={"markup": True},
        )

    def update_filesystem(self):
        log.debug(f"Instance with id %d has path '%s'", self.id, self.dir)
        os.mkdir(self.dir)

        log.debug("Creating symlinks")
        for dest_pattern, src_pattern in self.cfg["symlinks"].items():
            for src, dest in self.search_glob(src_pattern, dest_pattern):
                dest_rel = dest.relative_to(self.dir)
                log.info(
                    f"[bold yellow]Symlink[/]\t'{dest_rel}' ← '{src}'",
                    extra={"markup": True},
                )
                os.symlink(src, dest)

        log.debug("Creating copies")
        for dest_pattern, options in self.cfg["copies"].items():
            src_pattern = options["path"]
            template = options["template"]

            for src, dest in self.search_glob(src_pattern, dest_pattern):
                dest_rel = dest.relative_to(self.dir)
                template_msg = "✓" if template else "✗"
                log.info(
                    f"[bold bright_cyan]Copy[/]\t'{dest_rel}' ← '{src}' [bright_black][ Template {template_msg} ][/]",
                    extra={"markup": True},
                )
                if template:
                    with open(src, "r") as f:
                        contents = f.read()
                    templated = config.template_envs(contents, self.env)
                    with open(dest, "w") as f:
                        f.write(templated)
                else:
                    shutil.copy2(src, dest)

    def search_glob(self, src, dest):
        # template the source and destination
        dest_t = config.template_envs(dest, self.env)
        src_t = config.template_envs(src, self.env)
        # has the user explicitly asked for a directory?
        is_dir = dest_t.endswith("/")

        # convert to Pathlib object
        dest_t = self.dir / Path(dest_t)

        path_matches = list(glob.glob(src_t))
        if not path_matches:
            raise FileNotFoundError(f"Could not find pattern '{src_t}'")

        # if there are multiple results, dest MUST be a directory
        if len(path_matches) > 1 and not is_dir:
            is_dir = True
            dest_rel = dest_t.relative_to(self.dir)

            # warn user
            log.warn(
                f"Treating '{dest_t}/' as a directory, as there are multiple matches for the pattern '{src}'.\n"
                + f"To avoid this warning, explicitly set the destination to '{dest}/' (currently '{dest}') in the configuration file, to indicate that you want to output to a directory."
            )

        # make directory if needed
        if is_dir:
            os.makedirs(dest_t, exist_ok=True)

        for path in path_matches:
            # get absolute file path
            file_src = Path(path).resolve(strict=True)
            file_dest = (dest_t / file_src.name) if is_dir else dest_t

            # ensure that the parent directory exists
            os.makedirs(file_dest.parent, exist_ok=True)

            yield (file_src, file_dest)

    def write_files(self):
        # create environment file
        #
        # a SLURM environment file is:
        # >  ... one or more environment variable definitions of the form NAME=value,
        # >  each separated by a null character. This allows the use of special characters
        # >  in environment definitions
        #    - from https://slurm.schedmd.com/sbatch.html
        #
        # if you want to inspect this environment log file, run
        # $ cat job_environment | python -c 'import sys; sys.stdout.write(sys.stdin.read().replace("\0", "\n"))'
        # which will replace all null bytes with a newline.
        log.debug(f"Create environment file %s", self.env)
        envs = [f"{k}={v}" for k, v in self.env.items()]
        env_file_contents = "\x00".join(envs) + "\x00"
        with open(self.dir / "job_environment", "w") as f:
            f.write(env_file_contents)
            log.info(
                f"[bold magenta]Write[/]\t'job_environment' (environment variable file)",
                extra={"markup": True},
            )

        # create the script files
        # an intentional design choice is to NOT use templating here, as all variables will be available to the environment
        with open(self.dir / "job_run.sh", "w") as f:
            f.write(self.cfg["script"]["slurm_exec"])
            log.info(
                f"[bold magenta]Write[/]\t'job_run.sh' (main SLURM file to be executed)",
                extra={"markup": True},
            )

        for k, v in self.cfg["script"].items():
            if k == "slurm_exec":
                continue
            dest = (self.dir / Path(k)).resolve()
            dest_rel = dest.relative_to(self.dir)

            log.info(
                f"[bold magenta]Write[/]\t'{dest_rel}'",
                extra={"markup": True},
            )

            # make parent directory if needed
            os.makedirs(dest.parent, exist_ok=True)

            with open(dest, "w") as f:
                f.write(v)

    def report_state(self):
        return {
            "id": self.id,
            "dir": self.dir,
            "env": self.env,
            "matrix_state": self.state,
            "cfg": self.cfg,
            "slurm_id": self.slurm_id,
        }
