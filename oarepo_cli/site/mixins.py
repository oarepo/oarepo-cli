import json
import os
from functools import cached_property

from dotenv import dotenv_values

from oarepo_cli.site.site_support import SiteSupport


class SiteWizardStepMixin:
    @cached_property
    def site_support(self):
        return SiteSupport(self.data)

    @property
    def site_dir(self):
        return self.site_support.site_dir

    def get_invenio_configuration(self, *keys):
        values = dotenv_values(self.site_dir / "variables")
        values.update({
            k: v for k, v in os.environ.items()
            if k.startswith('INVENIO_')
        })
        def convert(x):
            try:
                if x == "False":
                    return False
                if x == "True":
                    return True
                return json.loads(x)
            except:
                return x

        try:
            return [convert(values[x]) for x in keys]
        except KeyError as e:
            raise KeyError(
                f"Configuration key not found in defaults: {values.keys()}: {e}"
            )
