import functools
import os
import re
import select
import shutil
import subprocess
import sys
from pathlib import Path

import click
import deepmerge
import git
import pydriller
import yaml
from colorama import Fore, Style

from oarepo_cli.config import MonorepoConfig


def run_cmdline(
    *cmdline,
    cwd=".",
    environ=None,
    check_only=False,
    grab_stdout=False,
    grab_stderr=False,
    discard_output=False,
    raise_exception=False,
    with_tty=False,
    no_input=False,
):
    env = os.environ.copy()
    env.update(environ or {})
    cwd = Path(cwd).absolute()
    cmdline = [str(x) for x in cmdline]
    print(
        f"{Fore.BLUE}Running {Style.RESET_ALL} {' '.join(cmdline)}", file=sys.__stderr__
    )
    if "DOCKER_AROUND" in os.environ:
        inside_docker = "docker at path "
    else:
        inside_docker = ""
    print(
        f"{Fore.BLUE}    inside {Style.RESET_ALL} {inside_docker}{cwd}",
        file=sys.__stderr__,
    )
    try:
        kwargs = {}
        if no_input:
            kwargs["stdin"] = subprocess.DEVNULL
        if grab_stdout or grab_stderr or discard_output:
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
            if with_tty:
                ret = run_with_tty(cmdline, cwd=cwd, env=env)
            else:
                ret = subprocess.call(cmdline, cwd=cwd, env=env, **kwargs)
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


def run_with_tty(cmd, cwd=None, env=None):
    # https://stackoverflow.com/questions/41542960/run-interactive-bash-with-popen-and-a-dedicated-tty-python
    import pty
    import termios
    import tty

    # save original tty setting then set it to raw mode
    old_tty = termios.tcgetattr(sys.stdin)
    tty.setraw(sys.stdin.fileno())

    # open pseudo-terminal to interact with subprocess
    master_fd, slave_fd = pty.openpty()
    try:
        # use os.setsid() make it run in a new process group, or bash job control will not be enabled
        p = subprocess.Popen(
            cmd,
            preexec_fn=os.setsid,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            universal_newlines=True,
        )

        while p.poll() is None:
            r, w, e = select.select([sys.stdin, master_fd], [], [], 1)
            if sys.stdin in r:
                d = os.read(sys.stdin.fileno(), 10240)
                os.write(master_fd, d)
            elif master_fd in r:
                o = os.read(master_fd, 10240)
                if o:
                    os.write(sys.stdout.fileno(), o)
        return p.returncode
    finally:
        # restore tty settings back
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_tty)


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
    if "DOCKER_AROUND" in os.environ:
        return
    tag_index = 1

    if not (repo_dir / ".git").exists():
        git.Repo.init(repo_dir)

    try:
        for commit in pydriller.Repository(str(repo_dir)).traverse_commits():
            for m in commit.msg.split("\n"):
                if m.startswith("omb-"):
                    tag_index += 1
    except git.exc.GitCommandError:
        pass
    except git.exc.InvalidGitRepositoryError:
        pass

    repo = git.Repo(repo_dir)
    tag_name = f"omb-{tag_index:05d}-{tag_name}"
    repo.git.add(repo_dir)
    index = repo.index
    if index.entries:
        index.commit(message + "\n\n" + tag_name)


def must_be_committed(repo_dir):
    if "DOCKER_AROUND" in os.environ:
        return
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


def path_type(path):
    if os.path.isdir(path):
        return "dir"
    elif os.path.isfile(path):
        return "file"
    elif os.path.islink(path):
        return "link"
    else:
        return "unknown"


unique_merger = deepmerge.Merger(
    [(list, ["append_unique"]), (dict, ["merge"]), (set, ["union"])],
    # next, choose the fallback strategies,
    # applied to all other types:
    ["override"],
    # finally, choose the strategies in
    # the case where the types conflict:
    ["override"],
)


def snail_to_title(v):
    return "".join(ele.title() for ele in v.split("_"))


