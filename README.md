# canvas_material-skill

> 主 skill 名：`canvas_material`

一个用于 **Canvas 课程资料同步、分类整理、首次全量下载、后续增量更新、可选定时执行** 的公开 skill / 脚本仓库。

它会扫描 Canvas 中常见的资料来源，并把检测到的课件或附件下载到本地分类文件夹中；如果开启 PDF 转换，还会尽量把常见文档转换为 PDF 版本。

## 主要功能

> **核心目标：把 Canvas 上分散的资料自动收拢到本地，并持续做增量同步。**

- **首次全量扫描**
  - 扫描课程文件、公告、作业正文、syllabus、pages、discussions、modules 等常见资料入口

- **自动分类整理**
  - 按你设置的分类文件夹保存，例如 `lecture`、`tutorial`

- **增量更新**
  - 后续只检查上次同步之后的新动作，避免每次重复全量下载

- **最后更新时间落盘**
  - 每次成功同步后，都会刷新下载目录里的 `_canvas_material_sync_last_update.txt`

- **可选 PDF 转换**
  - 对常见文档尽量生成 PDF，方便统一查看和归档

- **可选定时执行**
  - 支持：
    - **每隔 N 分钟**
    - **每天固定时间**
    - **每周固定星期 + 时间**

- **可接入 AI 分类**
  - 如果存在 `OPENAI_API_KEY`，可启用 AI 辅助分类

---

## 安装

### AI 一句话安装

你可以直接对支持 skill / agent 工作流的 AI 说一句话安装，例如：

```text
请把这个 GitHub 仓库安装成名为 canvas_material 的本地 skill：
https://github.com/bgzhang1/canvas_material-skill
```

适用于你常用的 AI 工具链场景，例如 **Codex / Claude Code / OpenClaw** 等。

安装后，主调用名应为：

```text
canvas_material
```

### 手动获取仓库

```bash
git clone https://github.com/bgzhang1/canvas_material-skill.git
cd canvas_material-skill
```

---

## 使用说明

### 0. 先准备环境变量

在第一次运行前，先准备好 Canvas 访问地址和访问令牌。

#### 第一步：确认你的 Canvas 站点地址

先打开你平时登录的 Canvas 页面，浏览器地址栏里的域名就是 `CANVAS_URL`。

例如：

- `https://cityu-dg.instructure.com`
- `https://canvas.example.edu`

> 注意：这里填写的是 **站点根地址**，不要带 `/api/v1`，也不要带具体课程路径。

#### 第二步：生成 Canvas Token

你需要一个 Canvas Access Token，供脚本通过 API 拉取课程资料。

通用步骤通常是：

1. 登录 Canvas
2. 打开个人账号相关页面
3. 进入 **Settings** 或 **Account Settings**
4. 找到 **Approved Integrations**、**Access Tokens**、**New Access Token** 或类似入口
5. 创建一个新的 token
6. 复制生成后的 token

> 不同学校的 Canvas 界面可能略有差异，但一般都能在账号设置页面找到 token 生成功能。  
> token 往往只会完整显示一次，建议生成后立刻保存。

#### 第三步：设置环境变量

必需变量：

- `CANVAS_TOKEN`

可选变量：

- `CANVAS_URL`
  - 默认值：`https://canvas.example.edu`
- `OPENAI_API_KEY`
  - 用于 AI 分类
- `OPENAI_MODEL`
  - 可选，默认 `gpt-5-mini`

#### PowerShell（当前窗口临时生效）

```powershell
$env:CANVAS_TOKEN = "your_canvas_token"
$env:CANVAS_URL = "https://your-canvas-domain"
```

如果你还想启用 AI 分类：

```powershell
$env:OPENAI_API_KEY = "your_openai_api_key"
$env:OPENAI_MODEL = "gpt-5-mini"
```

#### Bash（当前窗口临时生效）

```bash
export CANVAS_TOKEN="your_canvas_token"
export CANVAS_URL="https://your-canvas-domain"
```

