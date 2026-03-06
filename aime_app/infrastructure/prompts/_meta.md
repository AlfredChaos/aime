# prompts/

本目录提供 prompt 仓库的基础设施实现：负责读取/写入系统提示词，并向上层提供“可回退”的稳定接口。

## 关键文件

- `langfuse_repo.py`：基于 Langfuse 的 prompt 获取与写入（失败走 fallback）

