"""
电影名称翻译工具
使用大模型 API 在中英文电影名称之间进行权威翻译
"""
import re
import requests


# ------------------------------------------------------------------ #
#  大模型 API 配置 — 通过环境变量读取，禁止硬编码
#  请使用 run.py 启动（会交互式提示输入），或提前设置环境变量：
#    LLM_API_KEY   大模型 API Key
#    LLM_API_URL   大模型 Base URL（如 https://api.openai.com/v1）
#    LLM_MODEL     模型名称（可选，默认 gpt-4o-mini）
# ------------------------------------------------------------------ #
import os as _os

def _get_llm_config():
    """运行时读取环境变量，保证 run.py 设置好 env 后才取值。"""
    return (
        _os.environ.get("LLM_API_URL", "").rstrip("/"),
        _os.environ.get("LLM_API_KEY", ""),
        _os.environ.get("LLM_MODEL", "gpt-4o-mini"),
    )


def _contains_chinese(text: str) -> bool:
    """检测字符串中是否含有中文字符"""
    return bool(re.search(r'[\u4e00-\u9fff]', text))


def _call_llm(prompt: str) -> str | None:
    """
    向大模型 API 发送单轮对话请求，返回模型回复文本。
    如果请求失败则返回 None。
    """
    llm_api_url, llm_api_key, llm_model = _get_llm_config()

    if not llm_api_url or not llm_api_key:
        print("[Translator] 未配置 LLM_API_URL 或 LLM_API_KEY，跳过翻译")
        return None

    headers = {
        "Authorization": f"Bearer {llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": llm_model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "你是一个专业的电影名称翻译助手。"
                    "请只输出译名本身，不要加任何解释、标点或额外文字。"
                    "如果有多个常见译名，只输出最权威、最广泛使用的一个。"
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0.0,   # 保持确定性输出
        "max_tokens": 60,
    }

    try:
        resp = requests.post(f"{llm_api_url}/chat/completions", json=payload, headers=headers, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        translated = data["choices"][0]["message"]["content"].strip()
        return translated
    except Exception as e:
        print(f"[Translator] LLM API 请求失败: {e}")
        return None


def translate_movie_name(movie_name: str) -> str | None:
    """
    将电影名称翻译为对应语言的权威译名。

    - 输入英文 → 输出大陆权威中文译名
    - 输入中文 → 输出英语世界权威英文译名

    :param movie_name: 电影名称（中文或英文）
    :return: 翻译结果字符串，翻译失败返回 None
    """
    movie_name = movie_name.strip()
    if not movie_name:
        return None

    if _contains_chinese(movie_name):
        # 中文 → 英文
        prompt = (
            f"请你给出这个电影中文名称在英语世界对应的权威英文译名：《{movie_name}》"
        )
        direction = f"中文→英文"
    else:
        # 英文 → 中文
        prompt = (
            f"请你给出这个电影英文名称在大陆对应的权威中文译名：{movie_name}"
        )
        direction = f"英文→中文"

    print(f"[Translator] 翻译请求（{direction}）: {movie_name}")
    result = _call_llm(prompt)
    if result:
        print(f"[Translator] 翻译结果: {result}")
    return result


def get_omdb_name(movie_name: str) -> str:
    """
    给定任意语言的电影名，返回适合 OMDb 搜索的英文名。
    如果输入已是英文则直接返回；如果是中文则翻译为英文。
    失败时返回原始输入。

    :param movie_name: 电影名称
    :return: 英文电影名
    """
    if not _contains_chinese(movie_name):
        return movie_name  # 已是英文
    translated = translate_movie_name(movie_name)
    return translated if translated else movie_name


def get_douban_name(movie_name: str) -> str:
    """
    给定任意语言的电影名，返回适合豆瓣搜索的中文名。
    如果输入已是中文则直接返回；如果是英文则翻译为中文。
    失败时返回原始输入。

    :param movie_name: 电影名称
    :return: 中文电影名
    """
    if _contains_chinese(movie_name):
        return movie_name  # 已是中文
    translated = translate_movie_name(movie_name)
    return translated if translated else movie_name


# ------------------------------------------------------------------ #
#  测试代码
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    tests = [
        "Inception",
        "The Shawshank Redemption",
        "Interstellar",
        "盗梦空间",
        "肖申克的救赎",
        "星际穿越",
    ]
    for name in tests:
        result = translate_movie_name(name)
        print(f"  {name}  →  {result}")
        print()
