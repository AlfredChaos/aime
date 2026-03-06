from __future__ import annotations

import asyncio
import uuid
from datetime import datetime


def _get_lancedb_table_names(db) -> list[str]:
    list_tables = getattr(db, "list_tables", None)
    if callable(list_tables):
        result = list_tables()
        tables = getattr(result, "tables", None)
        if isinstance(tables, list) and all(isinstance(x, str) for x in tables):
            return tables
        if isinstance(result, dict):
            tables = result.get("tables")
            if isinstance(tables, list) and all(isinstance(x, str) for x in tables):
                return tables
        try:
            as_dict = dict(result)
            tables = as_dict.get("tables")
            if isinstance(tables, list) and all(isinstance(x, str) for x in tables):
                return tables
        except Exception:
            pass

    table_names = getattr(db, "table_names", None)
    if callable(table_names):
        result = table_names()
        if isinstance(result, list) and all(isinstance(x, str) for x in result):
            return result
    return []


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
        if table_name not in set(_get_lancedb_table_names(db)):
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


def ensure_lancedb_table_exists(
    *,
    uri: str,
    table_name: str,
    embedding_dim: int,
    template_table_name: str | None = None,
) -> None:
    import lancedb
    import pyarrow as pa

    db = lancedb.connect(uri)
    existing = set(_get_lancedb_table_names(db))
    if table_name in existing:
        return

    schema = None
    if template_table_name and template_table_name in existing:
        tmpl = db.open_table(template_table_name).schema
        fields: list[pa.Field] = []
        for field in tmpl:
            if field.name == "vector":
                fields.append(
                    pa.field(
                        "vector",
                        pa.list_(pa.float32(), list_size=embedding_dim),
                    ),
                )
            else:
                fields.append(field)
        schema = pa.schema(fields)

    if schema is None:
        schema = pa.schema(
            [
                pa.field("vector", pa.list_(pa.float32(), list_size=embedding_dim)),
                pa.field("id", pa.string()),
                pa.field("text", pa.string()),
                pa.field(
                    "metadata",
                    pa.struct(
                        [
                            pa.field("type", pa.string()),
                            pa.field("user_id", pa.string()),
                            pa.field("agent_id", pa.string()),
                        ],
                    ),
                ),
            ],
        )

    db.create_table(table_name, schema=schema, data=[])


async def migrate_lancedb_table_embeddings(
    *,
    uri: str,
    source_table_name: str,
    target_table_name: str,
    embedding_model,
    batch_size: int = 64,
) -> int:
    import lancedb

    db = lancedb.connect(uri)
    source = db.open_table(source_table_name)
    target = db.open_table(target_table_name)

    try:
        existing_rows = int(target.count_rows())
    except Exception:
        existing_rows = 0
    if existing_rows > 0:
        return 0

    rows = source.to_arrow().to_pydict()
    ids: list[str] = rows.get("id") or []
    texts: list[str] = rows.get("text") or []
    metadatas: list[dict] = rows.get("metadata") or []

    to_migrate: list[tuple[str, str, dict]] = []
    for i in range(min(len(ids), len(texts), len(metadatas))):
        text = texts[i]
        if not text:
            meta = metadatas[i] if isinstance(metadatas[i], dict) else {}
            candidate = meta.get("data") if isinstance(meta, dict) else None
            text = str(candidate) if candidate else ""
        if not text:
            continue
        meta = metadatas[i] if isinstance(metadatas[i], dict) else {}
        to_migrate.append((ids[i], text, meta))

    inserted = 0
    for start in range(0, len(to_migrate), batch_size):
        batch = to_migrate[start : start + batch_size]
        resp = await embedding_model([t for _, t, _ in batch])
        embeddings = getattr(resp, "embeddings", None) or []
        if len(embeddings) != len(batch):
            raise RuntimeError(
                "Embedding batch size mismatch while migrating LanceDB table",
            )
        docs = []
        for (doc_id, text, meta), vec in zip(batch, embeddings):
            docs.append(
                {
                    "vector": vec,
                    "id": doc_id,
                    "text": text,
                    "metadata": meta,
                },
            )
        target.add(docs)
        inserted += len(docs)
    return inserted


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
