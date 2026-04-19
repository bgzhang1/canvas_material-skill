---
name: canvas_material
description: 对话驱动的 Canvas 资料下载与整理 skill。首次启动时询问 Canvas Base URL 和 API Key，保存到下载目录 config；首次更新时先列出课程与学期，询问用户要下载的学期、是否转换 PDF、以及分类方式，然后逐课程下载资料、按需转 PDF、再按分类方式整理到课程目录下。支持增量更新命令：按指定时间获取已选课程的新公告/作业/文件动作并下载、转 PDF、再分类移动。
---

# canvas_material

这个 skill 是 **对话驱动** 的。

重点不是让用户自己背命令，而是：

1. 你在对话里收集必要信息
2. 你调用本 skill 下的小脚本逐步完成任务
3. 你在关键节点继续和用户确认
4. 你把结果整理到本地下载目录

除非用户明确要求，否则**不要把“请你自己运行某个脚本”作为默认工作流**。

---

## 当前脚本清单

本 skill 当前使用这些脚本：

- `scripts/list_courses.py`
  - 脚本一：获取课程编号 + 学期 + 课程名称
- `scripts/download_course_links.py`
  - 脚本二：按课程编号抓取该课程下的下载链接并下载到 `输出根目录/课程名称/`
- `scripts/convert_to_pdf.py`
  - 脚本三：把 `doc/docx/ppt/pptx/xls/xlsx/...` 等文件转成 PDF
- `scripts/list_course_files.py`
  - 脚本四：列出课程目录下所有文件，包含文件名与目录/路径
- `scripts/move_files.py`
  - 脚本五：批量移动文件
- `scripts/incremental_update.py`
  - 增量更新脚本：获取指定时间往后的 Canvas 新动作（公告/作业/文件等）并下载其中可能存在的下载链接/文件到对应课程名称目录下

---

## 本 skill 的默认本地配置文件

所有关键配置都应保存在**下载目录**里的本地 config 中：

- `<download_root>/_canvas_material_sync_config.json`

这个 config 至少应保存：

- `canvas_url`
- `canvas_token`
- `output_root`
- `pdf_convert`
- `category_folders`
- `selected_term`
- `selected_courses`
- `last_update_at` — 最近一次更新完成的时间（中国时间 ISO 格式，如 `2026-04-19T22:00:00+08:00`）。每次更新（包括首次）完成后都必须写入。增量更新时默认用这个时间作为 `since`。

如果该文件不存在，就把这次任务视为**首次启动**。

如果该文件已存在，但缺少上面任一关键字段，也视为**未完整初始化**。

---

## 首次启动：必须多轮对话

首次启动时，你必须在对话里先问用户：

1. Canvas Base URL 是什么
2. Canvas API Key / Access Token 是什么

这两项拿到之后：

- 将它们写入下载目录 config
- 默认下载目录如果用户没指定，就使用当前工作目录下的 `canvas_materials`
- Base URL 应保存为站点根地址，例如：
  - `https://canvas.example.edu`
- 不要自动附加 `/api/v1`
- Token 属于敏感信息，不要在回复里反复回显

### 首次启动时的对话要求

- 不要一次性跳过确认直接开始下载
- 不要假设 token 已经可用，除非你确实从已有 config 或环境变量读到了
- 不要把“学期、PDF、分类方式”也和 Base URL / token 混成一个超长问题一次扔给用户
- 这一步只负责完成**连接信息初始化**

---

## 首次更新工作流

当 Base URL 和 token 已保存后，首次更新必须按下面顺序进行。

### 第一步：列出课程与学期，然后继续问用户

先运行：

```powershell
python scripts/list_courses.py
```

拿到课程编号、学期、课程名称后，在对话里继续问用户：

1. 想下载哪个学期
2. 是否开启 PDF 转换
3. 分类方式是什么

分类方式默认值：

- `lecture`
- `tutorial`

把用户的选择写入下载目录 config：

- `selected_term`
- `pdf_convert`
- `category_folders`
- `selected_courses`

### 这一轮对话的要求

- 必须把当前可选学期明确展示给用户
- 不要偷偷替用户决定学期
- PDF 转换必须问
- 分类方式必须问；如果用户说默认，就写入 `lecture` / `tutorial`
- 必须把最终选中的课程编号列表写入 `selected_courses`

---

## 第二步：按课程逐个下载

在用户确定学期后：

1. 从课程列表中筛出该学期下的课程
2. 按课程一个一个处理
3. 每门课都调用：

```powershell
python scripts/download_course_links.py <course_id>
```

这个脚本负责从这些来源寻找下载链接：

- `course files`
- `announcements`
- `assignment descriptions`
- `syllabus`
- `front page`
- `pages`
- `discussions`
- `modules / module items`

