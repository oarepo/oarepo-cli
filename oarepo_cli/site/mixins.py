from functools import cached_property
from pathlib import Path

from oarepo_cli.site.site_support import SiteSupport


class SiteWizardStepMixin:
    @cached_property
    def site_support(self) -> SiteSupport:
        return self.root.site_support

    @property
    def site_dir(self) -> Path:
        return self.site_support.site_dir

    def get_invenio_configuration(self, *keys):
        return self.site_support.get_invenio_configuration(*keys)
