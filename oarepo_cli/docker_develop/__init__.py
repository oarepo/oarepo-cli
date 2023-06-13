import os
import select
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

import click as click
import yaml

from oarepo_cli.assets import build_assets
from oarepo_cli.config import MonorepoConfig
from oarepo_cli.utils import check_call, with_config


@click.command(
    name="docker-develop",
    hidden=True,
    help="Internal action called inside the development docker. "
    "Do not call from outside as it will not work. "
    "Call from the directory containing the oarepo.yaml",
)
@click.option(
    "--virtualenv",
    help="Path to invenio virtualenv",
    type=click.Path(exists=True, file_okay=False, path_type=Path),
)
@click.option(
    "--invenio",
    help="Path to invenio instance directory",
    type=click.Path(file_okay=False, path_type=Path),
)
@click.option(
    "--skip-initialization",
    help="Skip the database/es initialization and loading fixtures",
    is_flag=True,
)
@click.option("--site", help="Name of the site to run the development in")
@click.option("--host", help="Bind host", default="127.0.0.1")
@click.option("--port", help="Bind port", default="5000")
@with_config(config_section=lambda site=None, **kwargs: ["sites", site])
def docker_develop(
    cfg, *, virtualenv: Path, invenio: Path, skip_initialization, host, port, **kwargs
):
    if not invenio:
        invenio = virtualenv / "var" / "instance"
        if not invenio.exists():
            invenio.mkdir(parents=True)
    site_dir = cfg.project_dir / cfg["site_dir"]

    call_task(install_editable_sources, cfg=cfg, virtualenv=virtualenv, invenio=invenio)
    if not skip_initialization:
        call_task(copy_invenio_cfg, cfg=cfg, virtualenv=virtualenv, invenio=invenio)
        call_task(db_init, virtualenv=virtualenv, invenio=invenio)
        call_task(search_init, virtualenv=virtualenv, invenio=invenio)
        call_task(create_custom_fields, virtualenv=virtualenv, invenio=invenio)
        call_task(import_fixtures, virtualenv=virtualenv, invenio=invenio)
    # call_task(build_assets, virtualenv=virtualenv, invenio=invenio, site_dir=site_dir)
    # call_task(development_script, virtualenv=virtualenv, invenio=invenio)

    runner = Runner(virtualenv, invenio, site_dir, host, port)
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


def install_editable_sources(*, cfg: MonorepoConfig, virtualenv, **kwargs):
    site_name = cfg.section_path[-1]
    # 1. go through all models and install them
    for model_name, model in cfg.whole_data.get("models", {}).items():
        if site_name in model.get("sites"):
            install_dir(cfg.project_dir / model["model_dir"], virtualenv)
    # 2. go through all uis and install them
    for ui_name, ui in cfg.whole_data.get("ui", {}).items():
        if site_name in ui.get("sites"):
            install_dir(cfg.project_dir / ui["ui_dir"], virtualenv)
    # 3. install site's site folder
    install_dir(cfg.project_dir / cfg["site_dir"] / "site", virtualenv)


def install_dir(dirname, virtualenv):
    if not dirname.exists():
        return
    check_call(
        [
            f"{virtualenv}/bin/pip",
            "install",
            "--no-deps",  # do not install dependencies as they were installed during container build
            "-e",
            str(dirname),
        ]
    )


def copy_invenio_cfg(*, cfg, invenio, **kwargs):
    site_dir = cfg.project_dir / cfg["site_dir"]
    shutil.copy(site_dir / "invenio.cfg", invenio / "invenio.cfg")
    shutil.copy(site_dir / "variables", invenio / "variables")


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


class Runner:
    def __init__(self, venv, invenio, site_dir, host, port):
        self.venv = venv
        self.invenio = invenio
        self.server_handle = None
        self.ui_handle = None
        self.watch_handle = None
        self.site_dir = site_dir
        self.host = host
        self.port = port

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
                    build_assets(
                        virtualenv=self.venv,
                        invenio=self.invenio,
                        site_dir=self.site_dir,
                    )
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
                str(self.site_dir / "docker" / "nginx" / "test.crt"),
                "--key",
                str(self.site_dir / "docker" / "nginx" / "test.key"),
                "-h",
                self.host,
                "-p",
                self.port,
            ],
            env={
                "INVENIO_TEMPLATES_AUTO_RELOAD": "1",
                "FLASK_DEBUG": "1",
                **os.environ,
            },
            stdin=subprocess.DEVNULL,
            cwd=self.site_dir,
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
                f"{self.site_dir}/assets=assets",
                f"{self.site_dir}/static=static",
            ],
            cwd=self.site_dir,
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
