---
name: douyin-obsidian
description: "抖音内容提取与归档工具（视频 + 图文）。从抖音分享链接解析内容：视频帖子支持无水印下载、语音识别提取口播文案；图文帖子提取正文文字、批量下载图片。结构化归档到 Obsidian vault。触发场景：用户说'把这个视频转成文字''扒一下这个帖子''图片里说了什么''帮我保存到笔记''下载这个抖音视频''提取口播''转文字版''整理到知识库''存到 Obsidian''保存到 raw-data''发我文案''整理一下'；用户要求下载抖音无水印视频、保存图文图片、批量整理抖音收藏/喜欢的内容。当用户需要处理抖音链接、提取文案、转录语音、下载视频、下载图片、或批量整理抖音内容到 Obsidian 时使用此 skill。"
compatibility: 需要 Python 3.8+，需联网访问抖音。视频文案提取需要硅基流动 API
---
# 抖音内容提取与归档（视频 + 图文）

从抖音分享链接 → 自动识别内容类型 → 视频帖子走「无水印下载 → 语音识别 → 文案提取」管线，图文帖子走「正文提取 → 图片批量下载」管线 → 结构化 Markdown 归档，一键完成。

## 前置检查（每次对话必做）

### 步骤 1：解析链接，识别帖子类型

```bash
uv run python .claude/skills/douyin-obsidian/scripts/douyin_pipeline.py --link "抖音分享链接" --action info
```

返回帖子类型（视频/图文）、ID、标题。**无需 API Key，先解析再决定后续步骤。**

**自动降级机制**：抖音反爬升级后标准解析（`_ROUTER_DATA`）可能失败，此时管线自动降级到浏览器方案（真实 Chrome + detail API，带冷却重试），全程无需手动干预，只需本机装有 Chrome。

### 步骤 2：根据类型准备 API Key（仅视频帖子需要）

| 帖子类型 | 是否需要 API Key | 说明                         |
| -------- | ---------------- | ---------------------------- |
| 视频     | 需要             | 语音识别必需，见下方配置流程 |
| 图文     | 不需要           | 直接提取正文和图片           |

**视频帖子首次配置流程（对话交互）**：

```
环境变量 API_KEY / DOUYIN_API_KEY  →  有就用（最高优先级）
            ↓ 没有
~/.douyin-video/config.json        →  读持久化配置
            ↓ 也没有
→ 触发首次配置流程
```

**首次配置流程（对话交互）**：

```
🎬 检测到你还没有配置 API Key。

这是视频文案提取必需的凭证，图文帖子不需要。免费获取，2 分钟搞定：

1. 打开 https://cloud.siliconflow.cn/
2. 注册账号（支持手机号 / 微信）
3. 登录后进入「API 密钥」页面
4. 点击「新建密钥」，复制以 sk- 开头的字符串
5. 把密钥粘贴给我，我帮你存好，以后不用再填

⚠️ 密钥只存在你本机，不会上传到任何地方。
```

用户发送 Key 后，执行：

```
python douyin_downloader.py --setup-key "<用户提供的密钥>"
```

返回成功消息：

```
✅ API Key 已保存，以后转录视频时不会再提醒你。
```

此后所有使用，Claude 先读取 `~/.douyin-video/config.json`，有 Key 直接走流程，全程静默。

## 环境安装

### uv 环境（本项目推荐）

