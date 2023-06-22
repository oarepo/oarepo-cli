import requirements
import tomli_w

from oarepo_cli.package_versions import OAREPO_VERSION, PYTHON_VERSION
from oarepo_cli.site.utils import SiteWizardStepMixin, get_site_local_packages
from oarepo_cli.wizard import WizardStep


class ResolveDependenciesStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading="""
I am going to resolve the python dependencies.
            """,
            **kwargs,
        )

    def after_run(self):
        # create pyproject.toml file
        models, uis, local_packages = get_site_local_packages(self.data)
        extras = [
            *[
                f"{model} @ file:///${{PROJECT_ROOT}}/../../models/{model}"
                for model in models
                if (self.site_dir.parent.parent / "models" / model).exists()
            ],
            *[
                f"{ui} @ file:///${{PROJECT_ROOT}}/../../ui/{ui}"
                for ui in uis
                if (self.site_dir.parent.parent / "models" / ui).exists()
            ],
            *[
                f"{local} @ file:///${{PROJECT_ROOT}}/../../local/{local}"
                for local in local_packages
                if (self.site_dir.parent.parent / "local" / local).exists()
            ],
            "site @ file:///${PROJECT_ROOT}/site",
        ]
        # generate requirements just for oarepo package
        oarepo_requirements = self.generate_requirements([])
        oarepo_requirements = list(requirements.parse(oarepo_requirements))

        # get the current version of oarepo
        oarepo_requirement = [x for x in oarepo_requirements if x.name == "oarepo"][0]

        # generate requirements for the local packages as well
        all_requirements = self.generate_requirements(extras)
        all_requirements = list(requirements.parse(all_requirements))

        # now make the difference of those two (we do not want to have oarepo dependencies in the result)
        # as oarepo will be installed to virtualenv separately (to handle system packages)
        oarepo_requirements_names = {x.name for x in oarepo_requirements}
        non_oarepo_requirements = [
            x for x in all_requirements if x.name not in oarepo_requirements_names
        ]

        # remove local packages
        non_oarepo_requirements = [
            x for x in non_oarepo_requirements if "file://" not in x.line
        ]

        # and generate final requirements
        resolved_requirements = "\n".join(
            [oarepo_requirement.line, *[x.line for x in non_oarepo_requirements]]
        )
        (self.site_dir / "requirements.txt").write_text(resolved_requirements)

    def generate_requirements(self, extras):
        pdm_file = {
            "project": {
                "name": f"{self.data.section}-repository",
                "version": "1.0.0",
                "description": "",
                "packages": [],
                "authors": [
                    {
                        "name": self.data["author_name"],
                        "email": self.data["author_email"],
                    },
                ],
                "dependencies": [OAREPO_VERSION, *extras],
                "requires-python": PYTHON_VERSION,
            }
        }
        with open(self.site_dir / "pyproject.toml", "wb") as f:
            tomli_w.dump(pdm_file, f)

        self.call_pdm(
            "lock",
            *(["-v"] if self.root.verbose else []),
        )
        return self.call_pdm(
            "export", "-f", "requirements", "--without-hashes", grab_stdout=True
        )

    def should_run(self):
        return True
