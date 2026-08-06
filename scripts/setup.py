#!/usr/bin/env python3
"""
douyin-video skill 环境自动安装脚本

一键完成：
  1. 检查 Python 版本
  2. 安装 pip 依赖（requests, ffmpeg-python）
  3. 安装 FFmpeg 二进制
  4. 验证安装结果
  5. 提示配置 API Key

使用方法：
  python setup.py
"""

import sys
import subprocess
import os
from pathlib import Path

MIN_PYTHON = (3, 8)
PIP_PACKAGES = ["requests", "ffmpeg-python"]
PIP_INDEX_URL = "https://pypi.tuna.tsinghua.edu.cn/simple"
PYTHON_DIR = Path(sys.executable).parent
FFMPEG_TARGET = PYTHON_DIR / "Scripts" / "ffmpeg.exe"


def check_python_version():
    """检查 Python 版本"""
    version = sys.version_info[:2]
    if version < MIN_PYTHON:
        print(f"[ERROR] 需要 Python {MIN_PYTHON[0]}.{MIN_PYTHON[1]}+，当前版本: {sys.version}")
        sys.exit(1)
    print(f"[OK] Python {sys.version.split()[0]}")


def run_command(cmd, description=""):
    """执行命令并返回是否成功"""
    print(f"\n[RUN] {description or cmd}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[WARN] 命令返回非零状态: {result.stderr.strip()[:200]}")
        return False
    print("[OK]")
    return True


def install_pip_packages():
    """安装 pip 依赖"""
    print("\n=== 安装 Python 依赖 ===")
    for pkg in PIP_PACKAGES:
        cmd = f'"{sys.executable}" -m pip install {pkg} -i {PIP_INDEX_URL} --quiet'
        run_command(cmd, f"安装 {pkg}")


def install_ffmpeg():
    """安装 FFmpeg 二进制"""
    print("\n=== 安装 FFmpeg ===")

    if FFMPEG_TARGET.exists():
        print(f"[SKIP] FFmpeg 已存在: {FFMPEG_TARGET}")
        return True

    # 通过 imageio-ffmpeg 获取 Gyan build 的 FFmpeg 二进制
    run_command(
        f'"{sys.executable}" -m pip install imageio-ffmpeg -i {PIP_INDEX_URL} --quiet',
        "安装 imageio-ffmpeg（获取 FFmpeg 二进制）"
    )

    # 查找 site-packages 中的 ffmpeg 二进制
    import site
    site_packages = Path(site.getsitepackages()[0])
    ffmpeg_binaries = list(site_packages.glob("imageio_ffmpeg/binaries/ffmpeg*.exe"))

    if not ffmpeg_binaries:
        print("[ERROR] 未找到 FFmpeg 二进制文件")
        return False

    source = ffmpeg_binaries[0]
    print(f"[INFO] 找到 FFmpeg: {source.name} ({source.stat().st_size / 1024 / 1024:.1f} MB)")

    # 拷贝到 Scripts 目录
    FFMPEG_TARGET.parent.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy2(source, FFMPEG_TARGET)
    print(f"[OK] FFmpeg 已安装到: {FFMPEG_TARGET}")

    # 卸载搬运工包
    run_command(
        f'"{sys.executable}" -m pip uninstall -y imageio-ffmpeg --quiet',
        "卸载 imageio-ffmpeg（二进制已独立）"
    )

    return True


def verify_installation():
    """验证所有依赖已正确安装"""
    print("\n=== 验证安装 ===")

    all_ok = True

    # 检查 pip 包
    for pkg in PIP_PACKAGES:
        try:
            if pkg == "ffmpeg-python":
                __import__("ffmpeg")
            else:
                __import__(pkg)
            print(f"[OK] {pkg}")
        except ImportError:
            print(f"[FAIL] {pkg} 未安装")
            all_ok = False

    # 检查 FFmpeg 二进制
    if FFMPEG_TARGET.exists():
        print(f"[OK] FFmpeg 二进制: {FFMPEG_TARGET.name}")
    else:
        print(f"[FAIL] FFmpeg 二进制不存在: {FFMPEG_TARGET}")
        all_ok = False

    # 检查 ffmpeg 是否在 PATH 中可调用
    try:
        import ffmpeg
        ffmpeg.probe("NUL")  # Windows 空设备，快速验证
    except Exception:
        try:
            # 可能不在 PATH，但 Scripts 目录里有
            result = subprocess.run(
                [str(FFMPEG_TARGET), "-version"],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                print("[OK] FFmpeg 可执行")
            else:
                print("[WARN] FFmpeg 执行测试失败，但文件存在")
        except Exception as e:
            print(f"[WARN] FFmpeg 验证异常: {e}")

    return all_ok


def prompt_api_key_setup():
    """提示用户配置 API Key"""
    print("\n=== API Key 配置 ===")
    print("语音识别需要硅基流动 API Key（免费）：")
    print("  1. 打开 https://cloud.siliconflow.cn/")
    print("  2. 注册账号（支持手机号/微信）")
    print("  3. 进入「API 密钥」页面，创建新密钥")
    print("  4. 将密钥粘贴给 Claude，或手动运行：")
    print(f'     python douyin_downloader.py --setup-key "你的密钥"')
    print()


def main():
    print("=" * 50)
    print("douyin-video skill 环境安装")
    print("=" * 50)

    check_python_version()
    install_pip_packages()
    install_ffmpeg()

    if verify_installation():
        print("\n" + "=" * 50)
        print("[SUCCESS] 环境安装完成！")
        print("=" * 50)
        prompt_api_key_setup()
    else:
        print("\n[WARN] 部分组件安装失败，请检查上方错误信息")
        sys.exit(1)


if __name__ == "__main__":
    main()
