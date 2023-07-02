import subprocess
import time
import traceback
from pathlib import Path

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from oarepo_cli.site.assets import copy_watched_paths, load_watched_paths
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import copy_tree
from oarepo_cli.wizard import WizardStep


class WatcherStep(WizardStep):
    def __init__(self, run_ui):
        super().__init__()
        self.run_ui = run_ui

    def should_run(self):
        return True

    @property
    def site_support(self) -> SiteSupport:
        return self.root.site_support

    @property
    def invenio_instance_path(self):
        return self.site_support.invenio_instance_path

    def after_run(self):
        observer = self.create_observer()
        ui_builder = self.create_ui_builder()

        observer.start()

        while True:
            try:
                # TODO: better termination handling
                time.sleep(60)
            except InterruptedError:
                break

        observer.join()
        if ui_builder:
            try:
                ui_builder.terminate()
                time.sleep(1)
                ui_builder.kill()
            except Exception as e:
                pass

    def create_observer(self):
        destination = self.invenio_instance_path
        watched_paths = load_watched_paths(
            self.invenio_instance_path / "watch.list.json",
            [
                f"{self.site_support.site_dir}/assets=assets",
                f"{self.site_support.site_dir}/static=static",
            ],
        )
        # recursively copy to destination
        copy_watched_paths(watched_paths, destination)
        # start watching
        observer = Observer()
        for path, target in watched_paths.items():
            print(f"Will watch {path} => {target}")
            observer.schedule(
                EventHandler(path, destination / target), path, recursive=True
            )
        return observer

    def create_ui_builder(self):
        if self.run_ui:
            return subprocess.Popen(
                ["npm", "run", "start"], cwd=f"{self.invenio_instance_path}/assets"
            )


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
