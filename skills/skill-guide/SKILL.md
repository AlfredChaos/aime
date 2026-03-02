---
name: SkillGuide
description: 解释 skills 的组织方式与“渐进式披露”使用方法
---

# SkillGuide

本 Skill 是给“人类开发者 + 智能体”两边看的：它解释 `skills/` 目录的结构约定，以及本项目里“渐进式披露（Progressive Disclosure）”到底是什么意思、怎么用。

## 1) skills/ 目录结构约定

每个 Skill 是一个子目录，至少包含：

- `SKILL.md`：说明书（必须存在）

可选包含：

- `scripts/`：示例脚本
- `prompts/`：长 prompt / 模板
- `assets/`：示例数据等

Skill 的“可发现性”依赖 `SKILL.md` 顶部的 YAML front matter：

- `name`：给模型看的名字（不一定等于目录名）
- `description`：一句话解释用途（尽量短，利于索引）

## 2) 什么是“渐进式披露”

在智能体系统里，Prompt 既是能力入口也是成本中心：把所有工具/技能一次性塞给模型，会带来三个问题：

1. token 成本飙升，且上下文容易溢出  
2. 模型注意力被无关技能稀释，调用更不稳定  
3. 维护成本高：每加一个能力都要重新审视“系统提示词是否爆炸”

“渐进式披露”是一种信息架构策略：**先给最小的索引信息，让模型知道“有什么”；当模型确定要用某个能力时，再通过工具按需读取细节**。

在本项目中：

- 启动时：仅把每个 Skill 的 `name/description/目录路径` 暴露给模型（索引层）
- 运行时：模型需要细节时，再调用工具读取对应文件（细节层）

这等价于把技能信息从“推送（push）”改为“拉取（pull）”。

## 3) 智能体如何按需读取 Skill

本项目提供了 3 个与 Skill 相关的工具（函数名可能在工具列表里显示）：

1. `list_skills()`  
   - 返回所有可用 Skill 的索引（目录名、描述、路径）

2. `read_skill_markdown(skill_name)`  
   - 读取 `skills/<skill_name>/SKILL.md` 全文

3. `read_skill_file(skill_name, relative_path)`  
   - 读取该 Skill 目录下的任意文件，比如示例脚本或更长的 prompt

推荐的调用模式：

1) 先 `list_skills()` 找到候选 skill  
2) 只对需要的 skill 调 `read_skill_markdown(...)`  
3) 如果 SKILL.md 提到还有其它文件，再用 `read_skill_file(...)` 精确读取  

## 4) 给人类开发者的实践建议

- 把 `description` 写成“检索友好”的关键词短语（例如“解析日志 + 生成诊断建议”）
- 在 `SKILL.md` 里优先写“何时使用 / 何时不要使用 / 输入输出约定”
- 复杂技能把细节拆分到 `prompts/` 或 `scripts/`，让模型按需读取

