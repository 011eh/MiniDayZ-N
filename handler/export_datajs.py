import json
import re
from pathlib import Path


def find_project_root() -> Path:
    starts = [Path(__file__).absolute(), Path.cwd().absolute()]

    for start in starts:
        for parent in [start, *start.parents]:
            candidate = parent / "origin" / "original_docs" / "data.js"
            if candidate.exists():
                return parent

    raise FileNotFoundError("Cannot find origin/original_docs/data.js")


ROOT = find_project_root()
SRC = ROOT / "origin" / "original_docs" / "data.js"
OUT = ROOT / "origin" / "文档" / "datajs_export"


def safe_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]+', "_", name)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def describe_project(project: list) -> str:
    lines = [
        "# data.js 解析导出",
        "",
        "来源：`origin/original_docs/data.js`",
        "",
        "## project 顶层索引",
        "",
    ]

    for index, item in enumerate(project):
        if isinstance(item, list):
            lines.append(f"- `project[{index}]`: list, length={len(item)}")
        else:
            lines.append(
                f"- `project[{index}]`: `{type(item).__name__}` = `{item}`"
            )

    return "\n".join(lines) + "\n"


def export_event_sheets(project: list) -> None:
    events_dir = OUT / "event_sheets"
    events_dir.mkdir(parents=True, exist_ok=True)

    for sheet_name, sheet_data in project[6]:
        write_json(events_dir / f"{safe_filename(sheet_name)}.json", sheet_data)


def export_objects(project: list) -> None:
    objects_dir = OUT / "objects"
    objects_dir.mkdir(parents=True, exist_ok=True)

    for index, obj in enumerate(project[3]):
        write_json(objects_dir / f"object_{index:03d}.json", obj)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)

    data = json.loads(SRC.read_text(encoding="utf-8-sig"))
    project = data["project"]

    write_json(OUT / "data.pretty.json", data)
    (OUT / "README.md").write_text(describe_project(project), encoding="utf-8")
    export_event_sheets(project)
    export_objects(project)

    print(f"导出完成：{OUT}")
    print("完整数据：data.pretty.json")
    print("顶层说明：README.md")
    print("事件表：event_sheets/")
    print("对象定义：objects/")


if __name__ == "__main__":
    main()
