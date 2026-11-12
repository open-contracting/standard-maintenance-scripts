import pytest

from tests.test_requirements import check_requirements


def write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def project(tmp_path):
    write(tmp_path / "requirements.in", "requests\n")
    write(tmp_path / "main.py", "import requests\n")
    return tmp_path


def test_nested_project(project):
    write(project / "sub-project" / "requirements.in", "django\n")
    write(project / "sub-project" / "core" / "__init__.py")
    write(project / "sub-project" / "manage.py", "import core\nimport django\n")

    check_requirements(str(project))


def test_subdirectory(project):
    write(project / "scripts" / "run.py", "import yaml\n")

    with pytest.raises(AssertionError, match=r"Missing requirements for modules: yaml\n"):
        check_requirements(str(project))
