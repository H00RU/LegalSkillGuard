# 复现说明

原始运行：Python 3，NumPy 2.0.2，SciPy 1.15.3，z3-solver 4.15.4.0。程序需要 Python 3.10 或更新版本。方法一、原方法二、独立 BFS 和源锚定检查仅使用标准库；闭式算法本身也只需标准库，但其完整验证入口另调用 SciPy 重数对照。精确强对照使用 Z3。

原始记录请保留。以下程序会覆盖与脚本同目录的结果文件，建议先把整个证据包复制到临时目录，再在副本中复现。无需 API、GPU、网络模型调用或旧冻结测试。

在副本根目录：

```text
python -m pip install -r requirements.txt
python -X utf8 method1/run_validation.py
python -X utf8 method1/write_report.py
python -X utf8 method1/independent_review_checks.py
python -X utf8 method2/validate_method2.py
python -X utf8 replacement/capped_fold_direct.py
python -X utf8 replacement/cutoff_independent_checks.py
python -X utf8 replacement/capped_fold_z3_comparison.py
python -X utf8 source_fixture_audit.py
```

最后一项优先寻找原作者工作区中的 SARA 归档，否则读取随包源文摘录，并明确记录“本次未重新核验原归档”。如有原文件，可显式指定：

```text
python -X utf8 source_fixture_audit.py --archive /path/to/sara_v2.tar.gz
```

原归档 SHA256：`f433146a8a83d351b7797ff12a9a5afdb3986ad790af9cfbc1c2b6d3f2dca85b`。相关摘录、许可和各原文件 hash 随包提供；固定的是数据集历史文本，不是当前法律咨询。

可选历史对照 `replacement/aggregate_witness.py` 是第一版 SciPy 重数优化，不是本轮保留的新算法；其浮点优化状态不可冒充形式化 UNSAT 证明。主比较以精确 Z3 与独立 BFS 为准。

源码/输入与结果完整性由根目录 `manifest.json` 记录。方法一 summary、原方法二 manifest 另包含自身源码 hash。复现后运行时间和新结果 hash 会变化；比较语义输出和计数，不要求毫秒级计时相等。

Z3 比较脚本先尝试原工作区的可选本地依赖目录；该目录不存在时使用当前 Python 环境中安装的 z3-solver，不需要复制作者环境。逐记录 Z3 的单次 3 秒超时只用于记录有界对照状态；unknown 不等于不等价，也不等于验证成功。
