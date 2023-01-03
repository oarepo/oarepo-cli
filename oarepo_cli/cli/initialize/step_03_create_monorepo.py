import os
import shutil
from pathlib import Path

from cookiecutter.main import cookiecutter

from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.ui.wizard import WizardStep


class CreateMonorepoStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="Now I will create the monorepo inside the selected directory.",
            **kwargs
        )

    def after_run(self, data):
        project_dir, repo_name, repo_out = self._repo_params(data)
        cookiecutter(
            get_cookiecutter_template("repo"),
            no_input=True,
            output_dir=repo_out,
            extra_context={
                **data,
                "repo_name": repo_name,
                "repo_human_name": repo_name,
            },
        )
        for f in (Path(repo_out) / repo_name).iterdir():
            shutil.move(f, project_dir)
        os.rmdir(Path(repo_out) / repo_name)
        os.rmdir(repo_out)

        return True

    def _repo_params(self, data):
        project_dir = data["project_dir"]
        while project_dir.endswith("/"):
            project_dir = project_dir[:-1]
        repo_name = Path(project_dir).name
        repo_out = project_dir + "-tmp"
        return project_dir,repo_name,repo_out

    def should_run(self, data):
        project_dir, repo_name, repo_out = self._repo_params(data)
        return not (Path(project_dir) / repo_name / 'invenio-cli').exists()
