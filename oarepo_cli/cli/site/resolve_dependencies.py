import requirements

from oarepo_cli.cli.site.utils import SiteWizardStepMixin, get_site_local_packages
from oarepo_cli.wizard import WizardStep
from ...package_versions import OAREPO_VERSION, PYTHON_VERSION

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
        models, uis = get_site_local_packages(self.data)
        extras = [
            *[
                f"{model} @ file:///${{PROJECT_ROOT}}/../../models/{model}" for model in models
            ],
            *[
                f"{ui} @ file:///${{PROJECT_ROOT}}/../../ui/{ui}" for ui in uis
            ],
            "site @ file:///${PROJECT_ROOT}/site"
        ]
        # generate requirements just for oarepo package
        oarepo_requirements = self.generate_requirements([])
        oarepo_requirements = list(requirements.parse(oarepo_requirements))

        # get the current version of oarepo
        oarepo_requirement = [x for x in oarepo_requirements if x.name == 'oarepo'][0]

        # generate requirements for the local packages as well
        all_requirements = self.generate_requirements(extras)
        all_requirements = list(requirements.parse(all_requirements))

        # now make the difference of those two (we do not want to have oarepo dependencies in the result)
        # as oarepo will be installed to virtualenv separately (to handle system packages)
        oarepo_requirements_names = {
            x.name for x in oarepo_requirements
        }
        non_oarepo_requirements = [x for x in all_requirements if x.name not in oarepo_requirements_names]

        # remove local packages
        non_oarepo_requirements = [x for x in non_oarepo_requirements if 'file://' not in x.line]

        # and generate final requirements
        resolved_requirements = '\n'.join([
            oarepo_requirement.line,
            *[x.line for x in non_oarepo_requirements]
        ])
        (self.site_dir/'requirements.txt').write_text(resolved_requirements)


    def generate_requirements(self, extras):
        pdm_file = {
            "project": {
                'name': f"{self.data.section}-repository",
                'version': '1.0.0',
                'description': "",
                "packages": [],
                'authors': [
                    {'name': self.data['author_name'],
                     'email': self.data['author_email']},
                ],
                'dependencies': [
                    OAREPO_VERSION,
                    *extras
                ],
                'requires-python': PYTHON_VERSION,
            }
        }
        with open(self.site_dir/'pyproject.toml', 'wb') as f:
            tomli_w.dump(pdm_file, f)
        if not (self.site_dir / '.venv').exists():
            run_cmdline(
                "pdm",
                "venv",
                "create",
                "--with-pip",
                cwd=self.site_dir,
                environ={
                    'PDM_IGNORE_ACTIVE_VENV': '1'
                }
            )
        run_cmdline(
            "pdm",
            "lock",
            *(["-v"] if self.root.verbose else []),
            cwd=self.site_dir,
            environ={
                'PDM_IGNORE_ACTIVE_VENV': '1'
            }
        )
        requirements = run_cmdline(
            "pdm",
            "export",
            "-f", "requirements",
            "--without-hashes",
            cwd=self.site_dir,
            environ={
                'PDM_IGNORE_ACTIVE_VENV': '1'
            },
            grab_stdout=True
        )
        return requirements


    def should_run(self):
        return True
