# Canvas Material Sync

一个用于同步 Canvas 资料的 skill / 脚本集合。

它会从 Canvas 课程中抓取课件与资料链接，按课程与类别整理到本地，并支持首次全量同步、后续增量同步、可选 PDF 转换以及定时任务。

## 功能

- 首次全量扫描 Canvas 资料
- 后续按上次同步时间做增量更新
- 扫描多个资料来源
  - course files
  - announcements
  - assignments
  - syllabus
  - front page
  - pages
  - discussions
  - modules
- 自动分类到如 `lecture` / `tutorial` 等目录
- 可选把 `docx` / `pptx` / `ipynb` 转成 PDF
- 支持 Windows Task Scheduler / cron 风格定时执行
- 内置 Canvas REST API 调用说明

## 仓库结构

```text
canvas-material-sync/
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

## 环境变量

必需：

- `CANVAS_TOKEN`

可选：

- `CANVAS_URL`
  - 默认值在代码中可配置

如果启用 AI 分类，还需要：

- `OPENAI_API_KEY`

## 用法

### 1. 初始化

```powershell
python scripts/canvas_material_sync.py setup
```

### 2. 后续运行

```powershell
python scripts/canvas_material_sync.py run --config C:/path/to/_canvas_material_sync_config.json --mode auto
```

### 3. 重新安装定时任务

```powershell
python scripts/canvas_material_sync.py install-scheduler --config C:/path/to/_canvas_material_sync_config.json
```

## 定时执行

当前支持：

- 每隔 N 分钟
- 每天固定时间
- 每周固定时间

skill 层可以让用户直接用自然语言描述，例如：

- `每 30 分钟`
- `每天 09:00`
- `每周一和周三 09:00`

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
