import ast
import json
import logging
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


@dataclass
class Config:
    libs_path: Path
    packages_path: Path
    max_file_statement_count_percent: float
    max_component_statement_count_percent: float
    max_component_statement_std_deviation_count: float


@dataclass
class Report:
    file_statement_count_warnings: list[str]
    component_statement_count_warnings: list[str]
    import_warnings: list[str]
    files_in_root_warnings: list[str]
    common_components_warnings: list[str]
    common_files_warnings: list[str]
    counter: GlobalCounter


def get_package_names(path: Path) -> list[str]:
    packages_names: list[str] = []

    for dir_path, dir_names, file_names in path.walk():
        if "__init__.py" in file_names:
            packages_names.append(dir_path.name)
            dir_names.clear()

    return packages_names


def generate_counter(folder_path: Path) -> GlobalCounter:
    component_counters: dict[Path, ComponentCounter] = defaultdict(
        lambda: ComponentCounter(
            component_path=Path(), statement_count=0, file_counters=[]
        )
    )
    total_statement_count = 0

    for dir_path, dir_names, file_names in folder_path.walk():
        for dir_name in dir_names:
            if should_skip_dir(dir_name):
                dir_names.remove(dir_name)

        for file in file_names:
            if should_skip_file(file):
                continue

            file_path = dir_path / file
            component_path = file_path.parent
            if not dir_is_package(component_path):
                continue

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


def should_skip_dir(dir_name: str) -> bool:
    return dir_name.startswith(".") or dir_name.startswith("_")


def dir_is_package(dir_path: Path) -> bool:
    return (
        dir_path.is_dir()
        and next(
            (f for f in dir_path.iterdir() if f.name == "__init__.py"),
            None,
        )
        is not None
    )


def calculate_std_dev_and_mean(counter: GlobalCounter) -> tuple[float, float]:
    square_diff_sum = 0
    component_count = len(counter.component_counters)
    component_statement_mean = counter.statement_count / component_count

    for component_counter in counter.component_counters:
        diff = abs(component_counter.statement_count - component_statement_mean)
        square_diff_sum += diff**2

    std_dev = (square_diff_sum / (component_count - 1)) ** 0.5
    return std_dev, component_statement_mean


def save_report(report: Report) -> None:
    sorted_components = sorted(
        report.counter.component_counters,
        key=lambda counter: counter.statement_count,
        reverse=True,
    )

    with open("components.json", "w") as f:
        json.dump(
            {
                str(component_counter.component_path): component_counter.statement_count
                for component_counter in sorted_components
            },
            f,
            indent=2,
        )


def generate_report(config: Config) -> Report:
    root_path = Path(".").resolve()
    counter = generate_counter(root_path)
    max_file_statement_count = round(
        counter.statement_count * config.max_component_statement_count_percent
    )
    package_names = get_package_names(config.packages_path)

    file_statement_count_warnings: list[str] = []
    component_statement_count_warnings: list[str] = []
    import_warnings: list[str] = []
    files_in_root_warnings: list[str] = []
    common_components_warnings: list[str] = []
    common_files_warnings: list[str] = []

    for component_counter in counter.component_counters:
        for file_counter in component_counter.file_counters:
            if file_counter.statement_count > max_file_statement_count:
                file_statement_count_warnings.append(
                    f"Path {file_counter.file_path} has {round(file_counter.statement_count)} statements. Maximim allowed statement count per file is {max_file_statement_count}"
                )

            is_lib = file_counter.file_path.is_relative_to(config.libs_path)
            if is_lib:
                for import_ in file_counter.imports:
                    for package_name in package_names:
                        if package_name in import_.split("."):
                            import_warnings.append(
                                f"Path {file_counter.file_path} is a lib and should not import package {package_name}"
                            )

            is_package = file_counter.file_path.is_relative_to(config.packages_path)
            if is_package:
                for import_ in file_counter.imports:
                    for package_name in package_names:
                        if package_name not in str(
                            file_counter.file_path
                        ) and package_name in import_.split("."):
                            import_warnings.append(
                                f"Path {file_counter.file_path} should not import another package {package_name}"
                            )

    std_dev, component_statement_mean = calculate_std_dev_and_mean(counter)
    leaf_nodes: set[str] = set()
    common_components: set[str] = set()

    for component_counter in counter.component_counters:
        diff_from_mean = abs(
            component_counter.statement_count - component_statement_mean
        )
        std_dev_count = diff_from_mean / std_dev

        if std_dev_count > 3:
            component_statement_count_warnings.append(
                f"Path {component_counter} is an outlier with {std_dev_count} standard deviations from the mean"
            )

        leaf_name = Path(component_counter.component_path).name
        if leaf_name in leaf_nodes:
            common_components.add(str(component_counter.component_path))
        else:
            leaf_nodes.add(leaf_name)

    if len(common_components) > 0:
        common_components_warnings.append(
            f"There are common component names {common_components}"
        )

    seen_files: set[str] = set()
    common_files: set[str] = set()
    files_in_root: set[Path] = set()

    for component_counter in counter.component_counters:
        for file_counter in component_counter.file_counters:
            file_name = file_counter.file_path.name
            if file_name in seen_files:
                common_files.add(file_name)
            else:
                seen_files.add(file_name)

            for look_up_counter in counter.component_counters:
                if str(component_counter.component_path) in str(
                    look_up_counter.component_path
                ) and len(str(look_up_counter.component_path)) > len(
                    str(component_counter.component_path)
                ):
                    files_in_root.add(file_counter.file_path)

    if len(common_files) > 0:
        common_files_warnings.append(f"There are common file names {common_files}")

    if len(files_in_root) > 0:
        files_in_root_warnings.append(f"There are files in root {files_in_root}")

    report = Report(
        file_statement_count_warnings=file_statement_count_warnings,
        component_statement_count_warnings=component_statement_count_warnings,
        import_warnings=import_warnings,
        files_in_root_warnings=files_in_root_warnings,
        common_components_warnings=common_components_warnings,
        common_files_warnings=common_files_warnings,
        counter=counter,
    )

    return report


if __name__ == "__main__":
    config = Config(
        libs_path=Path("libs").resolve(),
        packages_path=Path("packages").resolve(),
        max_file_statement_count_percent=0.1,
        max_component_statement_count_percent=0.1,
        max_component_statement_std_deviation_count=3,
    )
    report = generate_report(config)
    save_report(report)
    print(report)
