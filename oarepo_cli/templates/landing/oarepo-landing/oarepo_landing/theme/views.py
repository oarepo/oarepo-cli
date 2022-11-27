from flask import Blueprint, current_app, render_template
from flask_babelex import get_locale
from flask_babelex import lazy_gettext as _
from flask_menu import current_menu


#
# Registration
#
def create_blueprint(app):
    blueprint = Blueprint(
        "oarepo_landing",
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    blueprint.add_url_rule(routes["index"], view_func=index)
    return blueprint


#
# Views
#
def index():
    """Frontpage."""
    return render_template(
        current_app.config["THEME_FRONTPAGE_TEMPLATE"],
    )
