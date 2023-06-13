import shutil

from oarepo_cli.utils import ProjectWizardMixin
from oarepo_cli.wizard import WizardStep


class RemoveLocalWizardStep(ProjectWizardMixin, WizardStep):
    def after_run(self):
        shutil.rmtree(self.local_dir)

    def should_run(self):
        return self.local_dir.exists()

    @property
    def local_name(self):
        return self.data.section_path[-1]

    @property
    def local_dir(self):
        return self.data.project_dir / self.data["local_dir"]
