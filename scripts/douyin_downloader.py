#!/usr/bin/env python3
"""
抖音无水印视频下载和文案提取工具

功能:
1. 从抖音分享链接获取无水印视频下载链接
2. 下载视频并提取音频
3. 使用硅基流动 API 从音频中提取文本
4. 自动保存文案到文件 (一个视频一个文件夹)

环境变量:
- API_KEY: 硅基流动 API 密钥 (用于文案提取功能)
- DOUYIN_API_KEY: 备用环境变量名

本地配置:
- ~/.douyin-video/config.json: 持久化 API Key（由 --setup-key 写入）

使用示例:
  # 获取下载链接 (无需 API 密钥)
  python douyin_downloader.py --link "抖音分享链接" --action info

  # 下载视频
  python douyin_downloader.py --link "抖音分享链接" --action download --output ./videos

  # 提取文案并保存到文件 (需要 API_KEY)
  python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output

  # 持久化 API Key（仅首次配置）
  python douyin_downloader.py --setup-key "你的硅基流动密钥"
"""

import os
import re
import sys
import json
import argparse
import tempfile
import shutil
from pathlib import Path
from typing import Optional
from datetime import datetime


def check_dependencies():
    """检查必要的依赖是否已安装"""
    missing = []
    try:
        import requests
    except ImportError:
        missing.append("requests")
    try:
        import ffmpeg
    except ImportError:
        missing.append("ffmpeg-python")

    if missing:
        print(f"缺少依赖: {', '.join(missing)}")
        print(f"请运行: pip install {' '.join(missing)}")
        sys.exit(1)


check_dependencies()

import requests
import ffmpeg

# 请求头，模拟移动端访问
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_2 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) EdgiOS/121.0.2277.107 Version/17.0 Mobile/15E148 Safari/604.1'
}

# 硅基流动 API 配置
DEFAULT_API_BASE_URL = "https://api.siliconflow.cn/v1/audio/transcriptions"
DEFAULT_MODEL = "FunAudioLLM/SenseVoiceSmall"

# 本地持久化配置目录
CONFIG_DIR_NAME = ".douyin-video"
CONFIG_FILE_NAME = "config.json"


def _get_config_dir() -> Path:
    """获取本地配置目录路径（跨平台）"""
    home = Path.home()
    return home / CONFIG_DIR_NAME


def _get_config_path() -> Path:
    """获取配置文件完整路径"""
    return _get_config_dir() / CONFIG_FILE_NAME


def load_persisted_api_key() -> Optional[str]:
    """
    从本地配置文件读取持久化的 API Key。

    查找顺序：
    1. 环境变量 API_KEY / DOUYIN_API_KEY（由 extract_text() 优先检查）
    2. ~/.douyin-video/config.json（本函数负责）

    返回:
        API Key 字符串，未配置则返回 None
    """
    config_path = _get_config_path()
    if not config_path.is_file():
        return None
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = json.load(f)
        return config.get('api_key')
    except (json.JSONDecodeError, OSError):
        return None


