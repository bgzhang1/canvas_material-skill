#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
import html
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

DEFAULT_URL = 'https://canvas.example.edu'
DEFAULT_CONFIG = r'.\\canvas_materials\\_canvas_material_sync_config.json'
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
                'User-Agent': 'canvas-material-skill/download-course-links',
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
        return None

    def download_binary(self, url: str) -> Tuple[bytes, Dict[str, str], str]:
        return self._request(url, binary=True)


def load_config(path: str) -> Dict[str, Any]:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {}


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
        if 'pdf' in ctype:
            ext = '.pdf'
        elif 'word' in ctype:
            ext = '.docx'
        elif 'powerpoint' in ctype or 'presentationml' in ctype:
            ext = '.pptx'
        elif 'html' in ctype:
            ext = '.html'
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


def add_html_candidates(client: CanvasClient, out: List[Dict[str, Any]], *, source_type: str, source_id: str, source_title: str, html_body: str) -> None:
    context = strip_html(html_body)
    for href in FILE_LINK_RE.findall(html_body or ''):
        real = client.resolve_canvas_file_link(href)
        if not real:
            continue
        out.append({
            'source_type': source_type,
            'source_id': source_id,
            'source_title': source_title,
            'download_url': real,
            'context_text': context,
        })


def collect_course_links(client: CanvasClient, course_id: int) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    course_info, _, _ = client.api_json(f'/courses/{course_id}?include[]=term&include[]=syllabus_body')
    links: List[Dict[str, Any]] = []

    files = client.paged(f'/courses/{course_id}/files?per_page=100')
    for item in files:
        if item.get('url'):
            links.append({
                'source_type': 'file',
                'source_id': str(item.get('id') or ''),
                'source_title': item.get('display_name') or item.get('filename') or 'file',
                'download_url': item['url'],
                'context_text': f"course file {item.get('display_name') or item.get('filename') or ''}",
            })

    announcements = client.paged(f'/announcements?context_codes[]=course_{course_id}&per_page=100')
    for item in announcements:
        add_html_candidates(client, links, source_type='announcement', source_id=str(item.get('id') or ''), source_title=item.get('title') or 'announcement', html_body=item.get('message') or '')

    assignments = client.paged(f'/courses/{course_id}/assignments?per_page=100')
    for item in assignments:
        add_html_candidates(client, links, source_type='assignment', source_id=str(item.get('id') or ''), source_title=item.get('name') or 'assignment', html_body=item.get('description') or '')

    add_html_candidates(client, links, source_type='syllabus', source_id=str(course_id), source_title='syllabus', html_body=course_info.get('syllabus_body') or '')

    try:
        front, _, _ = client.api_json(f'/courses/{course_id}/front_page')
        add_html_candidates(client, links, source_type='front_page', source_id=str(front.get('page_id') or 'front'), source_title=front.get('title') or 'front_page', html_body=front.get('body') or '')
    except Exception:
        pass

    try:
        pages = client.paged(f'/courses/{course_id}/pages?per_page=100')
        for page in pages:
            try:
                detail, _, _ = client.api_json(f"/courses/{course_id}/pages/{page.get('url')}")
            except Exception:
                continue
            add_html_candidates(client, links, source_type='page', source_id=str(detail.get('page_id') or page.get('url') or ''), source_title=detail.get('title') or 'page', html_body=detail.get('body') or '')
    except Exception:
        pass

    try:
        discussions = client.paged(f'/courses/{course_id}/discussion_topics?per_page=100')
        for item in discussions:
            add_html_candidates(client, links, source_type='discussion', source_id=str(item.get('id') or ''), source_title=item.get('title') or 'discussion', html_body=item.get('message') or '')
    except Exception:
        pass

    try:
        modules = client.paged(f'/courses/{course_id}/modules?include[]=items&per_page=100')
        for module in modules:
            module_name = module.get('name') or 'module'
            for item in module.get('items') or []:
                title = item.get('title') or module_name
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
                            'context_text': f'{module_name} {title}',
                        })
    except Exception:
        pass

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
    parser = argparse.ArgumentParser(description='Download all discoverable course file links into output_root/course_name/')
    parser.add_argument('course_id', type=int, help='Canvas course id')
    parser.add_argument('--canvas-url', default=None, help='Canvas base URL')
    parser.add_argument('--canvas-token', default=None, help='Canvas API token')
    parser.add_argument('--config', default=DEFAULT_CONFIG, help='Config JSON path')
    parser.add_argument('--output-root', default=None, help='Output root directory')
    parser.add_argument('--dry-run', action='store_true', help='Only print discovered links, do not download')
    parser.add_argument('--json', action='store_true', help='Print JSON summary')
    args = parser.parse_args()

    cfg = load_config(args.config) if args.config else {}
    base_url = args.canvas_url or os.environ.get('CANVAS_URL') or cfg.get('canvas_url') or DEFAULT_URL
    token = args.canvas_token or os.environ.get('CANVAS_TOKEN') or cfg.get('canvas_token')
    output_root = Path(args.output_root or cfg.get('output_root') or Path.cwd()).expanduser().resolve()

    if not token:
        print('Error: missing Canvas token. Provide --canvas-token, CANVAS_TOKEN, or a config containing canvas_token.', file=sys.stderr)
        return 1

    client = CanvasClient(base_url, token)
    course_meta, links = collect_course_links(client, args.course_id)
    course_dir = output_root / sanitize_filename(course_meta['name'])
    manifest_path = course_dir / '_download_links.json'

    if args.dry_run:
        if args.json:
            print(json.dumps({'course': course_meta, 'link_count': len(links), 'links': links}, ensure_ascii=False, indent=2))
        else:
            print(f"course_id\tterm\tname\tlink_count")
            print(f"{course_meta['id']}\t{course_meta['term']}\t{course_meta['name']}\t{len(links)}")
            print('source_type\tsource_title\tdownload_url')
            for item in links:
                print(f"{item['source_type']}\t{item['source_title']}\t{item['download_url']}")
        return 0

    course_dir.mkdir(parents=True, exist_ok=True)
    downloads = []
    errors = []
    for item in links:
        try:
            data, headers, final_url = client.download_binary(item['download_url'])
            file_name = choose_filename(headers, final_url, sanitize_filename(item['source_title'] or 'file'))
            dest = unique_path(course_dir, file_name)
            dest.write_bytes(data)
            downloads.append({
                **item,
                'saved_path': str(dest),
                'final_url': final_url,
                'content_type': headers.get('Content-Type', ''),
            })
            print(f"[saved] {course_meta['name']} :: {dest.name}")
        except Exception as exc:
            errors.append({
                **item,
                'error': str(exc),
            })
            print(f"[error] {course_meta['name']} :: {item['source_title']} :: {exc}", file=sys.stderr)

    manifest = {
        'course': course_meta,
        'output_root': str(output_root),
        'course_dir': str(course_dir),
        'link_count': len(links),
        'downloaded_count': len(downloads),
        'error_count': len(errors),
        'downloads': downloads,
        'errors': errors,
    }
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')

    if args.json:
        print(json.dumps({'course': course_meta, 'course_dir': str(course_dir), 'link_count': len(links), 'downloaded_count': len(downloads), 'error_count': len(errors), 'manifest_path': str(manifest_path)}, ensure_ascii=False, indent=2))
    else:
        print(f"course_id\tterm\tname\tlink_count\tdownloaded_count\terror_count\tcourse_dir")
        print(f"{course_meta['id']}\t{course_meta['term']}\t{course_meta['name']}\t{len(links)}\t{len(downloads)}\t{len(errors)}\t{course_dir}")
        print(f"manifest\t{manifest_path}")
    return 0 if not errors else 1


if __name__ == '__main__':
    raise SystemExit(main())

