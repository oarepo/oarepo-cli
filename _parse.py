from pathlib import Path
from pkg_resources import parse_requirements


def load_reqs(fn):
    ret = {}
    txt = Path(fn).read_text()
    for l in txt.splitlines():
        l = l.strip()
        if l[0] == "-" or l[0] == "#":
            continue
        try:
            for resource in parse_requirements(l):
                pn = resource.project_name.replace("_", "-").lower()
                version = None
                for spec in resource.specs:
                    if spec[0] == "==":
                        version = spec[1]
                ret[pn] = version
        except Exception as e:
            print(f"Error parsing {l}: {e}")
    return ret

def check_reqs(expected, actual)
    reqs = load_reqs(".reqs")
    reqs1 = load_reqs(".reqs1")

    IGNORED_PACKAGES = {"setuptools", "pip", "wheel"}

    for key, version in reqs.items():
        if key not in reqs1:
            if key in IGNORED_PACKAGES:
                continue
            print(f"{key} not found")
            continue
        if version != reqs1[key]:
            print(f"Version mismatch in {key}. Expected {version}, is {reqs1[key]}")

