#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request
import urllib.parse
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_URL = 'https://canvas.example.edu'
DEFAULT_CONFIG = r'.\\canvas_materials\\_canvas_material_sync_config.json'


def load_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def request_json(url: str, token: str) -> Tuple[Any, Dict[str, str]]:
    req = urllib.request.Request(
        url,
        headers={
            'Authorization': f'Bearer {token}',
            'User-Agent': 'canvas-material-skill/list-courses',
        },
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode('utf-8', errors='replace')
        headers = {k: v for k, v in resp.headers.items()}
    return json.loads(body), headers


def next_link(link_header: Optional[str]) -> Optional[str]:
    if not link_header:
        return None
    for part in link_header.split(','):
        part = part.strip()
        if 'rel="next"' in part:
            l = part.find('<')
            r = part.find('>', l + 1)
            if l != -1 and r != -1:
                return part[l + 1:r]
    return None


def paged_courses(base_url: str, token: str) -> List[Dict[str, Any]]:
    url = f"{base_url.rstrip('/')}/api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades"
    all_courses: List[Dict[str, Any]] = []
    while url:
        data, headers = request_json(url, token)
        if isinstance(data, list):
            all_courses.extend(data)
            url = next_link(headers.get('Link'))
        else:
            all_courses.append(data)
            break
    return all_courses


def main() -> int:
    parser = argparse.ArgumentParser(description='List Canvas courses as id + term + name.')
    parser.add_argument('--canvas-url', default=None, help='Canvas base URL')
    parser.add_argument('--canvas-token', default=None, help='Canvas API token')
    parser.add_argument('--config', default=DEFAULT_CONFIG, help='Optional config JSON path')
    parser.add_argument('--term', default=None, help='Optional exact term name filter, e.g. Semester B 2025/26')
    parser.add_argument('--json', action='store_true', help='Output JSON instead of tab-separated text')
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else {}
    base_url = args.canvas_url or os.environ.get('CANVAS_URL') or cfg.get('canvas_url') or DEFAULT_URL
    token = args.canvas_token or os.environ.get('CANVAS_TOKEN') or cfg.get('canvas_token')

    if not token:
        print('Error: missing Canvas token. Provide --canvas-token, CANVAS_TOKEN, or a config file containing canvas_token.', file=sys.stderr)
        return 1

    courses = paged_courses(base_url, token)
    rows = []
    for c in courses:
        term = (c.get('term') or {}).get('name') or ''
        name = c.get('name') or c.get('course_code') or ''
        rows.append({
            'id': c.get('id'),
            'term': term,
            'name': name,
        })

    rows.sort(key=lambda x: ((x.get('term') or ''), (x.get('name') or ''), x.get('id') or 0))

    if args.term:
        rows = [r for r in rows if r['term'] == args.term]

    if args.json:
        print(json.dumps(rows, ensure_ascii=False, indent=2))
    else:
        for r in rows:
            print(f"{r['id']}\t{r['term']}\t{r['name']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())

