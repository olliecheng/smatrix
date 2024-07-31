<div align="center">
	<h1>smatrix</h1>
	<p>
		<b>A batch job submitter for SLURM, for when you want to repeat one command with small changes</b>
	</p>
</div>

It is not uncommon to want to run the same command, but with minor changes. For instance, when benchmarking, perhaps you want to replicate the same command but with a different thread count each time; or, you may want to use the same pipeline to process a variety of files in the same way.

`smatrix` provides a simple way to do this without littering badly-documented script files all over the place. It can set up a file hierarchy, create symlinks to existing files, and enable simple summarisation and log file retrieval, by just writing one configuration file. And if you realise you've made a mistake, you can change the parameters for all the jobs in one go, by editing the one single file.

<div align="center">
 <a href="#example">Example</a> &nbsp;&nbsp; | &nbsp;&nbsp; <a href="#usage">Usage</a> &nbsp;&nbsp; | &nbsp;&nbsp; <a href="#installation">Installation</a>
</div>

## Getting started
You don't need to necessarily read the examples down below to get started. First, install smatrix using:
```sh
# todo
```
and then you can generate a default configuration file, which has prepopulated parameters and documentation, using:
```sh
$ smatrix init <config_file_to_write_to>
```
Then, once you've configured everything, you can create a matrix with
```sh
$ smatrix create config.toml
```

## Example

At its core, the philosophy of `smatrix` is that we can think about commands as distinct from their minutiae parameters. It's a bit like when you first define all your environment variables with `JOBFILE=/file/goes/here` at the top of your script, and then write all of your commands in terms of `$JOBFILE`. In fact, this specific configuration is one way that you can choose to work with `smatrix`: put in your `config.toml`

```toml
[general]
name = "simple_matrix"

[matrix]
"input" = [
  "input_value_1",
  "input_value_2",
  "input_value_3"
]

[script]
"slurm_exec" = """
#!/bin/bash

echo $input
"""
```

and then run `smatrix create config.toml --start`.

This will create and execute three distinct SLURM array jobs, each of which will output one of `input_value_x`, `x ∈ {1, 2, 3}`. Each one will have `input` defined in their environment variables, which is accessible through a variety of methods: not just `$input` in Bash, but also `os.environ["input"]` in Python, and so on.

If you want to only create the file structure without executing anything, just omit the `--start` parameter. Later on, you can run `sbatch ${root_dir}/job_executor.sh` and launch the job. `smatrix` doesn't substitute any core SLURM functionality; it just provides a wrapper around parts of it which are more ergonomic for batch jobs. You're always in control.

Another key design pattern that `smatrix` incorporates is liberal use of symbolic linking. Symlinks are a great way to bring together various datasets in one job. Say there's a symlink called `ref.fa` in your job execution folder. Six months down the line, this leaves very little ambiguity in figuring out what reference file your genome alignment was performed against - after all, it's right there! I believe that symlinks are a more ergonomic and clear way of linking *files* with *jobs*.

This is an encouraged design pattern in `smatrix`. See the following `config.toml`:

```toml
[general]
name = "simple_matrix"

[matrix]
"input_file" = [
  "file_1.fastq",
  "file_value_2.fastq",
  "temporary/file_value_4.fastq"
]

[symlinks]
"input.fastq" = "data_folder/$input_file"

[script]
"slurm_exec" = """
#!/bin/bash

cat input.fastq
"""
```

This will create 3 different folders. In each one, the `input.fastq` file will be symlinked to the respective value. Then, each job can just read the `input.fastq` file directly. This is of course identical to using environment variables like this:

```toml
[general]
name = "simple_matrix"

[matrix]
"input_file" = [
  "file_1.fastq",
  "file_value_2.fastq",
  "temporary/file_value_4.fastq"
]

[script]
"slurm_exec" = """
#!/bin/bash

cat "data_folder/$input_file"
"""
```
except it also populates the job folder with a direct link to the input file, in case you (or anyone else) wants to manually use it later on.
