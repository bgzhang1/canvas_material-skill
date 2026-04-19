# canvas_material

一个以 **对话驱动** 为核心的 Canvas 资料下载与整理 skill。

当前版本的工作流：

1. 首次启动时，在对话中询问用户 `baseurl` 和 `key`
2. 把它们保存到**下载目录**里的 config
3. 首次更新时，先列出课程与学期
4. 再询问用户：
   - 下载哪个学期
   - 是否转换 PDF
   - 分类方式是什么
5. 然后按课程逐个：
   - 下载资料
   - 按需转 PDF
   - 读取课程目录文件
   - 分类并移动文件
6. 每次更新（包括首次）完成后，将当前中国时间写入 config 的 `last_update_at`
7. 增量更新时，默认使用 config 中的 `last_update_at` 作为起始时间

---

## 核心原则

这个 skill 是给 AI 助手在对话中调用的，不是让用户手动串所有命令。

推荐的使用方式是：

```text
帮我初始化 canvas_material
```

或：

```text
帮我下载 Semester B 2025/26 的 Canvas 资料，并按 lecture/tutorial 分类
```

或：

```text
帮我增量更新
```

---

## 本地配置文件

默认把本地配置保存在下载目录：

```text
<download_root>/_canvas_material_sync_config.json
```

建议保存的字段：

- `canvas_url`
- `canvas_token`
- `output_root`
- `selected_term`
- `selected_courses`
- `pdf_convert`
- `category_folders`
- `last_update_at` — 最近一次更新完成的时间（中国时间 ISO 格式）

---

## 当前脚本

### 1. 列出课程与学期

```powershell
python scripts/list_courses.py
python scripts/list_courses.py --term "Semester B 2025/26"
python scripts/list_courses.py --json
```

输出：

- 课程编号
- 学期
- 课程名称

---

### 2. 按课程编号下载该课程可发现的资料链接

```powershell
python scripts/download_course_links.py 560
python scripts/download_course_links.py 560 --dry-run
python scripts/download_course_links.py 560 --json
```

来源覆盖：

- course files
- announcements
- assignment descriptions
- syllabus
- front page
- pages
- discussions
- modules / module items

下载到：

```text
<output_root>/<course_name>/
```

---

### 3. 转 PDF

```powershell
python scripts/convert_to_pdf.py "C:\path\course_dir" --recursive
python scripts/convert_to_pdf.py "C:\path\course_dir" --recursive --json
```

支持常见 Office 文件：

- doc / docx
- ppt / pptx
- xls / xlsx
- 以及部分兼容格式

后端：

- `auto`
- `office`
- `libreoffice`

---

### 4. 列出课程目录下所有文件

```powershell
python scripts/list_course_files.py "C:\path\course_dir" --relative
python scripts/list_course_files.py "C:\path\course_dir" --json
```

输出：

- 文件名
- 所在目录
- 路径

---

### 5. 批量移动文件

```powershell
python scripts/move_files.py "C:\src" "C:\dst" --recursive
python scripts/move_files.py "C:\src" "C:\dst" --pattern "*.pdf" --recursive
python scripts/move_files.py "C:\src" "C:\dst" --recursive --dry-run
```

支持：

- 按 pattern 筛选
- 递归
- 保留目录结构
- 预览移动结果

---

### 6. 增量更新

```powershell
# 指定时间
python scripts/incremental_update.py 560 500 --since 2026-04-19T10:00:00 --config .\canvas_materials\_canvas_material_sync_config.json

# 使用 config 中保存的上次更新时间
python scripts/incremental_update.py 560 500 --since last_update --config .\canvas_materials\_canvas_material_sync_config.json

# 只预览不下载
python scripts/incremental_update.py 560 500 --since last_update --dry-run --json
```

获取指定时间之后的 Canvas 新动作：

- 新公告
- 新作业
- 新文件
- 新页面/讨论/模块中的资料链接

并下载到对应课程名称目录下。

完成后自动将当前中国时间写入 config 的 `last_update_at`。

---

## 推荐工作流

### 首次启动

AI 应先问：

1. Canvas Base URL
2. Canvas API Key

然后把它们写入下载目录 config。

---

### 首次更新

#### 第一步：列出课程与学期

AI 调用：

```powershell
python scripts/list_courses.py
```

然后继续问用户：

1. 要下载哪个学期
2. 是否转换 PDF
3. 分类方式是什么（默认 `lecture` / `tutorial`）

并把这些偏好写入 config。

#### 第二步：逐课程下载

AI 对选中学期的课程逐个调用：

```powershell
python scripts/download_course_links.py <course_id>
```

#### 第三步：每门课下载后按需转 PDF

如果 config 里 `pdf_convert = true`，就调用：

```powershell
python scripts/convert_to_pdf.py "<course_dir>" --recursive
```

#### 第四步：每门课下载后分类整理

AI 先读取课程目录文件：

```powershell
python scripts/list_course_files.py "<course_dir>" --relative --json
```

再根据文件名和用户选择的分类方式，调用：

```powershell
python scripts/move_files.py ...
```

完成整理。

#### 第五步：写入更新时间

所有课程处理完成后，AI 将当前中国时间写入 config 的 `last_update_at`，供下次增量更新使用。

---

### 增量更新

当用户说"增量更新"时：

1. AI 读取 config 中的 `selected_courses` 和 `last_update_at`
2. 调用：

```powershell
python scripts/incremental_update.py <course_ids> --since last_update --config <config_path>
```

3. 对新增文件按课程继续转 PDF 和分类整理
4. 完成后更新 config 的 `last_update_at`

---

## 对话驱动要求

这个 skill 不是单轮黑盒执行，而是要多轮参与：

1. 先问连接信息
2. 再问下载学期 / PDF / 分类方式
3. 然后逐课程推进
4. 每门课完成后都汇报进度
5. 增量更新时确认时间范围

AI 在使用这个 skill 时，应优先说：

- "我先帮你读取课程和学期"
- "你想下载哪个学期？"
- "这次要不要自动转 PDF？"
- "分类还是用默认的 `lecture` 和 `tutorial` 吗？"
- "我现在开始逐门课下载"
- "我现在开始增量更新，从上次更新时间开始"

而不是把所有内部命令直接甩给用户。

---

## 说明

如果你是维护者，完整行为规范请看：

- `SKILL.md`

如果你是普通用户，只需要在对话里提出目标即可。
