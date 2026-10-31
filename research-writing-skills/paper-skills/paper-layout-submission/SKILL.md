---
name: "paper-layout-submission"
description: "论文 LaTeX 排版与投稿收尾：编译中英双版、消孤行和半空页、公式编号与留白、页面分布、参考文献、声明与匿名检查、投稿版本管理、署名版与高清版（版式不变）、源码打包、代码仓库与交付。排版、投稿、上传 arXiv 时使用。"
---

# 论文排版、投稿与发布

## 1. 工程与编译

- **目录结构**：
  - `main.tex`：英文匿名稿，pdflatex，natbib authoryear。
  - `main-zh.tex`：中文版，XeLaTeX，尽量用同一版式，方便对页。
  - 共用 `sections/`、`sections-zh/`、`figures/`、`refs.bib`。
- **英文编译顺序**：`pdflatex → bibtex → pdflatex ×2`。中文同理，把 pdflatex 换成 xelatex。
- **编译位置**：用户偏好在本机（Mac 沙箱）编译。缺少的 .sty（如 algorithm、algpseudocode）拷进工程目录，使工程自包含。
- **快照**：每轮大改前存快照，例如 `_v74/`、`_v75/`、`*.pre-compress`、`refs.bib.pre-verify`、`work.snap-日期-说明`，便于整体回退和取旧稿素材。
- **测试副本**：可能动版式的改动，先在副本目录里编译验证（页数、每页结尾、孤行、拉伸），通过后再写回主工程。
- **批量改句**：用容忍空白差异的查找替换，要求每个旧串恰好匹配一次，否则报 FAIL：

```python
import re
def apply(path, pairs):
    s = open(path).read(); bad = []
    for old, new in pairs:
        rx = r'\s+'.join(re.escape(p) for p in re.split(r'\s+', old.strip()))
        ms = list(re.finditer(rx, s))
        if len(ms) != 1: bad.append((len(ms), old[:70])); continue
        s = s[:ms[0].start()] + new + s[ms[0].end():]
    open(path, 'w').write(s); print('FAIL', bad) if bad else print('ok')
```

- **中文版（XeLaTeX）常见问题**：
  - `\emph` 在中文字体下没有斜体：`\setmainfont{Noto Serif CJK SC}[ItalicFont={Noto Serif CJK SC},ItalicFeatures={FakeSlant=0.18}]`。
  - 双栏浮动体跑偏，出现只放一张表的半空页：浮动体用 `[!t]`，并把 `\dbltopfraction` 调到 0.85 左右。
  - 中文版只做内容同步，页数和版式可以和英文不同；用对照脚本检查数字和英文一致，术语表固定译法。

## 2. 页面规范（固定要求）

- **页面分布**（9 页正文）：
  - 引言在第 2 页结束。
  - 预备知识加方法开头段在第 3 页结束。
  - 第 6 页写到实验节开头。
  - 5.1 在第 7 页。
  - 靠逐句压缩文字达到这个分布，不让章节溢出。
- **ACL/ARR（8 页正文）**：引言在第 2 页结束；方法在第 3–5 页；第 6 页开始实验；整页浮动体可以占第 7 页；正文以结论收在第 8 页末。
- **不能缩图**：超页时绝不靠缩小或重压图来腾空间，从文字里省。相关工作不能挪到附录。
- **页面要满**：
  - 不能有半空页。
  - 段落或图注的最后一行填充率必须 ≥50%（最好接近整行），否则就是孤行。
  - 处理孤行：要么用旧稿素材把句子写满，要么改写消掉。
  - 结果段、结论这类关键段落，段尾行最好 ≥90%。用户的原话是"这种孤行最好写满吧，本身就不够写"。补的内容是已有事实的明确化（例如图注定义里已有的 distinct、实验设定里已有的 throughout training），不加新主张。
  - 删句以后检查该段有没有新孤行，用用户确认过的事实补回（例如 "measured in training"）。
- **等长替换**：改一个词也可能让段落多出一行，把正文挤出页数限制。R²Orch 把 "held-out domains" 改成 "held-out benchmarks"，结论最后一行就跑到了第 9 页。每次改动都看正文末页，放不下时换等长或更短的说法（"OOD benchmarks"）。
- **浮动体**：
  - 引言开头用 `\suppressfloats[t]`，让图 1 不跑到标题上方。
  - 图 1 用 wrapfigure 嵌进第二段。
  - 图 2、图 3 用 `[t]`。