如果你还想启用 AI 分类：

```bash
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_MODEL="gpt-5-mini"
```

#### 第四步：检查是否设置成功

##### PowerShell

```powershell
echo $env:CANVAS_URL
echo $env:CANVAS_TOKEN
```

##### Bash

```bash
echo "$CANVAS_URL"
echo "$CANVAS_TOKEN"
```

如果能看到你刚设置的值，就说明当前终端已经可以运行脚本了。

> 建议不要把真实 token 贴到截图、公开 issue 或 GitHub 仓库里。

#### 第五步：如果你想长期保存

如果你不想每次开终端都重新设置，可以把环境变量写入你的 shell 启动文件或系统环境变量。

##### Windows PowerShell（写入用户级环境变量）

```powershell
setx CANVAS_URL "https://your-canvas-domain"
setx CANVAS_TOKEN "your_canvas_token"
```

如果要启用 AI 分类：

```powershell
setx OPENAI_API_KEY "your_openai_api_key"
setx OPENAI_MODEL "gpt-5-mini"
```

> `setx` 写入后，**需要重新打开一个新的终端窗口** 才会生效。

##### Bash（写入 shell 配置文件）

把下面内容追加到 `~/.bashrc`、`~/.zshrc` 或你正在使用的 shell 配置文件中：

```bash
export CANVAS_URL="https://your-canvas-domain"
export CANVAS_TOKEN="your_canvas_token"
export OPENAI_API_KEY="your_openai_api_key"
export OPENAI_MODEL="gpt-5-mini"
```

然后执行：

```bash
source ~/.bashrc
```

如果你实际使用的是 zsh，请改成：

```bash
source ~/.zshrc
```

#### 最小必需配置

如果你只想先跑通最基础版本，只需要这两个：

- `CANVAS_TOKEN`
- `CANVAS_URL`

---

### 1. 首次执行

首次执行使用：

```bash
python scripts/canvas_material_sync.py setup
```

执行时会交互确认：

1. 是否开启 PDF 转换
2. 是否开启定时执行
3. 如果开启定时执行，你想怎么定时执行
4. 资料要分成哪些分类文件夹

> 你只需要直接描述定时方式，例如：`每 30 分钟`、`每天 09:00`、`每周一 09:00`。

首次执行会完成这些事：

- 生成配置
- 执行一次**首次全量同步**
- 在输出目录生成状态文件
- 如果你开启了定时执行，则安装或生成对应的定时任务信息

默认会在输出目录下生成：

- `_canvas_material_sync_config.json`
- `_canvas_material_sync_state.json`
- `_canvas_material_sync_last_update.txt`

---

### 2. 首次更新

首次执行完成后，后续你可以基于已生成的配置再次运行：

```bash
python scripts/canvas_material_sync.py run --config <输出目录>/_canvas_material_sync_config.json --mode auto
```

`auto` 的行为是：

- 如果已经完成首次全量同步：自动走**增量更新**
- 如果状态文件丢失或未完成首次同步：回退到**全量同步**

---

### 3. 增量更新

如果你想明确执行增量模式：

```bash
python scripts/canvas_material_sync.py run --config <输出目录>/_canvas_material_sync_config.json --mode incremental
```

增量更新会优先参考以下时间基线：

1. `state.json` 中的 `last_sync_at`
2. 下载目录中的 `_canvas_material_sync_last_update.txt`
3. `last_incremental_sync_at`
4. `last_full_sync_at`

也就是说，**上次同步完成时间会写在下载目录里，并在每次成功同步后刷新**。

---

### 4. 重新安装或刷新定时任务

如果你修改了配置，或者想重新生成计划任务：

```bash
python scripts/canvas_material_sync.py install-scheduler --config <输出目录>/_canvas_material_sync_config.json
```

当前实现：

- Windows：优先使用 **Windows Task Scheduler**
- 非 Windows：生成 **cron stub / crontab 提示**

