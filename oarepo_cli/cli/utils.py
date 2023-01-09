from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import run_cmdline
from oarepo_cli.utils import add_to_pipfile_dependencies
from colorama import Fore, Style


class ProjectWizardMixin:
    def site_dir(self, data):
        if not hasattr(self, "site"):
            raise Exception("Current site not set")
        return data.project_dir / self.site["site_dir"]

    def invenio_cli(self, data):
        return data.project_dir / data.get("config.invenio_cli")

    def invenio_cli_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            self.invenio_cli(data),
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def pipenv_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def invenio_command(self, data, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            "run",
            "invenio",
            *args,
            cwd=cwd or self.site_dir(data),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )


class SiteMixin(ProjectWizardMixin):
    def site_dir(self, data):
        site_name = data.get("installation_site", None)
        if not site_name:
            raise Exception("Unexpected error: No installation site specified")
        site = data.get(f"sites.{site_name}")
        if not site:
            raise Exception(
                f"Unexpected error: Site with name {site_name} does not exist"
            )
        return data.project_dir / site["site_dir"]


class PipenvInstallWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    folder = None

    def get_steps(self, data):
        sites = data.whole_data.get("sites", {})
        if len(sites) == 1:
            data["installation_site"] = next(iter(sites))
            steps = []
        else:
            steps = [
                RadioWizardStep(
                    "installation_site",
                    options={
                        x: f"{Fore.GREEN}{x}{Style.RESET_ALL}"
                        for x in data.whole_data["sites"]
                    },
                    default=next(iter(data.whole_data["sites"])),
                    heading=f"""
            Select the site where you want to install the model to.
                """,
                    force_run=True,
                )
            ]
        return steps

    def heading(self, data):
        return f"""
    Now I will add the {self.folder} to site's Pipfile (if it is not there yet)
    and will run pipenv lock & install.
        """

    pause = True

    def after_run(self, data):
        # add package to pipfile
        self.add_to_pipfile(data)
        self.install_pipfile(data)

    def add_to_pipfile(self, data):
        pipfile = self.site_dir(data) / "Pipfile"
        add_to_pipfile_dependencies(
            pipfile, data.section, f"../../{self.folder}/{data.section}"
        )

    def install_pipfile(self, data):
        self.pipenv_command(data, "lock")
        self.pipenv_command(data, "install")

    def should_run(self, data):
        return True