本项目使用 [uv](https://docs.astral.sh/uv/) 管理 Python 环境，所有命令从项目根目录（`douyin-obsidian/`）运行：

```bash
# 一键安装（uv 自动解析项目 .venv）
uv run python .claude/skills/douyin-obsidian/scripts/setup.py
```

运行脚本时统一使用 `uv run python <脚本路径>`，例如：

```bash
uv run python .claude/skills/douyin-obsidian/scripts/douyin_downloader.py --link "抖音分享链接" --action info
```

FFmpeg/FFprobe 二进制位于 `.venv/Scripts/`（`uv run` 会自动加入 PATH）。若在其它项目目录运行 `uv run`，会解析到该项目的环境而找不到本 skill 依赖，务必从本项目根目录运行。

**浏览器降级方案依赖**：`douyin_pipeline.py` 在标准解析被反爬拦截时，会用 Playwright 驱动**系统已安装的 Chrome**（非 Playwright 内置浏览器），无需额外安装浏览器。依赖 `playwright` 包由 setup.py 自动安装。

### 一键安装（通用）

```bash
python scripts/setup.py
```

该脚本会自动完成：Python 版本检查 → 安装 pip 依赖（requests, ffmpeg-python） → 安装 FFmpeg → 验证结果。

### 手动安装

如果一键脚本失败，手动执行以下步骤：

**1. 安装 Python 依赖**

```bash
pip install requests ffmpeg-python -i https://pypi.tuna.tsinghua.edu.cn/simple
```

**2. 安装 FFmpeg 二进制**

Windows 上 `ffmpeg-python` 包不包含 FFmpeg 可执行文件，需要单独安装：

```bash
pip install imageio-ffmpeg -i https://pypi.tuna.tsinghua.edu.cn/simple

# 找到 imageio-ffmpeg 自带的 FFmpeg 二进制并拷贝到 Python Scripts 目录
$sitePkgs = python -c "import site; print(site.getsitepackages()[0])"
$ffmpeg = Get-ChildItem -Path $sitePkgs -Recurse -Filter "ffmpeg*.exe" | Select-Object -First 1
Copy-Item $ffmpeg.FullName "$(Join-Path $(Get-Command python).Source '..\Scripts\ffmpeg.exe')"

# 卸载搬运工包
pip uninstall -y imageio-ffmpeg
```

**3. 配置 API Key**

首次使用时，按「前置检查」中的对话流程配置。

## 使用方法

### 命令行方式

```bash
cd scripts

# 获取帖子信息（自动识别类型，无需 API Key）
python douyin_downloader.py --link "抖音分享链接" --action info

# === 视频帖子 ===

# 下载视频
python douyin_downloader.py --link "抖音分享链接" --action download --output ./videos

# 提取文案并保存到文件（需要 API Key）
python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output

# 提取文案并同时保存视频
python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output --save-video

# === 图文帖子 ===

# 提取正文和图片（无需 API Key）
python douyin_downloader.py --link "图文帖子分享链接" --action extract --output ./output

# 安静模式（减少输出）
python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output --quiet

# 持久化 API Key（仅视频帖子需要，首次配置）
python douyin_downloader.py --setup-key "你的硅基流动密钥"
```

### Python 代码调用

```python
from douyin_downloader import get_video_info, download_video, extract_text

# 获取帖子信息（自动识别类型）
info = get_video_info("抖音分享链接")

# 根据类型处理
if info.get("type") == "video":
    # 下载视频
    video_path = download_video("抖音分享链接", output_dir="./videos")

    # 提取文案并保存到文件（自动读取 ~/.douyin-video/config.json）
    result = extract_text("抖音分享链接", output_dir="./output")
else:
    # 图文帖子：提取正文和图片（无需 API Key）
    result = extract_text("抖音分享链接", output_dir="./output")
```

## 输出位置约定（重要）

所有任务产物统一放在项目根目录（`douyin-obsidian/`）下，结构如下：

```
douyin-obsidian/
├── <内容主题概括>-<日期>.md      # 笔记文件：主题概括 + 日期命名
└── assets/
    └── <内容主题概括>-<日期>/    # 每个任务一个附件子文件夹（Obsidian 规范命名 assets）
        ├── <帖子ID>.mp4          # 下载的视频
        ├── transcript.md         # 文案/逐字稿
        ├── transcript_raw.txt    # 原始转录文本
        ├── video_info.json       # 帖子信息（含无水印地址）
        ├── image_001.jpg         # 图文帖子的图片
        └── 图表/文档等副产物       # 思维导图、表格等生成物
```

规则：

- **笔记**：存到项目根，文件名 = 内容主题概括 + `-<YYYYMMDD>`（如 `功能测试用例编写方法-20260820.md`）
- **副产物**（视频/图片/转录稿/图表等）：一律放进 `assets/<笔记名>/` 子文件夹，**不删除、不移动**
- **笔记必须链接所有产物**：笔记末尾设「📎 原始素材与附件」区块，用 wikilink 列出全部产物——图片用 `![[xxx.png]]` 嵌入，视频用 `[[xxx.mp4]]` 链接，HTML/文档用 `[[xxx.html]]` 链接
- 每次任务完成后，**必须向用户汇报产物清单和完整路径**

## 执行流程

### 步骤 1：解析链接，识别类型

```bash
python douyin_downloader.py --link "<分享链接>" --action info
```

返回帖子类型（视频/图文）、ID、标题。解析失败就不用往下走了。如果识别为**图文帖子**，跳转到步骤 3。

### 步骤 2：提取内容（自动识别类型）

```bash
uv run python .claude/skills/douyin-obsidian/scripts/douyin_pipeline.py \
  --link "<分享链接>" --output "assets/<笔记名>" --quiet
```

- **自动识别帖子类型**：视频帖子走「下载无水印视频 → 提取音频 → 语音识别 → transcript」；图文帖子走「提取正文 → 批量下载图片」
- **安静模式 `--quiet` 必加**：否则下载进度条会输出大量字符
- 输出到 `assets/<笔记名>/`（见「输出位置约定」）
- **自动降级**：标准解析失败（抖音反爬）时自动切浏览器方案，无需重试或手动干预

产物：`assets/<笔记名>/transcript.md` + `transcript_raw.txt` + `video_info.json`（+ 视频 `mp4` 或 `image_0xx` 图片）

### 步骤 3：结构化整理

读取 transcript.md，加工成知识库笔记。**不要直接搬运原始转录**，要做两层：

1. **提炼层**：核心观点、结构化表格、方法论要点
2. **原文层**：完整原始文案放进 `<details>` 折叠块保留

**回答质量标准（硬性要求，每条笔记必过）**：

1. **满分回答**：交付直接可用的成品——有结论、有依据、有行动指引，像一篇能直接拿去用/转发/复习的笔记，而不是流水账或草稿
2. **实战经历感**：提炼时注入真实场景细节与判断——具体数字、踩坑点、对比结论、经验谈，避免教科书式空泛叙述（"要重视""要严谨"这类口号没有价值）
3. **完整不遗漏**：原文所有关键信息必须保留——核心观点、数据、步骤、金句一个都不能丢；提炼层拿不准是否重要的，保留到原文折叠块，宁可多留不可少收

收尾自检：写完笔记后对照原文检查一遍——有没有漏掉的关键点？有没有空话？用户读完是否可以直接照做？

**视频帖子**：读取语音逐字稿，提炼内容。
**图文帖子**：读取 desc 文案 + 读取原始图片（用视觉能力），提炼图片中的表格和数据。

frontmatter 必填字段：

```yaml
---
title: <内容主题，不要用原标签串>
date: <转录日期>
source: 抖音
author: <创作者>
video_id: "<视频ID>"
url: <分享链接>
duration: <秒数，图文帖子可不填>
type: raw-data
category: <relationships / knowledge / misc>
tags: [...]
---
```

**结构化笔记规范：**

按内容长度和复杂度分三档，避免对简单内容过度结构化：

### 轻量档（< 500字，简单图文/口语闲聊）

```
1. frontmatter
2. 核心观点 / 一句话摘要
3. 主体内容（简洁叙述或列表）
4. 总结 / 要点提炼
5. 原始图片 / 附件
6. 原文 <details> 折叠块
```

- 不需要目录

### 标准档（500-2000字，有明确主题/步骤/对比）

```
1. frontmatter
2. 目录（不超过5项）
3. 核心观点
4. 主体内容（表格/列表/分层段落）
5. 要点提炼（简短表格或列表）
6. 原始图片 / 附件
7. 原文 <details> 折叠块（可选，视原文价值决定）
```

### 深度档（> 2000字，多章节/多主题/复杂数据/视频逐字稿）

```
1. frontmatter
2. 目录
3. 核心观点
4. 主体内容（按原始结构或多层H2/H3）
5. 总结 / 方法论
6. 原始图片 / 附件
7. 原文 <details> 折叠块
```

### 结构优先级（重要）

1. **原内容自带明确结构**（如分章节图文、系列视频、分步骤教程）→ **优先保留原始结构**，按原章节顺序编排
2. **原内容无明显结构**（如口语闲聊、随机分享）→ 按逻辑重新组织：先总后分

内容组织原则：

- **结构优先**：原内容自带章节/分段/步骤结构时，直接沿用原始结构，不要强行重组
- **先总后分**：总览表格 → 逐层展开细节（仅在无原生结构时作为默认组织方式）
- **按主题分组**：相关内容放一起，不要按来源分散
- **用表格代替段落**：数据、对比、清单优先用表格
- **重点数据加粗**：关键数字、百分比用 `**加粗**` 突出
- **保持叙事线**：观点 → 证据 → 结论 → 行动建议
- **轻量/标准档图片放末尾**：正文中不插入图片，所有图片统一放在文末「原始图片」区块
- **深度档图文就近**：当文本内容较多、需要对照理解时，图片可插入在对应位置

### 步骤 4：归档与索引

- 笔记存到项目根：`douyin-obsidian/<内容主题概括>-<YYYYMMDD>.md`
- 原始素材与副产物（视频/图片/转录稿/图表）**保留在 `assets/<笔记名>/`**，不删除、不移动
- 笔记中通过 wikilink（`![[文件名]]`）引用 assets 中的图片，Obsidian 会全库解析
- 更新 `INDEX.md` 中对应目录的条目（如存在）
- 最后向用户汇报完整的产物位置清单

## 输出格式

提取内容后，每个帖子保存到独立文件夹：

```
output/
├── 7600361826030865707/           # 视频/笔记ID为文件夹名
│   └── transcript.md              # Markdown 格式文案文件
├── 7581044356631612699/           # 图文帖子示例
│   ├── transcript.md              # 正文内容
│   ├── image_001.jpg              # 下载的图片
│   ├── image_002.jpg
│   └── image_003.jpg
└── ...
```

### 视频帖子输出结构

```
<视频ID>/
├── transcript.md                   # 包含逐字稿
└── <视频ID>.mp4                    # 使用 --save-video 时保存
```

### 图文帖子输出结构

```
<笔记ID>/
├── transcript.md                   # 包含正文和图片引用
├── image_001.jpg                   # 下载的图片（格式可能为 jpg/webp/png）
├── image_002.jpg
└── ...
```

transcript.md 格式：

```markdown
# <标题>

| 属性 | 值 |
|------|----|
| 类型 | 图文 |
| ID | `xxx` |
| 提取时间 | 2026-08-06 xx:xx:xx |

---

## 正文内容

<desc 字段内容>

## 原始图片

![图片1](image_001.webp)
```

## 常见问题

### 无法解析链接

- 确保链接是有效的抖音分享链接
- 链接格式通常为 `https://v.douyin.com/xxxxx/` 或完整的抖音视频 URL
- 标准解析失败（抖音反爬 JSVM 壳）时，`douyin_pipeline.py` 会自动降级浏览器方案，**无需手动处理**
- 若浏览器方案也失败（连续风控 403），脚本会提示"标准解析与浏览器方案均失败"，等待几分钟后重试即可
- 浏览器方案需要本机安装 Chrome（Playwright 驱动系统 Chrome，非内置浏览器）

### 提取文案失败

- 确认 API Key 已配置（仅视频帖子需要）
- 运行 `python douyin_downloader.py --setup-key "你的密钥"`
- 确保 API 密钥有效且有足够的配额
- 确保 FFmpeg 已正确安装（运行 `python scripts/setup.py` 验证）

### 图文帖子提取失败

- 确认链接指向的是图文帖子（多图帖子）
- 图文帖子依赖抖音页面数据，如果页面结构变更可能失效
- 检查输出目录是否有写入权限

### FFmpeg 相关错误

- Windows：确认 `ffmpeg.exe` 已存在于 Python Scripts 目录
- macOS：`brew install ffmpeg`
- Linux：`apt install ffmpeg`

### 下载速度慢

- 这取决于网络条件和视频大小
- 脚本会显示下载进度

## 安全说明

- **API Key 存储**：仅保存在用户本地 `~/.douyin-video/config.json`，不会被上传或同步
- **密钥传输**：仅通过 HTTPS `Authorization: Bearer` 头发送给硅基流动 API，不写入任何日志
- **外发域名**：仅 `api.siliconflow.cn`（语音识别）和 `www.iesdouyin.com`（视频/图文解析）
- **无危险调用**：脚本不包含 `subprocess`/`socket`/`pickle`/`eval`/`exec` 等调用
- **图文帖子**：不涉及任何 API 调用，仅从抖音页面提取公开数据

## 注意事项

- 本工具仅供学习和研究使用
- 使用时需遵守相关法律法规
- 请勿用于任何侵犯版权或违法的目的
