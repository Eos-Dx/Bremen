# Aramina naming alignment

Aramina is the canonical name for the related EOS product throughout this
repository, including agent instructions and archived project-memory text.
Bremen remains a separate product with its own intended use.

This change updates product spelling, Python identifiers, workflow IDs, config
filenames, examples, and documentation references together. Consumers of the
previous workflow ID or Python module names must update their references; no
compatibility aliases are retained. Existing external datasets, model packages,
storage keys, repositories, and local workspaces are not migrated by this change.
Review external paths in example configs before using them.

The default registry uses the unavailable-provider scaffold in
`workflow_aramina_scaffold.py`. Catalog-selected models continue to use the
existing manifest-gated integration in `workflow_aramina.py`.

This is a naming change only: intended use, target population, clinical user,
label definitions, preprocessing algorithms, feature schema, decision thresholds,
and model versions remain unchanged. It does not establish clinical validation
or change the research/draft status of either product. Outputs require clinical
review.

Archived plans and reports use the current spelling for agent consistency;
Git history retains the original historical text.
