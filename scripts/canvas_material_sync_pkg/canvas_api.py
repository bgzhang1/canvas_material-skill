from __future__ import annotations

import html
import json
import re
import sys
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .common import FILE_LINK_RE, parse_dt, sanitize_filename, strip_html


class CanvasClient:
    def __init__(self, base_url: str, token: str, verbose: bool = False):
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.verbose = verbose

    def _request(self, url: str, *, binary: bool = False) -> Tuple[Any, Dict[str, str], str]:
        req = urllib.request.Request(url, headers={"Authorization": f"Bearer {self.token}", "User-Agent": "canvas-material-sync/2.0"})
        with urllib.request.urlopen(req, timeout=90) as resp:
            final_url = resp.geturl()
            headers = {k: v for k, v in resp.headers.items()}
            body = resp.read()
        if binary:
            return body, headers, final_url
        return body.decode("utf-8", errors="replace"), headers, final_url

    def api_json(self, endpoint_or_url: str) -> Tuple[Any, Dict[str, str], str]:
        url = endpoint_or_url if endpoint_or_url.startswith("http") else f"{self.base_url}/api/v1{endpoint_or_url}"
        text, headers, final = self._request(url)
        return json.loads(text), headers, final

    def paged(self, endpoint_or_url: str) -> List[Dict[str, Any]]:
        url = endpoint_or_url if endpoint_or_url.startswith("http") else f"{self.base_url}/api/v1{endpoint_or_url}"
        out: List[Dict[str, Any]] = []
        while url:
            data, headers, _ = self.api_json(url)
            if isinstance(data, list):
                out.extend(data)
                url = self._next_link(headers.get("Link"))
            else:
                return [data]
        return out

    @staticmethod
    def _next_link(link_header: Optional[str]) -> Optional[str]:
        if not link_header:
            return None
        for part in link_header.split(","):
            match = re.search(r'<([^>]+)>;\s*rel="next"', part)
            if match:
                return match.group(1)
        return None

    def fetch_courses(self, ids: Optional[List[int]] = None) -> List[Dict[str, Any]]:
        courses = self.paged("/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades")
        if ids:
            wanted = set(ids)
            courses = [course for course in courses if course.get("id") in wanted]
        return courses

    def resolve_canvas_file_link(self, href: str) -> Optional[str]:
        if not href:
            return None
        href = html.unescape(href)
        if href.startswith("/"):
            href = self.base_url + href
        if "/download" in href and href.startswith("http"):
            return href
        if "/files/" in href:
            try:
                page, _, _ = self._request(href)
            except Exception:
                page = ""
            if page:
                for link in FILE_LINK_RE.findall(page):
                    link = html.unescape(link)
                    if link.startswith("/"):
                        link = self.base_url + link
                    if "/download" in link:
                        return link
            if "?verifier=" in href:
                return href.replace("?verifier=", "/download?verifier=").replace("&wrap=1", "")
        return None

    def download_binary(self, url: str) -> Tuple[bytes, Dict[str, str], str]:
        return self._request(url, binary=True)


@dataclass
class Candidate:
    course_id: int
    course_name: str
    source_type: str
    source_id: str
    source_title: str
    source_updated_at: Optional[str]
    file_url: str
    context_text: str


def file_maybe_new(modified_at: Optional[str], baseline) -> bool:
    if baseline is None:
        return True
    item_dt = parse_dt(modified_at)
    if item_dt is None:
        return True
    return item_dt >= baseline


def choose_filename(headers: Dict[str, str], final_url: str, fallback: str) -> str:
    dispo = headers.get("Content-Disposition", "")
    match = re.search(r"filename\*?=(?:UTF-8''|\"?)([^\";]+)", dispo, re.I)
    if match:
        return sanitize_filename(urllib.parse.unquote(match.group(1)))
    path_name = Path(urllib.parse.urlparse(final_url).path).name
    if path_name and "." in path_name:
        return sanitize_filename(urllib.parse.unquote(path_name))
    ctype = headers.get("Content-Type", "").lower()
    ext = Path(fallback).suffix
    if not ext:
        if "pdf" in ctype:
            ext = ".pdf"
        elif "word" in ctype:
            ext = ".docx"
        elif "powerpoint" in ctype or "presentationml" in ctype:
            ext = ".pptx"
        elif "ipynb" in ctype or "json" in ctype:
            ext = ".ipynb"
    return sanitize_filename(fallback + ext)


def add_html_link_candidates(
    client: CanvasClient,
    candidates: List[Candidate],
    *,
    course_id: int,
    course_name: str,
    source_type: str,
    source_id: str,
    source_title: str,
    source_updated_at: Optional[str],
    html_body: str,
) -> None:
    context = strip_html(html_body)
    for href in FILE_LINK_RE.findall(html_body or ""):
        real = client.resolve_canvas_file_link(href)
        if not real:
            continue
        candidates.append(Candidate(course_id, course_name, source_type, source_id, source_title, source_updated_at, real, context))


