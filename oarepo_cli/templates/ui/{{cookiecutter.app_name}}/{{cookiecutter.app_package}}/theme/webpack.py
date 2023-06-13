from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": dict(
            entry={
                "{{cookiecutter.app_package}}_components": "./js/{{cookiecutter.app_package}}/custom-components.js"
            },
            dependencies={},
            devDependencies={},
            aliases={},
        )
    },
)
