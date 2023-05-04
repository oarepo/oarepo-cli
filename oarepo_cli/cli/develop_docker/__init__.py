import click as click
from pathlib import Path
import yaml
import subprocess
import os
import errno
import time
import traceback
import sys
import select
import shutil
from oarepo_cli.utils import copy_tree
from ..watch import load_watched_paths, copy_watched_paths


@click.command(
    name="docker-develop",
    hidden=True,
    help="Internal action called inside the development docker. "
    "Do not call from outside as it will not work. "
    "Call from the directory containing the oarepo.yaml",
)
@click.option("--virtualenv", help="Path to invenio virtualenv")
@click.option("--invenio", help="Path to invenio instance directory")
def docker_develop(**kwargs):
    call_task(install_editable_sources, **kwargs)
    call_task(db_init, **kwargs)
    call_task(search_init, **kwargs)
    call_task(create_custom_fields, **kwargs)
    call_task(import_fixtures, **kwargs)
    call_task(build_assets, **kwargs)
    call_task(development_script, **kwargs)

    runner = Runner(kwargs["virtualenv"], kwargs["invenio"])
    runner.run()


def call_task(task_func, **kwargs):
    status_file = Path(kwargs["invenio"]) / "docker-develop.yaml"
    if status_file.exists():
        with open(status_file, "r") as f:
            status = yaml.safe_load(f)
    else:
        status = {}
    if task_func.__name__ in status:
        return
    print(f"Calling task {task_func.__name__} with arguments {kwargs}")
    task_func(**kwargs)
    status[task_func.__name__] = True
    with open(status_file, "w") as f:
        yaml.safe_dump(status, f)


def install_editable_sources(*, virtualenv, **kwargs):
    """
    Editable sources are stored at virtualenv/requirements-editable.txt
    """
    check_call(
        [
            f"{virtualenv}/bin/pip",
            "install",
            "--no-deps",  # do not install dependencies as they were installed during container build
            "-r",
            f"{virtualenv}/requirements-editable.txt",
        ]
    )


def db_init(*, virtualenv, **kwargs):
    """
    Create database tables.
    """
    call([f"{virtualenv}/bin/invenio", "db", "drop", "--yes-i-know"])
    check_call([f"{virtualenv}/bin/invenio", "db", "create"])


def search_init(*, virtualenv, **kwargs):
    """
    Create search indices.
    """
    call([f"{virtualenv}/bin/invenio", "index", "destroy", "--force", "--yes-i-know"])
    check_call([f"{virtualenv}/bin/invenio", "index", "init"])


def create_custom_fields(*, virtualenv, **kwargs):
    """
    Create custom fields and patch indices.
    """
    check_call([f"{virtualenv}/bin/invenio", "oarepo", "cf", "init"])


def import_fixtures(*, virtualenv, **kwargs):
    """
    Import fixtures.
    """
    check_call([f"{virtualenv}/bin/invenio", "oarepo", "fixtures", "load"])


def development_script(**kwargs):
    if Path("development/initialize.sh").exists():
        check_call(["/bin/sh", "development/initialize.sh"])


# region Taken from Invenio-cli
#
# this and the following were taken from:
# https://github.com/inveniosoftware/invenio-cli/blob/0a49d438dc3c5ace872ce27f8555b401c5afc6e7/invenio_cli/commands/local.py#L45
# and must be called from the site directory
#
# The reason is that symlinking functionality is only part of invenio-cli
# and that is dependent on pipenv, which can not be used inside alpine
# (because we want to keep the image as small as possible, we do not install gcc
# and can only use compiled native python packages - like cairocffi or uwsgi). The
# version of these provided in alpine is slightly lower than the one created by Pipenv
# - that's why we use plain invenio & pip here.
#
# Another reason is that invenio-cli is inherently unstable when non-rdm version
# is used - it gets broken with each release.


def build_assets(*, virtualenv, invenio, **kwargs):
    shutil.rmtree(f"{invenio}/assets", ignore_errors=True)
    shutil.rmtree(f"{invenio}/static", ignore_errors=True)

    Path(f"{invenio}/assets").mkdir(parents=True)
    Path(f"{invenio}/static").mkdir(parents=True)

    check_call(
        [
            f"{virtualenv}/bin/invenio",
            "oarepo",
            "assets",
            "collect",
            f"{invenio}/watch.list.json",
        ]
    )
    check_call([f"{virtualenv}/bin/invenio", "webpack", "clean", "create"])
    check_call([f"{virtualenv}/bin/invenio", "webpack", "install"])

    watched_paths = load_watched_paths(
        f"{invenio}/watch.list.json", ["assets=assets", "static=static"]
    )
    copy_watched_paths(watched_paths, Path(invenio))

    check_call([f"{virtualenv}/bin/invenio", "webpack", "build"])

    # do not allow Clean plugin to remove files
    webpack_config = Path(f"{invenio}/assets/build/webpack.config.js").read_text()
    webpack_config = webpack_config.replace("dry: false", "dry: true")
    Path(f"{invenio}/assets/build/webpack.config.js").write_text(webpack_config)