---

## 常用命令

### 只做干跑（不落盘）

```bash
python scripts/canvas_material_sync.py run --config <输出目录>/_canvas_material_sync_config.json --mode incremental --dry-run
```

### 指定课程

```bash
python scripts/canvas_material_sync.py setup --course 12345 --course 67890
```

### 指定分类文件夹

```bash
python scripts/canvas_material_sync.py setup --categories lecture tutorial lab
```

---

## 仓库结构

```text
canvas_material-skill/
├─ agents/
│  └─ openai.yaml
├─ references/
│  └─ canvas_api_usage.md
├─ scripts/
│  ├─ canvas_material_sync.py
│  └─ canvas_material_sync_pkg/
│     ├─ __init__.py
│     ├─ canvas_api.py
│     ├─ cli.py
│     ├─ common.py
│     ├─ compatibility.py
│     ├─ constants.py
│     ├─ materials.py
│     ├─ prompts.py
│     ├─ state.py
│     ├─ sync_core.py
│     └─ utils.py
├─ LICENSE
├─ README.md
├─ rules.json
└─ SKILL.md
```

### 模块说明

- `scripts/canvas_material_sync.py`
  - 外部入口脚本

- `scripts/canvas_material_sync_pkg/cli.py`
  - CLI 子命令：`setup` / `run` / `install-scheduler`

- `scripts/canvas_material_sync_pkg/sync_core.py`
  - 配置构建、同步执行、调度安装

- `scripts/canvas_material_sync_pkg/canvas_api.py`
  - Canvas REST API 请求、翻页、候选资料收集

- `scripts/canvas_material_sync_pkg/materials.py`
  - 资料分类、文本提取、PDF 转换

- `scripts/canvas_material_sync_pkg/state.py`
  - 配置路径、状态文件、最后更新时间标记

- `scripts/canvas_material_sync_pkg/prompts.py`
  - 首次交互式提问与定时参数解析

- `references/canvas_api_usage.md`
  - Canvas API 调用说明

---

## Canvas API 调用方法

### 基础格式

所有请求都基于：

```text
<CANVAS_URL>/api/v1/<endpoint>
```

认证方式：

```text
Authorization: Bearer <CANVAS_TOKEN>
```

### 当前脚本实际使用的主要接口

- `GET /api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades`
- `GET /api/v1/courses/:course_id/files?per_page=100`
- `GET /api/v1/announcements?context_codes[]=course_:course_id&per_page=100`
- `GET /api/v1/courses/:course_id/assignments?per_page=100`
- `GET /api/v1/courses/:course_id?include[]=syllabus_body`
- `GET /api/v1/courses/:course_id/front_page`
- `GET /api/v1/courses/:course_id/pages?per_page=100`
- `GET /api/v1/courses/:course_id/pages/:page_url`
- `GET /api/v1/courses/:course_id/discussion_topics?per_page=100`
- `GET /api/v1/courses/:course_id/modules?include[]=items&per_page=100`

### PowerShell 示例

```powershell
$base = $env:CANVAS_URL
$headers = @{ Authorization = "Bearer $env:CANVAS_TOKEN" }

Invoke-RestMethod `
  -Headers $headers `
  -Uri "$base/api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades" `
  -Method Get
```

### Python 示例

```python
import json
import os
import urllib.request

base = os.environ.get("CANVAS_URL", "https://canvas.example.edu")
token = os.environ["CANVAS_TOKEN"]
url = f"{base}/api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades"

req = urllib.request.Request(
    url,
    headers={
        "Authorization": f"Bearer {token}",
        "User-Agent": "canvas-material-sync/2.0",
    },
)

with urllib.request.urlopen(req, timeout=30) as resp:
    body = resp.read().decode("utf-8", errors="replace")
    data = json.loads(body)
    print(data)
```

更完整的接口清单见：

- [`references/canvas_api_usage.md`](./references/canvas_api_usage.md)

---

## License

MIT
