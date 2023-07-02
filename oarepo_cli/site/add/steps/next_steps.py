from oarepo_cli.site.mixins import SiteWizardStepMixin
from oarepo_cli.wizard import WizardStep


class NextStepsStep(SiteWizardStepMixin, WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading=lambda data: f"""
The repository skeleton has been created and dependencies installed.
To check that everything has been installed successfully you may want
to start your new repository by running

    nrp run
    
and point your browser to 

    https://localhost:5000/
    
After doing so, add your model by calling

    nrp model add <modelname>
    
edit the contents of metadata.yaml to suit your needs and run

    nrp model compile <modelname>
    nrp model install <modelname>
    
If you run invenio again and head to https://localhost:5000/api/<modelname>
an empty listing should be returned.

In the next step, add a UI application by calling

    nrp ui add <uiname>
    nrp ui compile <uiname>
    nrp ui install <uiname>

After restarting the server, a UI will be available at 
https://localhost:5000/<uiname>
            """,
            **kwargs,
        )

    def should_run(self):
        return True
