import logging

from openai import AsyncOpenAI
from sqlalchemy import select, text, delete

from bot.database import async_session
from bot.models.embedding import DocumentEmbedding

logger = logging.getLogger(__name__)


class RAGService:
    def __init__(
        self,
        openai_api_key: str,
        embedding_model: str = "text-embedding-3-small",
        chunk_size: int = 800,
        chunk_overlap: int = 100,
        top_k: int = 5,
    ):
        self.client = AsyncOpenAI(api_key=openai_api_key)
        self.embedding_model = embedding_model
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.top_k = top_k

    def chunk_text(self, text_content: str) -> list[str]:
        """Split text into overlapping chunks."""
        if not text_content or not text_content.strip():
            return []

        chunks = []
        start = 0
        text_len = len(text_content)

        while start < text_len:
            end = start + self.chunk_size

            # Try to break at paragraph or sentence boundary
            if end < text_len:
                # Look for paragraph break
                para_break = text_content.rfind("\n\n", start, end)
                if para_break > start + self.chunk_size // 2:
                    end = para_break + 2
                else:
                    # Look for sentence break
                    for sep in (". ", ".\n", "! ", "? "):
                        sent_break = text_content.rfind(sep, start, end)
                        if sent_break > start + self.chunk_size // 2:
                            end = sent_break + len(sep)
                            break

            chunk = text_content[start:end].strip()
            if chunk:
                chunks.append(chunk)

            start = end - self.chunk_overlap
            if start >= text_len:
                break

        return chunks

    async def get_embedding(self, text_content: str) -> list[float]:
        """Get embedding vector for text."""
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=text_content,
        )
        return response.data[0].embedding

    async def get_embeddings_batch(self, texts: list[str]) -> list[list[float]]:
        """Get embeddings for multiple texts in one call."""
        if not texts:
            return []
        response = await self.client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def index_file(self, file_id: int, text_content: str) -> int:
        """Chunk text, generate embeddings, store in DB. Returns chunk count."""
        chunks = self.chunk_text(text_content)
        if not chunks:
            return 0

        # Delete old embeddings for this file
        async with async_session() as session:
            await session.execute(
                delete(DocumentEmbedding).where(DocumentEmbedding.file_id == file_id)
            )
            await session.commit()

        # Generate embeddings in batches of 100
        batch_size = 100
        total_stored = 0

        for batch_start in range(0, len(chunks), batch_size):
            batch = chunks[batch_start : batch_start + batch_size]
            embeddings = await self.get_embeddings_batch(batch)

            async with async_session() as session:
                for i, (chunk, emb) in enumerate(zip(batch, embeddings)):
                    doc_emb = DocumentEmbedding(
                        file_id=file_id,
                        chunk_text=chunk,
                        chunk_index=batch_start + i,
                        embedding=emb,
                    )
                    session.add(doc_emb)
                await session.commit()
                total_stored += len(batch)

        logger.info("Indexed file %d: %d chunks", file_id, total_stored)
        return total_stored

    async def search(
        self, query: str, user_file_ids: list[int] | None = None, top_k: int | None = None
    ) -> list[dict]:
        """Semantic search. Returns list of {chunk_text, file_id, score}."""
        k = top_k or self.top_k
        query_embedding = await self.get_embedding(query)

        async with async_session() as session:
            # Build query with cosine distance
            emb_str = "[" + ",".join(str(x) for x in query_embedding) + "]"

            if user_file_ids:
                file_ids_str = ",".join(str(fid) for fid in user_file_ids)
                sql = text(f"""
                    SELECT chunk_text, file_id, chunk_index,
                           1 - (embedding <=> :emb::vector) as score
                    FROM document_embeddings
                    WHERE file_id IN ({file_ids_str})
                    ORDER BY embedding <=> :emb::vector
                    LIMIT :k
                """)
            else:
                sql = text("""
                    SELECT chunk_text, file_id, chunk_index,
                           1 - (embedding <=> :emb::vector) as score
                    FROM document_embeddings
                    ORDER BY embedding <=> :emb::vector
                    LIMIT :k
                """)

            result = await session.execute(sql, {"emb": emb_str, "k": k})
            rows = result.fetchall()

        return [
            {
                "chunk_text": row[0],
                "file_id": row[1],
                "chunk_index": row[2],
                "score": float(row[3]),
            }
            for row in rows
        ]

    async def build_context(
        self, query: str, user_file_ids: list[int] | None = None
    ) -> str | None:
        """Search and format relevant chunks for AI context."""
        results = await self.search(query, user_file_ids)
        if not results:
            return None

        parts = []
        for r in results:
            parts.append(f"[Документ #{r['file_id']}, фрагмент {r['chunk_index']}]\n{r['chunk_text']}")

        return "\n\n---\n\n".join(parts)
