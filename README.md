# douyin-obsidian

抖音内容提取与归档工具（视频 + 图文），专为 Obsidian 知识库设计。

从抖音分享链接自动识别内容类型：视频帖子走「无水印下载 → 语音识别 → 文案提取」管线，图文帖子走「正文提取 → 图片批量下载」管线，结构化 Markdown 归档，一键完成。

![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![Obsidian](https://img.shields.io/badge/obsidian-skill-green)

## 功能特性

- 🎬 **视频帖子**：无水印下载 + 语音识别提取口播文案 + 保存视频文件
- 🖼️ **图文帖子**：提取正文文字 + 批量下载图片
- 📝 **结构化归档**：自动生成符合 Obsidian 知识库规范的 Markdown 笔记
- 🔐 **安全存储**：API Key 仅保存在本地，不上传
- ⚡ **一键安装**：提供自动安装脚本，自动配置 FFmpeg

## 环境要求

- Python 3.8+
- FFmpeg（视频帖子语音识别必需，一键安装脚本会自动配置）
- 硅基流动 API Key（仅视频帖子需要，[免费获取](https://cloud.siliconflow.cn/)）

## 快速开始

### 1. 克隆到 Agent Skills 目录

```bash
# Claude Code
git clone https://github.com/zzybrim/douyin-obsidian.git ~/.claude/skills/douyin-obsidian

# Codex CLI（项目级）
git clone https://github.com/zzybrim/douyin-obsidian.git .codex/skills/douyin-obsidian
```

### 2. 安装依赖

```bash
python scripts/setup.py
```

### 3. 配置 API Key（仅视频帖子需要）

向 Agent 发送抖音视频链接时，如果检测到未配置 API Key，会引导你完成首次配置：

1. 打开 https://cloud.siliconflow.cn/ 注册账号
2. 创建 API 密钥（以 `sk-` 开头）
3. 把密钥粘贴给 Agent，自动保存到 `~/.douyin-video/config.json`

## 使用方式

配置完成后，向 AI Agent 发送抖音链接即可自动调用：

```
把这个视频转成文字：https://v.douyin.com/xxxxx/
```

Agent 会自动完成：解析链接 → 识别帖子类型 → 提取内容 → 整理成知识库笔记。

### 触发条件（Trigger）

当用户表达以下任一意图时，自动触发本 skill：

**视频内容提取类**
- "把这个视频转成文字""提取文案""发我文案""口播是什么"
- "提取这个抖音视频的文案""扒一下口播""转录一下"
- "总结一下这个视频""讲了什么""核心观点是什么"

**图文内容提取类**
- "图片里说了什么""图里讲了什么""文字内容是什么"
- "提取图片文字""把图里的内容打出来"
- "这个图文帖子的正文"

**下载/保存类**
- "下载这个抖音视频""无水印下载""保存视频到本地"
- "下载这些图片""把图片保存下来""批量下载图片"
- "保存到 Obsidian""存到笔记""存到 raw-data"
- "整理到知识库""归档一下""保存到我的 vault"

**批量/整理类**
- "整理一下我的抖音收藏""批量整理抖音内容"
- "把喜欢的内容都存下来""扒一下我收藏的"

**同义/口语变体**
- "巴拉巴拉巴拉（这个链接）""帮我看看这个抖音"
- "转成笔记格式""整理成 Obsidian 格式"
- "提取+归档""转存到笔记"

## 工作原理

### 前置检查

每次对话先解析链接，识别帖子类型：

```bash
python scripts/douyin_downloader.py --link "抖音分享链接" --action info
```

返回帖子类型（视频/图文）、ID、标题。无需 API Key。

### 视频帖子处理流程

```
分享链接 → 无水印下载视频 → 提取音频 → 语音识别 → 文案提取 → 结构化 Markdown 笔记
```

需要 API Key，输出：
- `transcript.md`（包含逐字稿）
- `<视频ID>.mp4`（使用 `--save-video` 时保存）

### 图文帖子处理流程

```
分享链接 → 提取页面正文 → 批量下载图片 → 结构化 Markdown 笔记
```

无需 API Key，输出：
- `transcript.md`（包含正文和图片引用）
- `image_001.jpg` 等图片文件

## 输出结构

```
output/
├── <视频ID或笔记ID>/
│   ├── transcript.md      # 文案内容
│   ├── image_001.jpg      # 下载的图片（图文帖子）
│   └── <视频ID>.mp4       # 视频文件（可选）
└── ...
```

## Obsidian 用户

在 Obsidian 中使用此 skill，推荐通过 **Obsidian 的 AI 插件**（如 claudian、Copilot、Smart Connections 等支持 skill 规范的插件）来调用，将本 skill 安装到对应插件的 skill 目录即可。

## 命令行使用

```bash
# 查看帖子信息（无需 API Key）
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action info

# 下载视频
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action download --output ./videos

# 提取文案（需要 API Key）
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action extract --output ./output

# 图文帖子提取（无需 API Key）
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action extract --output ./output --quiet

# 持久化 API Key（首次配置）
python scripts/douyin_downloader.py --setup-key "你的硅基流动密钥"
```

## Python API

```python
from douyin_downloader import get_video_info, download_video, extract_text

info = get_video_info("抖音分享链接")

if info.get("type") == "video":
    video_path = download_video("抖音分享链接", output_dir="./videos")
    result = extract_text("抖音分享链接", output_dir="./output")
else:
    result = extract_text("抖音分享链接", output_dir="./output")
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

## 安全说明

- **API Key 存储**：仅保存在用户本地 `~/.douyin-video/config.json`，不会被上传或同步
- **密钥传输**：仅通过 HTTPS `Authorization: Bearer` 头发送给硅基流动 API，不写入任何日志
- **外发域名**：仅 `api.siliconflow.cn`（语音识别）和 `www.iesdouyin.com`（视频/图文解析）
- **无危险调用**：脚本不包含 `subprocess`/`socket`/`pickle`/`eval`/`exec` 等调用
- **图文帖子**：不涉及任何 API 调用，仅从抖音页面提取公开数据

## 注意事项

- 仅供学习和研究使用
- 使用时需遵守相关法律法规
- 请勿用于任何侵犯版权或违法的目的

## License

MIT
