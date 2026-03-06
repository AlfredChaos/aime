# patches/

本目录封装对第三方库的兼容性修复（monkey patch），用于解决上游 SDK/框架在特定版本组合下的边界问题。

## 约束

- patch 必须幂等（重复调用不应产生额外副作用）
- patch 的入口统一通过 `aime_app.infrastructure.patches.apply_all()` 暴露

