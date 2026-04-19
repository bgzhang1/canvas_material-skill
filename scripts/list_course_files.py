#!/usr/bin/env python3
import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='List all files under a course directory, including file name and directory/path.'
    )
    parser.add_argument('course_dir', help='Course directory path')
    parser.add_argument('--recursive', action='store_true', default=True, help='Recursively list files (default: true)')
    parser.add_argument('--relative', action='store_true', help='Show relative paths instead of absolute paths')
    parser.add_argument('--json', action='store_true', help='Output JSON')
    return parser


def collect_files(course_dir: Path, relative: bool) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for path in sorted(course_dir.rglob('*')):
        if not path.is_file():
            continue
        parent_dir = path.parent.relative_to(course_dir) if relative else path.parent
        file_path = path.relative_to(course_dir) if relative else path
        items.append({
            'name': path.name,
            'directory': str(parent_dir),
            'path': str(file_path),
        })
    return items


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    course_dir = Path(args.course_dir).expanduser().resolve()
    if not course_dir.exists() or not course_dir.is_dir():
        print(f'Error: course directory not found: {course_dir}', file=sys.stderr)
        return 1

    files = collect_files(course_dir, relative=args.relative)

    if args.json:
        print(json.dumps({
            'course_dir': str(course_dir),
            'file_count': len(files),
            'files': files,
        }, ensure_ascii=False, indent=2))
    else:
        print('name\tdirectory\tpath')
        for item in files:
            print(f"{item['name']}\t{item['directory']}\t{item['path']}")
        print(f'total\t{len(files)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
