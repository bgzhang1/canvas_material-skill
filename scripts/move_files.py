#!/usr/bin/env python3
import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Dict, List


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Batch move files from one directory to another.'
    )
    parser.add_argument('source_dir', help='Source directory')
    parser.add_argument('target_dir', help='Target directory')
    parser.add_argument('--pattern', default='*', help='Glob pattern, e.g. *.pdf')
    parser.add_argument('--recursive', action='store_true', help='Recursively search source directory')
    parser.add_argument('--preserve-tree', action='store_true', help='Preserve source relative directory structure in target')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing target files')
    parser.add_argument('--dry-run', action='store_true', help='Preview moves without changing files')
    parser.add_argument('--json', action='store_true', help='Output JSON summary')
    return parser


def unique_target(path: Path) -> Path:
    base = path.stem
    ext = path.suffix
    parent = path.parent
    i = 2
    candidate = path
    while candidate.exists():
        candidate = parent / f'{base}__{i}{ext}'
        i += 1
    return candidate



def collect_files(source_dir: Path, pattern: str, recursive: bool) -> List[Path]:
    iterator = source_dir.rglob(pattern) if recursive else source_dir.glob(pattern)
    return sorted([p for p in iterator if p.is_file()])



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    source_dir = Path(args.source_dir).expanduser().resolve()
    target_dir = Path(args.target_dir).expanduser().resolve()

    if not source_dir.exists() or not source_dir.is_dir():
        print(f'Error: source directory not found: {source_dir}', file=sys.stderr)
        return 1

    files = collect_files(source_dir, args.pattern, args.recursive)
    if not files:
        print('Error: no matching files found.', file=sys.stderr)
        return 1

    moves: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []

    for src in files:
        if args.preserve_tree:
            rel = src.relative_to(source_dir)
            dest = target_dir / rel
        else:
            dest = target_dir / src.name

        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            final_dest = dest
            if final_dest.exists() and not args.overwrite:
                final_dest = unique_target(final_dest)

            record = {'source': str(src), 'target': str(final_dest)}
            if args.dry_run:
                moves.append(record)
                continue

            shutil.move(str(src), str(final_dest))
            moves.append(record)
        except Exception as exc:
            errors.append({'source': str(src), 'target': str(dest), 'error': str(exc)})

    summary = {
        'source_dir': str(source_dir),
        'target_dir': str(target_dir),
        'pattern': args.pattern,
        'recursive': args.recursive,
        'preserve_tree': args.preserve_tree,
        'overwrite': args.overwrite,
        'dry_run': args.dry_run,
        'moved_count': len(moves),
        'error_count': len(errors),
        'moves': moves,
        'errors': errors,
    }

    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"moved={len(moves)}\terrors={len(errors)}")
        for item in moves:
            print(f"{item['source']} -> {item['target']}")
        for item in errors:
            print(f"[error] {item['source']} -> {item['target']} :: {item['error']}", file=sys.stderr)

    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())
