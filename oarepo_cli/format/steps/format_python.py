from collections import defaultdict

from oarepo_cli.wizard import WizardStep


class FormatPythonStep(WizardStep):
    def should_run(self):
        return True

    def after_run(self):
        pd = self.data.project_dir
        python_source_paths = [
            *[
                pd / "models" / model_name / model['package']
                for model_name, model in self.data.whole_data.get('models', {}).items()
                if (pd / "models" / model / model['package']).exists()
            ],
            *[
                pd / "ui"/ui_name/ui['package']
                for ui_name, ui in self.data.whole_data.get('ui', {}).items()
                if (pd / "ui" / ui / ui['package']).exists()
            ],
            *[
                pd / "local"/local_name
                for local_name in self.data.whole_data.get('local', {})
                if (pd / "local" / local_name).exists()
            ],
            *[
                pd / "sites" / site_name
                for site_name in self.data.whole_data.get('sites', {})
                if (pd / "sites" / site_name).exists()
            ]
        ]
        self.run_autoflake(python_source_paths)
        self.run_isort(python_source_paths)
        self.run_black(python_source_paths)

    def run_autoflake(self, dirs):
        from autoflake import find_files, fix_file

        exclude = []
        files = list(find_files([*dirs], True, exclude))

        for file_name in files:
            try:
                fix_file(
                    file_name,
                    args=defaultdict(
                        lambda: None,
                        in_place=True,
                        remove_all_unused_imports=True,
                        write_to_stdout=False,
                        verbose=True
                    )
                )
            except Exception as e:
                print(f'Error in autoflaking {file_name}: {e}')

    def run_isort(self, dirs):
        from isort.main import main
        main(['--profile', 'black', *[str(x) for x in dirs]])

    def run_black(self, dirs):
        import black
        result = black.main([*[str(x) for x in dirs]], standalone_mode=False)
