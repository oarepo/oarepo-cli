from functools import cached_property


class SiteWizardStepMixin:
    @cached_property
    def site_support(self):
        return self.root.site_support

    @property
    def site_dir(self):
        return self.site_support.site_dir

    def get_invenio_configuration(self, *keys):
        return self.site_support.get_invenio_configuration(*keys)
