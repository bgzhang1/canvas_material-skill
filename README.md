# canvas_material

> 一个以 **对话驱动** 为核心使用方式的 Canvas 资料同步 skill。

你不需要记命令。  
你只需要像和 AI 助手说话一样，直接描述你的目标，`canvas_material` 会负责：

- **首次全量扫描**
- **后续增量更新**
- **资料分类整理**
- **可选 PDF 转换**
- **可选定时同步**

---

## 这个 skill 的正确打开方式

这个仓库的重点不是让用户手动执行一堆 CLI 命令，而是：

1. **安装 skill**
2. **直接和 AI 对话**
3. **让 AI 理解你的需求并完成同步**

也就是说，推荐你说：

```text
帮我初始化 canvas_material
```

而不是优先自己敲：

```text
python scripts/canvas_material_sync.py setup
```

脚本依然存在，但属于**实现层**，不是 README 的主入口。

---

## 一句话安装

你可以直接对支持 skill / agent 工作流的 AI 说：

```text
请把这个仓库安装成名为 canvas_material 的本地 skill：
https://github.com/bgzhang1/canvas_material-skill
```

安装完成后，你后续直接通过自然语言调用它即可。

---

## 你只需要对 AI 说什么

下面是这个 skill 推荐的使用方式。

### 1. 首次初始化

你可以直接说：

```text
帮我初始化 canvas_material
```

或者一次性把关键信息说完整：

```text
帮我初始化 canvas_material：
- 输出目录放到 C:\Users\BGZHANG\Desktop\zip\canvas_materials
- 开启 PDF 转换
- 不开定时
- 分类用 lecture 和 tutorial
```

此时模型应继续在对话里确认必要信息，例如：

- 是否开启 PDF 转换
- 是否开启定时同步
- 如果开启，想怎么定时
- 分类文件夹有哪些

如果信息已经说全，模型应直接进入初始化流程，而不是反复追问。

---

### 2. 首次同步

初始化完成后，模型应自动完成首次全量扫描。  
你也可以直接这样说：

```text
初始化后立刻同步一次
```

或：

```text
帮我做第一次全量下载
```

模型应完成：

- 读取 Canvas 课程
- 扫描常见资料来源
- 下载资料
- 自动分类到本地目录
- 写入配置与状态文件

---

### 3. 后续增量更新

以后你不需要重新走初始化流程，只需要直接说：

```text
对 C:\Users\BGZHANG\Desktop\zip\canvas_materials 做一次增量更新
```

或者：

```text
帮我同步一下 Canvas 最新资料
```

或者：

```text
只更新 CS3103 和 CS3402
```

模型应基于已有配置和上次同步时间，自动完成增量更新，而不是要求你重新配置一遍。

---

### 4. 改定时同步

如果你希望自动同步，不需要自己写计划任务表达式，只要直接说：

```text
把这个资料目录改成每天 09:00 自动同步
```

或：

```text
改成每 30 分钟同步一次
```

或：

```text
改成每周一和周三 08:30 自动同步
```

模型应负责把自然语言里的时间描述解析成对应的定时任务配置。

---

### 5. 关闭定时同步

如果你不想继续自动同步，可以直接说：

```text
把这个目录的定时同步关掉
```

模型应更新配置，并取消或停用对应的计划任务。

---

## 一个理想的对话流程

### 场景一：首次接入

用户：

```text
帮我初始化 canvas_material
```

模型：

```text
好的，我先确认几项：
1. 是否开启 PDF 转换？
2. 是否开启定时同步？
3. 如果开启，想怎么定时？
4. 资料分成哪些分类目录？
5. 输出目录放在哪里？
```

用户：

```text
开启 PDF，不开定时，分类用 lecture 和 tutorial，输出到 C:\Users\BGZHANG\Desktop\zip\canvas_materials
```

模型随后应完成：

- 初始化配置
- 首次全量扫描
- 下载资料
- 自动分类
- 写入状态文件

---

### 场景二：后续更新

用户：

```text
对 C:\Users\BGZHANG\Desktop\zip\canvas_materials 做一次增量更新
```

模型随后应完成：

- 读取已有配置
- 根据上次同步时间确定增量基线
- 扫描 Canvas 新动作
- 下载新增或变更资料
- 刷新状态文件和最后更新时间

---

### 场景三：修改同步频率

用户：

```text
把这个资料目录改成每天早上 9 点同步
```

模型随后应完成：

- 解析时间表达
- 更新定时配置
- 安装或刷新计划任务

---

## 这个 skill 会扫描哪些地方

当前主要覆盖这些 Canvas 资料来源：

- `course files`
- `announcements`
- `assignment descriptions`
- `syllabus`
- `front page`
- `pages`
- `discussions`
- `modules / module items`

也就是说，模型在执行同步时，不只是看课程文件区，还会检查正文里嵌入的附件或下载链接。

---

## 状态文件是怎么用的

这个 skill 会在输出目录中保存可复用状态：

- `_canvas_material_sync_config.json`
- `_canvas_material_sync_state.json`
- `_canvas_material_sync_last_update.txt`

作用分别是：

- `config`：保存同步设置
- `state`：保存已下载资料和同步状态
- `last_update`：保存最后一次成功同步的时间

因此模型在后续对话中应该能够：

- 识别这是一个已经初始化过的目录
- 直接继续增量更新
- 不要求用户重新填写全部参数

---

## 环境与认证

这个 skill 使用 Canvas REST API。

基础形式：

```text
<CANVAS_URL>/api/v1/<endpoint>
Authorization: Bearer <CANVAS_TOKEN>
```

对普通用户来说，推荐的交互方式应当是：

- 用户告诉模型 Canvas 地址或 token 的准备情况
- 模型负责读取现有环境或引导补充最少必要信息
- 用户不需要每次手动回忆底层 API 调用方式

如果你是维护者或要做二次开发，可以再去看：

- `SKILL.md`
- `references/canvas_api_usage.md`

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
├─ LICENSE
├─ README.md
├─ SKILL.md
└─ rules.json
```

---

## 面向维护者的要求

如果你在维护这个 skill，请优先保证：

1. README 明确把 **对话驱动** 作为主要入口
2. `SKILL.md` 与 README 的交互方式一致
3. 脚本只作为底层实现，不把 CLI 暴露成主要使用方式
4. 模型可以基于已有配置完成增量更新和定时调整

---

## License

MIT
