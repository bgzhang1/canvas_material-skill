#!/usr/bin/env python3
"""Incremental update: fetch new Canvas actions since a given time and download files.

Usage examples:
  # Dry-run: list new links only
  python scripts/incremental_update.py 560 500 --since 2026-04-19T10:00:00 --dry-run

  # Download new files to output root
  python scripts/incremental_update.py 560 500 --since 2026-04-19T10:00:00 --output-root ./canvas_materials

  # Use config for credentials
  python scripts/incremental_update.py 560 500 --since 2026-04-19 --config ./canvas_materials/_canvas_material_sync_config.json
"""
import argparse
import json
import os
import re
import sys
import html
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_URL = 'https://canvas.example.edu'
FILE_LINK_RE = re.compile(r'href=["\']([^"\']+)["\']', re.I)


class CanvasClient:
    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token

    def _request(self, url: str, *, binary: bool = False) -> Tuple[Any, Dict[str, str], str]:
        req = urllib.request.Request(
            url,
            headers={
                'Authorization': f'Bearer {self.token}',
                'User-Agent': 'canvas-material-skill/incremental-update',
            },
        )
        with urllib.request.urlopen(req, timeout=90) as resp:
            final_url = resp.geturl()
            headers = {k: v for k, v in resp.headers.items()}
            body = resp.read()
        if binary:
            return body, headers, final_url
        return body.decode('utf-8', errors='replace'), headers, final_url

    def api_json(self, endpoint_or_url: str) -> Tuple[Any, Dict[str, str], str]:
        url = endpoint_or_url if endpoint_or_url.startswith('http') else f'{self.base_url}/api/v1{endpoint_or_url}'
        text, headers, final = self._request(url)
        return json.loads(text), headers, final

    def paged(self, endpoint_or_url: str) -> List[Dict[str, Any]]:
        url = endpoint_or_url if endpoint_or_url.startswith('http') else f'{self.base_url}/api/v1{endpoint_or_url}'
        out: List[Dict[str, Any]] = []
        while url:
            data, headers, _ = self.api_json(url)
            if isinstance(data, list):
                out.extend(data)
                url = self._next_link(headers.get('Link'))
            else:
                out.append(data)
                break
        return out

    @staticmethod
    def _next_link(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        for part in link_header.split(','):
            m = re.search(r'<([^>]+)>;\s*rel="next"', part)
            if m:
                return m.group(1)
        return None

    def resolve_canvas_file_link(self, href: str) -> Optional[str]:
        if not href:
            return None
        href = html.unescape(href)
        if href.startswith('/'):
            href = self.base_url + href
        if href.startswith('http') and '/download' in href:
            return href
        if '/files/' in href:
            try:
                page, _, _ = self._request(href)
            except Exception:
                page = ''
            if page:
                for link in FILE_LINK_RE.findall(page):
                    link = html.unescape(link)
                    if link.startswith('/'):
                        link = self.base_url + link
                    if '/download' in link:
                        return link
            if '?verifier=' in href:
                return href.replace('?verifier=', '/download?verifier=').replace('&wrap=1', '')
        return href if href.startswith('http') else None

    def download_binary(self, url: str) -> Tuple[bytes, Dict[str, str], str]:
        return self._request(url, binary=True)


def load_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


def parse_since(value: str, config: Dict[str, Any] = None) -> datetime:
    if value.strip().lower() == 'last_update':
        if config and config.get('last_update_at'):
            value = config['last_update_at']
        else:
            raise ValueError('last_update is not set in config. Provide an explicit --since time.')
    for fmt in ('%Y-%m-%dT%H:%M:%S%z', '%Y-%m-%dT%H:%M:%S', '%Y-%m-%dT%H:%M', '%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            return datetime.strptime(value, fmt)
        except ValueError:
            continue
    raise ValueError(f'Cannot parse since time: {value}. Use ISO format like 2026-04-19T10:00:00')


def sanitize_filename(name: str) -> str:
    if not name:
        return 'unnamed'
    return re.sub(r'[\\/:*?"<>|]+', '_', name).strip().rstrip('.') or 'unnamed'


def choose_filename(headers: Dict[str, str], final_url: str, fallback: str) -> str:
    dispo = headers.get('Content-Disposition', '')
    m = re.search(r'filename\*?=(?:UTF-8\'\'|"?)([^";]+)', dispo, re.I)
    if m:
        return sanitize_filename(urllib.parse.unquote(m.group(1)))
    path_name = Path(urllib.parse.urlparse(final_url).path).name
    if path_name and '.' in path_name:
        return sanitize_filename(urllib.parse.unquote(path_name))
    ctype = headers.get('Content-Type', '').lower()
    ext = Path(fallback).suffix
    if not ext:
        if 'pdf' in ctype: ext = '.pdf'
        elif 'word' in ctype: ext = '.docx'
        elif 'powerpoint' in ctype or 'presentationml' in ctype: ext = '.pptx'
        elif 'html' in ctype: ext = '.html'
    return sanitize_filename(fallback + ext)


def unique_path(folder: Path, file_name: str) -> Path:
    safe = sanitize_filename(file_name)
    base = Path(safe).stem
    ext = Path(safe).suffix
    p = folder / safe
    i = 2
    while p.exists():
        p = folder / f'{base}__{i}{ext}'
        i += 1
    return p


def strip_html(value: str) -> str:
    value = value or ''
    value = re.sub(r'<[^>]+>', ' ', value)
    value = html.unescape(value)
    value = re.sub(r'\s+', ' ', value).strip()
    return value


def add_html_candidates(client: CanvasClient, out: List[Dict[str, Any]], *,
                        source_type: str, source_id: str, source_title: str,
                        html_body: str, since: Optional[datetime],
                        source_updated_at: Optional[str]):
    if since and source_updated_at:
        try:
            updated = datetime.fromisoformat(source_updated_at.replace('Z', '+00:00'))
            if updated < since:
                return
        except Exception:
            pass
    context = strip_html(html_body)
    for href in FILE_LINK_RE.findall(html_body or ''):
        real = client.resolve_canvas_file_link(href)
        if real:
            out.append({
                'source_type': source_type,
                'source_id': source_id,
                'source_title': source_title,
                'download_url': real,
                'context_text': context,
                'source_updated_at': source_updated_at,
            })


def item_is_new(item: Dict[str, Any], since: Optional[datetime]) -> bool:
    if since is None:
        return True
    for field in ('updated_at', 'created_at', 'posted_at', 'due_at', 'modified_at'):
        val = item.get(field)
        if val:
            try:
                dt = datetime.fromisoformat(val.replace('Z', '+00:00'))
                if dt >= since:
                    return True
            except Exception:
                continue
    return False


def collect_course_new_links(client: CanvasClient, course_id: int,
                             since: Optional[datetime]) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    course_info, _, _ = client.api_json(f'/courses/{course_id}?include[]=term&include[]=syllabus_body')
    links: List[Dict[str, Any]] = []

    try:
        files = client.paged(f'/courses/{course_id}/files?per_page=100')
        for item in files:
            if not item_is_new(item, since):
                continue
            url = item.get('url')
            if url:
                links.append({
                    'source_type': 'file',
                    'source_id': str(item.get('id') or ''),
                    'source_title': item.get('display_name') or item.get('filename') or 'file',
                    'download_url': url,
                    'context_text': f"course file {item.get('display_name') or item.get('filename') or ''}",
                    'source_updated_at': item.get('updated_at') or item.get('created_at'),
                })
    except Exception as exc:
        print(f'[warn] files scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        announcements = client.paged(f'/announcements?context_codes[]=course_{course_id}&per_page=100')
        for item in announcements:
            if not item_is_new(item, since):
                continue
            add_html_candidates(client, links, source_type='announcement',
                                source_id=str(item.get('id') or ''),
                                source_title=item.get('title') or 'announcement',
                                html_body=item.get('message') or '',
                                since=since,
                                source_updated_at=item.get('posted_at') or item.get('updated_at'))
    except Exception as exc:
        print(f'[warn] announcements scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        assignments = client.paged(f'/courses/{course_id}/assignments?per_page=100')
        for item in assignments:
            if not item_is_new(item, since):
                continue
            add_html_candidates(client, links, source_type='assignment',
                                source_id=str(item.get('id') or ''),
                                source_title=item.get('name') or 'assignment',
                                html_body=item.get('description') or '',
                                since=since,
                                source_updated_at=item.get('updated_at') or item.get('created_at'))
    except Exception as exc:
        print(f'[warn] assignments scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        add_html_candidates(client, links, source_type='syllabus',
                            source_id=str(course_id),
                            source_title='syllabus',
                            html_body=course_info.get('syllabus_body') or '',
                            since=since,
                            source_updated_at=course_info.get('updated_at'))
    except Exception as exc:
        print(f'[warn] syllabus scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        front, _, _ = client.api_json(f'/courses/{course_id}/front_page')
        if item_is_new(front, since):
            add_html_candidates(client, links, source_type='front_page',
                                source_id=str(front.get('page_id') or 'front'),
                                source_title=front.get('title') or 'front_page',
                                html_body=front.get('body') or '',
                                since=since,
                                source_updated_at=front.get('updated_at') or front.get('created_at'))
    except Exception:
        pass

    try:
        pages = client.paged(f'/courses/{course_id}/pages?per_page=100')
        for page in pages:
            try:
                detail, _, _ = client.api_json(f"/courses/{course_id}/pages/{page.get('url')}")
            except Exception:
                continue
            if not item_is_new(detail, since):
                continue
            add_html_candidates(client, links, source_type='page',
                                source_id=str(detail.get('page_id') or page.get('url') or ''),
                                source_title=detail.get('title') or 'page',
                                html_body=detail.get('body') or '',
                                since=since,
                                source_updated_at=detail.get('updated_at') or detail.get('created_at'))
    except Exception as exc:
        print(f'[warn] pages scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        topics = client.paged(f'/courses/{course_id}/discussion_topics?per_page=100')
        for item in topics:
            if not item_is_new(item, since):
                continue
            add_html_candidates(client, links, source_type='discussion',
                                source_id=str(item.get('id') or ''),
                                source_title=item.get('title') or 'discussion',
                                html_body=item.get('message') or '',
                                since=since,
                                source_updated_at=item.get('posted_at') or item.get('updated_at'))
    except Exception as exc:
        print(f'[warn] discussions scan failed for {course_id}: {exc}', file=sys.stderr)

    try:
        modules = client.paged(f'/courses/{course_id}/modules?include[]=items&per_page=100')
        for module in modules:
            module_name = module.get('name') or 'module'
            for item in module.get('items') or []:
                if not item_is_new(item, since):
                    continue
                title = item.get('title') or module_name
                context = f'{module_name} {title}'
                for href in [item.get('external_url'), item.get('html_url'), item.get('url')]:
                    if not href:
                        continue
                    real = client.resolve_canvas_file_link(href)
                    if real:
                        links.append({
                            'source_type': 'module_item',
                            'source_id': str(item.get('id') or item.get('content_id') or ''),
                            'source_title': title,
                            'download_url': real,
                            'context_text': context,
                            'source_updated_at': item.get('updated_at') or item.get('created_at'),
                        })
    except Exception as exc:
        print(f'[warn] modules scan failed for {course_id}: {exc}', file=sys.stderr)

    dedup: Dict[str, Dict[str, Any]] = {}
    for item in links:
        dedup[item['download_url']] = item

    course_name = course_info.get('name') or course_info.get('course_code') or str(course_id)
    return {
        'id': course_id,
        'term': (course_info.get('term') or {}).get('name') or '',
        'name': course_name,
    }, list(dedup.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description='Fetch new Canvas actions since a given time and download new files/links to course-named directories.'
    )
    parser.add_argument('course_ids', nargs='+', type=int, help='One or more Canvas course IDs')
    parser.add_argument('--since', required=True, help='Only fetch items after this time (ISO, e.g. 2026-04-19T10:00:00). Use last_update to read from config')
    parser.add_argument('--canvas-url', default=None, help='Canvas base URL')
    parser.add_argument('--canvas-token', default=None, help='Canvas API token')
    parser.add_argument('--config', default=None, help='Config JSON path (read canvas_url/canvas_token/output_root)')
    parser.add_argument('--output-root', default=None, help='Output root directory')
    parser.add_argument('--dry-run', action='store_true', help='Only list new links, do not download')
    parser.add_argument('--json', action='store_true', help='Output JSON summary')
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else {}
    base_url = args.canvas_url or os.environ.get('CANVAS_URL') or cfg.get('canvas_url') or DEFAULT_URL
    token = args.canvas_token or os.environ.get('CANVAS_TOKEN') or cfg.get('canvas_token')
    output_root = Path(args.output_root or cfg.get('output_root') or Path.cwd()).expanduser().resolve()

    if not token:
        print('Error: missing Canvas token. Provide --canvas-token, CANVAS_TOKEN, or a config containing canvas_token.', file=sys.stderr)
        return 1

    cfg_for_since = cfg if args.config else {}
    since = parse_since(args.since, cfg_for_since)
    client = CanvasClient(base_url, token)

    total_links = 0
    total_downloaded = 0
    total_errors = 0
    summary_courses = []

    for course_id in args.course_ids:
        try:
            course_meta, links = collect_course_new_links(client, course_id, since)
        except Exception as exc:
            print(f'[error] course {course_id}: {exc}', file=sys.stderr)
            continue

        course_dir = output_root / sanitize_filename(course_meta['name'])
        total_links += len(links)
        downloaded = 0
        errors = 0

        print(f"[course] [{course_id}] {course_meta['name']} :: {len(links)} new link(s) since {since.isoformat()}")

        for item in links:
            if args.dry_run:
                print(f"  [{item['source_type']}] {item['source_title']} -> {item['download_url']}")
                continue
            try:
                data, headers, final_url = client.download_binary(item['download_url'])
                fallback = sanitize_filename(item['source_title'] or 'file')
                file_name = choose_filename(headers, final_url, fallback)
                course_dir.mkdir(parents=True, exist_ok=True)
                dest = unique_path(course_dir, file_name)
                dest.write_bytes(data)
                downloaded += 1
                print(f"[saved] {course_meta['name']} :: {dest.name}")
            except Exception as exc:
                errors += 1
                print(f"[error] {course_meta['name']} :: {item['source_title']} :: {exc}", file=sys.stderr)

        total_downloaded += downloaded
        total_errors += errors
        summary_courses.append({
            'id': course_id,
            'name': course_meta['name'],
            'term': course_meta['term'],
            'new_links': len(links),
            'downloaded': downloaded,
            'errors': errors,
        })

    result = {
        'since': since.isoformat(),
        'output_root': str(output_root),
        'course_count': len(args.course_ids),
        'total_new_links': total_links,
        'total_downloaded': total_downloaded,
        'total_errors': total_errors,
        'courses': summary_courses,
    }

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"since={since.isoformat()} courses={len(args.course_ids)} links={total_links} downloaded={total_downloaded} errors={total_errors}")
        for c in summary_courses:
            print(f"  [{c['id']}] {c['name']} :: links={c['new_links']} downloaded={c['downloaded']} errors={c['errors']}")

    # Write last_update_at back to config
    if args.config and not args.dry_run:
        try:
            now_china = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%dT%H:%M:%S+08:00')
            full_cfg = load_config(args.config)
            full_cfg['last_update_at'] = now_china
            with open(args.config, 'w', encoding='utf-8') as f:
                json.dump(full_cfg, f, ensure_ascii=False, indent=2)
            if not args.json:
                print(f'[config] last_update_at updated to {now_china}')
        except Exception as exc:
            print(f'[warn] failed to write last_update_at to config: {exc}', file=sys.stderr)

    return 0 if not total_errors else 1


if __name__ == '__main__':
    raise SystemExit(main())