def with_config(
    config_section=None, project_dir_as_argument=False, config_as_argument=False
):
    def wrapper(f):
        @(
            click.argument(
                "project_dir",
                type=click.Path(exists=False, file_okay=False),
                required=True,
            )
            if project_dir_as_argument
            else click.option(
                "--project-dir",
                type=click.Path(exists=True, file_okay=False),
                required=False,
                help="Directory containing an already initialized project. "
                "If not set, current directory is used",
            )
        )
        @click.option(
            "--no-input",
            is_flag=True,
            type=bool,
            required=False,
            help="Take options from the config file, skip user input",
        )
        @click.option(
            "--silent",
            is_flag=True,
            type=bool,
            required=False,
            help="Do not output program's messages. "
            "External program messages will still be displayed",
        )
        @click.option(
            "--verbose",
            is_flag=True,
            type=bool,
            required=False,
            help="Verbose output",
        )
        @click.option(
            "--step",
            required=False,
            multiple=True,
            help="Run only this step",
        )
        @click.option(
            "--steps",
            is_flag=True,
            type=bool,
            required=False,
            help="List all steps and exit",
        )
        @(
            click.argument(
                "config",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
                required=True,
            )
            if config_as_argument
            else click.option(
                "--config",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
                required=False,
                help="Merge this config to the main config in target directory and proceed",
            )
        )
        @click.option(
            "--use-docker",
            "use_docker",
            flag_value="docker",
            default=None,
            help="Run the command inside docker",
        )
        @click.option(
            "--outside-docker",
            "use_docker",
            flag_value="no docker",
            help="Run the command outside of docker container",
        )
        @click.pass_context
        @functools.wraps(f)
        def wrapped(
            context,
            project_dir=None,
            config=None,
            use_docker=None,
            **kwargs,
        ):
            if not project_dir:
                project_dir = Path.cwd()
            project_dir = Path(project_dir).absolute()
            oarepo_yaml_file = project_dir / "oarepo.yaml"

            if callable(config_section):
                section = config_section(**kwargs)
            else:
                section = config_section or "config"

            cfg = MonorepoConfig(oarepo_yaml_file, section=section)

            if oarepo_yaml_file.exists():
                cfg.load()

            if config:
                config_data = yaml.safe_load(Path(config).read_text())
                cfg.merge_config(config_data, top=not config_section)

            kwargs.pop("cfg", None)
            kwargs.pop("project_dir", None)

            cfg.running_in_docker = "DOCKER_AROUND" in os.environ
            if not use_docker:
                cfg.use_docker = None
            else:
                cfg.use_docker = use_docker == "docker"

            cfg.no_input = kwargs.get("no_input", False)

            try:
                return f(context=context, project_dir=project_dir, cfg=cfg, **kwargs)
            except Exception as e:
                if kwargs.get("verbose"):
                    import traceback

                    traceback.print_exc()
                else:
                    print(str(e))
                raise

        return wrapped

    return wrapper


def load_user_config(project_dir):
    if not project_dir.exists():
        return {}

    local_user_config = {}
    local_user_config_file = project_dir / ".oarepo-local.yaml"
    if local_user_config_file.exists():
        with open(local_user_config_file) as f:
            local_user_config = yaml.safe_load(f)

    if "use_docker" not in local_user_config:
        click.secho(
            """I can isolate all the commands into a docker container.
    The advantage is that only python and docker are needed, disadvantage is a slight performance
    penalty.
    
    Should I do so? (y/n)
            """
        )
        yn = input().strip().lower()
        if yn == "y":
            local_user_config["use_docker"] = True
            with open(local_user_config_file, "w") as f:
                yaml.safe_dump(local_user_config, f)
    return local_user_config


