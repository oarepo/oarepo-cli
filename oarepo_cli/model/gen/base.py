import functools
from pathlib import Path
from typing import Generic, TypeVar

import importlib_metadata

T = TypeVar("T")


class FileFormat(Generic[T]):
    def load(self, text: str) -> T:
        raise NotImplementedError("Implement this method")

    def dump(self, data: T) -> str:
        raise NotImplementedError("Implement this method")


class GeneratedFile:
    def __init__(self, files, fname: Path):
        self._files = files
        self._fname = fname
        if self._fname.exists():
            self._content = self._fname.read_text()
        else:
            self._content = ""
        self._active_format = "text"
        self._formats = {}

    def __getattr__(self, format_name):
        self._content = self._convert_to(format_name)
        self._active_format = format_name
        return self._content

    def _convert_to(self, format_name):
        if self._active_format == format_name:
            return self._content
        current_format = self._files.get_format(self._active_format)
        new_format = self._files.get_format(format_name)
        data = current_format.dump(self._content)
        return new_format.load(data)

    def save(self):
        self._fname.parent.mkdir(parents=True, exist_ok=True)
        self._fname.write_text(self._convert_to("text"))


class GeneratedFiles:
    def __init__(self, base_path: Path):
        self._base_path = base_path
        self._files = {}

    @functools.lru_cache
    def get_format(self, format_name) -> FileFormat:
        return list(
            importlib_metadata.entry_points().select(
                group="nrp_cli.file_formats", name=format_name
            )
        )[0].load()()

    def get(self, fname):
        if fname not in self._files:
            self._files[fname] = GeneratedFile(self, self._base_path / fname)
        return self._files[fname]
