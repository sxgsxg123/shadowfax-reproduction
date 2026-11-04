# Shadowfax 课程复现

本仓库记录课程作业对论文 **SHADOWFAX: Hybrid Security and Deniability for AKEMs** 的 Windows 复现。

- `ours/`：自行编写的复现脚本、Windows 兼容补丁和运行说明。
- `source/`：论文作者的[原始代码](https://github.com/vincentvbh/shadowfax)子模块，固定在提交 `20d9d2e60487d317d38f9e4070dde16630beeb1b`；兼容补丁不提交到作者仓库。
- `logs/`：实验的原始输出。
- `results.json`：整理后的测试和性能结果。

克隆时请同时获取子模块：

```powershell
git clone --recurse-submodules https://github.com/sxgsxg123/shadowfax-reproduction.git
cd shadowfax-reproduction
python .\ours\reproduce_shadowfax.py
```

运行环境、构建步骤和结果解释见 [`ours/README.md`](ours/README.md)。
