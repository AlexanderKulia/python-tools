import ast
import logging
import sys
from pathlib import Path

logging.basicConfig()
logger = logging.getLogger(__name__)


def generate_deps(folder_path: Path, map: dict[str, set[str]]) -> dict[str, set[str]]:
    for dir_path, dir_names, file_names in folder_path.walk():
        if ".venv" in dir_names:
            dir_names.remove(".venv")

        for file in file_names:
            if should_skip_file(file):
                continue

            file_path = dir_path / file
            deps = get_file_deps(file_path)
            map[str(file_path)] = deps

    return map


def get_file_deps(path: Path) -> set[str]:
    deps: set[str] = set()

    with open(path, "r") as f:
        file_ast = ast.parse(f.read())

        for node in ast.walk(file_ast):
            if isinstance(node, ast.ImportFrom):
                import_name = node.module
                if import_name:
                    deps.add(import_name)

            elif isinstance(node, ast.Import):
                for name in node.names:
                    deps.add(name.name)

    return deps


def should_skip_file(file_name: str) -> bool:
    return not file_name.endswith(".py") or file_name == "__init__.py"


if __name__ == "__main__":
    root_path = Path(".").resolve()
    map = generate_deps(root_path, {})
    print(map)

    is_success = True

    for path, deps in map.items():
        for dep in deps:
            if "/libs/" in path and "packages" in dep:
                logger.warning(f"Path {path} should not import {dep}")
                is_success = False

    sys.exit(1)
