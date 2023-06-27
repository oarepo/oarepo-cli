from oarepo_cli.model.gen.base import GeneratedFiles
from oarepo_cli.wizard import StaticStep, Wizard

from .steps.add_custom_fields import AddCustomFieldsWizardStep
from .steps.add_docs_base import AddDocsBaseWizardStep
from .steps.add_files import AddFilesWizardStep
from .steps.add_metadata import AddMetadataWizardStep
from .steps.add_nr_vocabularies import AddNRVocabulariesWizardStep
from .steps.add_permissions import AddPermissionsWizardStep
from .steps.add_pid_type import AddPIDTypeWizardStep
from .steps.add_relations import AddRelationsWizardStep
from .steps.add_tests import AddTestsWizardStep
from .steps.add_vocabularies import AddVocabulariesWizardStep
from .steps.create_model import EmptyModelWizardStep


class AddModelWizard(Wizard):
    def __init__(self):
        super().__init__(
            StaticStep(
                heading="""
        Before creating the datamodel, I'll ask you a few questions.
        If unsure, use the default value.
            """,
            ),
            # these just generate sources, no need to run them inside docker
            EmptyModelWizardStep(),
            AddDocsBaseWizardStep(),
            AddFilesWizardStep(),
            AddCustomFieldsWizardStep(),
            AddNRVocabulariesWizardStep(),
            AddVocabulariesWizardStep(),
            AddRelationsWizardStep(),
            AddMetadataWizardStep(),
            AddPermissionsWizardStep(),
            AddPIDTypeWizardStep(),
            AddTestsWizardStep(),
        )

    def run_wizard(
        self, data, *, no_input=False, silent=False, selected_steps=None, verbose=False
    ):
        self.files = GeneratedFiles(data.project_dir / "models" / data.section)
        super().run_wizard(
            data,
            no_input=no_input,
            silent=silent,
            selected_steps=selected_steps,
            verbose=verbose,
        )
