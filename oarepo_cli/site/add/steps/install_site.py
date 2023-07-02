from __future__ import annotations

import datetime
import os
import re

from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.templates import get_cookiecutter_template
from oarepo_cli.utils import ProjectWizardMixin, commit_git
from oarepo_cli.wizard import InputStep, RadioStep, StaticStep, WizardStep


class InstallSiteStep(SiteWizardStepMixin, ProjectWizardMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            InputStep(
                "repository_name",
                prompt="""Enter the repository name ("title" of the HTML site)""",
                default=lambda data: re.sub("[_-]", " ", self.site_dir.name).title(),
            ),
            InputStep(
                "www",
                prompt="""Enter the WWW address on which the repository will reside""",
            ),
            InputStep(
                "author_name",
                prompt="""Author name""",
                default=os.environ.get("USERNAME") or os.environ.get("USER"),
            ),
            InputStep("author_email", prompt="""Author email"""),
            InputStep(
                "year",
                prompt="""Year (for copyright)""",
                default=datetime.datetime.today().strftime("%Y"),
            ),
            InputStep("copyright_holder", prompt="""Copyright holder"""),
            RadioStep(
                "use_oarepo_vocabularies",
                options={"yes": "Yes", "no": "No"},
                default="yes",
                heading=f"""
                    Are you planning to use extended vocabularies (extra fields on vocabularies, hierarchy in vocabulary items)? If in doubt, select 'yes'.
                        """,
            ),
            StaticStep(
                heading="""I have all the information to generate the site.
        To do so, I'll call the cookiecutter to install the size template. If anything goes wrong, please fix the problem
        and run the wizard again.
                    """,
            ),
            heading="""
Now I will add site sources, that can be used to change the overall CSS style and
configure your repository. Please fill in the required values. 
If not sure, keep the default values.""",
            **kwargs,
        )

    def on_before_run(self):
        self.data.setdefault(
            "transifex_project", self.data.get("config.project_package", "")
        )
        return True

    def after_run(self):
        site_name = self.site_dir.name
        site_dir = self.site_dir
        if not site_dir.parent.exists():
            site_dir.parent.mkdir(parents=True)

        self.run_cookiecutter(
            template=get_cookiecutter_template("site"),
            config_file=f"site-{site_name}",
            output_dir=str(site_dir.parent),
            extra_context=dict(
                project_name=self.data["repository_name"],
                project_shortname=self.site_dir.name,
                project_site=self.data["www"],
                jsonschemas_host=get_host_name(self.data["www"]),
                github_repo="",
                description=f"{self.data['repository_name']} OARepo Instance",
                author_name=self.data["author_name"],
                author_email=self.data["author_email"],
                year=self.data["year"],
                python_version="3.9",
                database="postgresql",
                search="opensearch2",
                file_storage="S3",
                development_tools="yes",
                site_code="yes",
                use_oarepo_vocabularies=self.data["use_oarepo_vocabularies"],
            ),
        )

        commit_git(
            self.data.project_dir,
            f"after-site-cookiecutter-{self.data.section}",
            f"Committed automatically after site {self.data.section} cookiecutter has been called",
        )

    def should_run(self):
        return not (self.site_dir / "variables").exists()


def get_host_name(url):
    if url.startswith("http://"):
        url = url[7:]
    if url.startswith("https://"):
        url = url[8:]
    return url.split("/", maxsplit=1)[0]
