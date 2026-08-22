#!/usr/bin/env python3
"""抖音一键提取管线：标准解析优先，反爬时自动降级浏览器方案

管线流程:
  1. 标准解析 (douyin_downloader.parse_share_url, 依赖页面 _ROUTER_DATA)
  2. 解析失败 (抖音 2026 反爬 JSVM 壳) → 自动降级浏览器方案:
     真实 Chrome 建立 session → 手动调用 detail API (带冷却重试, 风控 403 自动重试)
  3. 视频帖子: 下载无水印视频 → 提取音频 → 语音识别 → transcript
     图文帖子: 提取正文 → 批量下载图片

用法:
  uv run python .claude/skills/douyin-obsidian/scripts/douyin_pipeline.py \
    --link "<抖音分享链接>" [--action info|extract] [--output <目录>] [--quiet]

示例:
  # 只获取帖子信息（标准解析失败会自动降级浏览器方案，无需 API Key）
  uv run python .claude/skills/douyin-obsidian/scripts/douyin_pipeline.py \
    --link "https://v.douyin.com/xxxxx/" --action info

  # 完整管线（下载 + 转录，产物输出到指定目录）
  uv run python .claude/skills/douyin-obsidian/scripts/douyin_pipeline.py \
    --link "https://v.douyin.com/xxxxx/" --output "assets/<笔记名>" --quiet
"""
import argparse
import json
import sys
import time
from pathlib import Path

from douyin_downloader import DouyinProcessor, load_persisted_api_key
from douyin_browser_extract import extract as browser_extract

MAX_BROWSER_ATTEMPTS = 6


def _log(quiet: bool, msg: str):
    if not quiet:
        print(msg, flush=True)


def browser_info_with_retry(share_url: str, quiet: bool = False) -> dict:
    """浏览器提取帖子信息，带冷却重试（detail API 风控 403 时自动重试）"""
    info = None
    for attempt in range(1, MAX_BROWSER_ATTEMPTS + 1):
        _log(quiet, f"  浏览器提取 [{attempt}/{MAX_BROWSER_ATTEMPTS}]...")
        try:
            info = browser_extract(share_url)
        except Exception as e:
            _log(quiet, f"  异常: {e}")
        if info and (info.get("play_url") or info.get("images")):
            return info
        if attempt < MAX_BROWSER_ATTEMPTS:
            wait = 10 * attempt
            _log(quiet, f"  风控或未取到数据，{wait}s 后重试...")
            time.sleep(wait)
    return {}


def _to_video_info(browser_info: dict, share_url: str) -> dict:
    """浏览器返回 → downloader 兼容的 video_info"""
    return {
        "url": browser_info["play_url"],
        "video_id": browser_info["video_id"],
        "title": browser_info["desc"],
        "type": "video",
        "author": browser_info.get("author", ""),
        "duration_ms": browser_info.get("duration_ms", 0),
        "source_url": share_url,
    }


def _to_note_info(browser_info: dict, share_url: str) -> dict:
    """浏览器返回 → downloader 兼容的 note_info"""
    return {
        "url": None,
        "video_id": browser_info["video_id"],
        "title": browser_info["desc"],
        "type": "note",
        "images": browser_info.get("images", []),
        "text_content": browser_info.get("desc", ""),
        "author": browser_info.get("author", ""),
        "duration_ms": browser_info.get("duration_ms", 0),
        "source_url": share_url,
    }


def _save_meta(info: dict, share_url: str, out_dir: Path, degraded: bool):
    """保存帖子元信息到 video_info.json"""
    meta = {
        "video_id": info.get("video_id", ""),
        "desc": info.get("title") or info.get("text_content") or "",
        "author": info.get("author", ""),
        "duration_ms": info.get("duration_ms", 0),
        "url": share_url,
        "play_url": info.get("url") or "",
        "images": info.get("images", []),
        "degraded": degraded,
    }
    (out_dir / "video_info.json").write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def _video_transcript_md(info: dict, text: str) -> str:
    """视频帖子 transcript.md（含元数据表 + 逐字稿）"""
    return (
        f"# {info['title']}\n\n"
        f"| 属性 | 值 |\n"
        f"|------|----|\n"
        f"| 类型 | 视频 |\n"
        f"| ID | `{info['video_id']}` |\n"
        f"| 作者 | {info.get('author', '')} |\n"
        f"| 时长 | {round((info.get('duration_ms') or 0) / 1000)}s |\n\n"
        f"---\n\n"
        f"## 逐字稿\n\n{text}\n"
    )