def collect_candidates(client: CanvasClient, course: Dict[str, Any], baseline, verbose: bool = False) -> List[Candidate]:
    cid = course["id"]
    cname = course.get("name") or course.get("course_code") or str(cid)
    candidates: List[Candidate] = []
    try:
        files = client.paged(f"/courses/{cid}/files?per_page=100")
        for file_info in files:
            modified = file_info.get("modified_at") or file_info.get("updated_at") or file_info.get("created_at")
            if not file_maybe_new(modified, baseline):
                continue
            url = file_info.get("url")
            if url:
                candidates.append(Candidate(cid, cname, "file", str(file_info.get("id")), file_info.get("display_name") or file_info.get("filename") or "file", modified, url, f"course file {file_info.get('display_name', '')} {file_info.get('content-type', '')}"))
    except Exception as exc:
        if verbose:
            print(f"[warn] files scan failed for {cid}: {exc}", file=sys.stderr)
    try:
        announcements = client.paged(f"/announcements?context_codes[]=course_{cid}&per_page=100")
        for item in announcements:
            modified = item.get("updated_at") or item.get("posted_at") or item.get("created_at")
            if not file_maybe_new(modified, baseline):
                continue
            add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="announcement", source_id=str(item.get("id")), source_title=item.get("title") or "announcement", source_updated_at=modified, html_body=item.get("message") or "")
    except Exception as exc:
        if verbose:
            print(f"[warn] announcements scan failed for {cid}: {exc}", file=sys.stderr)
    try:
        assignments = client.paged(f"/courses/{cid}/assignments?per_page=100")
        for item in assignments:
            modified = item.get("updated_at") or item.get("created_at") or item.get("due_at")
            if not file_maybe_new(modified, baseline):
                continue
            add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="assignment", source_id=str(item.get("id")), source_title=item.get("name") or "assignment", source_updated_at=modified, html_body=item.get("description") or "")
    except Exception as exc:
        if verbose:
            print(f"[warn] assignments scan failed for {cid}: {exc}", file=sys.stderr)
    try:
        course_info, _, _ = client.api_json(f"/courses/{cid}?include[]=syllabus_body")
        add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="syllabus", source_id=str(cid), source_title="syllabus", source_updated_at=course_info.get("updated_at"), html_body=course_info.get("syllabus_body") or "")
    except Exception as exc:
        if verbose:
            print(f"[warn] syllabus scan failed for {cid}: {exc}", file=sys.stderr)
    try:
        front, _, _ = client.api_json(f"/courses/{cid}/front_page")
        add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="front_page", source_id=str(front.get("page_id") or "front"), source_title=front.get("title") or "front_page", source_updated_at=front.get("updated_at") or front.get("created_at"), html_body=front.get("body") or "")
    except Exception:
        pass
    try:
        pages = client.paged(f"/courses/{cid}/pages?per_page=100")
        for page in pages:
            try:
                detail, _, _ = client.api_json(f"/courses/{cid}/pages/{page.get('url')}")
            except Exception:
                continue
            modified = detail.get("updated_at") or detail.get("edited_at") or detail.get("created_at")
            if not file_maybe_new(modified, baseline):
                continue
            add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="page", source_id=str(detail.get("page_id") or page.get("url")), source_title=detail.get("title") or "page", source_updated_at=modified, html_body=detail.get("body") or "")
    except Exception:
        pass
    try:
        topics = client.paged(f"/courses/{cid}/discussion_topics?per_page=100")
        for topic in topics:
            modified = topic.get("updated_at") or topic.get("posted_at") or topic.get("created_at")
            if not file_maybe_new(modified, baseline):
                continue
            add_html_link_candidates(client, candidates, course_id=cid, course_name=cname, source_type="discussion", source_id=str(topic.get("id")), source_title=topic.get("title") or "discussion", source_updated_at=modified, html_body=topic.get("message") or "")
    except Exception:
        pass
    try:
        modules = client.paged(f"/courses/{cid}/modules?include[]=items&per_page=100")
        for module in modules:
            module_name = module.get("name") or "module"
            for item in module.get("items") or []:
                modified = item.get("updated_at") or item.get("created_at")
                if not file_maybe_new(modified, baseline):
                    continue
                for href in [item.get("external_url"), item.get("html_url"), item.get("url")]:
                    if not href:
                        continue
                    real = client.resolve_canvas_file_link(href)
                    if real:
                        candidates.append(Candidate(cid, cname, "module_item", str(item.get("id") or item.get("content_id") or href), item.get("title") or module_name, modified, real, f"{module_name} {item.get('title', '')}"))
    except Exception:
        pass
    dedup: Dict[Tuple[int, str], Candidate] = {}
    for candidate in candidates:
        dedup[(candidate.course_id, candidate.file_url)] = candidate
    return list(dedup.values())
