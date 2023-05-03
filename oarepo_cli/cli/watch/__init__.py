import click
import json
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from pathlib import Path
import shutil
import traceback
from oarepo_cli.utils import copy_tree


class EventHandler(FileSystemEventHandler):
    def __init__(self, source, destination):
        self.source = Path(source)
        self.destination = Path(destination)

    def on_modified(self, event):
        if event.is_directory:
            return

        self._copy(event.src_path)

    def on_moved(self, event):
        self._copy(event.dest_path)

    def _copy(self, path):
        try:
            relative_path = Path(path).relative_to(self.source)
            copy_tree(path, self.destination / relative_path)
        except:
            traceback.print_exc()


@click.command(
    name="docker-watch",
    hidden=True,
    help="Internal action called inside the development docker. " "It watches the ",
)
@click.argument("paths_json")  # Path to json file describing paths to watch
@click.argument("destination")  # Path where to copy watched files to
@click.argument("extra_paths", nargs=-1)  # Extra paths
def docker_watch(paths_json, destination, extra_paths):
    destination = Path(destination)
    watched_paths = load_watched_paths(paths_json, extra_paths)
    # recursively copy to destination
    copy_watched_paths(watched_paths, destination)

    # start watching
    observer = Observer()
    for path, target in watched_paths.items():
        print(f"Will watch {path} => {target}")
        observer.schedule(
            EventHandler(path, destination / target), path, recursive=True
        )
    print("Starting observer")
    observer.start()
    observer.join()


def load_watched_paths(paths_json, extra_paths):
    watched_paths = {}
    with open(paths_json) as f:
        for target, paths in json.load(f).items():
            for pth in paths:
                watched_paths[pth] = target
    for e in extra_paths:
        source, target = e.split("=", maxsplit=1)
        watched_paths[source] = target
    return watched_paths


def copy_watched_paths(watched_paths, destination):
    destination.mkdir(parents=True, exist_ok=True)
    for source, target in watched_paths.items():
        copy_tree(source, destination / target)
