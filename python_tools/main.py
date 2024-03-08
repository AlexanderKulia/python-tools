import ast
import json
import logging
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

logging.basicConfig()
logger = logging.getLogger(__name__)


@dataclass
class FileCounter:
    file_path: Path
    statement_count: int
    imports: set[str]


@dataclass
class Counter:
    statement_count: int
    file_counters: list[FileCounter]


def generate_file_stats(folder_path: Path) -> Counter:
    file_counters: list[FileCounter] = []
    total_statement_count = 0

    for dir_path, dir_names, file_names in folder_path.walk():
        if ".venv" in dir_names:
            dir_names.remove(".venv")

        for file in file_names:
            if should_skip_file(file):
                continue

            file_path = dir_path / file
            file_statement_count = 0
            imports: set[str] = set()

            with open(file_path, "r") as f:
                file_ast = ast.parse(f.read())

                for node in ast.walk(file_ast):
                    if is_statement(node):
                        file_statement_count += 1
                        total_statement_count += 1

                    if isinstance(node, ast.ImportFrom):
                        import_name = node.module
                        if import_name:
                            imports.add(import_name)

                    elif isinstance(node, ast.Import):
                        for name in node.names:
                            imports.add(name.name)

            file_counters.append(
                FileCounter(
                    file_path=file_path,
                    statement_count=file_statement_count,
                    imports=imports,
                )
            )

    return Counter(statement_count=total_statement_count, file_counters=file_counters)


def is_statement(node: ast.AST) -> bool:
    return isinstance(
        node,
        (
            ast.Assert,
            ast.Assign,
            ast.AnnAssign,
            ast.AugAssign,
            ast.Break,
            ast.Continue,
            ast.Delete,
            ast.Expr,
            ast.ExceptHandler,
            ast.For,
            ast.Global,
            ast.If,
            ast.Nonlocal,
            ast.Pass,
            ast.Raise,
            ast.Return,
            ast.Try,
            ast.TryStar,
            ast.TypeAlias,
            ast.While,
            ast.With,
            ast.Match,
        ),
    )


def should_skip_file(file_name: str) -> bool:
    return not file_name.endswith(".py") or file_name == "__init__.py"


if __name__ == "__main__":
    root_path = Path(".").resolve()
    stats = generate_file_stats(root_path)
    is_success = True
    max_allowed_statement_percent_per_file = 0.1
    max_allowed_statement_count_per_file = round(
        stats.statement_count * max_allowed_statement_percent_per_file
    )

    component_map: dict[str, int] = defaultdict(int)

    for stat in stats.file_counters:
        component_name = stat.file_path.parent
        component_map[str(component_name)] += stat.statement_count

        for import_ in stat.imports:
            if "/libs/" in str(stat.file_path) and "packages" in import_:
                logger.warning(f"Path {stat.file_path} should not import {import_}")
                is_success = False

        if stat.statement_count > max_allowed_statement_count_per_file:
            logger.warning(
                f"Path {stat.file_path} has {round(stat.statement_count)} statements. Maximim allowed statement count per file is {max_allowed_statement_count_per_file}"
            )

    square_diff_sum = 0
    component_count = len(component_map.keys())
    component_statement_mean = stats.statement_count / component_count

    for component_path, statement_count in component_map.items():
        diff = statement_count - component_statement_mean
        square_diff_sum += diff**2
        diff_from_mean = abs(statement_count - component_statement_mean)

    std_dev = (square_diff_sum / (component_count - 1)) ** 0.5

    for component_path, statement_count in component_map.items():
        diff_from_mean = abs(statement_count - component_statement_mean)
        std_dev_count = diff_from_mean / std_dev

        if std_dev_count > 3:
            logger.warning(
                f"Path {stat.file_path} is an outlier with {std_dev_count} standard deviations from the mean"
            )
            is_success = False

    with open("components.json", "w") as f:
        json.dump(component_map, f)

    if not is_success:
        sys.exit(1)
