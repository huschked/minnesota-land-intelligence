"""Validate the Markdown backlog and render its repository Kanban board.

Uses only the standard library. Run with --check to verify without writing.
"""

from __future__ import annotations

import argparse
import re
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKLOG = ROOT / "docs/planning/backlog.md"
BOARD = ROOT / "docs/planning/kanban.md"
STATUSES = ("Backlog", "Ready", "In Progress", "Blocked", "Done")


@dataclass(frozen=True)
class Story:
    identity: str
    title: str
    status: str
    priority: str
    dependencies: tuple[str, ...]
    body: str


@dataclass(frozen=True)
class Epic:
    identity: str
    title: str
    state: str
    stories: tuple[Story, ...]


def field(body: str, name: str) -> str:
    match = re.search(rf"^\*\*{re.escape(name)}:\*\* (.+)$", body, re.MULTILINE)
    if match is None:
        raise ValueError(f"Missing required field: {name}")
    return match.group(1).strip()


def parse_backlog(text: str) -> list[Epic]:
    epic_headings = list(re.finditer(r"^## (E\d+) - (.+)$", text, re.MULTILINE))
    epics = []
    for index, heading in enumerate(epic_headings):
        end = epic_headings[index + 1].start() if index + 1 < len(epic_headings) else len(text)
        body = text[heading.end():end]
        story_headings = list(re.finditer(r"^### (ML-\d+) - (.+)$", body, re.MULTILINE))
        stories = []
        for story_index, story_heading in enumerate(story_headings):
            story_end = story_headings[story_index + 1].start() if story_index + 1 < len(story_headings) else len(body)
            story_body = body[story_heading.end():story_end]
            dependency_text = field(story_body, "Depends on")
            dependencies = () if dependency_text == "None" else tuple(
                value.strip() for value in dependency_text.split(",")
            )
            stories.append(Story(
                story_heading.group(1), story_heading.group(2),
                field(story_body, "Status"), field(story_body, "Priority"),
                dependencies, story_body,
            ))
        epics.append(Epic(heading.group(1), heading.group(2), field(body, "Epic state"), tuple(stories)))
    return epics


def validate(epics: list[Epic]) -> None:
    if not epics:
        raise ValueError("No epics found")
    stories = [story for epic in epics for story in epic.stories]
    by_id = {story.identity: story for story in stories}
    if len(by_id) != len(stories) or len({epic.identity for epic in epics}) != len(epics):
        raise ValueError("Duplicate story or epic IDs")
    for epic in epics:
        if not epic.stories:
            raise ValueError(f"Epic has no stories: {epic.identity}")
        expected_state = (
            "Complete" if all(s.status == "Done" for s in epic.stories)
            else "Active" if any(s.status in ("Done", "In Progress") for s in epic.stories)
            else "Backlog"
        )
        if epic.state != expected_state:
            raise ValueError(f"{epic.identity}: expected epic state {expected_state}")
    for story in stories:
        if story.status not in STATUSES or story.priority not in ("P0", "P1", "P2"):
            raise ValueError(f"Invalid status/priority: {story.identity}")
        for required in ("Kind", "User outcome", "Validation", "Evidence / starting points"):
            field(story.body, required)
        criteria = re.findall(r"^- \[([ x])\] (.+)$", story.body, re.MULTILINE)
        if len(criteria) < 2:
            raise ValueError(f"At least two acceptance checks required: {story.identity}")
        if story.status == "Done":
            if any(check != "x" for check, _ in criteria):
                raise ValueError(f"Done story has unfinished criteria: {story.identity}")
            if not re.search(r"\[[^\]]+\]\([^)]+\)", field(story.body, "Evidence / starting points")):
                raise ValueError(f"Done story lacks evidence links: {story.identity}")
        if story.status == "Blocked":
            field(story.body, "Blocker")
        for dependency in story.dependencies:
            if dependency not in by_id:
                raise ValueError(f"Unknown dependency {dependency} in {story.identity}")
            if story.status in ("Ready", "Done") and by_id[dependency].status != "Done":
                raise ValueError(f"{story.identity}: dependency {dependency} is not Done")
        if f'<a id="{story.identity.lower()}"></a>' not in story.body:
            raise ValueError(f"Missing stable anchor: {story.identity}")
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity: str) -> None:
        if identity in visiting:
            raise ValueError(f"Cyclic dependency involving {identity}")
        if identity in visited:
            return
        visiting.add(identity)
        for dependency in by_id[identity].dependencies:
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)

    for identity in by_id:
        visit(identity)


