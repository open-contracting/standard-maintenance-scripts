import pytest

from tests.test_requirements import CodeVisitor, check_requirements, stdlib


def write(path, content=""):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content)


@pytest.fixture
def project(tmp_path):
    write(tmp_path / "requirements.in", "requests\n")
    write(tmp_path / "main.py", "import requests\n")
    return tmp_path


def test_check_subdirectory_if_not_subproject(project):
    write(project / "scripts" / "run.py", "import yaml\n")

    with pytest.raises(AssertionError, match=r"Missing requirements for modules: yaml\n"):
        check_requirements(str(project))


@pytest.mark.parametrize("filename", ["requirements.in", "MANIFEST.in"])
def test_skip_subdirectory_if_subproject(project, filename):
    write(project / "sub-project" / filename)
    write(project / "sub-project" / "main.py", "import django\n")

    check_requirements(str(project))


def test_import_package_if_module(project):
    write(project / "core" / "__init__.py")
    write(project / "core" / "celery.py")
    write(project / "core" / "tasks.py", "from celery import shared_task\n")

    with pytest.raises(AssertionError, match=r"Missing requirements for modules: celery\n"):
        check_requirements(str(project))


def test_import_sibling_file_if_not_module(project):
    write(project / "scripts" / "helper.py")
    write(project / "scripts" / "run.py", "from helper import x\n")

    check_requirements(str(project))


def test_import_sibling_package_if_not_module(project):
    write(project / "scripts" / "utils" / "__init__.py")
    write(project / "scripts" / "run.py", "import utils\n")

    check_requirements(str(project))


def test_code_visitor_leaves_stdlib_unchanged():
    CodeVisitor("a.py", ["celery"])

    assert "celery" not in stdlib


def test_fail_unused_sibling_project(tmp_path):
    write(tmp_path / "library" / "mylib" / "__init__.py")
    write(tmp_path / "app" / "requirements.in", "-e ../library\n")
    write(tmp_path / "app" / "main.py")

    with pytest.raises(AssertionError, match=r"Unused requirements: \.\./library\n"):
        check_requirements(str(tmp_path / "app"))


@pytest.mark.parametrize("requirement", ["-e ../library", "../library"])
def test_pass_used_sibling_project(tmp_path, requirement):
    write(tmp_path / "library" / "mylib" / "__init__.py")
    write(tmp_path / "library" / "mylib" / "sub" / "__init__.py")
    write(tmp_path / "app" / "requirements.in", f"{requirement}\nrequests\n")
    write(tmp_path / "app" / "main.py", "import mylib.sub\nimport requests\n")

    check_requirements(str(tmp_path / "app"))