def _note_transcript_md(info: dict, text: str, out_dir: Path) -> str:
    """图文帖子 transcript.md（含正文 + 图片引用）"""
    images = sorted(out_dir.glob("image_*"))
    image_refs = "\n".join(f"![图片{i + 1}]({img.name})" for i, img in enumerate(images))
    return (
        f"# {info['title']}\n\n"
        f"| 属性 | 值 |\n"
        f"|------|----|\n"
        f"| 类型 | 图文 |\n"
        f"| ID | `{info['video_id']}` |\n"
        f"| 作者 | {info.get('author', '')} |\n\n"
        f"---\n\n"
        f"## 正文内容\n\n{text}\n"
        f"{('## 原始图片\n\n' + image_refs + '\n') if image_refs else ''}"
    )


def process_video(processor: DouyinProcessor, video_info: dict, out_dir: Path, quiet: bool) -> str:
    """下载视频 → 提取音频 → 语音识别 → 保存 transcript"""
    out_dir.mkdir(parents=True, exist_ok=True)
    _log(quiet, "下载视频...")
    video_path = processor.download_video(video_info, out_dir, show_progress=not quiet)
    _log(quiet, "提取音频...")
    audio_path = processor.extract_audio(video_path, show_progress=not quiet)
    _log(quiet, "语音识别（硅基流动）...")
    text = processor.extract_text_from_audio(audio_path, show_progress=not quiet)
    (out_dir / "transcript_raw.txt").write_text(text, encoding="utf-8")
    (out_dir / "transcript.md").write_text(_video_transcript_md(video_info, text), encoding="utf-8")
    return text


def process_note(processor: DouyinProcessor, note_info: dict, out_dir: Path, quiet: bool) -> str:
    """图文帖子：下载图片 + 保存正文"""
    out_dir.mkdir(parents=True, exist_ok=True)
    images = note_info.get("images", [])
    if images:
        _log(quiet, f"下载图片 {len(images)} 张...")
        processor.download_images(note_info, out_dir, show_progress=not quiet)
    text = note_info.get("text_content", "")
    (out_dir / "transcript_raw.txt").write_text(text, encoding="utf-8")
    (out_dir / "transcript.md").write_text(
        _note_transcript_md(note_info, text, out_dir), encoding="utf-8")
    return text


def resolve_info(link: str, quiet: bool) -> tuple[dict, bool]:
    """解析帖子信息：标准解析优先，失败自动降级浏览器方案

    返回: (info, degraded)
    """
    processor = DouyinProcessor(api_key=load_persisted_api_key() or "")
    try:
        info = processor.parse_share_url(link)
        return info, False
    except Exception as e:
        _log(quiet, f"标准解析失败（{e}）")
        _log(quiet, "→ 抖音反爬 JSVM 壳，降级浏览器方案...")
        browser_info = browser_info_with_retry(link, quiet)
        if not browser_info:
            return None, True
        if browser_info.get("images"):
            return _to_note_info(browser_info, link), True
        return _to_video_info(browser_info, link), True


def main():
    parser = argparse.ArgumentParser(description="抖音一键提取管线（标准解析优先，反爬自动降级浏览器方案）")
    parser.add_argument("--link", required=True, help="抖音分享链接")
    parser.add_argument("--action", choices=["info", "extract"], default="extract",
                        help="info: 只获取帖子信息；extract: 完整提取（默认）")
    parser.add_argument("--output", "-o", default=".", help="产物输出目录（默认当前目录）")
    parser.add_argument("--quiet", action="store_true", help="安静模式（减少输出）")
    args = parser.parse_args()

    info, degraded = resolve_info(args.link, args.quiet)
    if not info:
        print("ERROR: 标准解析与浏览器方案均失败，请稍后重试", file=sys.stderr)
        sys.exit(1)

    if args.action == "info":
        print(json.dumps({k: v for k, v in info.items() if v is not None},
                         ensure_ascii=False, indent=2))
        return

    processor = DouyinProcessor(api_key=load_persisted_api_key() or "")
    out_dir = Path(args.output)
    if info.get("type") == "note":
        text = process_note(processor, info, out_dir, args.quiet)
    else:
        text = process_video(processor, info, out_dir, args.quiet)
    _save_meta(info, args.link, out_dir, degraded)
    mode = "浏览器降级" if degraded else "标准解析"
    _log(args.quiet, f"✅ 完成（{mode}），文案 {len(text)} 字，产物在 {out_dir}")


if __name__ == "__main__":
    main()
