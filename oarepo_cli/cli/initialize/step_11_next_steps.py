from oarepo_cli.ui.wizard import WizardStep


class NextStepsStep(WizardStep):
    def __init__(self, **kwargs):
        super().__init__(
            heading=lambda data: f"""
The repository skeleton has been created and dependencies installed.
To check that everything has been installed successfully you may want
to start your new repository by running

    cd {data['project_dir']}/{data['site_package']}
    pipenv run invenio run --cert docker/nginx/test.crt --key docker/nginx/test.key
    
and point your browser to 

    https://localhost:5000/
    
After doing so, add your model by calling

    oarepo-configure model add <modelname>
    
edit the contents of metadata.yaml to suit your needs and run

    oarepo-configure model compile <modelname>
    oarepo-configure model install <modelname>
    
If you run invenio again and head to https://localhost:5000/api/<modelname>
an empty listing should be returned.

In the next step, add a UI application by calling

    oarepo-configure ui add <uiname>
    oarepo-configure ui compile <uiname>
    oarepo-configure ui install <uiname>

After restarting the server, a UI will be available at 
https://localhost:5000/<uiname>

Detailed information for using oarepo-configure and other
oarepo scripts is available at .....TODO......
            """,
            **kwargs,
        )

    def should_run(self, data):
        return True
