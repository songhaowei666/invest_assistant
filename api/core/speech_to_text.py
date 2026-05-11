"""
语音转文字：通过 OpenAI Audio Transcriptions（whisper-1）将本地音频转为文本。
"""

import sys
from pathlib import Path

# 直接运行本文件时（非 python -m），把 api 目录加入路径以便找到 core 包
_api_dir = Path(__file__).resolve().parent.parent
_api_dir_str = str(_api_dir)
if _api_dir_str not in sys.path:
    sys.path.insert(0, _api_dir_str)

from openai import OpenAI

from configs.config import settings


def transcribe_audio_file(
    audio_path: str | Path,
    *,
    model: str = "whisper-1",
    language: str | None = None,
) -> str:
    """
    将本地音频文件转写为文本。

    :param audio_path: 音频文件路径（支持 mp3、m4a、wav、webm 等 OpenAI 支持的格式）
    :param model: 转写模型，默认 whisper-1
    :param language: 可选，ISO-639-1 语言代码（如 zh、en），不传则由模型自动判断
    :return: 识别得到的纯文本
    """
    path = Path(audio_path)
    client = OpenAI(api_key=settings.OPENAI_API_KEY)
    with path.open("rb") as audio_file:
        kwargs: dict = {"model": model, "file": audio_file}
        if language:
            kwargs["language"] = language
        result = client.audio.transcriptions.create(**kwargs)
    return result.text


def _demo_example() -> None:
    """
    简单示例：对指定 wav/mp3 等文件做一次转写并打印结果。
    用法：python speech_to_text.py <音频路径>，或 cd api 后 python -m core.speech_to_text <音频路径>
    """

    if len(sys.argv) < 2:
        print("示例用法：python api/core/speech_to_text.py <音频文件路径>")
        print("或：cd api && python -m core.speech_to_text <音频文件路径>")
        print("请先在 .env 中配置 OPENAI_API_KEY。")
        return
    file_arg = sys.argv[1]
    text = transcribe_audio_file(file_arg, language="zh")
    print("转写结果：")
    print(text)


if __name__ == "__main__":
    _demo_example()
