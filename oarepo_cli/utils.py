import os
import re
import subprocess
import sys
from pathlib import Path
import shutil

import git
import pydriller
import pyfiglet
import tomlkit
from colorama import Fore, Style

from oarepo_cli.ui.utils import slow_print


def print_banner():
    intro_string = "\n".join(
        [
            "        " + x
            for x in pyfiglet.figlet_format(
                "O A R e p o", font="slant", width=120
            ).split("\n")
        ]
    )
    slow_print(f"\n\n\n{Fore.GREEN}{intro_string}{Style.RESET_ALL}")


def run_cmdline(
    *cmdline,
    cwd=".",
    environ=None,
    check_only=False,
    grab_stdout=False,
    grab_stderr=False,
    discard_output=False,
    raise_exception=False,
):
    env = os.environ.copy()
    env.update(environ or {})
    cwd = Path(cwd).absolute()
    cmdline = [str(x) for x in cmdline]
    print(
        f"{Fore.BLUE}Running {Style.RESET_ALL} {' '.join(cmdline)}", file=sys.__stderr__
    )
    print(f"{Fore.BLUE}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)
    try:
        if grab_stdout or grab_stderr or discard_output:
            kwargs = {}
            if grab_stdout or discard_output:
                kwargs["stdout"] = subprocess.PIPE
            if grab_stderr or discard_output:
                kwargs["stderr"] = subprocess.PIPE

            ret = subprocess.run(
                cmdline,
                check=True,
                cwd=cwd,
                env=env,
                **kwargs,
            )
            ret = (ret.stdout or b"") + b"\n" + (ret.stderr or b"")
        else:
            ret = subprocess.call(cmdline, cwd=cwd, env=env)
            if ret:
                raise subprocess.CalledProcessError(ret, cmdline)
    except subprocess.CalledProcessError as e:
        if check_only:
            return False
        print(f"Error running {' '.join(cmdline)}", file=sys.__stderr__)
        if e.stdout:
            print(e.stdout)
        if e.stderr:
            print(e.stderr)
        if raise_exception:
            raise
        sys.exit(e.returncode)
    print(
        f"{Fore.GREEN}Finished running {Style.RESET_ALL} {' '.join(cmdline)}",
        file=sys.__stderr__,
    )
    print(f"{Fore.GREEN}    inside {Style.RESET_ALL} {cwd}", file=sys.__stderr__)
    if grab_stdout:
        return ret.decode("utf-8").strip()
    return True


def find_oarepo_project(dirname, raises=False):
    dirname = Path(dirname).absolute()
    orig_dirname = dirname
    for _ in range(4):
        if (dirname / "oarepo.yaml").exists():
            return dirname
        dirname = dirname.parent
    if raises:
        raise Exception(
            f"Not part of OARepo project: directory {orig_dirname} "
            f"or its 4 ancestors do not contain oarepo.yaml file"
        )
    return


def add_to_pipfile_dependencies(pipfile, package_name, package_path):
    with open(pipfile, "r") as f:
        pipfile_data = tomlkit.load(f)
    for pkg in pipfile_data["packages"]:
        if pkg == package_name:
            break
    else:
        t = tomlkit.inline_table()
        t.comment("Added by nrp-cli")
        t.update({"editable": True, "path": package_path})
        pipfile_data["packages"].add(tomlkit.nl())
        pipfile_data["packages"][package_name] = t
        pipfile_data["packages"].add(tomlkit.nl())

        with open(pipfile, "w") as f:
            tomlkit.dump(pipfile_data, f)


def to_python_name(x):
    x = re.sub(r"(?<!^)(?=[A-Z])", "_", x).lower()
    x = x.replace("-", "_")
    return re.sub("[^a-z_]", "", x)


def pip_install(pip_binary, env_name, lib_name_and_version, lib_github):
    # run pip installation, taking env versions into account
    run_cmdline(pip_binary, "install", "-U", "--no-input", "setuptools", "pip", "wheel")
    installation_option = os.environ.get(env_name, "release")
    if installation_option == "release":
        # release
        run_cmdline(pip_binary, "install", "--no-input", lib_name_and_version)
    elif installation_option == "maintrunk":
        run_cmdline(
            pip_binary,
            "install",
            "--no-input",
            f"git+{lib_github}",
        )
    elif installation_option.startswith("https://"):
        run_cmdline(
            pip_binary,
            "install",
            "--no-input",
            f"git+{installation_option}",
        )
    else:
        run_cmdline(
            pip_binary,
            "install",
            "--no-input",
            "-e",
            Path(installation_option),
        )


def get_cookiecutter_source(env_name, lib_github, lib_version, master_version="master"):
    installation_option = os.environ.get(env_name, "release")
    if installation_option == "release":
        cookiecutter_path = lib_github
        cookiecutter_branch = lib_version
    elif installation_option == "maintrunk":
        cookiecutter_path = lib_github
        cookiecutter_branch = master_version
    elif installation_option.startswith("https://"):
        # something like https://github.com/oarepo/oarepo-model-builder/tree/datatypes
        cookiecutter_path, cookiecutter_branch = installation_option.rsplit(
            "/tree/", maxsplit=1
        )
    else:
        cookiecutter_path = installation_option
        cookiecutter_branch = None
    return cookiecutter_path, cookiecutter_branch


def commit_git(repo_dir, tag_name, message):
    tag_index = 1
    try:
        for commit in pydriller.Repository(str(repo_dir)).traverse_commits():
            for m in commit.msg.split("\n"):
                if m.startswith("omb-"):
                    tag_index += 1
    except git.exc.GitCommandError:
        pass
    repo = git.Repo(repo_dir)
    tag_name = f"omb-{tag_index:05d}-{tag_name}"
    index = repo.index
    repo.git.add(repo_dir)
    index.commit(message + "\n\n" + tag_name)


def must_be_committed(repo_dir):
    repo = git.Repo(repo_dir)
    if repo.is_dirty() or repo.untracked_files:
        for f in repo.untracked_files:
            print("    ", f)

        print(
            "The repository contains untracked or dirty files. Please commit/ignore them before continuing."
        )
        sys.exit(1)


def copy_tree(src, dest):
    to_copy = [(src, dest)]
    copied_files = []
    while to_copy:
        source, destination = to_copy.pop()
        if os.path.isdir(source):
            print(f"Copying directory {source} -> {destination}")
            if os.path.exists(destination):
                print("    ... already exists")
                if not os.path.isdir(destination):
                    raise AttributeError(
                        f"Destination {destination} should be a directory but is {path_type(destination)}"
                    )
            else:
                print("    ... creating and testing directory")
                os.makedirs(destination)
                if not os.path.isdir(destination):
                    raise AttributeError(
                        f"I've just created a {destination} directory but it failed and I've got {path_type(destination)}"
                    )
            for fn in reversed(os.listdir(source)):
                to_copy.append(
                    (os.path.join(source, fn), os.path.join(destination, fn))
                )
        else:
            print(f"Copying file {source} -> {destination}")
            if os.path.exists(destination):
                os.unlink(destination)
            if os.path.exists(destination):
                raise AttributeError(
                    f"I've just deleted {destination}, but it still exists and is {path_type(destination)}"
                )

            shutil.copy(source, destination, follow_symlinks=True)
            if not os.path.isfile(destination):
                raise AttributeError(
                    f"I've just copied file {source} into {destination}, but the destination is not a file, it is {path_type(destination)}"
                )
            if (
                os.stat(source, follow_symlinks=True).st_size
                != os.stat(destination).st_size
            ):
                raise AttributeError(
                    f"I've just copied file {source} into {destination}, but the sizes do not match. "
                    f"Source size {os.stat(source).st_size}, destination size {os.stat(destination).st_size}"
                )
            copied_files.append(destination)
    return copied_files
