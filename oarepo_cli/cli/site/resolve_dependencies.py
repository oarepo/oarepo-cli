from oarepo_cli.cli.site.utils import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep

from ...utils import run_cmdline
import tomli_w


class ResolveDependenciesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I am going to resolve the python dependencies. You can re-run this action
anytime by calling nrp-cli upgrade --lock-only.
            """,
            **kwargs,
        )

    def after_run(self):
        # create pyproject.toml file
        models = [
            model_name for model_name, model_section in self.data.whole_data['models'].items()
            if model_section['installation_site'] == self.data.section
        ]
        uis = [
            ui_name for ui_name, ui_section in self.data.whole_data['ui'].items()
            if ui_section['installation_site'] == self.data.section
        ]
        pdm_file = {
            "project": {
                'name': self.data.section,
                'version': '1.0.0',
                'description': "",
                'authors': [
                    {'name': self.data['author_name'],
                     'email': self.data['author_email']},
                ],
                'dependencies': [
                    "oarepo>=11,<12",
                    *[
                        f"{model} @ file://../../models/{model}" for model in models
                    ],
                     * [
                         f"{ui} @ file://../../ui/{ui}" for ui in uis
                     ],
                    "site @ file://./site"
                ],
                'requires-python': ">=3.9,<=3.10",
            }
        }
        with open(self.site_dir/'pyproject.toml', 'wb') as f:
            tomli_w.dump(pdm_file, f)

        run_cmdline(
            "pdm",
            "lock",
            cwd=self.site_dir,
            environ={
                'PDM_IGNORE_ACTIVE_VENV': '1'
            }
        )
        requirements = run_cmdline(
            "pdm",
            "export",
            "-o",
            "requirements.txt",
            "--without-hashes",
            cwd=self.site_dir,
            environ={
                'PDM_IGNORE_ACTIVE_VENV': '1'
            },
            grab_stdout=True
        )
        # TODO: local editable paths
        with open(self.site_dir/'requirements.txt', 'w') as f:
            f.write(requirements)


    def should_run(self):
        return True
