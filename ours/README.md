# Shadowfax Windows 实验复现脚本

此目录是课程作业的**自行编写的调用与核对代码**，与作者源码分开保存。
`reproduce_shadowfax.py` 固定作者源码提交，自动应用 `windows-compat.patch`，
分别构建 ML–KEM＋GandalfFalcon、BAT＋GandalfMitaka，运行作者的
DH/PQ/Hybrid 正确性测试，并对两组 Hybrid 配置各运行三次性能测试。
它将原始输出保存到 `../logs/`，将整理结果保存到 `../results.json`。

## 环境

- Windows 11 x86-64。
- MSYS2 UCRT64，安装 GCC 与 Make；脚本默认 Bash 路径为
  `D:\msys64\usr\bin\bash.exe`。如安装在别处，请修改脚本中的 `BASH` 常量。
- Windows Python 3 和 Git。

## 准备和运行

从本仓库克隆时执行：

```powershell
git submodule update --init
python .\ours\reproduce_shadowfax.py
```

脚本会先核验提交，再应用 Windows 兼容补丁。补丁只涉及标准头文件、
Windows 随机数函数声明与链接、将 `ffsll` 换为同语义的 GCC 内建函数、
基准程序栈大小及计时输出，不修改密码学方案本身。
代码与论文来源分别见
[作者仓库](https://github.com/vincentvbh/shadowfax)、
[USENIX Security 2026 正式论文](https://www.usenix.org/conference/usenixsecurity26/presentation/gajland)。

复现结果中的 `keygen_kcycles`、`encap_kcycles` 和 `decap_kcycles`
单位为千个 CPU 周期。Windows x86-64 与论文的 Apple M1 Pro 硬件不同，
原始周期数不应视为可直接对等的性能排名。
