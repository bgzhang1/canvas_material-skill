# canvas_material-skill

一个用于同步 Canvas 资料的 skill / 脚本集合。

它会从 Canvas 课程中抓取课件与资料链接，按课程与类别整理到本地，并支持首次全量同步、后续增量同步、可选 PDF 转换以及定时任务。

## 主要功能

> **一句话概括：**  
> 这份 skill 可以帮你把 **Canvas 里的课件与资料自动抓取、分类整理、持续增量更新，并支持定时执行**。

- **首次全量同步**
  - 第一次运行时，自动扫描并下载当前可见的 Canvas 资料。

- **增量更新**
  - 以后只检查并同步 **上次更新之后的新动作 / 新资料**，避免重复处理。

- **多来源扫描**
  - 不只抓 course files，还会扫描：
    - `course files`
    - `announcements`
    - `assignments`
    - `syllabus`
    - `front page`
    - `pages`
    - `discussions`
    - `modules`

- **自动分类整理**
  - 自动把资料归类到如 `lecture` / `tutorial` 等文件夹中。

- **可选 PDF 转换**
  - 支持将 `docx` / `pptx` / `ipynb` 等资料按需转换成 PDF。

- **定时同步**
  - 支持：
    - **每隔 N 分钟**
    - **每天固定时间**
    - **每周固定时间**

- **可被 AI 客户端直接调用**
  - 可由支持 skill / 仓库安装的 AI 客户端一句话安装并执行。

- **内置 Canvas API 说明**
  - 仓库内已经附带通用的 Canvas REST API 调用方法，便于继续扩展。

## 安装

### AI 一句话安装

对于支持 GitHub 仓库 / skill 安装的 AI 客户端（例如 Codex、Claude Code、OpenClaw 等），直接说一句：

```text
请安装 GitHub 仓库 bgzhang1/canvas_material-skill 作为一个可用 skill，并在涉及 Canvas 资料同步时使用它。
```

如果客户端更适合直接给 URL，也可以说：

```text
请把 https://github.com/bgzhang1/canvas_material-skill 安装成一个可用 skill。
```

## 使用说明

### 0. 先准备环境变量

必需：

- `CANVAS_TOKEN`

可选：

- `CANVAS_URL`
- `OPENAI_API_KEY`（仅在启用 AI 分类时需要）

### 1. 首次执行

第一次让 AI 客户端真正启用这份 skill，可以直接说：

```text
请使用 canvas_material-skill 初始化我的 Canvas 资料同步。
```

如果你想一次性把参数讲清楚，也可以直接说：

```text
请使用 canvas_material-skill 初始化我的 Canvas 资料同步：开启 PDF 转换；定时每天 09:00；分类为 lecture 和 tutorial。
```

流程：

1. AI 读取 `SKILL.md`
2. AI 确认首次配置所需信息
3. 进入首次同步流程

### 2. 首次更新

第一次真正执行同步时，建议直接说：

```text
请使用 canvas_material-skill 做第一次 Canvas 全量更新。
```

或者更完整一点：

```text
请使用 canvas_material-skill 做第一次 Canvas 全量更新：输出目录用默认；开启 PDF 转换；定时每周一和周三 09:00；分类为 lecture 和 tutorial。
```

底层命令对应：

```powershell
python scripts/canvas_material_sync.py setup
```

流程：

1. 收集配置
2. 执行首次全量扫描
3. 下载并分类资料
4. 写入 config / state / last update marker
5. 如果开启定时执行，则安装 scheduler

### 3. 增量更新

后续更新时，直接对 AI 说：

```text
请使用 canvas_material-skill 做一次增量更新。
```

或者：

```text
请按现有配置用 canvas_material-skill 同步 Canvas 最新资料。
```

底层命令对应：

```powershell
python scripts/canvas_material_sync.py run --config C:/path/to/_canvas_material_sync_config.json --mode auto
```

如果你明确只想跑增量，也可以用：

```powershell
python scripts/canvas_material_sync.py run --config C:/path/to/_canvas_material_sync_config.json --mode incremental
```

流程：

1. 读取现有 config
2. 读取 state 和下载目录里的最后更新时间
3. 检查上次同步之后的 Canvas 新动作
4. 下载并分类新增 / 更新资料
5. 刷新最后更新时间

### 4. 重新安装定时任务

如果只想刷新 scheduler：

```text
请使用 canvas_material-skill 重新安装当前配置的定时任务。
```

底层命令：

```powershell
python scripts/canvas_material_sync.py install-scheduler --config C:/path/to/_canvas_material_sync_config.json
```

## 仓库结构

```text
canvas_material-skill/
├─ SKILL.md
├─ README.md
├─ rules.json
├─ references/
│  └─ canvas_api_usage.md
└─ scripts/
   ├─ canvas_material_sync.py
   └─ canvas_material_sync_pkg/
      ├─ __init__.py
      ├─ cli.py
      ├─ common.py
      ├─ canvas_api.py
      ├─ materials.py
      └─ sync_core.py
```

## Canvas API

这份 skill 已内置通用的 Canvas REST API 使用说明。

参考：

- `SKILL.md`
- `references/canvas_api_usage.md`

核心规则：

```text
GET <CANVAS_URL>/api/v1/<endpoint>
Authorization: Bearer <CANVAS_TOKEN>
```
