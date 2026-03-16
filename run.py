# -*- coding: utf-8 -*-
"""
启动脚本 — 在运行 Flask 应用前检查并收集必要的 API Key。

使用方式：
    python run.py

也可通过环境变量或 .env 文件预先配置，跳过交互式输入：
    OMDB_API_KEY=xxxx  LLM_API_KEY=xxxx  python run.py
"""

import os
import sys
import getpass


# ─────────────────────────────────────────────
#  必要 API Key 定义
#  每项：(env_var_name, display_name, hint, is_secret)
# ─────────────────────────────────────────────
REQUIRED_KEYS = [
    (
        "OMDB_API_KEY",
        "OMDb API Key",
        "从 http://www.omdbapi.com/apikey.aspx 免费申请",
        True,
    ),
    (
        "LLM_API_KEY",
        "大模型 API Key",
        "用于电影名称中英互译（如 OpenAI / DeepSeek 等兼容 API 的 Key）",
        True,
    ),
    (
        "LLM_API_URL",
        "大模型 API 地址（Base URL）",
        "如 https://api.openai.com/v1  或其他兼容 OpenAI 格式的地址",
        False,
    ),
]

OPTIONAL_KEYS = [
    (
        "LLM_MODEL",
        "大模型名称（可选，留空使用默认值 gpt-4o-mini）",
        "如 gpt-4o / deepseek-chat / glm-4 等",
        False,
    ),
]


def _load_dotenv_if_exists():
    """尝试加载 .env 文件（如果 dotenv 可用）。"""
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass


def _prompt_key(env_name, display_name, hint, is_secret):
    """提示用户输入单个 Key，返回输入值（空字符串表示跳过/使用默认）。"""
    print(f"\n  [*]  {display_name}")
    print(f"       提示：{hint}")
    prompt_text = f"  请输入 {env_name}："
    try:
        if is_secret:
            value = getpass.getpass(prompt_text)
        else:
            value = input(prompt_text).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        value = ""
    return value.strip()


def collect_api_keys():
    """
    检查并收集所有必要的 API Key。
    - 已在环境变量（或 .env）中设置的跳过询问。
    - 缺少的交互式询问用户输入。
    """
    _load_dotenv_if_exists()

    missing = []
    for env_name, display_name, hint, is_secret in REQUIRED_KEYS:
        if not os.environ.get(env_name):
            missing.append((env_name, display_name, hint, is_secret))

    if missing:
        print("\n" + "=" * 60)
        print("  [KEY]  需要输入以下 API Key 才能启动应用")
        print("  （已在环境变量或 .env 文件中配置的项将自动跳过）")
        print("=" * 60)

        for env_name, display_name, hint, is_secret in missing:
            while True:
                value = _prompt_key(env_name, display_name, hint, is_secret)
                if value:
                    os.environ[env_name] = value
                    break
                else:
                    print(f"  [!]  {env_name} 不能为空，请重新输入。")

    # 可选 Key
    for env_name, display_name, hint, is_secret in OPTIONAL_KEYS:
        if not os.environ.get(env_name):
            value = _prompt_key(env_name, display_name, hint, is_secret)
            if value:
                os.environ[env_name] = value
            else:
                default = "gpt-4o-mini"
                os.environ.setdefault(env_name, default)
                print(f"  [i]  {env_name} 使用默认值：{default}")

    print("\n  [OK]  所有 API Key 已就绪，正在启动应用...\n")


def main():
    collect_api_keys()

    # 在设置好环境变量之后再导入 app，保证 config.py / movie_translator.py
    # 能够读取到正确的环境变量
    from app import app
    from config import Config

    host = Config.HOST
    port = Config.PORT
    debug = Config.DEBUG

    print(f"  [>>]  Flask 应用启动中  ->  http://{host}:{port}")
    app.run(debug=debug, host=host, port=port)


if __name__ == "__main__":
    main()