下载目标目录应为：

- `<download_root>/<course_name>/`

### 逐课程处理要求

- 必须按课程逐个做，不要先把所有课混在一起再处理
- 每完成一门课，就进入后续 PDF 转换与分类步骤
- 如果某门课没有找到可下载链接，也要在对话里简短说明

---

## 第三步：按用户习惯决定是否转 PDF

当某一门课完整下载完后：

- 读取 config 中的 `pdf_convert`
- 如果为 `true`，调用：

```powershell
python scripts/convert_to_pdf.py "<course_dir>" --recursive
```

- 如果为 `false`，跳过

### PDF 转换要求

- 这是**每门课下载完成后**立即做的步骤，不是所有课程全下载完才统一做
- 如果个别文件转换失败，不要因此中断整门课
- 应保留原文件，除非用户明确要求只保留 PDF

---

## 第四步：读取课程目录并分类

当某一门课完整下载完，并且该门课需要的 PDF 转换也处理完后：

1. 调用脚本四读取这门课目录下的所有文件：

```powershell
python scripts/list_course_files.py "<course_dir>" --relative --json
```

2. 根据文件名并参考它们在 Canvas 中的文件目录/来源信息，结合用户的分类方式，判断这些文件应被放到哪个分类目录
3. 再调用脚本五批量移动文件完成整理

例如默认分类方式是：

- `lecture`
- `tutorial`

那么你应根据文件名关键词自行判断：

- lecture / lec / slides / chapter / topic / syllabus / 课件 / 讲义等
  - 优先归到 `lecture`
- tutorial / tut / lab / assignment / homework / quiz / exercise / 作业 / 实验 / 练习等
  - 优先归到 `tutorial`
- 都不明显时：
  - 优先保留在课程目录根下或单独放入你本轮工作流中使用的兜底目录
  - 不要擅自删除

### 分类阶段要求

- 先列文件，再分类，再移动
- 不要直接盲移
- 如果用户给出的分类方式不是 `lecture/tutorial`，就按用户定义的新分类名整理
- 这个 skill 默认是**文件名驱动 + 目录信息辅助**，同时仍然依赖 AI 分类

---

## 增量更新命令

这个 skill 需要支持一个名为：

- `增量更新`

的对话命令。

当用户说类似：

```text
帮我增量更新
```

或：

```text
从昨天晚上 10 点之后开始增量更新
```

你应进入如下工作流。

### 增量更新工作流

1. 先读取下载目录 config：
   - `canvas_url`
   - `canvas_token`
   - `output_root`
   - `pdf_convert`
   - `category_folders`
   - `selected_courses`
2. 询问或确认“从什么时间之后开始增量更新”
3. 使用增量更新脚本：

```powershell
python scripts/incremental_update.py <course_id> <course_id> ... --since <time> --config <config_path>
# Use last_update to default to the time stored in config:
python scripts/incremental_update.py 560 500 --since last_update --config .\canvas_materials\_canvas_material_sync_config.json
```

4. 这个脚本会对**当前已选择的课程**抓取指定时间往后的新动作：
   - 新公告
   - 新作业正文
   - 新文件
   - 新页面/讨论/模块中的新资料链接
5. 下载这些新动作里可能存在的下载链接/文件到对应课程名称目录下
6. 如果 `pdf_convert = true`：
   - 对新增文件所在课程目录调用脚本三转换 PDF
7. 然后根据新增文件名称，并参考它们在 Canvas 中的文件目录/来源信息，按当前分类方法进行相应移动
   - 读取课程目录文件：

```powershell
python scripts/list_course_files.py "<course_dir>" --relative --json
```

   - 然后调用脚本五做分类移动

### 增量更新阶段要求

- 默认只处理 `selected_courses` 中的课程
- 如果 config 里没有 `selected_courses`，必须先回到“列课程并重新选择课程”的步骤
- 必须让用户能指定 `since` 时间
- 如果用户没有给时间，默认使用 config 中的 `last_update_at`（即上次更新完成时间，中国时间 ISO 格式）。如果 config 中没有 `last_update_at`，则必须追问用户
- 新增文件的处理顺序必须是：
  1. 下载
  2. 按需转 PDF
  3. 列文件
  4. 分类移动
- 不要跳过分类阶段

---


## 每次更新完成后必须写入时间戳

无论是首次更新还是增量更新，**每次成功完成后**都必须将当前中国时间写入 config 中的 `last_update_at` 字段。

格式：ISO 8601 带时区偏移，例如：

```text
2026-04-19T22:00:00+08:00
```

写入时机：

- 首次全量更新：所有课程下载、转 PDF、分类移动都完成后
- 增量更新：所有课程的新增文件下载、转 PDF、分类移动都完成后

