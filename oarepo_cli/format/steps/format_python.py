import os.path
from collections import defaultdict
from pathlib import Path

from oarepo_cli.utils import batched, run_cmdline
from oarepo_cli.wizard import WizardStep


class FormatPythonStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        pd = self.data.project_dir
        model_paths = [
            pd / "models" / model_name / model["package"]
            for model_name, model in self.data.whole_data.get("models", {}).items()
            if (pd / "models" / model / model["package"]).exists()
        ]
        ui_paths = [
            pd / "ui" / ui_name / ui["package"]
            for ui_name, ui in self.data.whole_data.get("ui", {}).items()
            if (pd / "ui" / ui / ui["package"]).exists()
        ]
        local_paths = [
            pd / "local" / local_name
            for local_name in self.data.whole_data.get("local", {})
            if (pd / "local" / local_name).exists()
        ]
        site_paths = [
            pd / "sites" / site_name
            for site_name in self.data.whole_data.get("sites", {})
            if (pd / "sites" / site_name).exists()
        ]
        python_source_paths = [*model_paths, *ui_paths, *local_paths, *site_paths]
        self.run_autoflake(python_source_paths, exclude=[])
        self.run_isort(python_source_paths)
        self.run_black(python_source_paths)
        self.format_jinja(ui_paths + local_paths, exclude=[])

    def run_autoflake(self, dirs, exclude):
        from autoflake import find_files, fix_file

        files = list(find_files([*dirs], True, exclude))

        for file_name in files:
            try:
                fix_file(
                    file_name,
                    args=defaultdict(
                        lambda: None,
                        in_place=True,
                        remove_all_unused_imports=True,
                        write_to_stdout=False,
                        verbose=True,
                    ),
                )
            except Exception as e:
                print(f"Error in autoflaking {file_name}: {e}")

    def run_isort(self, dirs):
        from isort.main import main

        main(["--profile", "black", *[str(x) for x in dirs]])

    def run_black(self, dirs):
        import black

        result = black.main([*[str(x) for x in dirs]], standalone_mode=False)

    def format_jinja(self, dirs, exclude):
        # look for 'templates' folder inside the paths
        from autoflake import find_files
        from djlint import Config, process

        for f in find_files([*dirs], True, exclude):
            if not "templates" in os.path.split(f) or not f.endswith(".html"):
                continue
            config = Config(src=f, profile="jinja")
            process(config, Path(f))

    def format_jsx(self, dirs, exclude):
        from autoflake import find_files

        if "INVENIO_INSTANCE_PATH" in os.environ:
            assets_dir = Path(os.environ["INVENIO_INSTANCE_PATH"]) / "assets"
        else:
            sites = self.data.whole_data.get("sites")
            if not sites:
                return
            site = next(iter(sites.values()))
            assets_dir = (
                self.data.project_dir / site["site_dir"] / ".venv" / "var" / "instance"
            )
        if assets_dir.exists() and (assets_dir / "package.json").exists():
            # TODO: only when needed
            run_cmdline(["npm", "ci"], cwd=assets_dir)
        else:
            return
        files = [
            f
            for f in find_files([*dirs], True, exclude)
            if f.endswith(".jsx")
            or f.endswith(".tsx")
            or f.endswith(".js")
            or f.endswith(".ts")
        ]
        for chunk in batched(files, 50):
            run_cmdline(["npm", "run", "lint", "--fix", *chunk], cwd=assets_dir)
            run_cmdline(["npm", "run", "prettier", "--write", *chunk], cwd=assets_dir)
