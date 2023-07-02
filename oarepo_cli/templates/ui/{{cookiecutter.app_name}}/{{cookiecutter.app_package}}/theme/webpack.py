from invenio_assets.webpack import WebpackThemeBundle

theme = WebpackThemeBundle(
    __name__,
    "assets",
    default="semantic-ui",
    themes={
        "semantic-ui": dict(
            entry={
                "{{cookiecutter.app_package}}_components": "./js/{{cookiecutter.app_package}}/custom-components.js",
                "{{cookiecutter.app_package}}_search": "./js/{{cookiecutter.app_package}}/search/index.js",
            },
            dependencies={
                "react-searchkit": "^2.0.0",
            },
            devDependencies={},
            aliases={
                "@translations/{{cookiecutter.app_package}}": "translations/{{cookiecutter.app_package}}",
            },
        )
    },
)