- **参考文献页数**：用 `\setlength{\bibsep}{…}` 微调，让参考文献刚好占满整数页，不溢出到几乎空的一页。附录前保留 `\clearpage`。
- **长 URL**：用 `\mbox{\href{…}{\nolinkurl{…}}}` 防止断行。

### 公式编号与留白

- **编号掉到下一行**：公式宽 w 加编号宽 e，超过"栏宽减 1em"（ACL 约 219 − 11 = 208pt）时，TeX 把编号放到下一行，白占一行。ACL 栏内，单数字编号要 w ≲ 195pt，两位数编号要 w ≲ 190pt。
- **量宽度**：用同一导言区编译一个小文件，`\setbox0\hbox{$\displaystyle …$}\typeout{W=\the\wd0}`。
- **压宽**，不改数学含义：
  - 去掉多余的 `\big` 和薄空格；
  - 按正文已有的简写约定省略参数（正文写了 $p_K=p_K(x)$ 时，公式里写 $p_K$）；
  - `aligned` 改 `gathered`；`\quad` 改 `\ \ `；$\mathbb E[\cdot]$ 去掉方括号。
- **underbrace 的标签**写成 `\underbrace{…}_{\smash{\text{…}}}`，标签不再把公式下方撑大。
- **ACL 用 `\flushbottom`**：省出的空间不会自动回流，会变成公式上下被拉开的空白。诊断：在测试副本的 `\begin{document}` 前加 `\vbadness=0`，编译后从 log 读出每页各栏的 underfull badness（某栏不出现即为刚好满）：

```python
# vbad.py main.log：列出每页各栏的 underfull badness
import re, sys
log = open(sys.argv[1], errors='ignore').read(); ev = []
ev += [(m.start(), 'U', int(m.group(1))) for m in re.finditer(r'Underfull \\vbox \(badness (\d+)\) has occurred while \\output is active', log)]
ev += [(m.start(), 'P', int(m.group(1))) for m in re.finditer(r'\[(\d+)(?=[\s\]{<])', log)]
last, res = 0, {}
for _, t, v in sorted(ev):
    if t == 'P': last = v if v == last + 1 else last
    else: res.setdefault(last + 1, []).append(v)
for p in sorted(res): print('page', p, res[p])
```

  把省出的行在同一页补回（例如命题证明指针加上引理编号），直到该页 badness 接近 0，并确认后面每页的结尾不变。

### 检查脚本（每次编译后跑）

```python
# widows.py pdf p0 p1 [thr]：列出填充率 < thr% 的段尾行。L、R 是正文左右边界（pt），按模板调整
import subprocess, re, sys
pdf, p0, p1 = sys.argv[1], int(sys.argv[2]), int(sys.argv[3]); thr = float(sys.argv[4]) if len(sys.argv) > 4 else 50
L, R = 108.0, 504.0
for pg in range(p0, p1 + 1):
    h = subprocess.run(['pdftotext', '-f', str(pg), '-l', str(pg), '-bbox', pdf, '-'], capture_output=True, text=True).stdout
    lines = {}
    for a, b, c, d, w in re.findall(r'xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">([^<]*)<', h):
        a, b, c, d = map(float, (a, b, c, d))
        if a < 100 or d > 745 or b < 60: continue
        lines.setdefault(round(d), []).append((a, c, w))
    ys = sorted(lines)
    for i, y in enumerate(ys):
        ws = sorted(lines[y]); x0 = ws[0][0]; x1 = max(w[1] for w in ws); t = ' '.join(w[2] for w in ws)
        gap = ys[i+1] - y if i + 1 < len(ys) else 99; prev = y - ys[i-1] if i else 99
        fill = (x1 - L) / (R - L) * 100
        if gap > 12.2 and fill < thr and x0 <= 115 and re.search(r'[.:;)]$', t) and prev <= 12.2:
            print(f'p{pg} y{y} {fill:5.1f}% | {t[:90]}')
```

- 双栏（ACL）按左右栏分别算填充率：左栏约 70.9–289.1pt，右栏约 306.1–524.4pt。行内加粗小标题和图里的文字会误报，只看新增的那几条。

