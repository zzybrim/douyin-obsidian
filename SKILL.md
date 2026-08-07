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
cd scripts
python douyin_downloader.py --link "抖音分享链接" --action info
```

返回帖子类型（视频/图文）、ID、标题。**无需 API Key，先解析再决定后续步骤。**

### 步骤 2：根据类型准备 API Key（仅视频帖子需要）

| 帖子类型 | 是否需要 API Key | 说明 |
|---------|----------------|------|
| 视频 | 需要 | 语音识别必需，见下方配置流程 |
| 图文 | 不需要 | 直接提取正文和图片 |

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
🎬 检测到你还没有配置硅基流动 API Key。

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

### 一键安装（推荐）

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

## 执行流程

### 步骤 1：解析链接，识别类型

```bash
python douyin_downloader.py --link "<分享链接>" --action info
```

返回帖子类型（视频/图文）、ID、标题。解析失败就不用往下走了。如果识别为**图文帖子**，跳转到步骤 3。

### 步骤 2：视频帖子 - 提取文案

```bash
python douyin_downloader.py \
  --link "<分享链接>" --action extract \
  --output "<临时目录>" --quiet
```

- **安静模式 `--quiet` 必加**：否则下载进度条会输出大量字符
- 先输出到临时目录，不要直接写进 vault——要经过整理再入库

产物：`<临时目录>/<视频ID>/transcript.md`

### 步骤 3：图文帖子 - 提取正文和图片

```bash
python douyin_downloader.py \
  --link "<分享链接>" --action extract \
  --output "<临时目录>" --quiet
```

- **无需 API Key**，图文帖子直接提取页面正文并批量下载图片

产物：`<临时目录>/<笔记ID>/transcript.md` + `image_001.jpg` 等图片文件

### 步骤 4：结构化整理

读取 transcript.md，加工成知识库笔记。**不要直接搬运原始转录**，要做两层：

1. **提炼层**：核心观点、结构化表格、方法论要点
2. **原文层**：完整原始文案放进 `<details>` 折叠块保留

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

### 步骤 5：归档与索引

- 存入 `0-raw-data/` 对应子目录，三位数字前缀命名，如 `001-douyin-self-integrity-scale.md`
- 图文帖子需将下载的图片一并放入附件目录
- 更新 `INDEX.md` 中对应目录的条目
- 清理临时目录

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
