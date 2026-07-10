"""Load and save case files as YAML."""

from pathlib import Path

import yaml

from planner_lab.schemas.case_file import CaseFile


def load_case(path: Path | str) -> CaseFile:
    with open(path) as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError(f"{path} does not contain a YAML mapping")
    return CaseFile.model_validate(data)


def save_case(case: CaseFile, path: Path | str) -> None:
    data = case.model_dump(mode="json")
    with open(path, "w") as f:
        yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
