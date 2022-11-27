from __future__ import annotations


def required(prop_name, prop_label=None):
    def _val(data):
        v = data.get(prop_name)
        if v is None or v == "":
            return f"Value required"

    return _val