增量更新时，`since` 时间的默认值就是 config 里的 `last_update_at`。

## 后续更新工作流

对于已经初始化过的下载目录：

1. 先读取 `<download_root>/_canvas_material_sync_config.json`
2. 获取：
   - `canvas_url`
   - `canvas_token`
   - `selected_term`
   - `selected_courses`
   - `pdf_convert`
   - `category_folders`
3. 如果用户没有明确要求切换学期：
   - 默认沿用 `selected_term`
4. 如果用户要求改学期、改 PDF 习惯、改分类方式：
   - 先更新 config，再执行下载流程
5. 如果用户要求增量更新：
   - 走“增量更新命令”流程

---

## 多轮参与规则

这个 skill 明确要求你在对话中**多轮参与**。

你不应把首次工作流压缩成“一次性执行所有动作”的黑盒流程。

推荐节奏：

### 回合 1：初始化连接信息

- 问 Base URL
- 问 API Key
- 写入 config

### 回合 2：决定首次下载策略

- 运行 `list_courses.py`
- 向用户展示课程与学期
- 问用户选择哪个学期
- 问是否转 PDF
- 问分类方式
- 更新 config

### 回合 3+：执行逐课程工作流

对每门课：

1. 下载
2. 转 PDF（如需要）
3. 列文件
4. 分类移动

### 增量更新回合

当用户说“增量更新”时：

1. 读取 config
2. 确认 since 时间
3. 调用 `incremental_update.py`
4. 对新增文件按课程继续做 PDF 转换与分类整理

对于进度汇报，优先用这种简洁形式：

- 当前处理哪门课
- 找到多少新增链接/文件
- 下载了多少文件
- 转 PDF 成功/失败多少
- 分类移动到了哪些目录

---

## 脚本调用约定

### 1. 列课程

```powershell
python scripts/list_courses.py
python scripts/list_courses.py --term "Semester B 2025/26"
python scripts/list_courses.py --json
```

### 2. 下载单门课

```powershell
python scripts/download_course_links.py 560
python scripts/download_course_links.py 560 --dry-run
python scripts/download_course_links.py 560 --json
```

### 3. 转 PDF

```powershell
python scripts/convert_to_pdf.py "C:\path\course_dir" --recursive
python scripts/convert_to_pdf.py "C:\path\course_dir" --recursive --json
```

### 4. 列课程目录文件

```powershell
python scripts/list_course_files.py "C:\path\course_dir" --relative
python scripts/list_course_files.py "C:\path\course_dir" --relative --json
```

### 5. 批量移动

```powershell
python scripts/move_files.py "C:\src" "C:\dst" --pattern "*.pdf" --recursive
python scripts/move_files.py "C:\src" "C:\dst" --recursive --dry-run
```

### 6. 增量更新

```powershell
python scripts/incremental_update.py 560 500 --since 2026-04-19T10:00:00 --config .\canvas_materials\_canvas_material_sync_config.json
python scripts/incremental_update.py 560 500 --since 2026-04-19 --dry-run --json
```

---

## 对用户的默认表达方式

优先这样和用户交流：

- “我先帮你读取课程和学期”
- “你想下载哪个学期？”
- “这次要不要自动转 PDF？”
- “分类还是用默认的 `lecture` 和 `tutorial` 吗？”
- “我现在开始逐门课下载，先处理 CS2312”
- “CS2312 已下载完，接下来开始转 PDF / 分类整理”
- “我现在开始增量更新，请告诉我从什么时间之后开始”

不要默认这样说：

- “你去执行这个命令”
- “请先手动配置环境变量”
- “请自己准备 cron / 计划任务”

---

## 安全与本地数据

- `canvas_token` 只保存在本地下载目录 config 中
- 不要把 token 写进公开仓库文件
- 不要在对话里反复明文展示 token
- 删除、移动文件前应尽量明确目标目录
- 批量移动时优先先做一次 `--dry-run` 预览，尤其是分类阶段

---

## 你最终要实现的体验

用户只需要说类似：

```text
帮我初始化并下载某个学期的 Canvas 资料
```

或者：

```text
帮我增量更新从昨天晚上开始的新资料
```

你就应该按以下顺序推进：

1. 问 Base URL 和 key
2. 保存 config
3. 列课程与学期
4. 问学期、PDF、分类方式
5. 按课程逐个下载
6. 每门课下载后立即按需转 PDF
7. 每门课下载后立即读取文件并分类移动
8. 用户要求增量更新时，读取已选课程并按指定时间抓取新动作
9. 对新增文件继续转 PDF 和分类移动
10. 在对话中持续汇报进度

这就是本 skill 的核心工作流。

