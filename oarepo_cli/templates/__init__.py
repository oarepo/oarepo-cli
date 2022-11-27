from pathlib import Path


def get_cookiecutter_template(name):
    return str(Path(__file__).parent / name)
