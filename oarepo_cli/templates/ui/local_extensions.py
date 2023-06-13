from cookiecutter.utils import simple_filter


@simple_filter
def snail_to_title(v):
    return "".join(ele.title() for ele in v.split("_"))
