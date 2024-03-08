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
class ComponentCounter:
    component_path: Path
    statement_count: int
    file_counters: list[FileCounter]


@dataclass
class GlobalCounter:
    statement_count: int
    component_counters: list[ComponentCounter]


def generate_stats(folder_path: Path) -> GlobalCounter:
    component_counters: dict[Path, ComponentCounter] = defaultdict(
        lambda: ComponentCounter(
            component_path=Path(), statement_count=0, file_counters=[]
        )
    )
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

            file_counter = FileCounter(
                file_path=file_path,
                statement_count=file_statement_count,
                imports=imports,
            )
            component_path = file_path.parent
            component_counters[component_path].component_path = component_path
            component_counters[component_path].statement_count += file_statement_count
            component_counters[component_path].file_counters.append(file_counter)

    return GlobalCounter(
        statement_count=total_statement_count,
        component_counters=list(component_counters.values()),
    )


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
    max_allowed_statement_percent_per_file = 0.1
    max_allowed_statement_count_per_file = round(
        stats.statement_count * max_allowed_statement_percent_per_file
    )

    for component_stat in stats.component_counters:
        for file_stat in component_stat.file_counters:
            for import_ in file_stat.imports:
                if "/libs/" in str(file_stat.file_path) and "packages" in import_:
                    logger.warning(
                        f"Path {file_stat.file_path} should not import {import_}"
                    )
                    is_success = False

            if file_stat.statement_count > max_allowed_statement_count_per_file:
                logger.warning(
                    f"Path {file_stat.file_path} has {round(file_stat.statement_count)} statements. Maximim allowed statement count per file is {max_allowed_statement_count_per_file}"
                )

    square_diff_sum = 0
    component_count = len(stats.component_counters)
    component_statement_mean = stats.statement_count / component_count

    for component_stat in stats.component_counters:
        diff = abs(component_stat.statement_count - component_statement_mean)
        square_diff_sum += diff**2

    std_dev = (square_diff_sum / (component_count - 1)) ** 0.5

    leaf_nodes: set[str] = set()
    common_components: set[str] = set()

    for component_stat in stats.component_counters:
        diff_from_mean = abs(component_stat.statement_count - component_statement_mean)
        std_dev_count = diff_from_mean / std_dev

        if std_dev_count > 3:
            logger.warning(
                f"Path {component_stat} is an outlier with {std_dev_count} standard deviations from the mean"
            )
            is_success = False

        leaf_name = Path(component_stat.component_path).name
        if leaf_name in leaf_nodes:
            common_components.add(str(component_stat.component_path))
        else:
            leaf_nodes.add(leaf_name)

    if len(common_components) > 0:
        logger.warning(f"There are common component names {common_components}")

    seen_files: set[str] = set()
    common_files: set[str] = set()
    files_in_root: set[str] = set()

    for component_stat in stats.component_counters:
        for file_stat in component_stat.file_counters:
            file_name = file_stat.file_path.name
            if file_name in seen_files:
                common_files.add(file_name)
            else:
                seen_files.add(file_name)

            file_is_in_root = False
            for cstat in stats.component_counters:
                if str(component_stat.component_path) in str(cstat.component_path):
                    file_is_in_root = True

        if file_is_in_root:
            logger.warning(f"File {file_stat.file_path} resides in root namespace")

    if len(common_files) > 0:
        logger.warning(f"There are common file names {common_files}")

    with open("components.json", "w") as f:
        json.dump(
            {
                str(stat.component_path): stat.statement_count
                for stat in stats.component_counters
            },
            f,
        )

    if not is_success:
        sys.exit(1)
