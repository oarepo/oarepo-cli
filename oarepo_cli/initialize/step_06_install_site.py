from __future__ import annotations

import datetime
import os
from pathlib import Path

from ..utils import run_cmdline

from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.ui.wizard import StaticWizardStep, WizardStep
from oarepo_cli.ui.wizard.steps import InputWizardStep


class InstallSiteStep(WizardStep):
    step_name = "install-site"

    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I will add site sources, that can be used to change the overall CSS style and
configure your repository. Please fill in the following values. 
If not sure, keep the default values.""",
            **kwargs,
        )

    def get_steps(self, data):
        data.setdefault("site_dir", "site")
        data.setdefault("site_package", "site")
        data.setdefault("year", datetime.datetime.today().strftime("%Y"))
        data.setdefault("transifex_project", data.get("project_package", ""))
        data.setdefault(
            "repository_name", data.get("project_package").replace("_", " ").title()
        )
        data.setdefault(
            "author_name", os.environ.get("USERNAME") or os.environ.get("USERNAME")
        )
        # substeps of this step
        return [
            InputWizardStep(
                "repository_name",
                prompt="""Enter the repository name ("title" of the HTML site)""",
            ),
            InputWizardStep(
                "www",
                prompt="""Enter the WWW address on which the repository will reside""",
            ),
            InputWizardStep(
                "site_package", prompt="""Site package (keep the default if not sure)"""
            ),
            InputWizardStep("author_name", prompt="""Author name"""),
            InputWizardStep("author_email", prompt="""Author email"""),
            InputWizardStep("year", prompt="""Year (for copyright)"""),
            InputWizardStep("copyright_holder", prompt="""Copyright holder"""),
            StaticWizardStep(
                "install-site-before-generate",
                heading="""I have all the information to generate the site.
To do so, I'll call the invenio client. If anything goes wrong, please fix the problem
and run the wizard again.
            """,
            ),
        ]

    def after_run(self, data):
        # create site config for invenio-cli
        cookiecutter_config_file = Path(data["project_dir"]) / ".invenio"
        with open(cookiecutter_config_file, "w") as f:
            print(
                f"""
[cookiecutter]
project_name = {data['repository_name']}
project_shortname = {data['site_package']}
project_site = {data['www']}
github_repo = 
description = {data['repository_name']} OARepo Instance
author_name = {data['author_name']}
author_email = {data['author_email']}
year = {data['year']}
python_version = 3.9
database = postgresql
search = opensearch2
file_storage = S3
development_tools = yes
                """,
                file=f,
            )
        # and run invenio-cli with our site template
        # (submodule from https://github.com/oarepo/cookiecutter-oarepo-instance)
        run_cmdline(
            data["invenio_cli"],
            "init",
            "rdm",
            "-t",
            "https://github.com/oarepo/cookiecutter-site",
            "-c",
            "v10.0",
            "--no-input",
            "--config",
            str(cookiecutter_config_file),
            cwd=Path(data["project_dir"]),
            environ={"PIPENV_IGNORE_VIRTUALENVS": "1"},
        )
