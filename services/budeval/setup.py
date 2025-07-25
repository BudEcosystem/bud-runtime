"""setup.py: setuptools control."""

import codecs
import os.path
import sys
from typing import List

from setuptools import find_packages, setup


ROOT_DIR = os.path.abspath(os.path.dirname(__file__))


def read_file(rel_path: str) -> str:
    """Read a file and return the contents."""
    _path = os.path.join(ROOT_DIR, rel_path)
    if os.path.isfile(_path):
        with codecs.open(_path, "r") as fp:
            return fp.read()
    else:
        return ""


def get_project_name_and_version(rel_path: str) -> List[str]:
    """Get the project name and version from a file specified by __version__ = name@version."""
    for line in read_file(rel_path).splitlines():
        if line.startswith("__version__"):
            delim = '"' if '"' in line else "'"
            return line.split(delim)[1].split("@")
    else:
        raise RuntimeError("Unable to find version string.")


def get_requirements() -> List[str]:
    """Get Python package dependencies from requirements.txt."""

    def _read_requirements(filename: str) -> List[str]:
        requirements = read_file(filename).strip().split("\n")
        resolved_requirements = []
        for line in requirements:
            if line.startswith("-r "):
                resolved_requirements += _read_requirements(line.split()[1])
            else:
                resolved_requirements.append(line)
        return resolved_requirements

    return _read_requirements("requirements.txt")


name, version = get_project_name_and_version("pyguard/__about__.py")
version_range_max = max(sys.version_info[1], 10) + 1

setup(
    name=name,
    version=version,
    description=(
        "PyGuard is a comprehensive guide and toolkit for Python projects within the bud-microframe ecosystem."
        "It provides essential tools such as hooks, testing frameworks, documentation guidelines, and profiling utilities"
        "to ensure code quality, consistency, and performance. Additionally, PyGuard offers scripts, configurations, "
        "and folder structures specifically designed for creating and deploying Python microservices. "
        "Streamline your development and deployment processes with PyGuard, the cornerstone of your Python microservice architecture in org-microframe."
    ),
    long_description=read_file("README.md"),
    long_description_content_type="text/markdown",
    url="https://github.com/BudEcosystem/pyguard",
    project_urls={
        "Homepage": "https://github.com/BudEcosystem/bud-microframe-pyguard",
        "Documentation": "https://github.com/BudEcosystem/bud-microframe-pyguard/blob/main/README.md",
        "Issues": "https://github.com/BudEcosystem/bud-microframe-pyguard/issues",
        "Changelog": "https://github.com/BudEcosystem/bud-microframe-pyguard/blob/main/CHANGELOG.md",
    },
    keywords="pre-commit hooks testing documentation profiling code quality project maintenance"
    "best practices continuous integration code standards",
    license="Apache 2.0 License",
    author="Bud Ecosystem Inc.",
    package_dir={"": "./"},
    packages=find_packages(
        "pyguard",
        exclude=(
            "docs",
            "examples",
            "tests",
            "docker",
            "assets*",
            "dist*",
            "scripts*",
            "README.md",
            ".gitignore",
            "requirements*.txt",
        ),
    ),
    package_data={"pyguard": ["py.typed"]},
    include_package_data=True,
    python_requires=">=3.8.0",
    install_requires=get_requirements(),
    extras_require={},
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "Intended Audience :: Developers",
        "Topic :: Software Development :: Quality Assurance",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Documentation",
        "License :: OSI Approved :: Apache Software License",
        "Operating System :: OS Independent",
        "Environment :: Console",
        "Framework :: Pytest" "Programming Language :: Python :: 3",
    ]
    + [f"Programming Language :: Python :: 3.{i}" for i in range(8, version_range_max)],
)
