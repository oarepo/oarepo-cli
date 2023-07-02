import shutil

from colorama import Fore, Style

from oarepo_cli.model.utils import ModelWizardStep
from oarepo_cli.wizard import RadioStep


class RemovePreviousModelStep(ModelWizardStep):
    def __init__(self):
        super().__init__(
            RadioStep(
                "merge_changes",
                options={
                    "merge": "Merge changes into the previously generated files",
                    "overwrite": "Remove previously generated files and start from scratch",
                },
                default="merge",
                heading=f"""
It seems that the model has been already generated. 

Should I try to {Fore.GREEN}merge{Fore.BLUE} the changes with the existing sources 
or {Fore.RED}remove{Fore.BLUE} the previously generated sources and generate from scratch?

{Fore.YELLOW}Please make sure that you have your existing sources safely committed into git repository
so that you might recover them if the compilation process fails.{Style.RESET_ALL}
""",
            )
        )

    def on_before_run(self):
        return (self.model_dir / "setup.cfg").exists()

    def after_run(self):
        if self.data.get("merge_changes") == "overwrite":

            def _rm(x):
                if x.exists():
                    if x.is_dir():
                        shutil.rmtree(x)
                    else:
                        x.unlink()

            _rm(self.model_package_dir)
            _rm(self.model_dir / "setup.cfg")
            _rm(self.model_dir / "data")
