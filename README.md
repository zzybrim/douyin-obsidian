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

## 快速开始

### 1. 安装依赖

```bash
git clone https://github.com/zzybrim/douyin-obsidian.git
cd douyin-obsidian
python scripts/setup.py
```

### 2. 配置 API Key（仅视频帖子需要）

```bash
python scripts/douyin_downloader.py --setup-key "你的硅基流动 API 密钥"
```

> 硅基流动 API 密钥免费获取：[https://cloud.siliconflow.cn/](https://cloud.siliconflow.cn/)

### 3. 使用示例

```bash
# 查看帖子信息（无需 API Key）
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action info

# 下载视频
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action download --output ./videos

# 提取文案（需要 API Key）
python scripts/douyin_downloader.py --link "https://v.douyin.com/xxxxx/" --action extract --output ./output
```

## 输出结构

```
output/
├── <视频ID>/
│   ├── transcript.md      # 文案内容
│   └── <视频ID>.mp4       # 视频文件（使用 --save-video 时保存）
└── ...
```

## 技术栈

- Python 3.8+
- requests
- ffmpeg-python
- 硅基流动 API（语音识别）

## 安装依赖

### 自动安装（推荐）

```bash
python scripts/setup.py
```

### 手动安装

```bash
pip install requests ffmpeg-python -i https://pypi.tuna.tsinghua.edu.cn/simple
```

## 作为 AI Agent Skill 使用

本 skill 适用于 **Claude Code**、**Codex CLI** 等支持 skill 规范的 AI Agent 工具。

### Claude Code / Codex CLI

将本仓库克隆到 AI Agent 工具的 skills 目录下：

```bash
# Claude Code
git clone https://github.com/zzybrim/douyin-obsidian.git ~/.claude/skills/douyin-obsidian

# Codex CLI（项目级）
git clone https://github.com/zzybrim/douyin-obsidian.git .codex/skills/douyin-obsidian
```

配置完成后，向 Agent 发送抖音链接即可自动调用：

> 把这个视频转成文字：https://v.douyin.com/xxxxx/

### Obsidian 用户

在 Obsidian 中使用此 skill，推荐通过 **Obsidian 的 AI 插件**（如 claudian、Copilot、Smart Connections 等支持 skill 规范的插件）来调用，将本 skill 安装到对应插件的 skill 目录即可。

## 安全说明

- API Key 仅保存在本地 `~/.douyin-video/config.json`，不会上传
- 仅通过 HTTPS 发送给硅基流动 API
- 不包含 `subprocess`/`socket`/`pickle`/`eval`/`exec` 等危险调用
- 图文帖子不涉及任何 API 调用，仅提取公开数据

## 注意事项

- 仅供学习和研究使用
- 使用时需遵守相关法律法规
- 请勿用于任何侵犯版权或违法的目的

## License

MIT
