"""
Embedding service for Memory Anchor.
使用 fastembed 生成本地 embedding 向量（隐私优先）。
"""
from functools import lru_cache
from typing import List

from fastembed import TextEmbedding


# 使用 multilingual-e5-large 模型（支持中文，1024维）
# 也可以使用 BAAI/bge-small-zh-v1.5（中文优化，512维）
MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
# 输出维度：384（比 3072 小，但对于 MVP 足够）


@lru_cache(maxsize=1)
def get_embedding_model() -> TextEmbedding:
    """
    获取 embedding 模型实例（单例）。
    首次调用会下载模型（约 100MB）。
    """
    return TextEmbedding(model_name=MODEL_NAME)


def embed_text(text: str) -> List[float]:
    """
    为单个文本生成 embedding 向量。

    Args:
        text: 要嵌入的文本

    Returns:
        embedding 向量（384维）
    """
    model = get_embedding_model()
    embeddings = list(model.embed([text]))
    emb = embeddings[0]
    return emb.tolist() if hasattr(emb, "tolist") else list(emb)


def embed_batch(texts: List[str]) -> List[List[float]]:
    """
    批量生成 embedding 向量。

    Args:
        texts: 文本列表

    Returns:
        embedding 向量列表
    """
    if not texts:
        return []

    model = get_embedding_model()
    embeddings = list(model.embed(texts))
    return [emb.tolist() if hasattr(emb, "tolist") else list(emb) for emb in embeddings]


# 导出
__all__ = ["embed_text", "embed_batch", "MODEL_NAME"]
