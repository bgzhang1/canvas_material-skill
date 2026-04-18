---
name: canvas_material
description: Ask the user whether to enable PDF conversion, whether to enable scheduled sync, and if enabled whether the sync should run every N minutes or on a daily/weekly schedule with a specific time; also ask which category folders to use; then perform a first full Canvas scan across likely material locations including announcements, assignment bodies, syllabus, pages, discussions, modules, and files; remember that the initial full download has completed; and optionally set up recurring incremental syncs that work across different terminal clients. This skill also includes reusable Canvas REST API calling conventions.
---

# canvas_material

Use this skill when the user wants ongoing Canvas material monitoring and automatic organization via the main skill name `canvas_material`.

## Required questions before first setup

Before running initial setup, always ask the user these questions in plain language:

1. 是否开启 PDF 转换
2. 是否开启定时执行
3. 如果开启定时执行，请直接说明你想怎么定时执行（例如：`每 30 分钟`、`每天 09:00`、`每周一和周三 09:00`）
4. 资料要分成哪些文件夹分类（默认 `lecture` 和 `tutorial`）

Questions 1, 2, and 4 are mandatory for the first setup and must not be skipped.
Question 3 is mandatory when and only when the user enables scheduled execution.
Do not silently infer them and do not silently accept defaults on the user's behalf.
Even if the surrounding client mode prefers making reasonable assumptions, this skill overrides that behavior for these required questions.
You may suggest defaults, but you must still ask and wait for the user's answer before running `setup`.

When the user answers question 3 in natural language, interpret it into one of these internal schedule styles before calling the script:

- `interval`: e.g. `每 30 分钟`
- `daily`: e.g. `每天 09:00`
- `weekly`: e.g. `每周一和周三 09:00`

If the user gives an ambiguous schedule description, ask one short follow-up question only for the missing part.

If output directory or target courses are not already clear from context, make a reasonable default:
- output root: a `canvas_materials` directory in the current working directory
- courses: all currently active Canvas courses visible to the token

## What the bundled script supports

The script has three modes:

- `setup`: interactive initialization, full scan, local memory/state write, and optional scheduler installation
- `run`: full or incremental sync using a saved config
- `install-scheduler`: refresh the recurring task later

Main script:
- `scripts/canvas_material_sync.py`

## Setup flow

Run:

```powershell
python scripts/canvas_material_sync.py setup
```

Or pass values directly:

```powershell
python scripts/canvas_material_sync.py setup \
  --output-root C:/path/to/canvas_materials \
  --course 560 --course 487 \
  --schedule \
  --schedule-type weekly \
  --schedule-time 09:00 \
  --schedule-days mon wed \
  --categories lecture tutorial \
  --pdf-convert \
  --use-ai
```

During setup the script will:

1. collect configuration
2. do an initial **full** scan and download
3. scan these likely source locations:
   - direct course files
   - announcement bodies
   - assignment descriptions / homework bodies
   - syllabus body
   - front page
   - pages
   - discussions
   - modules / module items
4. classify files into the chosen folders
5. remember that first full sync has completed
6. if scheduling is enabled, install a recurring incremental scheduler

Supported schedule styles:

- every N minutes
- daily at a fixed `HH:MM`
- weekly on specific weekdays at a fixed `HH:MM`

## Memory and state

The skill keeps durable memory in:

- skill memory: `memory.json` in the skill root
- skill rules: `rules.json` in the skill root
- per-output config: `<output-root>/_canvas_material_sync_config.json`
- per-output state: `<output-root>/_canvas_material_sync_state.json`
- per-output last update marker: `<output-root>/_canvas_material_sync_last_update.txt`

`memory.json` records that the first full download has already happened.
`rules.json` lets you keep course-specific classification overrides without changing the script.
`_canvas_material_sync_last_update.txt` stores the last completed real sync time directly inside the downloaded materials folder and is refreshed after each non-dry-run sync.

## Scheduling strategy across clients

If scheduling is enabled, the script itself prefers **OS-level scheduling** so it works across different terminal clients and local environments.

Current default backend selection:
- Windows -> Task Scheduler
- Unix-like systems -> cron stub / cron line

### Optional app-native automation note

If the current client supports app-native automation, you may additionally create a recurring run there. The script is still useful because it stores config, memory, and sync state in a portable way.

## Running later

Incremental or automatic mode from an existing config:

```powershell
python scripts/canvas_material_sync.py run --config C:/path/to/_canvas_material_sync_config.json --mode auto
```

`auto` means:
- if first full sync is not complete -> run full sync
- otherwise -> run incremental sync since the last full/incremental update timestamp

## Environment variables

Required:
- `CANVAS_TOKEN`