```python
# endcmp.py ref.pdf new.pdf：逐页比较最后 3 个词，确认版式未变
import pdfplumber, sys
a, b = pdfplumber.open(sys.argv[1]), pdfplumber.open(sys.argv[2])
last = lambda p: [w['text'] for w in p.extract_words() if not w['text'].isdigit()][-3:]
print('pages', len(a.pages), len(b.pages), 'diff', [i+1 for i in range(min(len(a.pages), len(b.pages))) if last(a.pages[i]) != last(b.pages[i])])
```

- pdfplumber 有时把整行拼成一个词，报 DIFF 时先看末行文字是否真的变了。

其他检查：

- 编译日志里 Overfull 必须为 0：`grep -c Overfull main.log`。
- 关键页用 `pdftoppm -r 110` 渲染出来，亲眼看一遍。
- 改公式或删句后同时跑 vbad，确认没有新的拉伸。
- 注意：中文版的孤行检测在表格和公式行上会误报。和匿名中文版逐条对比，只处理新增的孤行。

## 3. 参考文献

- 一律用用户提供的 Google Scholar BibTeX 原文，一个字都不改。用户给 docx 或文本时，整体替换 refs.bib。
- 正文没有引用的条目要删除。条目缺失或损坏时，把标题列给用户，由用户去取 Google Scholar 版本。
- 优先引用近期（近几个月）的工作。每条都要核实存在。
- 附录一般不放引用。

## 4. 投稿前检查（以 ICLR 为例，其他会议同理先查官方 CFP）

1. **页数**：正文不超过限制（ICLR 9 页，讨论期和终稿 10 页；ACL/ARR 长文 8 页）。
2. **声明**：放在参考文献之前，不计页数。
   - AI Use Statement：ICLR 必须有。内容如实写：润色编辑、LaTeX 排版、图表摆放、检索、BibTeX 取自 Google Scholar、作者人工核对、作者负全责。不要列"未用于…"这类可能不准确的清单。
   - Ethics Statement：建议写。
   - Reproducibility Statement：建议写，指向方法各节、附录证明、超参数表、实验细节、五次运行；最后一句是 **Code availability.**。
   - ACL/ARR：Limitations 节必须有，放在结论之后、参考文献之前，不计入页数。
3. **匿名检查**：
   - 正文、附录、图里的文字、PDF 元数据、代码链接（用 anonymous.4open.science）都不能暴露身份。
   - 自引用第三人称。
4. **数据一致性终检**：见 paper-figures-data 技能的核查清单，中英文数字也要一致。
5. **提交记录**：投稿当时的 PDF 另存一份（如 `XXX-submission.pdf`），永不覆盖。截止后的修改进匿名修订版（`_v75`…），并提醒用户下次能上传的窗口，例如 ICLR 讨论期 11 月 5–18 日。
6. **摘要和题目**：用户在系统里填写摘要时，给出纯文本版本，去掉 LaTeX 命令。

## 5. 署名版（全文版式和匿名版一致）

- 单独建 `main-arxiv.tex`、`main-zh-arxiv.tex`（或单独的署名目录），不改匿名稿。
- **ICLR 模板的设置**：
  - 用 `\iclrfinalcopy` 显示作者。
  - `\hypersetup{hidelinks}`。
  - 在 `\maketitle` 之后用 `\lhead{...}` 设页眉（"Under review…"，或按用户要求写 "Preprint"）。
- **ACL/ARR 模板的设置**：`\usepackage[preprint]{acl}`，显示作者、去掉行号、保留页码。标题框 `\titlebox` 高度固定，作者块放得下就不影响版式。
- **作者块**：
  - 作者名居中，分两行。
  - 单位 2–3 行，`\footnotesize`，只写到国家，用 `\quad` 分隔，上标编号；一人多单位写 `$^{1,2}$`。
  - 单位用官方全称，例如 "The University of Texas Health Science Center at Houston"、"The Chinese University of Hong Kong, Shenzhen"（不是 CUHK）。
  - `\author{}` 不是 `\long`，里面不能出现 `\par` 或空行。
  - ACL 的 `\author` 放在 tabular 里，每个 `\\` 开一个新单元格，所以每行开头都要重写字体命令，花括号也不能跨 `\\`（否则报 Missing }）：

