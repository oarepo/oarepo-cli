import functools
import shutil
import sys
import os
from pathlib import Path

import click
import yaml
from colorama import Fore, Style

from oarepo_cli.config import MonorepoConfig
from oarepo_cli.ui.wizard.steps import RadioWizardStep, WizardStep
from oarepo_cli.utils import add_to_pipfile_dependencies, run_cmdline


def with_config(
    config_section=None, project_dir_as_argument=False, config_as_argument=False
):
    def wrapper(f):
        @(
            click.argument(
                "project_dir",
                type=click.Path(exists=False, file_okay=False),
                required=True,
            )
            if project_dir_as_argument
            else click.option(
                "--project-dir",
                type=click.Path(exists=True, file_okay=False),
                required=False,
                help="Directory containing an already initialized project. "
                "If not set, current directory is used",
            )
        )
        @click.option(
            "--no-banner",
            is_flag=True,
            type=bool,
            required=False,
            help="Do not show the welcome banner",
        )
        @click.option(
            "--no-input",
            is_flag=True,
            type=bool,
            required=False,
            help="Take options from the config file, skip user input",
        )
        @click.option(
            "--silent",
            is_flag=True,
            type=bool,
            required=False,
            help="Do not output program's messages. "
            "External program messages will still be displayed",
        )
        @click.option(
            "--verbose",
            is_flag=True,
            type=bool,
            required=False,
            help="Verbose output",
        )
        @(
            click.argument(
                "config",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
                required=True,
            )
            if config_as_argument
            else click.option(
                "--config",
                type=click.Path(exists=True, file_okay=True, dir_okay=False),
                required=False,
                help="Merge this config to the main config in target directory and proceed",
            )
        )
        @functools.wraps(f)
        def wrapped(
            project_dir=None,
            no_input=False,
            silent=False,
            config=None,
            verbose=False,
            **kwargs,
        ):
            if not project_dir:
                project_dir = Path.cwd()
            project_dir = Path(project_dir).absolute()
            oarepo_yaml_file = project_dir / "oarepo.yaml"

            if callable(config_section):
                section = config_section(**kwargs)
            else:
                section = config_section or "config"

            cfg = MonorepoConfig(oarepo_yaml_file, section=section)

            if oarepo_yaml_file.exists():
                cfg.load()

            if config:
                config_data = yaml.safe_load(Path(config).read_text())
                cfg.merge_config(config_data, top=not config_section)

            cfg.no_input = no_input
            cfg.silent = silent
            cfg.verbose = verbose

            kwargs.pop("cfg", None)
            kwargs.pop("project_dir", None)
            try:
                return f(project_dir=project_dir, cfg=cfg, **kwargs)
            except Exception as e:
                if cfg.verbose:
                    import traceback

                    traceback.print_exc()
                else:
                    print(str(e))
                raise
                sys.exit(1)

        return wrapped

    return wrapper


class ProjectWizardMixin:
    @property
    def site_dir(self):
        if not hasattr(self, "site"):
            raise Exception("Current site not set")
        return self.data.project_dir / self.site["site_dir"]

    @property
    def invenio_cli(self):
        return self.data.project_dir / self.data.get("config.invenio_cli")

    @property
    def oarepo_cli(self):
        return self.data.project_dir / self.data.get("config.oarepo_cli")

    def invenio_cli_command(self, *args, cwd=None, environ=None):
        return run_cmdline(
            self.invenio_cli,
            *args,
            cwd=cwd or self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def pipenv_command(self, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            *args,
            cwd=cwd or self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def invenio_command(self, *args, cwd=None, environ=None):
        return run_cmdline(
            "pipenv",
            "run",
            "invenio",
            *args,
            cwd=cwd or self.site_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )

    def run_cookiecutter(
        self,
        template,
        config_file,
        checkout=None,
        output_dir=None,
        extra_context=None,
        environ=None,
    ):
        config_dir: Path = self.data.project_dir / ".cookiecutters"
        config_dir.mkdir(parents=True, exist_ok=True)
        config_file = config_dir / f"{config_file}.yaml"
        config_file.write_text(yaml.safe_dump({"default_context": extra_context}))
        cookiecutter_command = (
            Path(sys.executable or sys.argv[0]).absolute().parent / "cookiecutter"
        )
        output_dir_temp = f"{output_dir}-tmp"
        output_dir = Path(output_dir)
        output_dir_temp = Path(output_dir_temp)
        args = [
            template,
            "--no-input",
            "-o",
            output_dir_temp,
            "--config-file",
            config_file,
        ]
        if checkout:
            args.append("-c")
            args.append(checkout)

        run_cmdline(
            cookiecutter_command,
            *args,
            cwd=self.data.project_dir,
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1", **(environ or {})},
        )
        merge_from_temp_to_target(output_dir_temp, output_dir)


class SiteMixin(ProjectWizardMixin):
    @property
    def site_dir(self):
        site_name = self.data.get("installation_site", None)
        if not site_name:
            raise Exception("Unexpected error: No installation site specified")
        site = self.data.get(f"sites.{site_name}")
        if not site:
            raise Exception(
                f"Unexpected error: Site with name {site_name} does not exist"
            )
        return self.data.project_dir / site["site_dir"]


class PipenvInstallWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    folder = None

    def get_steps(self):
        sites = self.data.whole_data.get("sites", {})
        if len(sites) == 1:
            self.data["installation_site"] = next(iter(sites))
            steps = []
        else:
            steps = [
                RadioWizardStep(
                    "installation_site",
                    options={
                        x: f"{Fore.GREEN}{x}{Style.RESET_ALL}"
                        for x in self.data.whole_data["sites"]
                    },
                    default=next(iter(self.data.whole_data["sites"])),
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

    def after_run(self):
        # add package to pipfile
        self.add_to_pipfile()
        self.install_pipfile()

    def add_to_pipfile(self):
        pipfile = self.site_dir / "Pipfile"
        add_to_pipfile_dependencies(
            pipfile, self.data.section, f"../../{self.folder}/{self.data.section}"
        )

    def install_pipfile(self):
        self.pipenv_command("lock")
        self.pipenv_command("install")

    def should_run(self):
        return True


def merge_from_temp_to_target(output_dir_temp, output_dir):
    source: Path
    for source in output_dir_temp.rglob("*"):
        rel = source.relative_to(output_dir_temp)
        dest: Path = output_dir / rel
        if source.is_dir():
            if not dest.exists():
                dest.mkdir(parents=True)
        elif source.is_file():
            if not dest.exists():
                if not dest.parent.exists():
                    dest.parent.mkdir(parents=True)
                shutil.copy(source, dest)
    shutil.rmtree(output_dir_temp)
