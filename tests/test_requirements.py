import ast
import csv
import os
import pkg_resources
from collections import defaultdict
from io import StringIO
from setuptools import find_packages

import pytest

path = os.getcwd()
repo_name = os.path.basename(os.getenv('GITHUB_REPOSITORY', path))

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
        project = pkg_resources.get_distribution(project_name)
        try:
            for module in project.get_metadata('top_level.txt').splitlines():
                mapping[project_name].add(module)
        except FileNotFoundError:
            reader = csv.reader(StringIO(project.get_metadata('RECORD')))
            for row in reader:
                if row[0].endswith('.py'):
                    mapping[project_name].add(row[0].split(os.sep, 1)[0])
    return mapping


class SetupVisitor(ast.NodeVisitor):
    """
    Reads a setup.py file and collects the modules that can be imported from each requirement.
    """

    def __init__(self):
        self.mapping = {}

    def visit_keyword(self, node):
        if node.arg == 'install_requires':
            for elt in node.value.elts:
                self.mapping.update(projects_and_modules(elt.s))


class CodeVisitor(ast.NodeVisitor):
    """
    Reads a Python file and collects the modules that are imported.
    """

    def __init__(self, filename, packages):
        """
        :param str filename: The name of the file being read
        :param list packages: A list of first-party packages to ignore
        """
        self.filename = filename
        self.excluded = stdlib | set(packages)
        self.imports = set()

    def visit_Import(self, node):
        for alias in node.names:
            self.add(alias.name)

    def visit_ImportFrom(self, node):
        if node.module and not node.level:
            self.add(node.module)

    def visit_Assign(self, node):
        # Handle Django settings.py file.
        if self.filename == 'settings.py':
            for target in node.targets:
                if not isinstance(target, ast.Name):
                    continue
                # A requirement might be declared as an installed app or middleware.
                if target.id in ('INSTALLED_APPS', 'MIDDLEWARE'):
                    for elt in node.value.elts:
                        self.add(elt.s)
                # A requirement might be required by a backend.
                elif target.id == 'CACHES':
                    for value in node.value.values:
                        for k, v in zip(value.keys, value.values):
                            if k.s == 'BACKEND' and v.s == 'django.core.cache.backends.memcached.MemcachedCache':
                                self.add('memcache')

    # def __getattr__(self, name):
    #     def x(node):
    #         if self.filename == 'settings.py':
    #             print(repr([node, getattr(node, 'lineno', 0)]))
    #         self.generic_visit(node)

    #     return x

    def add(self, name):
        name = name.split('.', 1)[0]
        if name not in self.excluded:
            self.imports.add(name)


def check_requirements(path, *requirements_files, dev=False, ignore=()):
    filenames = ('setup.py', *requirements_files)
    setup_py = os.path.join(path, 'setup.py')
    if not any(os.path.exists(os.path.join(path, filename)) for filename in filenames):
        pytest.skip(f"No {'or'.join(filenames)} file found")

    excluded = ['.git', 'docs']
    if not dev:
        excluded.append('tests')

    # Collect the modules that are imported.
    imports = defaultdict(set)
    packages = find_packages(where=path, exclude=['tests', 'tests.*'])
    for root, dirs, files in os.walk(path):
        for directory in excluded:
            if directory in dirs:
                dirs.remove(directory)
        for file in files:
            if file.endswith('.py') and (dev or not file.startswith('test')):
                with open(os.path.join(root, file)) as f:
                    code = ast.parse(f.read())
                code_visitor = CodeVisitor(file, packages)
                code_visitor.visit(code)
                for module in code_visitor.imports:
                    imports[module].add(file)

    # Collect the requirements and the modules that can be imported.
    if os.path.exists(setup_py):
        with open(setup_py) as f:
            root = ast.parse(f.read())
        setup_visitor = SetupVisitor()
        setup_visitor.visit(root)
        mapping = setup_visitor.mapping
    else:
        mapping = {}
        for requirements_file in requirements_files:
            with open(os.path.join(path, requirements_file)) as f:
                mapping.update(projects_and_modules(f.read()))

    # Some modules affect the behavior of `jsonschema` without being imported.
    if 'jsonschema' in mapping:
        for project in ('rfc3987', 'strict-rfc3339'):
            mapping.discard(project)

    inverse_mapping = {module: project for project, modules in mapping.items() for module in modules}
    for module in imports:
        project = inverse_mapping.get(module)
        if project:
            del mapping[project]

    difference = {k: v for k, v in mapping.items() if k not in ignore}
    assert not difference, f"Unused requirements: {', '.join(sorted(difference))}"

    difference = {k: v for k, v in imports.items() if k not in inverse_mapping}
    assert not difference, f"Missing requirements for modules: {', '.join(sorted(difference))}"


def test_requirements():
    dev = repo_name == 'deploy'
    if dev:
        ignore = ('ocdsindex', 'pip-tools')
    else:
        ignore = ()
    check_requirements(path, 'requirements.in', dev=dev, ignore=ignore)


@pytest.mark.skipif(not os.path.exists(os.path.join(path, 'requirements_dev.in')),
                    reason='No requirements_dev.in file found')
def test_dev_requirements():
    check_requirements(path, 'requirements.in', 'requirements_dev.in', dev=True, ignore=(
        # Dependency management.
        'pip-tools',
        # Code linters.
        'flake8',
        'isort',
        # Pytest plugins.
        'pytest-cov',
        'pytest-django',
        'pytest-localserver',
        # Code coverage.
        'coverage',
        'coveralls',
        # Documentation dependencies.
        'sphinx',
        'sphinx-rtd-theme',
        # Build utilities.
        'libsass',
        'transifex-client',
    ))