def save_api_key_to_config(api_key: str) -> Path:
    """
    将 API Key 持久化到本地配置文件。

    参数:
        api_key: 硅基流动 API 密钥

    返回:
        配置文件路径
    """
    config_dir = _get_config_dir()
    config_dir.mkdir(parents=True, exist_ok=True)
    config_path = config_dir / CONFIG_FILE_NAME
    config = {
        'api_key': api_key,
        'configured_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'note': '由 douyin-video skill 首次配置生成'
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    return config_path


class DouyinProcessor:
    """抖音视频处理器"""

    def __init__(self, api_key: str = "", api_base_url: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key
        self.api_base_url = api_base_url or DEFAULT_API_BASE_URL
        self.model = model or DEFAULT_MODEL
        self.temp_dir = Path(tempfile.mkdtemp())

    def __del__(self):
        """清理临时目录"""
        if hasattr(self, 'temp_dir') and self.temp_dir.exists():
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def parse_share_url(self, share_text: str) -> dict:
        """从分享文本中提取无水印视频链接"""
        # 提取分享链接
        urls = re.findall(r'http[s]?://(?:[a-zA-Z]|[0-9]|[$-_@.&+]|[!*\(\),]|(?:%[0-9a-fA-F][0-9a-fA-F]))+', share_text)
        if not urls:
            raise ValueError("未找到有效的分享链接")

        share_url = urls[0]
        share_response = requests.get(share_url, headers=HEADERS)
        video_id = share_response.url.split("?")[0].strip("/").split("/")[-1]

        # 从重定向 URL 判断帖子类型，使用正确的域名和路径
        final_url = share_response.url
        if '/share/note/' in final_url or '/note/' in final_url:
            share_url = f'https://www.douyin.com/share/note/{video_id}'
        else:
            share_url = f'https://www.douyin.com/share/video/{video_id}'

        # 获取视频页面内容
        response = requests.get(share_url, headers=HEADERS)
        response.raise_for_status()

        pattern = re.compile(
            pattern=r"window\._ROUTER_DATA\s*=\s*(.*?)</script>",
            flags=re.DOTALL,
        )
        find_res = pattern.search(response.text)

        if not find_res or not find_res.group(1):
            raise ValueError("从HTML中解析视频信息失败")

        # 解析JSON数据
        json_data = json.loads(find_res.group(1).strip())
        VIDEO_ID_PAGE_KEY = "video_(id)/page"
        NOTE_ID_PAGE_KEY = "note_(id)/page"

        if VIDEO_ID_PAGE_KEY in json_data["loaderData"]:
            original_video_info = json_data["loaderData"][VIDEO_ID_PAGE_KEY]["videoInfoRes"]
        elif NOTE_ID_PAGE_KEY in json_data["loaderData"]:
            original_video_info = json_data["loaderData"][NOTE_ID_PAGE_KEY]["videoInfoRes"]
        else:
            raise Exception("无法从JSON中解析视频或图集信息")

        data = original_video_info["item_list"][0]

        # 检测帖子类型：图文优先（图文帖子也有 video 字段，但只是背景音乐）
        if "images" in data and data["images"]:
            # 图文帖子
            images = data.get("images", [])
            image_urls = []
            for img in images:
                url_list = img.get("url_list", [])
                if url_list:
                    image_urls.append(url_list[0])

            desc = data.get("desc", "").strip() or f"douyin_note_{video_id}"
            desc = re.sub(r'[\\/:*?"<>|]', '_', desc)

            return {
                "url": None,
                "title": desc,
                "video_id": video_id,
                "type": "note",
                "images": image_urls,
                "text_content": data.get("desc", "")
            }
        elif "video" in data and "play_addr" in data.get("video", {}):
            # 视频帖子
            video_url = data["video"]["play_addr"]["url_list"][0].replace("playwm", "play")
            desc = data.get("desc", "").strip() or f"douyin_{video_id}"
            desc = re.sub(r'[\\/:*?"<>|]', '_', desc)

            return {
                "url": video_url,
                "title": desc,
                "video_id": video_id,
                "type": "video"
            }
        else:
            raise Exception("无法识别的帖子类型：既不是视频也不是图文")

    def download_video(self, video_info: dict, output_dir: Optional[Path] = None, show_progress: bool = True) -> Path:
        """下载视频"""
        if output_dir is None:
            output_dir = self.temp_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{video_info['video_id']}.mp4"
        filepath = output_dir / filename

        if show_progress:
            print(f"正在下载视频: {video_info['title']}")

        response = requests.get(video_info['url'], headers=HEADERS, stream=True)
        response.raise_for_status()

        # 获取文件大小
        total_size = int(response.headers.get('content-length', 0))

        # 下载文件
        downloaded = 0
        with open(filepath, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
                    downloaded += len(chunk)
                    if show_progress and total_size > 0:
                        progress = downloaded / total_size * 100
                        print(f"\r下载进度: {progress:.1f}%", end="", flush=True)

        if show_progress:
            print(f"\n视频下载完成: {filepath}")
        return filepath

    def download_images(self, note_info: dict, output_dir: Optional[Path] = None, show_progress: bool = True) -> list:
        """下载图文帖子的所有图片"""
        if output_dir is None:
            output_dir = self.temp_dir
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

        image_urls = note_info.get("images", [])
        if not image_urls:
            return []

        image_paths = []

        for i, img_url in enumerate(image_urls):
            # 根据 URL 推断图片格式
            if ".webp" in img_url:
                ext = "webp"
            elif ".png" in img_url:
                ext = "png"
            else:
                ext = "jpg"

            filename = f"image_{i + 1:03d}.{ext}"
            filepath = output_dir / filename

            try:
                response = requests.get(img_url, headers=HEADERS, stream=True)
                response.raise_for_status()

                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                image_paths.append(filepath)
                if show_progress:
                    print(f"\r图片下载进度: {i + 1}/{len(image_urls)}", end="", flush=True)

            except Exception as e:
                if show_progress:
                    print(f"\n下载图片 {i + 1} 失败: {e}")

        if show_progress and image_paths:
            print(f"\n图片下载完成: {len(image_paths)}/{len(image_urls)} 张")

        return image_paths

    def extract_audio(self, video_path: Path, show_progress: bool = True) -> Path:
        """从视频文件中提取音频"""
        audio_path = video_path.with_suffix('.mp3')

        if show_progress:
            print("正在提取音频...")
        try:
            (
                ffmpeg
                .input(str(video_path))
                .output(str(audio_path), acodec='libmp3lame', q=0)
                .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
            )
            if show_progress:
                print(f"音频提取完成: {audio_path}")
            return audio_path
        except Exception as e:
            raise Exception(f"提取音频时出错: {str(e)}")

    def get_audio_info(self, audio_path: Path) -> dict:
        """获取音频文件信息（时长和大小）"""
        try:
            probe = ffmpeg.probe(str(audio_path))
            duration = float(probe['format'].get('duration', 0))
            size = audio_path.stat().st_size
            return {'duration': duration, 'size': size}
        except Exception:
            return {'duration': 0, 'size': audio_path.stat().st_size}

    def split_audio(self, audio_path: Path, segment_duration: int = 600, show_progress: bool = True) -> list:
        """
        将音频分割成多个片段

        参数:
            audio_path: 音频文件路径
            segment_duration: 每段时长（秒），默认 10 分钟
            show_progress: 是否显示进度

        返回:
            分割后的音频文件路径列表
        """
        audio_info = self.get_audio_info(audio_path)
        duration = audio_info['duration']

        if duration <= segment_duration:
            return [audio_path]

        segments = []
        segment_index = 0
        current_time = 0

        if show_progress:
            total_segments = int(duration / segment_duration) + 1
            print(f"音频时长 {duration:.0f} 秒，将分割为 {total_segments} 段...")

        while current_time < duration:
            segment_path = self.temp_dir / f"segment_{segment_index}.mp3"

            try:
                (
                    ffmpeg
                    .input(str(audio_path), ss=current_time, t=segment_duration)
                    .output(str(segment_path), acodec='libmp3lame', q=0)
                    .run(capture_stdout=True, capture_stderr=True, overwrite_output=True)
                )
                segments.append(segment_path)

                if show_progress:
                    print(f"  分割片段 {segment_index + 1}: {current_time:.0f}s - {min(current_time + segment_duration, duration):.0f}s")

            except Exception as e:
                raise Exception(f"分割音频片段 {segment_index} 时出错: {str(e)}")

            current_time += segment_duration
            segment_index += 1

        return segments

    def transcribe_single_audio(self, audio_path: Path) -> str:
        """转录单个音频文件"""
        files = {
            'file': (audio_path.name, open(audio_path, 'rb'), 'audio/mpeg'),
            'model': (None, self.model)
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        try:
            response = requests.post(self.api_base_url, files=files, headers=headers)
            response.raise_for_status()

            result = response.json()
            if 'text' in result:
                return result['text']
            else:
                return response.text

        except Exception as e:
            raise Exception(f"提取文字时出错: {str(e)}")
        finally:
            files['file'][1].close()

    def extract_text_from_audio(self, audio_path: Path, show_progress: bool = True) -> str:
        """从音频文件中提取文字（支持大文件自动分段）"""
        if not self.api_key:
            raise ValueError("未设置 API 密钥，请设置环境变量 API_KEY")

        # 检查文件大小和时长
        audio_info = self.get_audio_info(audio_path)
        max_duration = 3600  # 1 小时
        max_size = 50 * 1024 * 1024  # 50MB

        # 判断是否需要分段
        need_split = audio_info['duration'] > max_duration or audio_info['size'] > max_size

        if not need_split:
            # 文件在限制范围内，直接处理
            if show_progress:
                print("正在识别语音...")
            return self.transcribe_single_audio(audio_path)

        # 需要分段处理
        if show_progress:
            print(f"音频文件较大（时长: {audio_info['duration']:.0f}秒, 大小: {audio_info['size'] / 1024 / 1024:.1f}MB）")
            print("将自动分段处理...")

        # 分割音频
        segments = self.split_audio(audio_path, segment_duration=540, show_progress=show_progress)  # 9分钟一段，留余量

        # 逐段转录
        all_texts = []
        for i, segment_path in enumerate(segments):
            if show_progress:
                print(f"正在识别第 {i + 1}/{len(segments)} 段...")

            text = self.transcribe_single_audio(segment_path)
            all_texts.append(text)

            # 清理分段文件
            if segment_path != audio_path:
                self.cleanup_files(segment_path)

        # 合并文本
        merged_text = ''.join(all_texts)

        if show_progress:
            print(f"语音识别完成，共处理 {len(segments)} 个片段")

        return merged_text

    def cleanup_files(self, *file_paths: Path):
        """清理指定的文件"""
        for file_path in file_paths:
            if file_path.exists():
                file_path.unlink()


def get_video_info(share_link: str) -> dict:
    """获取视频信息和下载链接"""
    processor = DouyinProcessor()
    return processor.parse_share_url(share_link)


def download_video(share_link: str, output_dir: str = ".") -> Path:
    """下载视频到指定目录"""
    processor = DouyinProcessor()
    video_info = processor.parse_share_url(share_link)
    return processor.download_video(video_info, Path(output_dir))


def extract_text(share_link: str, api_key: Optional[str] = None, output_dir: Optional[str] = None,
                 save_video: bool = False, show_progress: bool = True) -> dict:
    """
    从视频或图文帖子中提取文案并保存到文件

    返回:
        dict: 包含 info, text, output_path 的字典
    """
    processor = DouyinProcessor()

    if show_progress:
        print("正在解析抖音分享链接...")
    info = processor.parse_share_url(share_link)
    post_type = info.get("type", "video")

    result = {
        "info": info,
        "text": None,
        "output_path": None
    }

    if post_type == "video":
        # === 视频帖子流程 ===
        api_key = api_key or os.getenv('API_KEY') or os.getenv('DOUYIN_API_KEY')
        if not api_key:
            api_key = load_persisted_api_key()
        if not api_key:
            raise ValueError(
                "未设置 API 密钥。请通过以下方式之一配置：\n"
                "  1. 环境变量：setx API_KEY \"你的密钥\"（Windows）或 export API_KEY=\"你的密钥\"（macOS/Linux）\n"
                "  2. 首次配置：在对话中发送 API Key，Claude 会帮你持久化到 ~/.douyin-video/config.json\n"
                "获取密钥：https://cloud.siliconflow.cn/"
            )

        processor = DouyinProcessor(api_key)

        if show_progress:
            print("正在下载视频...")
        video_path = processor.download_video(info, show_progress=show_progress)

        if show_progress:
            print("正在提取音频...")
        audio_path = processor.extract_audio(video_path, show_progress=show_progress)

        if show_progress:
            print("正在从音频中提取文本...")
        text_content = processor.extract_text_from_audio(audio_path, show_progress=show_progress)
        result["text"] = text_content

    elif post_type == "note":
        # === 图文帖子流程 ===
        if show_progress:
            print(f"检测到图文帖子（{len(info.get('images', []))} 张图片）")

        text_content = info.get("text_content", "")
        result["text"] = text_content

        # 下载图片（保存到输出目录）
        image_paths = []
        if info.get("images"):
            if output_dir:
                post_folder = Path(output_dir) / info['video_id']
                post_folder.mkdir(parents=True, exist_ok=True)
            else:
                post_folder = processor.temp_dir

            if show_progress:
                print("正在下载图片...")
            image_paths = processor.download_images(info, output_dir=post_folder, show_progress=show_progress)

        result["image_paths"] = image_paths

    # 保存到文件
    if output_dir:
        output_base = Path(output_dir)
        post_folder = output_base / info['video_id']
        post_folder.mkdir(parents=True, exist_ok=True)

        # 保存文案为 Markdown 格式
        transcript_path = post_folder / "transcript.md"
        with open(transcript_path, 'w', encoding='utf-8') as f:
            f.write(f"# {info['title']}\n\n")
            f.write(f"| 属性 | 值 |\n")
            f.write(f"|------|----|\n")
            f.write(f"| 类型 | {'视频' if post_type == 'video' else '图文'} |\n")
            f.write(f"| ID | `{info['video_id']}` |\n")
            f.write(f"| 提取时间 | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} |\n")
            if post_type == "video":
                f.write(f"| 下载链接 | [点击下载]({info['url']}) |\n")
            f.write(f"\n---\n\n")

            if post_type == "video":
                f.write(f"## 文案内容\n\n")
                f.write(text_content or "（无文案）")
            else:
                f.write(f"## 正文内容\n\n")
                f.write(text_content or "（无正文）")
                f.write(f"\n\n")

                if result.get("image_paths"):
                    f.write(f"## 原始图片\n\n")
                    for i, img_path in enumerate(result["image_paths"], 1):
                        rel_path = Path(img_path).name
                        f.write(f"![图片{i}]({rel_path})\n\n")

        result["output_path"] = str(post_folder)

        if show_progress:
            print(f"内容已保存到: {transcript_path}")

    # 清理临时文件（仅视频帖子）
    if post_type == "video":
        if show_progress:
            print("正在清理临时文件...")
        processor.cleanup_files(video_path, audio_path)

    return result


def main():
    parser = argparse.ArgumentParser(
        description="抖音无水印视频下载和文案提取工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取视频信息和下载链接
  python douyin_downloader.py --link "抖音分享链接" --action info

  # 下载视频
  python douyin_downloader.py --link "抖音分享链接" --action download --output ./videos

  # 提取文案并保存到文件 (需要设置 API_KEY 环境变量)
  python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output

  # 提取文案并同时保存视频
  python douyin_downloader.py --link "抖音分享链接" --action extract --output ./output --save-video
        """
    )
    parser.add_argument("--link", "-l", help="抖音分享链接或包含链接的文本（--setup-key 模式下不需要）")
    parser.add_argument("--action", "-a", choices=["info", "download", "extract"],
                        default=None, help="操作类型: info(获取信息), download(下载视频), extract(提取文案)。--setup-key 模式下不需要")
    parser.add_argument("--output", "-o", default="./output", help="输出目录 (默认 ./output)")
    parser.add_argument("--api-key", "-k", help="硅基流动 API 密钥 (也可通过 API_KEY 环境变量设置)")
    parser.add_argument("--setup-key", "-K", help="将 API 密钥持久化到本地配置（仅首次使用）")
    parser.add_argument("--save-video", "-v", action="store_true", help="提取文案时同时保存视频")
    parser.add_argument("--quiet", "-q", action="store_true", help="安静模式，减少输出")

    args = parser.parse_args()

    # --setup-key 模式不需要 link
    if not args.setup_key and not args.link:
        parser.error("--link 是必需的（除非使用 --setup-key）")

    try:
        if args.setup_key:
            config_path = save_api_key_to_config(args.setup_key)
            print(f"API Key 已持久化到: {config_path}")
            print("此后使用 douyin-video skill 时无需再次配置。")
            sys.exit(0)

        if args.action == "info":
            info = get_video_info(args.link)
            post_type = info.get("type", "video")
            print("\n" + "=" * 50)
            print("帖子信息:")
            print("=" * 50)
            print(f"类型: {'视频' if post_type == 'video' else '图文'}")
            print(f"ID: {info['video_id']}")
            print(f"标题: {info['title']}")
            if post_type == "video":
                print(f"下载链接: {info['url']}")
            elif info.get("images"):
                print(f"图片数量: {len(info['images'])}")
            print("=" * 50)

        elif args.action == "download":
            video_path = download_video(args.link, args.output)
            print(f"\n视频已保存到: {video_path}")

        elif args.action == "extract":
            result = extract_text(
                args.link,
                args.api_key,
                output_dir=args.output,
                save_video=args.save_video,
                show_progress=not args.quiet
            )

            if not args.quiet:
                info = result["info"]
                post_type = info.get("type", "video")
                print("\n" + "=" * 50)
                print("提取完成!")
                print("=" * 50)
                print(f"类型: {'视频' if post_type == 'video' else '图文'}")
                print(f"ID: {info['video_id']}")
                print(f"标题: {info['title']}")
                if post_type == "video":
                    print(f"文案: {result['text'][:200]}...")
                elif result.get("image_paths"):
                    print(f"图片: {len(result['image_paths'])} 张已下载")
                    print(f"正文: {result['text'][:200]}...")
                if result['output_path']:
                    print(f"保存位置: {result['output_path']}")
                print("=" * 50)

    except Exception as e:
        print(f"\n错误: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