class Runner:
    def __init__(self, venv, invenio):
        self.venv = venv
        self.invenio = invenio
        self.server_handle = None
        self.ui_handle = None
        self.watch_handle = None

    def run(self):
        try:
            self.start_server()
            time.sleep(10)
            self.start_watch()
            self.start_ui()
        except:
            traceback.print_exc()
            self.stop_watch()
            self.stop_server()
            self.stop_ui()
            return

        while True:
            try:
                l = input_with_timeout(60)
                if not l:
                    continue
                if l == "stop":
                    break
                if l == "server":
                    self.stop_server()
                    subprocess.call(["ps", "-A"])
                    self.start_server()
                    subprocess.call(["ps", "-A"])
                    continue
                if l == "ui":
                    self.stop_ui()
                    subprocess.call(["ps", "-A"])
                    self.start_ui()
                    subprocess.call(["ps", "-A"])
                    continue
                if l == "build":
                    self.stop_ui()
                    self.stop_server()
                    self.stop_watch()
                    subprocess.call(["ps", "-A"])
                    build_assets(virtualenv=self.venv, invenio=self.invenio)
                    self.start_server()
                    time.sleep(10)
                    self.start_watch()
                    self.start_ui()
                    subprocess.call(["ps", "-A"])

            except InterruptedError:
                self.stop_watch()
                self.stop_server()
                self.stop_ui()
                return
            except Exception:
                traceback.print_exc()
        self.stop_server()
        self.stop_ui()
        self.stop_watch()

    def start_server(self):
        print("Starting server")
        self.server_handle = subprocess.Popen(
            [
                f"{self.venv}/bin/invenio",
                "run",
                "--cert",
                "docker/nginx/test.crt",
                "--key",
                "docker/nginx/test.key",
                "-h",
                "0.0.0.0",
                "-p",
                "5000",
            ],
            env={
                "INVENIO_TEMPLATES_AUTO_RELOAD": "1",
                "FLASK_DEBUG": "1",
                **os.environ,
            },
            stdin=subprocess.DEVNULL,
        )

    def stop_server(self):
        print("Stopping server")
        self.stop(self.server_handle)
        self.server_handle = None

    def start_watch(self):
        print("Starting file watcher")
        self.watch_handle = subprocess.Popen(
            [
                os.environ.get("NRP_CLI", "nrp-cli"),
                "docker-watch",
                f"{self.invenio}/watch.list.json",
                self.invenio,
                "assets=assets",
                "static=static",
            ],
        )
        time.sleep(5)

    def stop_watch(self):
        print("Stopping file watcher")
        self.stop(self.watch_handle)
        self.watch_handle = None

    def stop(self, handle):
        if handle:
            try:
                handle.terminate()
            except:
                pass
            time.sleep(5)
            try:
                handle.kill()
            except:
                pass
            time.sleep(5)

    def start_ui(self):
        print("Starting ui watcher")
        self.ui_handle = subprocess.Popen(
            ["npm", "run", "start"], cwd=f"{self.invenio}/assets"
        )

    def stop_ui(self):
        print("Stopping ui watcher")
        self.stop(self.ui_handle)
        self.ui_handle = None


#
# end of code taken from invenio-cli
# endregion


def check_call(*args, **kwargs):
    cmdline = " ".join(args[0])
    print(f"Calling command {cmdline} with kwargs {kwargs}")
    return subprocess.check_call(*args, **kwargs)


def call(*args, **kwargs):
    cmdline = " ".join(args[0])
    print(f"Calling command {cmdline} with kwargs {kwargs}")
    return subprocess.call(*args, **kwargs)


def input_with_timeout(timeout):
    print("=======================================================================")
    print()
    print("Type: ")
    print()
    print("    server <enter>    --- restart server")
    print("    ui <enter>        --- restart ui watcher")
    print("    build <enter>     --- stop server and watcher, ")
    print("                          call ui build, then start again")
    print("    stop <enter>      --- stop the server and ui and exit")
    print()
    i, o, e = select.select([sys.stdin], [], [], timeout)

    if i:
        return sys.stdin.readline().strip()


def path_type(path):
    if os.path.isdir(path):
        return "dir"
    elif os.path.isfile(path):
        return "file"
    elif os.path.islink(path):
        return "link"
    else:
        return "unknown"
