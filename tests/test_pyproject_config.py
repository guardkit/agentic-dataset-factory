"""Validate pyproject.toml configuration for agent factory packages.

Ensures that:
- deepagents>=0.5.3,<0.6 is in project dependencies (per ADR-ARCH-011)
- agents*, prompts*, config* are in setuptools package includes
- Test paths include new test locations (config/tests, agents/tests, prompts/tests)
- pyproject.toml is valid TOML

References TASK-AF-011 acceptance criteria AC-001 through AC-004.
Pin updated under TASK-AD14-A / ADR-ARCH-011 (LangChain 1.x portfolio alignment).
"""

from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

# Resolve project root relative to this test file
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


@pytest.fixture(scope="module")
def pyproject() -> dict:
    """Parse pyproject.toml and return as dict."""
    with open(PYPROJECT_PATH, "rb") as f:
        return tomllib.load(f)


class TestPyprojectDependencies:
    """AC-001: deepagents pin matches ADR-ARCH-011 portfolio alignment."""

    def test_pyproject_is_valid_toml(self, pyproject: dict) -> None:
        """pyproject.toml must parse without errors."""
        assert isinstance(pyproject, dict)

    def test_deepagents_in_dependencies(self, pyproject: dict) -> None:
        """deepagents>=0.5.3,<0.6 must be listed in [project].dependencies (ADR-ARCH-011)."""
        deps = pyproject["project"]["dependencies"]
        deepagents_deps = [d for d in deps if d.startswith("deepagents")]
        assert len(deepagents_deps) == 1, f"Expected exactly one deepagents dep, got: {deepagents_deps}"
        assert deepagents_deps[0] == "deepagents>=0.5.3,<0.6"

    def test_langchain_in_dependencies(self, pyproject: dict) -> None:
        """LangChain ecosystem packages must be in dependencies."""
        deps = pyproject["project"]["dependencies"]
        dep_names = {d.split(">=")[0].split(">")[0].split("<")[0].split("==")[0] for d in deps}
        required = {"langchain", "langchain-core", "langchain-community", "langgraph"}
        missing = required - dep_names
        assert not missing, f"Missing LangChain deps: {missing}"

    def test_existing_dependencies_preserved(self, pyproject: dict) -> None:
        """Pre-existing dependencies must not be removed."""
        deps = pyproject["project"]["dependencies"]
        dep_names = {d.split(">=")[0].split(">")[0].split("<")[0].split("==")[0] for d in deps}
        preserved = {"anthropic", "chromadb", "pyyaml", "pydantic", "langchain-text-splitters"}
        missing = preserved - dep_names
        assert not missing, f"Pre-existing deps were removed: {missing}"


class TestPackageIncludes:
    """AC-002: Package includes updated for agents*, prompts*, config*."""

    def test_agents_in_package_includes(self, pyproject: dict) -> None:
        """agents* must be in [tool.setuptools.packages.find].include."""
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "agents*" in includes, f"agents* not in includes: {includes}"

    def test_prompts_in_package_includes(self, pyproject: dict) -> None:
        """prompts* must be in [tool.setuptools.packages.find].include."""
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "prompts*" in includes, f"prompts* not in includes: {includes}"

    def test_config_in_package_includes(self, pyproject: dict) -> None:
        """config* must be in [tool.setuptools.packages.find].include."""
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "config*" in includes, f"config* not in includes: {includes}"

    def test_existing_includes_preserved(self, pyproject: dict) -> None:
        """Pre-existing package includes must not be removed."""
        includes = pyproject["tool"]["setuptools"]["packages"]["find"]["include"]
        assert "synthesis*" in includes, f"synthesis* removed from includes: {includes}"
        assert "ingestion*" in includes, f"ingestion* removed from includes: {includes}"


class TestTestPaths:
    """AC-003: Test paths include new test locations."""

    def test_config_tests_in_testpaths(self, pyproject: dict) -> None:
        """config/tests must be in [tool.pytest.ini_options].testpaths."""
        testpaths = pyproject["tool"]["pytest"]["ini_options"]["testpaths"]
        assert "config/tests" in testpaths, f"config/tests not in testpaths: {testpaths}"

    def test_agents_tests_in_testpaths(self, pyproject: dict) -> None:
        """agents/tests must be in [tool.pytest.ini_options].testpaths."""
        testpaths = pyproject["tool"]["pytest"]["ini_options"]["testpaths"]
        assert "agents/tests" in testpaths, f"agents/tests not in testpaths: {testpaths}"

    def test_prompts_tests_in_testpaths(self, pyproject: dict) -> None:
        """prompts/tests must be in [tool.pytest.ini_options].testpaths."""
        testpaths = pyproject["tool"]["pytest"]["ini_options"]["testpaths"]
        assert "prompts/tests" in testpaths, f"prompts/tests not in testpaths: {testpaths}"

    def test_existing_testpaths_preserved(self, pyproject: dict) -> None:
        """Pre-existing test paths must not be removed."""
        testpaths = pyproject["tool"]["pytest"]["ini_options"]["testpaths"]
        expected = ["synthesis/tests", "domain_config/tests", "ingestion/tests", "src/tools/tests"]
        for path in expected:
            assert path in testpaths, f"{path} removed from testpaths: {testpaths}"


class TestPackageDirectories:
    """Verify package directories exist as importable Python packages."""

    @pytest.mark.parametrize(
        "package_dir",
        ["agents", "prompts", "config"],
    )
    def test_package_init_exists(self, package_dir: str) -> None:
        """Each new package directory must have an __init__.py."""
        init_file = PROJECT_ROOT / package_dir / "__init__.py"
        assert init_file.exists(), f"{init_file} does not exist"

    @pytest.mark.parametrize(
        "package_dir",
        ["agents", "prompts", "config"],
    )
    def test_tests_dir_exists(self, package_dir: str) -> None:
        """Each new package must have a tests/ subdirectory."""
        tests_dir = PROJECT_ROOT / package_dir / "tests"
        assert tests_dir.is_dir(), f"{tests_dir} does not exist"
