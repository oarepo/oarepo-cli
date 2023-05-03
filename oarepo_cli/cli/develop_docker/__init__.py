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

    check_call([f"{virtualenv}/bin/invenio", "collect", "--verbose"])
    check_call([f"{virtualenv}/bin/invenio", "webpack", "clean", "create"])
    check_call([f"{virtualenv}/bin/invenio", "webpack", "install"])

    copied_files = copy_statics_and_assets(invenio)
    symlink_assets_templates(copied_files, invenio)

    check_call([f"{virtualenv}/bin/invenio", "webpack", "build"])

    # do not allow Clean plugin to remove files
    webpack_config = Path(f"{invenio}/assets/build/webpack.config.js").read_text()
    webpack_config = webpack_config.replace("dry: false", "dry: true")
    Path(f"{invenio}/assets/build/webpack.config.js").write_text(webpack_config)


def copy_statics_and_assets(invenio):
    rdm_static_dir_exists = os.path.exists("static")
    rdm_assets_dir_exists = os.path.exists("assets")

    if rdm_static_dir_exists:
        src_dir = "static"
        dst_dir = f"{invenio}/static"
        for i in range(5):
            try:
                copy_tree(src_dir, dst_dir)
                break
            except:
                traceback.print_exc()
                time.sleep(10)
        else:
            raise Exception("Could not copy tree, see the log above")

    if rdm_assets_dir_exists:
        src_dir = "assets"
        dst_dir = f"{invenio}/assets"
        # The full path to the files that were copied is returned
        for i in range(5):
            try:
                ret = copy_tree(src_dir, dst_dir)
                break
            except:
                traceback.print_exc()
                time.sleep(10)
        else:
            raise Exception("Could not copy tree, see log above")
        return ret
    return []


def symlink_assets_templates(files_to_link, invenio):
    """Symlink the assets folder."""
    assets = "assets"
    click.secho("Symlinking {}...".format(assets), fg="green")

    instance_path = Path(invenio)
    project_dir = Path.cwd()
    for file_path in files_to_link:
        file_path = Path(file_path)
        relative_path = file_path.relative_to(instance_path)
        target_path = project_dir / relative_path
        force_symlink(target_path, file_path)


def force_symlink(target, link_name):
    """Forcefully create symlink at link_name pointing to target."""
    output = f"Symlinked {target} successfully."
    try:
        os.symlink(target, link_name)
    except OSError as e:
        if e.errno == errno.EEXIST:
            os.remove(link_name)
            os.symlink(target, link_name)
            output = output + "Deleted already existing link."

    print(target, output)


class Runner:
    def __init__(self, venv, invenio):
        self.venv = venv
        self.invenio = invenio
        self.server_handle = None
        self.ui_handle = None

    def run(self):
        try:
            self.start_server()
            time.sleep(10)
            self.start_ui()
        except:
            traceback.print_exc()
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
                    subprocess.call(["ps", "-A"])
                    build_assets(virtualenv=self.venv, invenio=self.invenio)
                    self.start_server()
                    time.sleep(10)
                    self.start_ui()
                    subprocess.call(["ps", "-A"])

            except InterruptedError:
                self.stop_server()
                self.stop_ui()
                return
            except Exception:
                traceback.print_exc()
        self.stop_server()
        self.stop_ui()

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


def copy_tree(src, dest):
    to_copy = [(src, dest)]
    copied_files = []
    while to_copy:
        source, destination = to_copy.pop()
        if os.path.isdir(source):
            print(f"Will copy directory {source} -> {destination}")
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
            print(f"Will copy file {source} -> {destination}")
            if os.path.exists(destination):
                print("    ... already exists, removing")
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
