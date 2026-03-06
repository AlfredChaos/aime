# domain/ 协作指南

`domain/` 放领域对象与纯策略：不依赖第三方 SDK，不读环境变量，不做 I/O。这里的代码应当“可拷贝到任何项目里仍然成立”。

## 当前领域模型

- [team_spec.py](file:///home/shixuan/code/agentscope-research/aime_app/domain/team_spec.py)
  - `TeamSpec` / `TeamMemberSpec`：描述团队结构（成员 ID 与角色）
- [prompt_policy.py](file:///home/shixuan/code/agentscope-research/aime_app/domain/prompt_policy.py)
  - `ensure_memory_policy()`：在系统提示词中缺失记忆工具约定时，注入一段“记忆管理指南”

## 约束

- 只允许依赖标准库与其他 `domain/` 模块。
- 若需要表达外部概念（如“向量库”“模型”），只在这里表达规则/约束，不表达实现细节。
- 领域对象尽量使用不可变结构（当前使用 `@dataclass(frozen=True)`）。

