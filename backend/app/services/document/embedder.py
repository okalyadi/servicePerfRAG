from typing import List
from fastembed import TextEmbedding

_model = TextEmbedding("BAAI/bge-small-en-v1.5")


def embed_texts(texts: List[str]) -> List[List[float]]:
    return [v.tolist() for v in _model.embed(texts)]


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
