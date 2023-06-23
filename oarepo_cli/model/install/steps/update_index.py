from colorama import Fore, Style

from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.wizard import RadioStep


class UpdateSearchIndexModelStep(ModelWizardStep):
    steps = (
        RadioStep(
            "update_opensearch",
            options={
                "run": f"{Fore.GREEN}Update opensearch index{Style.RESET_ALL}",
                "skip": f"{Fore.RED}Do not update opensearch index{Style.RESET_ALL}",
            },
            default="run",
            heading=f"""
Before the model can be used, I need to create index inside opensearch server.
This is not necessary if the model has not been changed. Should I create/update
the index? 
                            """,
            force_run=True,
        ),
    )

    def after_run(self):
        if self.data["update_opensearch"] == "run":
            self.site_support.call_invenio("oarepo", "index", "init")

    def should_run(self):
        return True
