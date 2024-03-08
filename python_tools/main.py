import ast
import logging
import sys
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


def generate_stats(folder_path: Path) -> Counter:
    file_counters: list[FileCounter] = []
    total_statement_count = 0

    for dir_path, dir_names, file_names in folder_path.walk():
        if ".venv" in dir_names:
            dir_names.remove(".venv")

        for file in file_names:
            if should_skip_file(file):
                continue

            file_path = dir_path / file
            statement_count = 0
            imports: set[str] = set()

            with open(file_path, "r") as f:
                file_ast = ast.parse(f.read())

                for node in ast.walk(file_ast):
                    if is_statement(node):
                        statement_count += 1
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
                    statement_count=statement_count,
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
    stats = generate_stats(root_path)
    is_success = True
    max_allowed_statement_percent_per_file = 0.05
    max_allowed_statement_count_per_file = round(
        stats.statement_count * max_allowed_statement_percent_per_file
    )

    for stat in stats.file_counters:
        for import_ in stat.imports:
            if "/libs/" in str(stat.file_path) and "packages" in import_:
                logger.warning(f"Path {stat.file_path} should not import {import_}")
                is_success = False

        if stat.statement_count > max_allowed_statement_count_per_file:
            logger.warning(
                f"Path {stat.file_path} has {round(stat.statement_count)} statements. Maximim allowed statement count per file is {max_allowed_statement_count_per_file}"
            )

    if not is_success:
        sys.exit(1)
