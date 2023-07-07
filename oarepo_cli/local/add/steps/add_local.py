from pathlib import Path

from oarepo_cli.utils import ProjectWizardMixin, run_cmdline
from oarepo_cli.wizard import WizardStep


class GitHubCloneWizardStep(ProjectWizardMixin, WizardStep):
    def after_run(self):
        self.local_dir.parent.mkdir(exist_ok=True, parents=True)
        if self.data.get("github_clone_url"):
            if self.data.get("branch"):
                run_cmdline(
                    "git",
                    "clone",
                    "--branch",
                    self.data["branch"],
                    self.data["github_clone_url"],
                    str(self.local_dir),
                    cwd=self.local_dir.parent,
                )
            else:
                run_cmdline(
                    "git",
                    "clone",
                    self.data["github_clone_url"],
                    str(self.local_dir),
                    cwd=self.local_dir.parent,
                )
            # it has been checked out, so it probably is there just because we are working
            # on a library - so put it to gitignore
            self.add_to_gitignore()
        else:
            self.run_cookiecutter(
                template="https://github.com/AntoineCezar/cookiecutter-pypkg",
                config_file=f"local-{self.local_name}",
                output_dir=self.data.project_dir / "local",
                extra_context={
                    "project_name": "Python Project",
                    "project_slug": self.local_name,
                    "package_name": "{{ cookiecutter.project_slug.replace('-', '_') }}",
                    "test_runner": "pytest",
                    "build_docs": "n",
                    "build_rpm": "n",
                    "exemple": "n",
                    "git_init": "n",
                },
            )
            # this is a newly created, probably will stay here - so do not put it to gitignore

    def should_run(self):
        return not self.local_dir.exists()

    @property
    def local_name(self):
        return self.data.section_path[-1]

    @property
    def local_dir(self):
        return self.data.project_dir / self.data["local_dir"]

    def add_to_gitignore(self):
        gitignore: Path = self.local_dir.parent / ".gitignore"
        if gitignore.exists():
            content = gitignore.read_text()
        else:
            content = ""
        content = [x.strip() for x in content.split("\n")]
        if self.local_name not in content:
            content.append(self.local_name)
            gitignore.write_text("\n".join(content))
