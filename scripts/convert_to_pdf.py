#!/usr/bin/env python3
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

WORD_EXTS = {'.doc', '.docx', '.rtf', '.odt'}
POWERPOINT_EXTS = {'.ppt', '.pptx', '.pps', '.ppsx', '.odp'}
EXCEL_EXTS = {'.xls', '.xlsx', '.xlsm', '.xlsb', '.ods', '.csv'}
SUPPORTED_EXTS = WORD_EXTS | POWERPOINT_EXTS | EXCEL_EXTS


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description='Convert Office files such as docx/pptx/xlsx to PDF.'
    )
    parser.add_argument('input_path', help='Input file or directory')
    parser.add_argument('--output-dir', help='Output directory; defaults to alongside input file(s)')
    parser.add_argument('--recursive', action='store_true', help='Recursively scan input directory')
    parser.add_argument('--backend', choices=['auto', 'office', 'libreoffice'], default='auto', help='Conversion backend')
    parser.add_argument('--overwrite', action='store_true', help='Overwrite existing PDF files')
    parser.add_argument('--json', action='store_true', help='Print JSON summary')
    return parser


def find_soffice() -> Optional[str]:
    candidates = [
        shutil.which('soffice'),
        shutil.which('libreoffice'),
        r'C:\Program Files\LibreOffice\program\soffice.exe',
        r'C:\Program Files (x86)\LibreOffice\program\soffice.exe',
    ]
    for path in candidates:
        if path and Path(path).exists():
            return str(Path(path))
    return None


def office_app_for_suffix(suffix: str) -> str:
    suffix = suffix.lower()
    if suffix in WORD_EXTS:
        return 'word'
    if suffix in POWERPOINT_EXTS:
        return 'powerpoint'
    if suffix in EXCEL_EXTS:
        return 'excel'
    raise ValueError(f'Unsupported suffix: {suffix}')


def office_ps_script() -> str:
    return r'''
param(
  [Parameter(Mandatory=$true)][string]$App,
  [Parameter(Mandatory=$true)][string]$InFile,
  [Parameter(Mandatory=$true)][string]$OutFile
)

$ErrorActionPreference = 'Stop'

function Release-ComObject($obj) {
  if ($null -ne $obj) {
    try { [void][System.Runtime.InteropServices.Marshal]::FinalReleaseComObject($obj) } catch {}
  }
}

$InFile = (Resolve-Path -LiteralPath $InFile).Path
$OutDir = Split-Path -Parent $OutFile
if (-not (Test-Path -LiteralPath $OutDir)) {
  New-Item -ItemType Directory -Path $OutDir -Force | Out-Null
}

switch ($App.ToLowerInvariant()) {
  'word' {
    $word = $null
    $doc = $null
    try {
      $word = New-Object -ComObject Word.Application
      $word.Visible = $false
      $word.DisplayAlerts = 0
      $doc = $word.Documents.Open($InFile, $false, $true)
      $doc.ExportAsFixedFormat($OutFile, 17)
    }
    finally {
      if ($doc) { try { $doc.Close($false) } catch {} }
      if ($word) { try { $word.Quit() } catch {} }
      Release-ComObject $doc
      Release-ComObject $word
      [GC]::Collect()
      [GC]::WaitForPendingFinalizers()
    }
  }
  'powerpoint' {
    $ppt = $null
    $pres = $null
    try {
      $ppt = New-Object -ComObject PowerPoint.Application
      $pres = $ppt.Presentations.Open($InFile, $true, $false, $false)
      $pres.SaveAs($OutFile, 32)
    }
    finally {
      if ($pres) { try { $pres.Close() } catch {} }
      if ($ppt) { try { $ppt.Quit() } catch {} }
      Release-ComObject $pres
      Release-ComObject $ppt
      [GC]::Collect()
      [GC]::WaitForPendingFinalizers()
    }
  }
  'excel' {
    $excel = $null
    $wb = $null
    try {
      $excel = New-Object -ComObject Excel.Application
      $excel.Visible = $false
      $excel.DisplayAlerts = $false
      $wb = $excel.Workbooks.Open($InFile)
      $wb.ExportAsFixedFormat(0, $OutFile)
    }
    finally {
      if ($wb) { try { $wb.Close($false) } catch {} }
      if ($excel) { try { $excel.Quit() } catch {} }
      Release-ComObject $wb
      Release-ComObject $excel
      [GC]::Collect()
      [GC]::WaitForPendingFinalizers()
    }
  }
  default {
    throw "Unsupported Office app: $App"
  }
}
'''


