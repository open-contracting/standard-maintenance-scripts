import ast
import csv
import os
from collections import defaultdict
from io import StringIO
from pathlib import Path
from urllib.parse import urlsplit

import pkg_resources
import pytest
from setuptools import find_packages

path = os.getcwd()

# https://github.com/PyCQA/isort/blob/develop/isort/stdlibs/py36.py
stdlib = {
    "_dummy_thread", "_thread", "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore", "atexit",
    "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins", "bz2", "cProfile", "calendar", "cgi",
    "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "copy", "copyreg", "crypt", "csv", "ctypes", "curses", "datetime",
    "dbm", "decimal", "difflib", "dis", "distutils", "doctest", "dummy_threading", "email", "encodings", "ensurepip",
    "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "formatter", "fpectl", "fractions",
    "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", "grp", "gzip", "hashlib", "heapq", "hmac",
    "html", "http", "imaplib", "imghdr", "imp", "importlib", "inspect", "io", "ipaddress", "itertools", "json",
    "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "macpath", "mailbox", "mailcap", "marshal", "math",
    "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing", "netrc", "nis", "nntplib", "ntpath",
    "numbers", "operator", "optparse", "os", "ossaudiodev", "parser", "pathlib", "pdb", "pickle", "pickletools",
    "pipes", "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile", "pstats", "pty",
    "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib", "resource",
    "rlcompleter", "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil", "signal", "site",
    "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "sre", "sre_compile", "sre_constants",
    "sre_parse", "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess", "sunau", "symbol",
    "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios", "test",
    "textwrap", "threading", "time", "timeit", "tkinter", "token", "tokenize", "trace", "traceback", "tracemalloc",
    "tty", "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid", "venv",
    "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc", "zipapp",
    "zipfile", "zipimport", "zlib"
}

IGNORE = [
    # https://docs.python.org/3/library/__future__.html
    '__future__',
    # Web server dependencies.
    'gunicorn',
]


def val(node):
    # ast.Num, ast.Str, ast.Bytes, ast.NameConstant and ast.Ellipsis are deprecated in favor of ast.Constant in 3.8.
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Str):
        return node.s
    raise NotImplementedError


# https://setuptools.readthedocs.io/en/latest/pkg_resources.html#requirements-parsing
# https://setuptools.readthedocs.io/en/latest/deprecated/python_eggs.html#top-level-txt-conflict-management-metadata
# https://packaging.python.org/specifications/recording-installed-packages/#the-record-file
def projects_and_modules(requirements):
    """
    :param str requirements: one or more requirements
    :returns: a dict in which the key is a project and the value is a list of the project's top-level modules
    :rtype: dict
    """
    mapping = defaultdict(set)
    requirements = [line for line in requirements.splitlines() if not line.startswith('-')]
    for requirement in pkg_resources.parse_requirements(requirements):
        project_name = requirement.project_name
        if requirement.marker and not requirement.marker.evaluate():
            continue
        project = pkg_resources.get_distribution(project_name)
        try:
            for module in project.get_metadata('top_level.txt').splitlines():
                mapping[project_name].add(module)
        except FileNotFoundError:
            reader = csv.reader(StringIO(project.get_metadata('RECORD')))
            for row in reader:
                if row[0].endswith('.py'):
                    mapping[project_name].add(row[0].split(os.sep, 1)[0])
                elif row[0].endswith('.so'):
                    mapping[project_name].add(row[0].split('.', 1)[0])
    return mapping


class SetupVisitor(ast.NodeVisitor):
    """
    Reads a setup.py file and collects the modules that can be imported from each requirement.
    """

    def __init__(self, extras=()):
        self.mapping = {}
        self.extras = extras

    def visit_keyword(self, node):
        if node.arg == 'install_requires':
            for elt in node.value.elts:
                self.mapping.update(projects_and_modules(val(elt)))
        elif node.arg == 'extras_require' and self.extras:
            for key, value in zip(node.value.keys, node.value.values):
                if val(key) in self.extras:
                    for elt in value.elts:
                        self.mapping.update(projects_and_modules(val(elt)))


class CodeVisitor(ast.NodeVisitor):
    """
    Reads a Python file and collects the modules that are imported.
    """

    def __init__(self, filename, packages):
        """
        :param str filename: The name of the file being read
        :param list packages: A list of first-party packages to ignore
        """
        self.imports = set()
        self.path = Path(filename)
        self.excluded = stdlib
        self.excluded.update(packages)
        if self.path.name == 'setup.py':
            self.excluded.add('setuptools')

    def visit_Try(self, node):
        if not any(h.type.id == 'ImportError' for h in node.handlers if isinstance(h.type, ast.Name)):
            self.generic_visit(node)

    def visit_Import(self, node):
        for alias in node.names:
            self.add(alias.name)

    def visit_ImportFrom(self, node):
        if node.module and not node.level:
            self.add(node.module)

    def visit_Assign(self, node):
        # Handle Django settings.py file.
        if self.path.name == 'settings.py' or self.path.parent.name == 'settings':
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                # A requirement might be declared as an installed app or middleware.
                if target.id in ('INSTALLED_APPS', 'MIDDLEWARE'):
                    for elt in node.value.elts:
                        self.add(val(elt))
                # A requirement might be required by a backend.
                elif target.id == 'CACHES':
                    for value in node.value.values:
                        for k, v in zip(value.keys, value.values):
                            if val(k) == 'BACKEND':
                                if val(v) == 'django.core.cache.backends.memcached.MemcachedCache':
                                    self.add('memcache')
                                elif val(v) == 'django.core.cache.backends.memcached.PyMemcacheCache':
                                    self.add('pymemcache')
                elif target.id == 'DATABASES':
                    for value in node.value.values:
                        if isinstance(value, ast.Call):
                            # value.func <ast.Attribute>
                            #   .value <ast.Name>
                            #     .id == "dj_database_url"
                            #   .attr == "config"
                            # value.keywords[0] <ast.keyword>
                            #   .arg == "default"
                            #   .value <ast.Constant>
                            #     .value == "postgresql://"
                            default = next((keyword for keyword in value.keywords if keyword.arg == "default"), None)
                            if default and urlsplit(val(default.value)).scheme == 'postgresql':
                                self.add('psycopg2')
                        elif isinstance(value, ast.Dict):
                            for k, v in zip(value.keys, value.values):
                                if val(k) == 'ENGINE' and val(v) in (
                                    'django.db.backends.postgresql',
                                    'django.db.backends.postgresql_psycopg2',
                                ):
                                    self.add('psycopg2')

    def add(self, name):
        if 'django.contrib.postgres' in name:
            self.add('psycopg2')

        name = name.split('.', 1)[0]
        if name not in self.excluded:
            self.imports.add(name)


