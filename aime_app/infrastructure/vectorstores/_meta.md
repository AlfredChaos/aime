# vectorstores/

本目录负责长期记忆的向量存储适配：封装 LanceDB 连接、向量维度处理、以及与 Mem0/LangChain 之间的胶水逻辑。

## 关键文件

- `lancedb_store.py`：LanceDB 适配与 Mem0 VectorStoreConfig 构建

