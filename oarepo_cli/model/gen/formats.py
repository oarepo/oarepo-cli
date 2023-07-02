import typing
from configparser import ConfigParser
from io import StringIO

from ruamel.yaml import YAML, CommentedMap

from oarepo_cli.model.gen.base import FileFormat


class TextFormat(FileFormat[str]):
    def load(self, text: str) -> str:
        return text or ""

    def dump(self, data: str) -> str:
        return data


class YAMLFormat(FileFormat[typing.Any]):
    def __init__(self):
        self._yaml = YAML(typ="rt")

    def load(self, text: str) -> typing.Any:
        return self._yaml.load(StringIO(text)) or CommentedMap()

    def dump(self, data: typing.Any) -> str:
        io = StringIO()
        self._yaml.dump(data, io)
        return io.getvalue()


class PermissiveConfigParser(ConfigParser):
    def get_section(self, section_name):
        if not self.has_section(section_name):
            self.add_section(section_name)
        return self[section_name]


class CFGFormat(FileFormat[ConfigParser]):
    def load(self, text: str) -> ConfigParser:
        parser = ConfigParser()
        parser.read_string(text)
        return parser

    def dump(self, data: ConfigParser) -> str:
        io = StringIO()
        data.write(io)
        return io.getvalue()
