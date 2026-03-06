# models/

本目录集中管理大模型相关实例的创建（factory）：把环境变量与 SDK 参数收敛到单处，供上层装配复用。

## 关键文件

- `gemini_factory.py`：创建 Gemini chat 与 embedding 模型实例

