# Canvas API Usage for `canvas-material-sync`

这个文档整理了当前 skill 使用的 Canvas REST API 方式，方便后续扩展。

## 1. 环境变量

必需：

- `CANVAS_TOKEN`

可选：

- `CANVAS_URL`
  - 默认：`https://canvas.example.edu`

## 2. 认证方式

所有请求都使用 Bearer Token：

```text
Authorization: Bearer <CANVAS_TOKEN>
```

基础 URL：

```text
<CANVAS_URL>/api/v1/<endpoint>
```

---

## 3. 直接调用示例

### PowerShell

```powershell
$base = $env:CANVAS_URL
$headers = @{ Authorization = "Bearer $env:CANVAS_TOKEN" }

Invoke-RestMethod `
  -Headers $headers `
  -Uri "$base/api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades" `
  -Method Get
```

### Python

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

---

## 4. 当前同步脚本实际使用的 API

### 4.1 课程列表

```text
GET /api/v1/courses?per_page=100&include[]=term&include[]=total_scores&include[]=current_period_grades
```

用途：

- 获取可见课程
- 可按 course ID 过滤本地目标课程

### 4.2 课程文件

```text
GET /api/v1/courses/:course_id/files?per_page=100
```

用途：

- 获取课程文件及其下载 URL

### 4.3 公告

```text
GET /api/v1/announcements?context_codes[]=course_:course_id&per_page=100
```

用途：

- 获取公告正文
- 再从 HTML 正文里提取资料链接

### 4.4 作业

```text
GET /api/v1/courses/:course_id/assignments?per_page=100
```

用途：

- 获取 assignment 描述
- 从 description HTML 中提取附件链接

### 4.5 syllabus

```text
GET /api/v1/courses/:course_id?include[]=syllabus_body
```

用途：

- 获取 syllabus HTML
- 解析里面的文件链接

### 4.6 front page

```text
GET /api/v1/courses/:course_id/front_page
```

用途：

- 获取 front page HTML
- 解析里面的文件链接

### 4.7 pages

```text
GET /api/v1/courses/:course_id/pages?per_page=100
GET /api/v1/courses/:course_id/pages/:page_url
```

用途：

- 先列出 page
- 再逐个读取正文
- 从正文 HTML 中提取文件链接

### 4.8 discussions

```text
GET /api/v1/courses/:course_id/discussion_topics?per_page=100
```

用途：

- 读取讨论区帖子正文
- 从 HTML 中提取链接

### 4.9 modules

```text
GET /api/v1/courses/:course_id/modules?include[]=items&per_page=100
```

用途：

- 从 module item 中找 `external_url` / `html_url` / `url`
- 解析可能的 Canvas 文件下载链接

---

## 5. 分页

Canvas 的列表接口通常会分页。

当前脚本处理方式：

1. 请求参数里尽量加 `per_page=100`
2. 读取响应头 `Link`
3. 找 `rel="next"`
4. 递归/循环继续请求直到没有下一页

如果后续加新的列表接口，也应保持一致。

---

## 6. 文件链接解析逻辑

同步脚本不是只依赖 `files` API。

它会同时处理：

1. **直接下载链接**
   - 来自 `courses/:id/files`

2. **正文 HTML 里的嵌入链接**
   - 公告
   - 作业描述
   - syllabus
   - front page
   - pages
   - discussions

当 HTML 里的链接不是最终 `/download` 链接时，脚本会：

- 先请求文件页
- 再从返回 HTML 里找真正的 `/download` 地址

---

## 7. 常见扩展接口

这些常见学生接口，当前同步脚本后续也可继续复用：

- `GET /api/v1/users/self`
- `GET /api/v1/users/self/todo`
- `GET /api/v1/conversations`
- `GET /api/v1/courses/:id/assignments`
- `GET /api/v1/courses/:id/assignments/:aid/submissions/self`
- `GET /api/v1/courses/:id/files`
- `GET /api/v1/courses/:id/discussion_topics`
- `GET /api/v1/calendar_events`

---

## 8. 错误处理建议

- `401`
  - token 无效或过期
- `404`
  - 没权限，或 course/file/page 不存在
- `400`
  - 参数不对
- HTML 中的文件链接无法解析
  - 记录 warning，继续处理其他资料

---

## 9. 当前代码里的建议复用点

如果后续继续扩展脚本，优先复用这些现有逻辑：

- `CanvasClient.api_json()`：通用 GET JSON
- `CanvasClient.paged()`：自动翻页
- `CanvasClient.resolve_canvas_file_link()`：把文件页解析成真实下载地址
- `CanvasClient.download_binary()`：下载文件
- `collect_candidates()`：把各资料来源统一收敛成候选列表