```latex
\author{Author A$^{1,2}$\quad Author B$^{2}$\quad Author C$^{2}$\\
\bfseries Author D$^{2}$\quad Author E$^{3}$\quad Author F$^{1}$\\[4pt]
\mdseries\footnotesize $^{1}$Institution One, Country\quad $^{2}$Institution Two, Country\\
\mdseries\footnotesize $^{3}$Institution Three, Country}
```

- **ICLR 保持版式**：自定义 `\@maketitle`，留两个可调间距，调到标题块总高度和匿名版接近；第 1 页剩余的空间能吸收小差异：

```latex
\makeatletter
\def\@maketitle{\vbox{\hsize\textwidth
{\LARGE\sc \@title\par}\vskip\GAPA
{\centering\bfseries\begin{tabular}[t]{@{}c@{}}\@author\end{tabular}\par}\vskip\GAPB}}
\makeatother
```

  - 中文版（article 类）同样重定义 `\@maketitle`，作者行用 `\linespread{1.05}\large`；单位放不下时压成 2 行。
- **验收**：
  - 用 endcmp.py 对匿名版：页数相同、每页结尾相同。更严格的做法是逐词比对坐标（`pdftotext -bbox`，去掉页边行号），除第 1 页标题块外全部一致。
  - 0 overfull，无新孤行。
  - 渲染第 1 页标题块，亲眼确认。
- **请求的理解**：用户的语音转写可能有错字（例如"不利名"其实是"署名"），按上下文判断，并在回复里一句话说明是怎么理解的。用户说署名版不再更新后，只更新匿名版。
- **代码链接**：
  - 只在 arXiv 版换成公开的 GitHub 链接。做法是建 `sections-arxiv/` 存放受影响章节的副本（摘要、声明、附录里的 "anonymous code repository"），由 arxiv 主文件 `\input` 这些副本；匿名稿保持不动。
  - 换链接后重查孤行。URL 显示时带上 `https://` 也是一种补满行的手段。

## 6. 高清版

- 单独编译一个 hd 目录：主工程的副本，把图 1–3 换成无损原图（文字矢量、插画保持原分辨率），数据图保持矢量 PDF，文件约 13–14 MB。用 endcmp.py 确认和普通版逐页一致。
- 用户单独要图时，给无损 PDF 和 PNG（见 paper-figures-data 的 A.15）。

## 7. arXiv 源码包

- 用 `-recorder` 编译，从 `.fls` 收集实际用到的文件：sty/bst、章节、图、TikZ、bib。
- 主文件改名为 `main.tex`，附上 `main.bbl`。
- 用 `arxiv_latex_cleaner <dir> --keep_bib` 清除注释。注释里有对齐笔记、内部信息，还可能提到对比基线的实现来源，这一步必须做。
- 在干净目录只用 pdflatex 编译两遍，`pdftotext` 结果和交付 PDF 做 diff，必须一致。
- 中文版依赖本地 CJK 字体，不适合上传 arXiv，打包留档即可。

## 8. 代码仓库

- 投稿时用 anonymous.4open.science 镜像私有仓库。**警告**：匿名镜像会自动同步源仓库。清空或改写源仓库后，审稿人看到的匿名代码也会跟着变。动源仓库之前先提醒用户。
- **"代码即将发布"占位仓库**：
  1. 先做完整备份：`git clone --mirror` 后 `git bundle create … --all`，存进用户文件夹。
  2. 用 orphan 新 main（只含 README.md）强制推送，清掉历史。
  3. 最后再改为公开。
  - 顺序必须是先清空、再公开。
- 本会话没有推送权限时，生成 `.command` 或 `.sh` 脚本交给用户运行，不要绕过终端的权限限制。

## 9. 交付

- 默认每次交英文 PDF 和中文 PDF 两份，文件名形如 `XXX-arXiv.pdf` 和 `XXX-arXiv-中文版.pdf`。用户明确说"只要英文"或"给我中文的"时，按最新的指示只给对应版本。
- 每轮交付用新文件名（v2、v3…），旧版不覆盖。用户说以后还要更新时，把修订前的 PDF 另存一个文件夹（例如 `v1-审稿修订前/`），源码快照同步保留。
- 先复制到 outputs，用 SendUserFile 发出，再提交到用户连接的文件夹（同名覆盖旧版，提交稿除外）。
- 回复简洁、用中文、不用破折号，说明三件事：改了什么、版式是否不变、还需用户做什么。