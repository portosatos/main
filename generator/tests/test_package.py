"""The package is installed with the htgen entry point and names the format it writes."""

from importlib.metadata import entry_points

import htgen


def test_meta_constants_match_data_format() -> None:
    assert htgen.GENERATOR == "htgen 0.1"
    assert htgen.SCHEMA == "ht.v1"


def test_htgen_console_script_points_to_cli_main() -> None:
    (ep,) = [ep for ep in entry_points(group="console_scripts") if ep.name == "htgen"]
    assert ep.value == "htgen.cli:main"
