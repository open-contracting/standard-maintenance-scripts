import ast
import glob
import os
from collections import defaultdict
from importlib.metadata import distribution
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from packaging.requirements import Requirement
from setuptools import find_packages

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # Python 3.10 or less

path = os.getcwd()

# https://github.com/PyCQA/isort/blob/develop/isort/stdlibs/py38.py
stdlib = {
    "_ast", "_dummy_thread", "_thread", "abc", "aifc", "argparse", "array", "ast", "asynchat", "asyncio", "asyncore",
    "atexit", "audioop", "base64", "bdb", "binascii", "binhex", "bisect", "builtins", "bz2", "cProfile", "calendar",
    "cgi", "cgitb", "chunk", "cmath", "cmd", "code", "codecs", "codeop", "collections", "colorsys", "compileall",
    "concurrent", "configparser", "contextlib", "contextvars", "copy", "copyreg", "crypt", "csv", "ctypes", "curses",
    "dataclasses", "datetime", "dbm", "decimal", "difflib", "dis", "distutils", "doctest", "dummy_threading", "email",
    "encodings", "ensurepip", "enum", "errno", "faulthandler", "fcntl", "filecmp", "fileinput", "fnmatch", "formatter",
    "fractions", "ftplib", "functools", "gc", "getopt", "getpass", "gettext", "glob", "grp", "gzip", "hashlib",
    "heapq", "hmac", "html", "http", "imaplib", "imghdr", "imp", "importlib", "inspect", "io", "ipaddress",
    "itertools", "json", "keyword", "lib2to3", "linecache", "locale", "logging", "lzma", "mailbox", "mailcap",
    "marshal", "math", "mimetypes", "mmap", "modulefinder", "msilib", "msvcrt", "multiprocessing", "netrc", "nis",
    "nntplib", "ntpath", "numbers", "operator", "optparse", "os", "ossaudiodev", "parser", "pathlib", "pdb", "pickle",
    "pickletools", "pipes", "pkgutil", "platform", "plistlib", "poplib", "posix", "posixpath", "pprint", "profile",
    "pstats", "pty", "pwd", "py_compile", "pyclbr", "pydoc", "queue", "quopri", "random", "re", "readline", "reprlib",
    "resource", "rlcompleter", "runpy", "sched", "secrets", "select", "selectors", "shelve", "shlex", "shutil",
    "signal", "site", "smtpd", "smtplib", "sndhdr", "socket", "socketserver", "spwd", "sqlite3", "sre", "sre_compile",
    "sre_constants", "sre_parse", "ssl", "stat", "statistics", "string", "stringprep", "struct", "subprocess", "sunau",
    "symbol", "symtable", "sys", "sysconfig", "syslog", "tabnanny", "tarfile", "telnetlib", "tempfile", "termios",
    "test", "textwrap", "threading", "time", "timeit", "tkinter", "token", "tokenize", "trace", "traceback",
    "tracemalloc", "tty", "turtle", "turtledemo", "types", "typing", "unicodedata", "unittest", "urllib", "uu", "uuid",
    "venv", "warnings", "wave", "weakref", "webbrowser", "winreg", "winsound", "wsgiref", "xdrlib", "xml", "xmlrpc",
    "zipapp", "zipfile", "zipimport", "zlib",
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
    # django-environ sets the default value when creating the Env object, not when setting the engine key.
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "env" and not node.keywords:
        return None
    raise NotImplementedError(ast.dump(node))


def projects_and_modules(requirements):
    """
    :param list requirements: one or more requirements
    :returns: a dict in which the key is a project and the value is a list of the project's top-level modules
    :rtype: dict
    """
    mapping = defaultdict(set)
    if isinstance(requirements, str):
        requirements = requirements.splitlines()
    for line in requirements:
        if not line or line.startswith(('-', '#', 'git+')):
            continue
        requirement = Requirement(line)
        if requirement.marker and not requirement.marker.evaluate():
            continue
        for file in distribution(requirement.name).files:
            path = str(file)
            if path.startswith(f'src{os.sep}'):
                path = path[4:]
            if path.endswith('.py') and os.sep in path:
                mapping[requirement.name].add(path.split(os.sep, 1)[0])
            elif path.endswith(('.py', '.so')):
                mapping[requirement.name].add(path.split('.', 1)[0])
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
            for key, value in zip(node.value.keys, node.value.values, strict=True):
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
        # Don't collect imports in `try: ... except ImportError: ...` blocks.
        if not any(h.type.id == 'ImportError' for h in node.handlers if isinstance(h.type, ast.Name)):
            self.generic_visit(node)

    def visit_If(self, node):
        # Don't collect imports in `if sys.version_info >= (3, 8): ... else: ...` blocks.
        if (
            not isinstance(node.test, ast.Compare)
            or any(isinstance(op, ast.In | ast.NotIn | ast.Is | ast.IsNot) for op in node.test.ops)
            or isinstance(node.test.left, ast.Tuple)
            or not any(
                isinstance(val(e), int) for c in node.test.comparators if isinstance(c, ast.Tuple) for e in c.elts
            )
        ):
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
                elif target.id == 'CELERY_BROKER_URL':
                    if isinstance(node.value, ast.Call):
                        default = node.value.args[1] if len(node.value.args) == 2 else None
                        if default and urlsplit(val(default)).scheme == 'redis':
                            self.add('redis')
                # A requirement might be required by a backend.
                elif target.id == 'CACHES':
                    for value in node.value.values:  # noqa: PD011 # false positive
                        for k, v in zip(value.keys, value.values, strict=True):
                            if val(k) == 'BACKEND':
                                if val(v) == 'django.core.cache.backends.memcached.MemcachedCache':
                                    self.add('memcache')
                                elif val(v) == 'django.core.cache.backends.memcached.PyMemcacheCache':
                                    self.add('pymemcache')
                elif target.id == 'CHANNEL_LAYERS':
                    for value in node.value.values:  # noqa: PD011 # false positive
                        for k, v in zip(value.keys, value.values, strict=True):
                            if val(k) in 'BACKEND' and val(v) == 'channels_redis.core.RedisChannelLayer':
                                self.add('channels_redis')
                elif target.id == 'DATABASES':
                    for value in node.value.values:  # noqa: PD011 # false positive
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
                            for k, v in zip(value.keys, value.values, strict=True):
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
    pyproject_toml = os.path.join(path, 'pyproject.toml')
    setup_py = os.path.join(path, 'setup.py')
    requirements_in = os.path.join(path, 'requirements.in')

    ignore = list(ignore) + os.getenv('STANDARD_MAINTENANCE_SCRIPTS_IGNORE', '').split(',')
    extras = os.getenv('STANDARD_MAINTENANCE_SCRIPTS_EXTRAS', '').split(',')
    files = os.getenv('STANDARD_MAINTENANCE_SCRIPTS_FILES', '').split(',')
    if any(files):
        requirements_files += tuple(files)
    if os.path.exists(requirements_in):
        requirements_files += (requirements_in,)

    files = (pyproject_toml, setup_py, *requirements_files)
    if not any(os.path.exists(filename) for filename in files):
        pytest.skip(f"No {', '.join(files)} file found")

    excluded = ['.git', '.venv', 'docs', 'node_modules', 'vendor']
    find_packages_kwargs = {}
    if not dev:
        find_packages_kwargs['exclude'] = ['tests', 'tests.*']
        excluded.append('tests')

    packages = find_packages(where=path, **find_packages_kwargs)
    for filename in glob.glob(os.path.join(path, '*.py')):
        packages.append(os.path.splitext(os.path.basename(filename))[0])

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
    if os.path.exists(pyproject_toml):
        with open(pyproject_toml, 'rb') as f:
            config = tomllib.load(f)
        mapping = projects_and_modules(config['project'].get('dependencies', []))
        for extra in extras:
            mapping.update(projects_and_modules(config['project'].get('optional-dependencies', {}).get(extra, [])))

    if os.path.exists(setup_py):
        with open(setup_py) as f:
            root = ast.parse(f.read())
        setup_visitor = SetupVisitor(extras=extras)
        setup_visitor.visit(root)
        mapping = setup_visitor.mapping

    if any(os.path.exists(filename) for filename in requirements_files):
        mapping = {}
        for requirements_file in requirements_files:
            with open(os.path.join(path, requirements_file)) as f:
                mapping.update(projects_and_modules(f.read().splitlines()))

    if 'psycopg2-binary' in mapping and 'psycopg2' in mapping:
        del mapping['psycopg2-binary']

    # Some modules affect the behavior of `jsonschema` without being imported.
    if 'jsonschema' in mapping:
        for project in ('rfc3339-validator', 'rfc3986-validator', 'rfc3987'):
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
        # Code linters.
        'mypy',
        'nbqa',
        'pre-commit',
        'pylint',
        # Test runners.
        'pytest',
        # Pytest plugins, which provide fixtures, for example.
        'pytest-asyncio',
        'pytest-django',
        'pytest-env',
        'pytest-flask',
        'pytest-localserver',
        'pytest-mock',
        'pytest-order',
        'pytest-random-order',
        'pytest-subtests',
        # Code coverage.
        'coverage',
        # Documentation dependencies.
        'furo',
        'sphinx',
        'sphinx-design',
        'sphinx-intl',
        # Build utilities.
        'libsass',
    ]

    check_requirements(path, 'requirements_dev.in', dev=True, ignore=IGNORE + ignore)
