from oarepo_ui.resources import BabelComponent
from oarepo_ui.resources.config import RecordsUIResourceConfig


class {{cookiecutter.resource_config}}(RecordsUIResourceConfig):
    template_folder = "../templates"
    url_prefix = "{{cookiecutter.url_prefix}}"
    blueprint_name = "{{cookiecutter.app_name}}"
    ui_serializer_class = "{{cookiecutter.ui_serializer_class}}"
    api_service = "{{cookiecutter.api_service}}"
    layout = "{{cookiecutter.api_service}}"

    components = [BabelComponent]
    try:
        from oarepo_vocabularies.ui.resources.components import (
            DepositVocabularyOptionsComponent,
        )
        components.append(DepositVocabularyOptionsComponent)
    except ImportError:
        pass

    templates = {
        "detail": {
            "layout": "{{cookiecutter.app_package}}/Detail.html.jinja",
            "blocks": {
                "record_main_content": "Main",
                "record_sidebar": "Sidebar"
            },
        },
        "search": {"layout": "{{cookiecutter.app_package}}/Search.html.jinja", "app_id": "{{cookiecutter.app_package|title}}.Search"},
        "edit": {"layout": "{{cookiecutter.app_package}}/Deposit.html.jinja"},
        "create": {"layout": "{{cookiecutter.app_package}}/Deposit.html.jinja"},
    }
