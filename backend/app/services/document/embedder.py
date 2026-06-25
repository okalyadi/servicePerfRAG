from typing import List
from sentence_transformers import SentenceTransformer

_model = SentenceTransformer("all-MiniLM-L6-v2")


def embed_texts(texts: List[str]) -> List[List[float]]:
    return _model.encode(texts, convert_to_numpy=True).tolist()


def embed_query(text: str) -> List[float]:
    return embed_texts([text])[0]
