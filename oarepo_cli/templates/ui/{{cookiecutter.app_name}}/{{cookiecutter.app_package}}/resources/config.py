from oarepo_ui.resources.config import RecordsUIResourceConfig


class {{cookiecutter.resource_config}}(RecordsUIResourceConfig):
    template_folder = "../templates"
    url_prefix = "{{cookiecutter.url_prefix}}"
    blueprint_name = "{{cookiecutter.app_name}}"
    ui_serializer_class = "{{cookiecutter.ui_serializer_class}}"
    api_service = "{{cookiecutter.api_service}}"
    layout = "{{cookiecutter.api_service}}"

    templates = {
        "detail": {
            "layout": "{{cookiecutter.app_package}}/detail.html",
            "blocks": {
                "record_main_content": "{{cookiecutter.app_package}}/main.html",
                "record_sidebar": "{{cookiecutter.app_package}}/sidebar.html"                
            },
        },
        "search": {"layout": "{{cookiecutter.app_package}}/search.html"},
    }