def link(story: Story) -> str:
    return f"[{story.identity}: {story.title}](backlog.md#{story.identity.lower()})"


def render(epics: list[Epic], date: str) -> str:
    stories = [story for epic in epics for story in epic.stories]
    counts = {status: sum(story.status == status for story in stories) for status in STATUSES}
    lines = [
        "# Minnesota Land Intelligence Platform - Kanban",
        "",
        f"Planning snapshot: {date}. {len(epics)} epics; {len(stories)} stories.",
        "",
        ("Repository-based board: linked cards open their story details. This is not a hosted or drag-and-drop application. "
         "Update statuses in [the backlog](backlog.md), then regenerate this view using [the workflow](workflow.md)."),
        "",
        "## Work status",
        "",
        "| Backlog | Ready | In Progress | Blocked | Done |",
        "|---:|---:|---:|---:|---:|",
        "| " + " | ".join(str(counts[status]) for status in STATUSES) + " |",
        "",
        "Done means implemented with recorded evidence, not necessarily a deployed release or remote backup. "
        "Ready means refined enough to select, not authorization to start every later phase. "
        + ("Nothing is currently marked In Progress." if counts["In Progress"] == 0
           else f"Currently In Progress: {counts['In Progress']} stories; check the workflow WIP limit."),
        "",
        "## Recommended next pulls",
        "",
    ]
    by_id = {story.identity: story for story in stories}
    for identity in ("ML-120", "ML-118", "ML-119", "ML-125", "ML-126", "ML-127", "ML-129", "ML-123", "ML-201", "ML-124"):
        story = by_id.get(identity)
        if story and story.status == "Ready":
            lines.append(f"- {link(story)} ({story.priority}).")
    lines.extend([
        "",
        ("The UI discovery card can be selected independently of county accounting replies. "
         "UI implementation depends on the snapshot/reliability stories identified in its epic. "
         "GIS, scoring, hosted deployment, and AI implementation remain future scope."),
        "",
        "## Epics with story cards",
        "",
        "Each epic is a swimlane. Select a card to read its outcome, acceptance checks, dependencies, blocker/notes, and evidence.",
        "",
        "| Epic | Backlog | Ready | In Progress | Blocked | Done |",
        "|---|---|---|---|---|---|",
    ])
    for epic in epics:
        name = f"[{epic.identity}: {epic.title}](backlog.md#{epic.identity.lower()})<br>{epic.state}"
        columns = [name]
        for status in STATUSES:
            cards = [f"{link(story)} ({story.priority})" for story in epic.stories if story.status == status]
            columns.append("<br><br>".join(cards) if cards else "-")
        lines.append("| " + " | ".join(columns) + " |")
    lines.extend([
        "",
        "## Current external blockers",
        "",
    ])
    lines.extend(f"- {link(story)}: {field(story.body, 'Blocker')}" for story in stories if story.status == "Blocked")
    lines.extend([
        "",
        ("The [roadmap](../roadmap.md) defines outcomes and sequence. "
         "The [backlog](backlog.md) owns story status. The [workflow](workflow.md) defines WIP limits and completion rules."),
        "",
    ])
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Validate without modifying files")
    args = parser.parse_args()
    text = BACKLOG.read_text(encoding="utf-8")
    epics = parse_backlog(text)
    validate(epics)
    date_match = re.search(r"^Updated: (\d{4}-\d{2}-\d{2})\.", text, re.MULTILINE)
    if date_match is None:
        raise ValueError("Backlog must declare Updated: YYYY-MM-DD.")
    expected = render(epics, date_match.group(1))
    if args.check:
        if not BOARD.is_file() or BOARD.read_text(encoding="utf-8") != expected:
            raise ValueError("Kanban view is stale; run scripts/render_kanban.py")
        print(f"Validated {len(epics)} epics and {sum(len(epic.stories) for epic in epics)} stories; board is current.")
        return 0
    BOARD.parent.mkdir(parents=True, exist_ok=True)
    BOARD.write_text(expected, encoding="utf-8")
    print(f"Rendered {BOARD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
