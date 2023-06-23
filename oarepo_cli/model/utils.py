import os

from oarepo_cli.model.model_support import ModelSupport
from oarepo_cli.site.site_support import SiteSupport
from oarepo_cli.utils import ProjectWizardMixin, SiteMixin
from oarepo_cli.wizard import WizardStep


class ModelWizardStep(SiteMixin, ProjectWizardMixin, WizardStep):
    @property
    def model_support(self) -> ModelSupport:
        return self.root.model_support

    @property
    def site_support(self) -> SiteSupport:
        return self.root.site_support

    @property
    def model_name(self):
        return self.model_support.model_name

    @property
    def model_dir(self):
        return self.model_support.model_dir

    @property
    def model_package_dir(self):
        return self.model_dir / os.sep.join(self.data["model_package"].split("."))