class ProjectWizardMixin:
    @property
    def site_dir(self):
        if not hasattr(self, "site"):
            raise Exception("Current site not set")
        return self.data.project_dir / self.site["site_dir"]

    @property
    def oarepo_cli(self):
        return self.data.project_dir / self.data.get("config.oarepo_cli")

    def run_cookiecutter(
        self,
        template,
        config_file,
        checkout=None,
        output_dir=None,
        extra_context=None,
        environ=None,
    ):
        config_dir: Path = self.data.project_dir / ".cookiecutters"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / f"{config_file}.yaml"
        config_file.write_text(yaml.safe_dump({"default_context": extra_context}))
        cookiecutter_command = (
            Path(sys.executable or sys.argv[0]).absolute().parent / "cookiecutter"
        )
        output_dir_temp = f"{output_dir}-tmp"
        output_dir = Path(output_dir)
        output_dir_temp = Path(output_dir_temp)
        args = [
            template,
            "--no-input",
            "-o",
            output_dir_temp,
            "--config-file",
            config_file,
        ]
        if checkout:
            args.append("-c")
            args.append(checkout)

        run_cmdline(
            cookiecutter_command,
            *args,
            cwd=self.data.project_dir,
            environ={**(environ or {})},
        )
        merge_from_temp_to_target(output_dir_temp, output_dir)


class SiteMixin(ProjectWizardMixin):
    @property
    def site_dir(self):
        site_name = self.data.get("sites", [])
        if not site_name:
            raise Exception("Unexpected error: No installation site specified")
        site = self.data.get(f"sites.{site_name[0]}")
        if not site:
            raise Exception(
                f"Unexpected error: Site with name {site_name[0]} does not exist"
            )
        return self.data.project_dir / site["site_dir"]


def merge_from_temp_to_target(output_dir_temp, output_dir):
    source: Path
    for source in output_dir_temp.rglob("*"):
        rel = source.relative_to(output_dir_temp)
        dest: Path = output_dir / rel
        if source.is_dir():
            if not dest.exists():
                dest.mkdir(parents=True)
        elif source.is_file():
            if not dest.exists():
                if not dest.parent.exists():
                    dest.parent.mkdir(parents=True)
                shutil.copy(source, dest)
    shutil.rmtree(output_dir_temp)


def check_call(*args, **kwargs):
    cmdline = " ".join(str(x) for x in args[0])
    print(f"Calling command {cmdline} with kwargs {kwargs}")
    return subprocess.check_call(*args, **kwargs)


def run_nrp_in_docker_compose(
    site_dir, *arguments, interactive=True, no_input=False, networking=True, name=None
):
    run_cmdline(
        "docker",
        "compose",
        "run",
        *(["--service-ports"] if networking else []),
        "--rm",
        *(["-i"] if interactive else []),
        *(["--no-TTY"] if no_input else []),
        *(["--name", name] if name else []),
        "repo",
        *arguments,
        cwd=site_dir,
        environ={**os.environ, "INVENIO_DOCKER_USER_ID": str(os.getuid())},
        with_tty=False,
        no_input=no_input,
    )


def exec_nrp_in_docker(site_dir, container_name, *arguments, interactive=True):
    run_cmdline(
        "docker",
        "exec",
        *(["-it"] if interactive else []),
        container_name,
        "/nrp/bin/nrp",
        *arguments,
        cwd=site_dir,
        environ={**os.environ, "INVENIO_DOCKER_USER_ID": str(os.getuid())},
        with_tty=False,
        no_input=not interactive,
    )


def run_nrp_in_docker(repo_dir: Path, *arguments, interactive=True):
    run_cmdline(
        "docker",
        "run",
        *(["-it"] if interactive else []),
        "-v",
        f"{str(repo_dir)}:/repository",
        "--user",
        f"{os.getuid()}:{os.getgid()}",
        "-e",
        f"REPOSITORY_DIR={repo_dir.name}",
        "--rm",
        "oarepo/oarepo-base-development:11",
        *arguments,
        cwd=repo_dir,
        with_tty=True,
    )


def batched(lst, n):
    if n < 1:
        raise ValueError("n must be at least one")

    while lst:
        data = lst[:n]
        lst = lst[n:]
        yield data
