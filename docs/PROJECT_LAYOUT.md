# Repository layout

See [PROJECT_MAP.md](../PROJECT_MAP.md) for the current entry and [the handoff](handoff_next_stage.md) for exact study artifacts.

The repository root is the complete project. legal_skill_guard/ is its Python source package, alongside experiments/, configs/, data/, runs/ and paper/. These are components of one project, not independent copies.

- legal_skill_guard/ contains learning, inference transport, task adaptation, scoring and storage.
- experiments/ contains executable drivers. Use the configuration recorded for a particular study, not an arbitrary historical default.
- configs/ and their frozen manifests identify scientific versions.
- data/ and runs/ hold research material; they must not be treated as disposable caches.
- paper/ and manuscript-review artifacts identify the completed v16 documents.
- ops/ and patches/ preserve the measured inference setup.
- recovery/ records publication distributions, not another active development tree.
- Dated reports and protocols describe their own completed experiments, not current launch instructions.

Authoring-agent instructions, private working goals, machine-specific cache directories, virtual environments and model weights are excluded from this public source view. The original immutable scientific sources and supplementary data are preserved separately from updated navigation.

The [integrity report](PROJECT_INTEGRITY_20261105.json) records the source-workspace checks. The full test suite is not described as all green: five historical AST-lock assertions differ from the frozen v6 implementation and were reproduced against the pre-move snapshot.