Optional:
- `CANVAS_URL`

## Canvas API 调用方法

这个 skill 现在统一使用 **Canvas REST API + Bearer Token**。

基础规则：

- Base URL：`<CANVAS_URL>`，默认 `https://canvas.example.edu`
- 所有 API 路径都挂在：`<CANVAS_URL>/api/v1/...`
- 认证头：

```text
Authorization: Bearer <CANVAS_TOKEN>
```

### 最小调用格式

#### PowerShell

```powershell
$headers = @{ Authorization = "Bearer $env:CANVAS_TOKEN" }
Invoke-RestMethod `
  -Headers $headers `
  -Uri "$env:CANVAS_URL/api/v1/users/self" `
  -Method Get
```

#### Python

```python
import json, os, urllib.request

url = f"{os.environ['CANVAS_URL']}/api/v1/users/self"
req = urllib.request.Request(
    url,
    headers={"Authorization": f"Bearer {os.environ['CANVAS_TOKEN']}"},
)
with urllib.request.urlopen(req, timeout=30) as resp:
    data = json.loads(resp.read().decode("utf-8"))
print(data)
```

### 这个 skill 当前实际会调用的接口

脚本 `scripts/canvas_material_sync.py` 目前直接访问这些端点：

- `GET /api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades`
  - 拉当前可见课程
- `GET /api/v1/courses/:course_id/files?per_page=100`
  - 拉课程文件
- `GET /api/v1/announcements?context_codes[]=course_:course_id&per_page=100`
  - 拉公告
- `GET /api/v1/courses/:course_id/assignments?per_page=100`
  - 拉作业描述
- `GET /api/v1/courses/:course_id?include[]=syllabus_body`
  - 拉 syllabus HTML
- `GET /api/v1/courses/:course_id/front_page`
  - 拉 front page
- `GET /api/v1/courses/:course_id/pages?per_page=100`
  - 列出 pages
- `GET /api/v1/courses/:course_id/pages/:page_url`
  - 拉 page 正文
- `GET /api/v1/courses/:course_id/discussion_topics?per_page=100`
  - 拉讨论区帖子
- `GET /api/v1/courses/:course_id/modules?include[]=items&per_page=100`
  - 拉模块及模块项

### 文件下载方式

这个 skill 处理文件下载有两种来源：

1. **直接文件 API**
   - `courses/:id/files` 返回的对象里通常会有 `url`
   - 脚本直接拿这个 URL 下载二进制内容

2. **HTML 正文中的文件链接**
   - 公告、assignment、page、discussion、syllabus 里可能嵌入 `<a href=\"...\">`
   - 脚本会先提取 href
   - 如果是 Canvas 文件页而不是最终下载链接，会进一步解析成 `/download...` 链接后再下载

也就是说，当前脚本不仅扫“文件列表”，还会扫“正文里挂的资料链接”。

### 分页规则

Canvas 列表接口常见分页；这个 skill 的 `CanvasClient.paged(...)` 用法是：

- 请求时尽量带 `per_page=100`
- 读取响应头 `Link`
- 如果有 `rel=\"next\"`，继续抓下一页

如果你后面扩展新接口，也应该沿用这个模式。

### 常用扩展接口

当前同步脚本没直接用到，但如果你要把它继续扩展成“查询型 + 同步型”混合 skill，推荐沿用这些接口：

- `GET /api/v1/users/self`
- `GET /api/v1/users/self/todo`
- `GET /api/v1/conversations`
- `GET /api/v1/courses/:id/assignments/:aid/submissions/self`
- `GET /api/v1/courses/:id/discussion_topics`
- `GET /api/v1/calendar_events`

### 建议的 API 扩展写法

新增接口时建议统一复用当前脚本里的模式：

1. 在 `CanvasClient.api_json()` 里走带认证的 GET
2. 列表接口优先走 `CanvasClient.paged()`
3. 需要下载文件时走 `download_binary()`
4. 需要从正文 HTML 中找文件时，先提取链接，再解析真实下载地址

更完整的接口说明可放在：

- `references/canvas_api_usage.md`

## PDF conversion

If PDF conversion is enabled, the script tries to convert supported files after download.

Currently supported best:
- Windows Office documents via PowerShell COM automation for `docx` / `pptx`
- `ipynb` via `jupyter nbconvert` if available

If conversion fails, the original file is kept.

## Classification behavior

The classifier uses:
1. source context
2. filename/title heuristics
3. extracted text from supported file types
4. optional OpenAI classification when enabled

Prefer tutorial-like folders for:
- tutorials
- labs
- exercises
- homework sheets
- assignment questions

Prefer lecture-like folders for:
- lecture slides
- chapter notes
- topic notes
- week notes
