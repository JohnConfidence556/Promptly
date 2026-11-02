
import json

import pytest

from app.agents.architect import ArchitectError, parse_architecture
from tests.test_architecture import valid_architecture


def test_parse_broken_json():
    with pytest.raises(ArchitectError, match="invalid JSON"):
        parse_architecture("{broken json")


def test_parse_json_array_instead_of_object():
    with pytest.raises(ArchitectError, match="top-level value was not an object"):
        parse_architecture("[]")


def test_parse_valid_json_with_wrong_shape():
    raw = json.dumps({"unexpected": "shape"})

    with pytest.raises(ArchitectError, match="does not match the schema"):
        parse_architecture(raw)


def test_parse_valid_architecture():
    raw = json.dumps(valid_architecture())

    result = parse_architecture(raw)

    assert result.file_tasks[0].filename == "index.html"
