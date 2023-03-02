import os
import shutil
from pathlib import Path

from oarepo_cli.cli.utils import ProjectWizardMixin
from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.ui.wizard import WizardStep
from oarepo_cli.utils import commit_git


def keep_existing_copy(src, dst, *, follow_symlinks=True):
    if os.path.isdir(dst):
        _dst = os.path.join(dst, os.path.basename(src))
    else:
        _dst = dst
    if Path(_dst).exists():
        return _dst
    return shutil.copy2(src, dst, follow_symlinks=follow_symlinks)


class CreateMonorepoStep(ProjectWizardMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="Now I will create the monorepo inside the selected directory.",
            **kwargs
        )

    def after_run(self):
        project_dir, repo_name, repo_out = self._repo_params
        self.run_cookiecutter(
            template=get_cookiecutter_template("repo"),
            config_file="monorepo",
            output_dir=str(repo_out),
            extra_context={
                **self.data,
                "repo_name": repo_name,
                "repo_human_name": repo_name,
            },
        )
        for f in (repo_out / repo_name).iterdir():
            shutil.move(f, project_dir, copy_function=keep_existing_copy)
        os.rmdir(repo_out / repo_name)
        os.rmdir(repo_out)
        commit_git(
            project_dir,
            "after-monorepo",
            "Committed automatically after monorepo has been created",
        )
        return True

    @property
    def _repo_params(self):
        project_dir = self.data.project_dir
        repo_name = project_dir.name
        repo_out = project_dir.parent / (project_dir.name + "-tmp")
        return project_dir, repo_name, repo_out

    def should_run(self):
        project_dir, repo_name, repo_out = self._repo_params
        return not (project_dir / "invenio-cli").exists()