def check_requirements(path, *requirements_files, dev=False, ignore=()):
    setup_py = os.path.join(path, 'setup.py')
    requirements_in = os.path.join(path, 'requirements.in')
    if not any(os.path.exists(filename) for filename in (setup_py, requirements_in)):
        pytest.skip(f"No setup.py or requirements.in file found")

    excluded = ['.git', 'docs', 'node_modules']
    find_packages_kwargs = {}
    if not dev:
        find_packages_kwargs['exclude'] = ['tests', 'tests.*']
        excluded.append('tests')

    packages = find_packages(where=path, **find_packages_kwargs)
    if os.path.exists(os.path.join(path, 'manage.py')):
        packages.append('manage')

    ignore = list(ignore) + os.getenv('STANDARD_MAINTENANCE_SCRIPTS_IGNORE', '').split(',')
    extras = os.getenv('STANDARD_MAINTENANCE_SCRIPTS_EXTRAS', '').split(',')

    # Collect the modules that are imported.
    imports = defaultdict(set)
    for root, dirs, files in os.walk(path):
        for directory in excluded:
            if directory in dirs:
                dirs.remove(directory)
        for file in files:
            if file.endswith('.py') and (dev or not file.startswith('test') and file != 'conftest.py'):
                filename = os.path.join(root, file)
                with open(filename) as f:
                    code = ast.parse(f.read())
                code_visitor = CodeVisitor(os.path.relpath(filename, path), packages)
                code_visitor.visit(code)
                for module in code_visitor.imports:
                    imports[module].add(file)

    # Collect the requirements and the modules that can be imported.
    if os.path.exists(setup_py):
        with open(setup_py) as f:
            root = ast.parse(f.read())
        setup_visitor = SetupVisitor(extras=extras)
        setup_visitor.visit(root)
        mapping = setup_visitor.mapping

    if os.path.exists(requirements_in):
        mapping = {}
        for requirements_file in ('requirements.in', *requirements_files):
            with open(os.path.join(path, requirements_file)) as f:
                mapping.update(projects_and_modules(f.read()))

    if 'psycopg2-binary' in mapping and 'psycopg2' in mapping:
        del mapping['psycopg2-binary']

    # Some modules affect the behavior of `jsonschema` without being imported.
    if 'jsonschema' in mapping:
        for project in ('rfc3339-validator', 'rfc3987', 'strict-rfc3339'):
            if project in mapping and not any(module for module in mapping[project] if module in imports):
                del mapping[project]

    inverse_mapping = {module: project for project, modules in mapping.items() for module in modules}
    for module in imports:
        project = inverse_mapping.get(module)
        if project:
            del mapping[project]

    difference = {k: v for k, v in mapping.items() if k not in ignore}
    assert not difference, f"Unused requirements: {', '.join(sorted(difference))}"

    difference = {k: v for k, v in imports.items() if k not in inverse_mapping and k not in ignore}
    assert not difference, f"Missing requirements for modules: {', '.join(sorted(difference))}"


def test_requirements():
    check_requirements(path, ignore=IGNORE)


@pytest.mark.skipif(not os.path.exists(os.path.join(path, 'requirements_dev.in')),
                    reason='No requirements_dev.in file found')
def test_dev_requirements():
    # Ignore development dependencies that are not typically imported.
    ignore = [
        # Dependency management.
        'pip-tools',
        # Interactive shells.
        'ipython',
        # Code linters.
        'autopep8',
        'black',
        'flake8',
        'isort',
        'pre-commit',
        'pylint',
        # Debuggers.
        'ipdb',
        # Test runners.
        'pytest',
        # Pytest plugins, which provide fixtures, for example.
        'pytest-cov',
        'pytest-django',
        'pytest-flask',
        'pytest-localserver',
        'pytest-order',
        'pytest-subtests',
        # Code coverage.
        'coverage',
        'coveralls',
        # Documentation dependencies.
        'sphinx',
        'sphinx-rtd-theme',
        # Build utilities.
        'libsass',
        'transifex-client',
    ]

    check_requirements(path, 'requirements_dev.in', dev=True, ignore=IGNORE + ignore)
