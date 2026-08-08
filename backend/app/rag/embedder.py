from sentence_transformers import SentenceTransformer

from app.config import settings


class Embedder:
    def __init__(self):
        self.model = SentenceTransformer(settings.EMBEDDING_MODEL)
        
    def embed_text(self, text: str):
        return self.model.encode(text).tolist()
        
embedder = Embedder()