def run_office_conversion(input_file: Path, output_file: Path) -> None:
    if os.name != 'nt':
        raise RuntimeError('Office COM conversion is only supported on Windows.')
    app = office_app_for_suffix(input_file.suffix)
    ps = office_ps_script()
    with tempfile.NamedTemporaryFile('w', suffix='.ps1', delete=False, encoding='utf-8') as f:
        f.write(ps)
        ps_path = f.name
    try:
        result = subprocess.run(
            [
                'powershell.exe',
                '-NoProfile',
                '-ExecutionPolicy', 'Bypass',
                '-File', ps_path,
                '-App', app,
                '-InFile', str(input_file),
                '-OutFile', str(output_file),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise RuntimeError((result.stderr or result.stdout or 'Office conversion failed').strip())
    finally:
        try:
            Path(ps_path).unlink(missing_ok=True)
        except Exception:
            pass



def run_libreoffice_conversion(input_file: Path, output_dir: Path, soffice_path: Optional[str] = None) -> Path:
    soffice = soffice_path or find_soffice()
    if not soffice:
        raise RuntimeError('LibreOffice/soffice not found.')
    output_dir.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            soffice,
            '--headless',
            '--convert-to', 'pdf',
            '--outdir', str(output_dir),
            str(input_file),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError((result.stderr or result.stdout or 'LibreOffice conversion failed').strip())
    pdf_path = output_dir / (input_file.stem + '.pdf')
    if not pdf_path.exists():
        raise RuntimeError('Conversion finished but PDF output was not found.')
    return pdf_path



def convert_one(input_file: Path, output_file: Path, backend: str) -> str:
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if backend in ('auto', 'office'):
        try:
            run_office_conversion(input_file, output_file)
            return 'office'
        except Exception:
            if backend == 'office':
                raise
    if backend in ('auto', 'libreoffice'):
        temp_pdf = run_libreoffice_conversion(input_file, output_file.parent)
        if temp_pdf.resolve() != output_file.resolve():
            if output_file.exists():
                output_file.unlink()
            temp_pdf.replace(output_file)
        return 'libreoffice'
    raise RuntimeError('No available backend succeeded.')



def collect_inputs(input_path: Path, recursive: bool) -> List[Path]:
    if input_path.is_file():
        return [input_path] if input_path.suffix.lower() in SUPPORTED_EXTS else []
    if input_path.is_dir():
        iterator = input_path.rglob('*') if recursive else input_path.glob('*')
        return sorted([p for p in iterator if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS])
    return []



def default_output_for(input_file: Path, input_root: Path, output_dir: Optional[Path]) -> Path:
    if output_dir is None:
        return input_file.with_suffix('.pdf')
    if input_root.is_dir():
        rel = input_file.relative_to(input_root)
        return output_dir / rel.with_suffix('.pdf')
    return output_dir / (input_file.stem + '.pdf')



def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    input_path = Path(args.input_path).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve() if args.output_dir else None

    files = collect_inputs(input_path, args.recursive)
    if not files:
        print('Error: no supported input files found.', file=sys.stderr)
        return 1

    summary: Dict[str, List[Dict[str, str]]] = {'converted': [], 'skipped': [], 'errors': []}

    for f in files:
        out = default_output_for(f, input_path, output_dir)
        if out.exists() and not args.overwrite:
            summary['skipped'].append({'input': str(f), 'output': str(out), 'reason': 'exists'})
            continue
        try:
            backend_used = convert_one(f, out, args.backend)
            summary['converted'].append({'input': str(f), 'output': str(out), 'backend': backend_used})
            print(f'[converted] {f} -> {out} ({backend_used})')
        except Exception as exc:
            summary['errors'].append({'input': str(f), 'output': str(out), 'error': str(exc)})
            print(f'[error] {f} :: {exc}', file=sys.stderr)

    exit_code = 0 if not summary['errors'] else 1
    if args.json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"converted={len(summary['converted'])}\tskipped={len(summary['skipped'])}\terrors={len(summary['errors'])}")
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
