from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .constants import DOC_EXTS, IGNORE_EXTS, IGNORE_RE, LECTURE_RE, TUTORIAL_RE
from .prompts import category_mapping
from .utils import strip_html


def io_bytes(data: bytes):
    import io
    return io.BytesIO(data)


class OpenAIClassifier:
    def __init__(self, api_key: str, model: str = "gpt-5-mini"):
        self.api_key = api_key
        self.model = model

    def classify(self, *, filename: str, source_type: str, source_title: str, context_text: str, extracted_text: str, categories: List[str]) -> Optional[Dict[str, str]]:
        payload = {
            "filename": filename,
            "source_type": source_type,
            "source_title": source_title,
            "context_text": context_text[:2000],
            "extracted_text": extracted_text[:4000],
            "allowed_categories": categories + ["ignore"],
            "task": "Choose the best category for this Canvas material. Prefer tutorial-like categories for tutorial sheets, labs, exercises, homework sheets, and assignment questions. Prefer lecture-like categories for lecture slides and chapter notes. Return JSON only.",
        }
        schema = {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "category": {"type": "string", "enum": categories + ["ignore"]},
                "reason": {"type": "string"},
            },
            "required": ["category", "reason"],
        }
        body = {
            "model": self.model,
            "input": [
                {"role": "system", "content": [{"type": "text", "text": "You classify educational materials. Output JSON only."}]},
                {"role": "user", "content": [{"type": "text", "text": json.dumps(payload, ensure_ascii=False)}]},
            ],
            "text": {"format": {"type": "json_schema", "name": "canvas_material_class", "schema": schema}},
        }
        req = urllib.request.Request(
            "https://api.openai.com/v1/responses",
            headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            text = data.get("output_text") or ""
            if text:
                parsed = json.loads(text)
                if parsed.get("category") in set(categories + ["ignore"]):
                    return parsed
        except Exception:
            return None
        return None


class MaterialClassifier:
    def __init__(self, categories: List[str], ai: Optional[OpenAIClassifier] = None, rules: Optional[List[Dict[str, Any]]] = None):
        self.categories = categories
        self.ai = ai
        self.rules = rules or []
        self.lecture_category, self.tutorial_category = category_mapping(categories)

    def _match_rule(self, *, course_name: str, filename: str, source_type: str, source_title: str, context_text: str) -> Optional[Tuple[str, str]]:
        for rule in self.rules:
            category = rule.get("category")
            if category not in set(self.categories + ["ignore"]):
                continue
            course_pat = rule.get("course_name_regex")
            file_pat = rule.get("filename_regex")
            title_pat = rule.get("source_title_regex")
            source_kind = rule.get("source_type")
            context_pat = rule.get("context_regex")
            if course_pat and not re.search(course_pat, course_name, re.I):
                continue
            if file_pat and not re.search(file_pat, filename, re.I):
                continue
            if title_pat and not re.search(title_pat, source_title, re.I):
                continue
            if source_kind and source_kind != source_type:
                continue
            if context_pat and not re.search(context_pat, context_text, re.I):
                continue
            return category, f"rule: {rule.get('reason', 'matched custom override')}"
        return None

    def classify(self, *, course_name: str, filename: str, source_type: str, source_title: str, context_text: str, extracted_text: str) -> Tuple[str, str]:
        combined = " ".join([filename, source_type, source_title, context_text[:1500], extracted_text[:2000]])
        lecture_score = 0
        tutorial_score = 0
        ext = Path(filename).suffix.lower()
        rule_hit = self._match_rule(course_name=course_name, filename=filename, source_type=source_type, source_title=source_title, context_text=context_text)
        if rule_hit:
            return rule_hit
        if IGNORE_RE.search(combined) or ext in IGNORE_EXTS:
            return "ignore", "matched ignore heuristic"
        if ext and ext not in DOC_EXTS and ext not in IGNORE_EXTS:
            return "ignore", f"unsupported/non-document extension {ext}"
        if TUTORIAL_RE.search(filename):
            tutorial_score += 5
        if LECTURE_RE.search(filename):
            lecture_score += 5
        if source_type == "assignment":
            tutorial_score += 4
        if TUTORIAL_RE.search(source_title):
            tutorial_score += 4
        if LECTURE_RE.search(source_title):
            lecture_score += 4
        if TUTORIAL_RE.search(context_text):
            tutorial_score += 3
        if LECTURE_RE.search(context_text):
            lecture_score += 3
        if TUTORIAL_RE.search(extracted_text):
            tutorial_score += 2
        if LECTURE_RE.search(extracted_text):
            lecture_score += 2
        if self.ai:
            result = self.ai.classify(
                filename=filename,
                source_type=source_type,
                source_title=source_title,
                context_text=context_text,
                extracted_text=extracted_text,
                categories=self.categories,
            )
            if result:
                return result["category"], f"ai: {result.get('reason', '')}"
        if tutorial_score > lecture_score:
            return self.tutorial_category, f"heuristic tutorial>{lecture_score}:{tutorial_score}"
        if lecture_score > tutorial_score:
            return self.lecture_category, f"heuristic lecture>{lecture_score}:{tutorial_score}"
        if source_type == "assignment":
            return self.tutorial_category, "assignment default fallback"
        return self.lecture_category, "default fallback"


def extract_openxml_text(data: bytes, target: str) -> str:
    try:
        with zipfile.ZipFile(io_bytes(data)) as zf:
            raw = zf.read(target).decode("utf-8", errors="replace")
        return strip_html(raw)[:8000]
    except Exception:
        return ""


def extract_pptx_text(data: bytes) -> str:
    try:
        texts: List[str] = []
        with zipfile.ZipFile(io_bytes(data)) as zf:
            for name in sorted(zf.namelist()):
                if name.startswith("ppt/slides/slide") and name.endswith(".xml"):
                    raw = zf.read(name).decode("utf-8", errors="replace")
                    texts.append(strip_html(raw))
        return " ".join(texts)[:8000]
    except Exception:
        return ""


def extract_pdf_text_light(data: bytes) -> str:
    try:
        raw = data.decode("latin-1", errors="ignore")
        parts = re.findall(r"\(([^\)]{3,200})\)", raw)
        text = " ".join(parts)
        text = re.sub(r"\\[nrt]", " ", text)
        text = re.sub(r"\\\d{3}", " ", text)
        return re.sub(r"\s+", " ", text)[:4000]
    except Exception:
        return ""


def extract_text_from_bytes(data: bytes, filename: str, content_type: str = "") -> str:
    ext = Path(filename).suffix.lower()
    if ext in {".txt", ".md", ".html", ".htm", ".csv", ".json", ".py", ".ipynb", ".yaml", ".yml", ".xml"}:
        return data.decode("utf-8", errors="replace")[:8000]
    if ext == ".docx":
        return extract_openxml_text(data, "word/document.xml")
    if ext in {".pptx", ".ppsx"}:
        return extract_pptx_text(data)
    if ext == ".pdf":
        return extract_pdf_text_light(data)
    return ""


def convert_ipynb_to_pdf(src: Path, pdf_path: Path) -> Tuple[bool, str]:
    if not shutil.which("jupyter"):
        return False, "jupyter not found"
    cmd = ["jupyter", "nbconvert", "--to", "webpdf", "--output", pdf_path.stem, str(src)]
    try:
        proc = subprocess.run(cmd, cwd=str(src.parent), capture_output=True, text=True, timeout=180)
        if proc.returncode == 0 and pdf_path.exists():
            return True, "converted with jupyter nbconvert"
        return False, (proc.stderr or proc.stdout or "nbconvert failed").strip()[:300]
    except Exception as exc:
        return False, str(exc)


def convert_via_powershell_office(src: Path, pdf_path: Path, mode: str) -> Tuple[bool, str]:
    if os.name != "nt":
        return False, "office com conversion only implemented on Windows"
    powershell = shutil.which("powershell") or shutil.which("pwsh")
    if not powershell:
        return False, "powershell not found"
    if mode == "word":
        script = f"""
$ErrorActionPreference='Stop'
$word = New-Object -ComObject Word.Application
$word.Visible = $false
$word.DisplayAlerts = 0
try {{
  $doc = $word.Documents.Open('{str(src).replace("'", "''")}', $false, $true)
  $doc.SaveAs([ref]'{str(pdf_path).replace("'", "''")}', [ref]17)
  $doc.Close()
}} finally {{
  try {{ $word.Quit() }} catch {{}}
}}
"""
        kill_names = ["WINWORD"]
    else:
        script = f"""
$ErrorActionPreference='Stop'
$ppt = New-Object -ComObject PowerPoint.Application
$ppt.Visible = -1
try {{
  $pres = $ppt.Presentations.Open('{str(src).replace("'", "''")}', $true, $false, $false)
  $pres.SaveAs('{str(pdf_path).replace("'", "''")}', 32)
  $pres.Close()
}} finally {{
  try {{ $ppt.Quit() }} catch {{}}
}}
"""
        kill_names = ["POWERPNT"]
    fd, tmp_path = tempfile.mkstemp(suffix=".ps1")
    os.close(fd)
    Path(tmp_path).write_text(script, encoding="utf-8")
    try:
        proc = subprocess.Popen([powershell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", tmp_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            out, err = proc.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            proc.kill()
            for name in kill_names:
                subprocess.run(["taskkill", "/F", "/IM", f"{name}.EXE"], capture_output=True)
            return False, "office conversion timeout"
        if proc.returncode == 0 and pdf_path.exists() and pdf_path.stat().st_size > 0:
            return True, "converted via office com"
        return False, ((err or out) or "office conversion failed").strip()[:300]
    except Exception as exc:
        return False, str(exc)
    finally:
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except Exception:
            pass


def ensure_pdf(path: Path, *, keep_original: bool) -> Tuple[Optional[Path], str]:
    ext = path.suffix.lower()
    if ext == ".pdf":
        return path, "already pdf"
    pdf_path = path.with_suffix(".pdf")
    if pdf_path.exists() and pdf_path.stat().st_size > 0:
        if not keep_original and path.exists():
            try:
                path.unlink()
            except Exception:
                pass
        return pdf_path, "pdf already exists"
    if ext in {".doc", ".docx"}:
        ok, reason = convert_via_powershell_office(path, pdf_path, "word")
    elif ext in {".ppt", ".pptx", ".pps", ".ppsx"}:
        ok, reason = convert_via_powershell_office(path, pdf_path, "powerpoint")
    elif ext == ".ipynb":
        ok, reason = convert_ipynb_to_pdf(path, pdf_path)
    else:
        return None, f"no converter for {ext}"
    if ok and pdf_path.exists() and pdf_path.stat().st_size > 0:
        if not keep_original:
            try:
                path.unlink()
            except Exception:
                pass
        return pdf_path, reason
    return None, reason
