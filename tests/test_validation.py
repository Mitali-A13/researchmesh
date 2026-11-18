import os

import pytest
from pydantic import ValidationError

os.environ.setdefault("SECRET_KEY", "test-secret-key-for-pytest-1234")

from backend.auth import validate_secret_key
from backend.schemas.research import ResearchRequest


def test_whitespace_only_topic_is_rejected():
    for bad in ["   ", "\t\t\t", "a  ", " ab "]:
        with pytest.raises(ValidationError):
            ResearchRequest(topic=bad)


def test_topic_is_cleaned():
    assert (
        ResearchRequest(topic="  solid   state\nbatteries ").topic
        == "solid state batteries"
    )


def test_topic_length_limits_still_apply():
    with pytest.raises(ValidationError):
        ResearchRequest(topic="x" * 301)


def test_secret_key_must_be_present_and_long_enough():
    for bad in [None, "", "short"]:
        with pytest.raises(RuntimeError):
            validate_secret_key(bad)
    assert validate_secret_key("a-long-enough-secret-key") == "a-long-enough-secret-key"
