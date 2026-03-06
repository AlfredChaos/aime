from __future__ import annotations

import asyncio
import uuid
from datetime import datetime


async def probe_embedding_dim(embedding_model) -> int | None:
    try:
        resp = await embedding_model(["dimension_probe"])
        embeddings = getattr(resp, "embeddings", None)
        if not embeddings:
            return None
        first = embeddings[0]
        if not first:
            return None
        return len(first)
    except Exception:
        return None


def get_existing_lancedb_vector_dim(uri: str, table_name: str) -> int | None:
    try:
        import lancedb

        db = lancedb.connect(uri)
        list_tables = getattr(db, "list_tables", None)
        table_names = list_tables() if callable(list_tables) else db.table_names()
        if table_name not in set(table_names):
            return None
        tbl = db.open_table(table_name)
        schema = tbl.schema
        if "vector" not in schema.names:
            return None
        vec_type = schema.field("vector").type
        if hasattr(vec_type, "list_size"):
            return int(vec_type.list_size)
        return None
    except Exception:
        return None


def resolve_lancedb_table_name(*, uri: str, table_name: str, embedding_dim: int | None) -> str:
    if embedding_dim is None:
        return table_name
    existing_dim = get_existing_lancedb_vector_dim(uri, table_name)
    if existing_dim is None or existing_dim == embedding_dim:
        return table_name
    return f"{table_name}_d{embedding_dim}"


def create_lancedb_vector_store(uri: str, table_name: str, embedding_model):
    from langchain_community.vectorstores import LanceDB as _LanceDB
    from langchain_core.embeddings import Embeddings as _Embeddings
    from langchain_core.documents import Document as _Document

    class _AgentscopeEmbeddingsAdapter(_Embeddings):
        def __init__(self, model):
            self._model = model

        def embed_documents(self, texts: list[str]) -> list[list[float]]:
            try:
                asyncio.get_running_loop()
            except RuntimeError:
                resp = asyncio.run(self._model(texts))
                return resp.embeddings

            import concurrent.futures

            def _run():
                return asyncio.run(self._model(texts))

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                return executor.submit(_run).result().embeddings

        def embed_query(self, text: str) -> list[float]:
            return self.embed_documents([text])[0]

        async def aembed_documents(self, texts: list[str]) -> list[list[float]]:
            resp = await self._model(texts)
            return resp.embeddings

        async def aembed_query(self, text: str) -> list[float]:
            resp = await self._model([text])
            return resp.embeddings[0]

    class LanceDBPrecomputedEmbeddings(_LanceDB):
        @staticmethod
        def _quote_lance_sql_value(value):
            if value is None:
                return "NULL"
            if isinstance(value, bool):
                return "true" if value else "false"
            if isinstance(value, (int, float)):
                return str(value)
            text = str(value).replace("\\", "\\\\").replace("'", "\\'")
            return f"'{text}'"

        @classmethod
        def _to_lance_where(cls, filter_dict: dict) -> str:
            parts: list[str] = []
            for key, value in filter_dict.items():
                if key.startswith("$"):
                    raise ValueError(f"Unsupported filter operator: {key}")
                parts.append(f"metadata.{key} = {cls._quote_lance_sql_value(value)}")
            return " AND ".join(parts)

        def add_embeddings(self, embeddings, metadatas=None, ids=None):
            ids = ids or [str(uuid.uuid4()) for _ in embeddings]
            docs = []
            tbl = self.get_table()
            metadata_allowed_keys = None
            if tbl is not None and "metadata" in tbl.schema.names:
                try:
                    meta_field = tbl.schema.field("metadata")
                    meta_type = meta_field.type
                    if hasattr(meta_type, "names") and meta_type.names:
                        metadata_allowed_keys = set(meta_type.names)
                except Exception:
                    metadata_allowed_keys = None

            for idx, embedding in enumerate(embeddings):
                metadata = metadatas[idx] if metadatas else {"id": ids[idx]}
                text = ""
                if isinstance(metadata, dict):
                    text = str(metadata.get("data", ""))
                    if metadata_allowed_keys is not None:
                        metadata = {k: v for k, v in metadata.items() if k in metadata_allowed_keys}
                docs.append(
                    {
                        self._vector_key: embedding,
                        self._id_key: ids[idx],
                        self._text_key: text,
                        "metadata": metadata,
                    },
                )

            if tbl is None:
                tbl = self._connection.create_table(self._table_name, data=docs)
                self._table = tbl
            else:
                if self.api_key is None:
                    tbl.add(docs, mode=self.mode)
                else:
                    tbl.add(docs)

            self._fts_index = None
            return ids

        def similarity_search_by_vector(
            self,
            embedding,
            k: int | None = None,
            filter: dict | str | None = None,
            name: str | None = None,
            **kwargs,
        ):
            if isinstance(embedding, list) and embedding and isinstance(
                embedding[0],
                (list, tuple),
            ):
                embedding = embedding[0]

            where = None
            if isinstance(filter, dict):
                where = self._to_lance_where(filter)
            else:
                where = filter

            docs = self._query(embedding, k, filter=where, name=name, **kwargs)
            ids = []
            scores = []
            metadatas = []

            relevance_score_fn = self._select_relevance_score_fn()
            distance_col = "_distance" if "_distance" in docs.schema.names else None

            for idx in range(len(docs)):
                ids.append(docs[self._id_key][idx].as_py())
                metadatas.append(docs["metadata"][idx].as_py() if "metadata" in docs.schema.names else {})
                if distance_col is not None:
                    scores.append(relevance_score_fn(float(docs[distance_col][idx].as_py())))
                else:
                    scores.append(None)

            return {"ids": [ids], "distances": [scores], "metadatas": [metadatas]}

        def get_by_ids(self, ids: list[str], name: str | None = None):
            if not ids:
                return []
            tbl = self.get_table(name)
            quoted = ",".join(self._quote_lance_sql_value(i) for i in ids)
            rows = tbl.search().where(f"{self._id_key} in ({quoted})").to_arrow()
            docs = []
            for idx in range(len(rows)):
                page_content = rows[self._text_key][idx].as_py()
                metadata = rows["metadata"][idx].as_py() if "metadata" in rows.schema.names else {}
                doc_id = rows[self._id_key][idx].as_py()
                docs.append(_Document(page_content=page_content, metadata=metadata, id=doc_id))
            return docs

    return LanceDBPrecomputedEmbeddings(
        uri=uri,
        table_name=table_name,
        embedding=_AgentscopeEmbeddingsAdapter(embedding_model),
        mode="append",
    )


def create_vector_store_config(*, lancedb_vs, effective_embedding_dim: int | None):
    import mem0

    try:
        from mem0.vector_stores.langchain import Langchain as _Mem0LangchainVectorStore

        if effective_embedding_dim is not None:
            _Mem0LangchainVectorStore.embedding_model_dims = effective_embedding_dim
    except Exception:
        pass

    return mem0.vector_stores.configs.VectorStoreConfig(
        provider="langchain",
        config={"client": lancedb_vs, "collection_name": "mem0"},
    )

