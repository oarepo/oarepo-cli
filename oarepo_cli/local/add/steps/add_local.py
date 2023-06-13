from oarepo_cli.utils import ProjectWizardMixin, run_cmdline
from oarepo_cli.wizard import InputStep, WizardStep


class GitHubCloneWizardStep(ProjectWizardMixin, WizardStep):
    def __init__(self):
        super().__init__(
            InputStep(
                "github_clone_url",
                prompt="Enter github clone url (or empty to initialize an empty package)",
                required=False,
            ),
        )

    def after_run(self):
        self.local_dir.parent.mkdir(exist_ok=True, parents=True)
        if self.data.get("github_clone_url"):
            run_cmdline(
                "git",
                "clone",
                self.data["github_clone_url"],
                str(self.local_dir),
                cwd=self.local_dir.parent,
            )
        else:
            self.run_cookiecutter(
                template="https://github.com/AntoineCezar/cookiecutter-pypkg/blob/develop/cookiecutter.json",
                config_file=f"local-{self.local_name}",
                output_dir=self.data.project_dir / "ui",
                extra_context={
                    "project_name": "Python Project",
                    "project_slug": self.local_name,
                    "package_name": "{{ cookiecutter.project_slug.replace('-', '_') }}",
                    "test_runner": ["pytest"],
                    "build_docs": "n",
                    "build_rpm": "n",
                    "exemple": "n",
                    "git_init": "n",
                },
            )

    def should_run(self):
        return not self.local_dir.exists()

    @property
    def local_name(self):
        return self.data.section_path[-1]

    @property
    def local_dir(self):
        return self.data.project_dir / self.data["local_dir"]
