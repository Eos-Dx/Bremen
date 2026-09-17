# Target Source Tree

```text
src/bremen/
├── contracts/
│   ├── __init__.py
│   ├── model_runtime.py
│   └── execution.py
├── platform/
│   ├── api/
│   │   ├── app.py
│   │   ├── dependencies.py
│   │   └── routers/
│   │       ├── auth.py
│   │       ├── models.py
│   │       ├── sources.py
│   │       ├── jobs.py
│   │       ├── reports.py
│   │       ├── events.py
│   │       └── pages.py
│   ├── auth/
│   ├── events/
│   ├── jobs/
│   ├── models/
│   ├── reports/
│   ├── runtime/
│   └── sources/
├── model_packages/
│   ├── bremen_v01/
│   └── aramina_v0213/
├── training/
├── ui/
└── compat/  # temporary migration-only package; must trend to zero
```

Dependency rule:

```text
platform -> contracts <- model_packages
platform -> model_packages only through runtime/package factory
model_packages must never import platform/api/jobs/reports/auth
```
