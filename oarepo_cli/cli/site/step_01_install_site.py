from __future__ import annotations

import datetime
import os
import re

from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.ui.wizard import StaticWizardStep, WizardStep
from oarepo_cli.ui.wizard.steps import InputWizardStep, RadioWizardStep

from ...utils import commit_git, get_cookiecutter_source, run_cmdline


class InstallSiteStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
Now I will add site sources, that can be used to change the overall CSS style and
configure your repository. Please fill in the following values. 
If not sure, keep the default values.""",
            **kwargs,
        )

    def get_steps(self):
        self.data.setdefault(
            "transifex_project", self.data.get("config.project_package", "")
        )
        # substeps of this step
        site_dir_name = self.site_dir.name
        return [
            InputWizardStep(
                "repository_name",
                prompt="""Enter the repository name ("title" of the HTML site)""",
                default=re.sub("[_-]", " ", site_dir_name).title(),
            ),
            InputWizardStep(
                "www",
                prompt="""Enter the WWW address on which the repository will reside""",
            ),
            InputWizardStep(
                "author_name",
                prompt="""Author name""",
                default=os.environ.get("USERNAME") or os.environ.get("USER"),
            ),
            InputWizardStep("author_email", prompt="""Author email"""),
            InputWizardStep(
                "year",
                prompt="""Year (for copyright)""",
                default=datetime.datetime.today().strftime("%Y"),
            ),
            InputWizardStep("copyright_holder", prompt="""Copyright holder"""),
            RadioWizardStep(
                "use_oarepo_vocabularies",
                options={"yes": "Yes", "no": "No"},
                default="yes",
                heading=f"""
            Are you planning to use extended vocabularies (extra fields on vocabularies, hierarchy in vocabulary items)? If in doubt, select 'yes'.
                """,
            ),
            StaticWizardStep(
                heading="""I have all the information to generate the site.
To do so, I'll call the invenio client. If anything goes wrong, please fix the problem
and run the wizard again.
            """,
            ),
        ]

    def after_run(self):
        # create site config for invenio-cli
        cookiecutter_config_file = self.data.project_dir / ".invenio"
        site_dir = self.site_dir
        if not site_dir.parent.exists():
            site_dir.parent.mkdir(parents=True)

        with open(cookiecutter_config_file, "w") as f:
            print(
                f"""
[cookiecutter]
project_name = {self.data['repository_name']}
project_shortname = {self.site_dir.name}
project_site = {self.data['www']}
github_repo = 
description = {self.data['repository_name']} OARepo Instance
author_name = {self.data['author_name']}
author_email = {self.data['author_email']}
year = {self.data['year']}
python_version = 3.9
database = postgresql
search = opensearch2
file_storage = S3
development_tools = yes
site_code = yes
use_oarepo_vocabularies = {self.data['use_oarepo_vocabularies']}
                """,
                file=f,
            )
        # and run invenio-cli with our site template
        # (submodule from https://github.com/oarepo/cookiecutter-oarepo-instance)

        cookiecutter_path, cookiecutter_branch = get_cookiecutter_source(
            "OAREPO_SITE_COOKIECUTTER_VERSION",
            "https://github.com/oarepo/cookiecutter-site",
            "v11.0",
            master_version="master",
        )

        run_cmdline(
            self.data.project_dir / self.data.get("config.invenio_cli"),
            "init",
            "rdm",
            "-t",
            cookiecutter_path,
            *(
                [
                    "-c",
                    cookiecutter_branch,
                ]
                if cookiecutter_branch
                else []
            ),
            "--no-input",
            "--config",
            str(cookiecutter_config_file),
            cwd=self.data.project_dir / "sites",
            environ={
                "PIPENV_IGNORE_VIRTUALENVS": "1",
                # use our own cookiecutter, not the system one
                "PATH": f"{self.data.get('config.project_dir')}/.bin:{os.environ['PATH']}",
            },
        )
        with open(self.site_dir / ".check.ok", "w") as f:
            f.write("oarepo check ok")
        commit_git(
            self.data.project_dir,
            f"after-site-cookiecutter-{self.data.section}",
            f"Committed automatically after site {self.data.section} cookiecutter has been called",
        )

    def should_run(self):
        return not (self.site_dir / ".check.ok").exists()
