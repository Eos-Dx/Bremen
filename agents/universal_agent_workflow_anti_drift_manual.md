# Универсальный рабочий протокол для агентной разработки без дрейфа

## Назначение документа

Этот файл предназначен как опорный документ для любого нового чат-окна, агента, команды или проекта, где работа ведётся через последовательные итерации, планы, ревью, реализацию и precommit-проверку.

Документ описывает:

- как организована работа по PR/итерациям;
- какие роли участвуют в цикле;
- как писать промпты для каждого агента;
- как не терять контекст между окнами, устройствами, днями и исполнителями;
- как отличать утверждение агента от доказательства;
- как не допускать drift: файлового, смыслового, поведенческого, архитектурного, validation-дрейфа и future-scope-дрейфа;
- как закрывать gates только на основе наблюдаемого evidence;
- как строить artifacts, которые можно передать другому инженеру или агенту без перезапуска проекта с нуля.

Главная идея:

```text
Модель может быть заменяемой.
Надёжность создаёт не модель сама по себе, а рабочий substrate: планы, ревью, runtime evidence, validation, snapshot, continuity и строгие gates.
```

Этот документ не должен восприниматься как разовая инструкция. Это рабочая дисциплина, которую нужно применять в каждом новом окне и в каждой итерации.

---

## Базовая философия

### 1. Агентский вывод не равен доказательству

Нельзя принимать как факт фразы вида:

```text
implementation complete
review passed
validation passed
no drift observed
scope is clean
all tests passed
```

Такие фразы являются только claims. Они должны быть подтверждены наблюдаемым evidence:

- содержимым файлов;
- `git status --short`;
- `git diff --name-only`;
- точным списком files read;
- validation commands;
- exit codes;
- короткими outputs;
- review artifact;
- соответствием approved PLAN.md.

Правило:

```text
Не прочитано = не наблюдалось.
Не выполнено = не доказано.
Не записано в artifact = не существует как review evidence.
```

### 2. PLAN.md является контрактом

После прохождения plan-review утверждённый `PLAN.md` становится контрактом реализации.

Implementation agent не должен:

- переизобретать scope;
- расширять PR;
- добавлять удобные, но не запланированные изменения;
- менять команды;
- менять CLI-shape;
- менять runtime object shape;
- добавлять поля, статусы, reason codes;
- трогать frontend/backend/docs/schema/deps вне плана;
- реализовывать будущие PR.

Рабочий код недостаточен, если он drift-ит от approved PLAN.md.

### 3. Review должен проверять claims against evidence

Review artifact не должен быть пересказом того, что агент хотел сделать. Он должен отвечать:

```text
Что реально изменилось?
Какие файлы были прочитаны?
Какие команды были выполнены?
Какие tests прошли?
Какие claims подтверждены?
Какие claims не имеют evidence?
Есть ли drift от PLAN.md?
```

### 4. Контекст должен жить вне модели

Context window может насыщаться. Модель может забывать стратегию, решения, ограничения и intent. Поэтому проект должен хранить thread в явных artifacts:

- planning artifacts;
- review artifacts;
- runtime evidence;
- validation outputs;
- continuity packets;
- handoff summaries;
- explicit next safe actions;
- forbidden actions;
- deferred capabilities.

Цель:

```text
Любой новый агент или инженер должен уметь продолжить работу, не угадывая, где остановился предыдущий исполнитель.
```

### 5. Лучше маленький точный PR, чем большой умный drift

Один PR должен иметь один coherent purpose.

Плохой PR:

```text
Добавляет runtime object, чинит frontend, меняет schema, обновляет docs, добавляет CLI, меняет tests, правит roadmap.
```

Хороший PR:

```text
Добавляет один runtime object + focused tests + минимальную CLI-интеграцию, если она явно выбрана PLAN.md.
```

---

## Общая структура рабочего цикла

Каждая итерация проходит через два больших этапа.

```text
Stage A: Planning Gate
1. planner пишет PLAN.md
2. plan-review проверяет PLAN.md
3. человек коммитит planning artifacts

Stage B: Implementation Gate
4. implementation реализует строго approved PLAN.md
5. precommit-review проверяет implementation against PLAN.md
6. человек коммитит код и создаёт PR
```

Ни один агент не должен самостоятельно делать `git add`, `git commit`, `git push`, `gh pr create`, если это не явная человеческая финальная команда вне агентского review/implementation режима.

---

## Роли агентов

### 1. planner

Назначение:

```text
Создать точный PLAN.md, который станет контрактом реализации.
```

Planner не пишет код, tests, review artifacts, PR body, docs вне разрешённого plan path.

Planner должен:

- определить конкретный scope;
- выбрать exact implementation files;
- выбрать exact test files;
- определить runtime object shape;
- определить command/CLI shape, если нужно;
- определить validation commands;
- определить forbidden scope;
- включить stop conditions;
- включить future precommit Plan Drift Gate requirements;
- зафиксировать roadmap/sequence alignment;
- явно указать deferred capabilities.

Planner не должен:

- писать implementation;
- изменять tests;
- менять roadmap, если задача не roadmap PR;
- придумывать scope за пределами итерации;
- оставлять “we can later decide” там, где implementation должен быть bounded.

### 2. plan-review

Назначение:

```text
Проверить PLAN.md до реализации.
```

Plan-review должен подтвердить:

- PLAN.md exists;
- planning-only;
- exact files selected;
- scope coherent;
- no docs-only/schema-only/frontend-only drift;
- validation strategy adequate;
- prior PR evidence read;
- roadmap alignment checked;
- anti-drift constraints present;
- deferred capabilities explicit;
- implementation can be reviewed later.

Plan-review не запускает full implementation tests, потому что реализации ещё нет.

Plan-review verdicts:

```text
approve = план можно принять
warning = план можно принять, но есть осознанные ограничения
block = план нельзя принимать
```

Если `VERDICT: warning`, секция `BLOCKERS` должна быть пустой.

### 3. implementation

Назначение:

```text
Реализовать approved PLAN.md без расширения scope.
```

Implementation agent должен:

- сначала прочитать PLAN.md и plan-review;
- определить exact allowed files;
- изменить только selected implementation/test files;
- выполнить validation commands;
- записать final implementation report;
- явно указать Plan Drift Check.

Implementation agent не пишет review artifact.

Implementation agent не должен:

- менять PLAN.md;
- менять plan-review;
- менять roadmap/docs/schemas/agents/deps;
- добавлять future behavior;
- реализовывать “удобное” сверх плана;
- делать git mutation;
- запускать Docker/network/provider calls, если это не selected и не безопасно.

### 4. precommit-review

Назначение:

```text
Перед коммитом проверить implementation against PLAN.md на основе evidence.
```

Precommit-review — самый строгий gate.

Он должен:

- читать PLAN.md;
- читать plan-review;
- читать all changed files;
- читать relevant prior artifacts;
- run exact validation commands;
- record git snapshot;
- complete PLAN DRIFT GATE;
- write only precommit-review artifact;
- not modify code/tests.

Precommit-review не должен просто сказать:

```text
validation missing, please confirm if I should run it
```

Если task is full precommit-review, он обязан попытаться выполнить read-only snapshot/grep/validation commands в текущей сессии. Missing validation можно заявлять только если команда была попытана и реально не смогла выполниться.

---

## Структура директорий и artifacts

Рекомендуемая структура:

```text
.project-memory/
  pr/
    0001-example-feature/
      PLAN.md
      reviews/
        plan-review.yml
        precommit-review.yml
  post-milestone/
    strategic-direction/
      agent-manifest.md
  review-artifact.schema.yml
  project_contract.yml
  memory_index.yml
  anchors.yml
```

Код и тесты зависят от проекта, например:

```text
services/<service>/src/<package>/<module>.py
services/<service>/tests/test_<module>.py
```

Главное правило:

```text
Каждый PR имеет свой isolated memory folder.
```

Это позволяет открыть новый чат и сразу понять:

- что планировалось;
- что проверялось;
- что было реализовано;
- какие gates прошли;
- что осталось deferred.

---

## Stage A: Planning Gate подробно

### Цель planning gate

Planning gate нужен не для “подумать”. Он нужен, чтобы создать executable contract.

Хороший PLAN.md должен быть настолько точным, чтобы implementation agent мог действовать без уточнений и без фантазии.

### Минимальная структура PLAN.md

```markdown
# PR <number> — <title>

## Goal

## Context

## Scope

## Non-goals

## Required reads

## Allowed files

## Forbidden files

## Runtime behavior

## Object shape

## Statuses / reason codes

## CLI integration, if selected

## Artifact/output format, if selected

## Rejection behavior

## Tests required

## Validation commands

## Plan Drift Gate requirements for precommit-review

## Stop conditions

## Deferred capabilities

## Roadmap alignment

## Boundary confirmations
```

### PLAN.md должен отвечать на вопросы

```text
Что именно делаем?
Почему это следующий шаг?
Какие файлы можно менять?
Какие файлы нельзя менять?
Какие объекты/функции должны появиться?
Какие поля обязательны?
Какие статусы допустимы?
Какие reason codes допустимы?
Какие tests должны быть добавлены?
Какие validation commands обязательны?
Что считается drift?
Что блокирует implementation?
Что deferred?
```

### Required reads в planner prompt

Planner prompt должен перечислять exact files, которые нужно прочитать.

Плохой вариант:

```text
Read relevant files.
```

Хороший вариант:

```text
Required reads:
* .project-memory/pr/0007-previous-feature/PLAN.md
* .project-memory/pr/0007-previous-feature/reviews/precommit-review.yml
* services/core/src/core/runtime_object.py
* services/core/tests/test_runtime_object.py
```

Причина:

```text
Если файл не указан, агент может его не прочитать.
Если файл не прочитан, review не может ссылаться на него как evidence.
```

### Stop conditions в PLAN.md

Каждый PLAN.md должен включать stop conditions.

Примеры:

```text
Block if implementation would require files outside selected paths.
Block if prior PR evidence is missing.
Block if validation command cannot be selected.
Block if implementation would require dependency changes.
Block if implementation would become docs-only.
Block if hidden reasoning logging is required.
Block if arbitrary command execution is required.
Block if frontend changes are needed but not selected.
```

Stop condition — это не слабое предупреждение. Это инструкция остановиться, а не импровизировать.

---

## Stage A: Plan Review подробно

### Цель plan-review

Plan-review проверяет качество плана до того, как кто-то начнёт писать код.

Plan-review отвечает:

```text
Этот PLAN.md достаточно точный, безопасный и проверяемый?
```

### Verdict semantics

```text
approve = можно идти в implementation
warning = можно идти в implementation, но есть явные ограничения
block = нельзя идти дальше
```

Правило:

```text
warning не может иметь blockers.
block должен иметь blockers.
approve не должен иметь blockers.
```

Если artifact пишет:

```text
VERDICT: warning
BLOCKERS:
- this is not a blocker
```

это artifact drift. Нужно correction.

### Plan-review artifact structure

```yaml
REVIEW ARTIFACT WRITTEN: yes
VERDICT: approve | warning | block

BLOCKERS

WARNINGS

VALIDATION

FILES READ

FILES WRITTEN

SNAPSHOT DELTA

ROADMAP / SEQUENCE CHECK

SCOPE CHECK

DEPENDENCY CHECK

OBJECT / BEHAVIOR CHECK

VALIDATION STRATEGY CHECK

DEFERRED CAPABILITIES CHECK

EVIDENCE COMPLETENESS CHECK

CLAIM-TO-EVIDENCE CONSISTENCY CHECK

DIRTY-TREE CHECK

BOUNDARY CONFIRMATIONS
```

### Allowed dirty tree during planning

During planning gate, a new PR directory can be untracked.

Allowed:

```text
?? .project-memory/pr/<slug>/
```

Only if `find` shows expected files:

```text
.project-memory/pr/<slug>/PLAN.md
.project-memory/pr/<slug>/reviews/plan-review.yml
```

Not allowed:

```text
source files changed during plan-review
schema files changed during plan-review
docs changed during plan-review unless explicitly selected
roadmap changed unexpectedly
agents changed unexpectedly
package/dependency files changed
```

### Plan-review must not overclaim

Plan-review cannot say:

```text
Runtime behavior works.
```

unless runtime behavior already exists and was validated.

For a plan, better wording:

```text
Runtime behavior is planned and appears reviewable.
Implementation behavior cannot be confirmed until tests run in precommit-review.
```

---

## Planning commit

After plan-review passes or has acceptable warning:

```bash
git status --short

git add .project-memory/pr/<slug>/PLAN.md \
        .project-memory/pr/<slug>/reviews/plan-review.yml

git commit -m "chore(<area>): plan <feature>"
```

Do not include implementation files in planning commit.

Planning commit should contain only:

```text
PLAN.md
plan-review.yml
```

---

## Stage B: Implementation подробно

### Цель implementation stage

Implementation agent реализует approved PLAN.md.

Он не архитектор и не planner. Его задача — bounded execution.

### Implementation prompt должен содержать

```text
Task title
Agent role
Mode
Branch
Approved PLAN.md path
Plan-review artifact path
Goal
Context
Do not re-plan
Allowed paths
Forbidden paths
Implementation requirements
Runtime object requirements
Reason codes
Rejection behavior
CLI behavior if selected
Tests required
Validation commands
Plan Drift Check
Stop conditions
Final output format
Boundary confirmations
```

### Implementation output format

```text
IMPLEMENTATION COMPLETE: yes | no

FILES CHANGED

BEHAVIOR IMPLEMENTED

TESTS ADDED OR UPDATED

VALIDATION RUN

VALIDATION RESULTS

DIFF SUMMARY

PLAN COMPLIANCE

PLAN DRIFT CHECK

BLOCKERS

WARNINGS

BOUNDARY CONFIRMATIONS
```

### What implementation may claim

Implementation may claim:

```text
I changed these files.
I added these tests.
I ran these commands.
This command returned exit code 0.
```

Implementation should not be final authority on:

```text
precommit passed
scope is definitely clean
no drift exists
ready to merge
```

Those are precommit-review claims.

### Implementation anti-drift rules

Before each change, implementation must check:

```text
Is this file selected by PLAN.md?
Is this behavior selected by PLAN.md?
Is this field selected by PLAN.md?
Is this CLI shape selected by PLAN.md?
Is this test selected by PLAN.md?
Is this future work?
```

If unsure, implementation must choose the narrower safe path or stop with blocker.

---

## Stage B: Precommit Review подробно

### Цель precommit-review

Precommit-review determines whether the implementation can be safely committed.

It is not a style review. It is an evidence gate.

### Required first actions

A proper precommit-review starts with snapshot:

```bash
git rev-parse --verify HEAD
git status --short
git diff --name-only
```

Then it reads every changed file.

Important nuance:

```text
git diff --name-only may not show untracked files.
git status --short is required to catch untracked files.
```

So if status shows:

```text
?? services/core/src/core/new_module.py
?? services/core/tests/test_new_module.py
```

those files must be read even if `git diff --name-only` is empty.

### Required validation evidence

Precommit-review must run exact validation commands from PLAN.md.

Each command must include:

```text
command string
exit_code
short output
```

Example:

```text
- PYTHONPATH=services/core/src python -m pytest services/core/tests/test_runtime_object.py -q
  - exit_code: 0
  - output: 24 passed
```

Not enough:

```text
Tests passed.
```

### Required grep checks

For autonomy-safe projects, include grep checks such as:

```bash
grep -R -n "PLACEHOLDER" services/core/src services/core/tests .project-memory/pr/<slug> || true

grep -R -n "subprocess\|os.system\|shell=True\|docker\|requests\|urllib\|openai\|anthropic\|git commit\|git push\|gh pr create" \
  services/core/src/core/<module>.py \
  services/core/tests/test_<module>.py \
  2>/dev/null || true
```

Matches are not automatically blockers. They must be classified.

Allowed examples:

```text
forbidden phrase appears in a test assertion ensuring it is rejected
PLACEHOLDER appears in an old test that asserts placeholder absence
```

Blocker examples:

```text
runtime source imports requests unexpectedly
runtime source calls subprocess
runtime source contains non-semantic PLACEHOLDER
runtime source embeds git commit behavior
```

### Precommit artifact structure

```yaml
REVIEW ARTIFACT WRITTEN: yes
VERDICT: pass | warning | block

BLOCKERS

WARNINGS

VALIDATION

FILES READ

FILES WRITTEN

SNAPSHOT DELTA

PLAN DRIFT GATE
  verdict:
  file drift:
  behavior drift:
  object-shape drift:
  CLI drift:
  frontend drift:
  validation drift:
  semantic drift:
  future-scope drift:
  accepted deviations:
  blockers:

SCOPE CHECK

DEPENDENCY CHECK

RUNTIME OBJECT CHECK

EVIDENCE SOURCE CHECK

AUTONOMY SAFETY CHECK

FRONTEND BOUNDARY CHECK

CLI INTEGRATION CHECK

COMMAND EXECUTION SAFETY CHECK

PLACEHOLDER CHECK

PACKAGING/DEPENDENCY CHECK

DEFERRED CAPABILITIES CHECK

EXECUTABLE-FIRST CHECK

VALIDATION COMPLETENESS CHECK

EVIDENCE COMPLETENESS CHECK

CLAIM-TO-EVIDENCE CONSISTENCY CHECK

DIFF COMPLETENESS CHECK

DIRTY-TREE CHECK

BOUNDARY CONFIRMATIONS
```

---

## PLAN DRIFT GATE

PLAN DRIFT GATE is mandatory in precommit-review.

It answers:

```text
Does the implementation match the approved PLAN.md?
```

Working code is not enough.

### Required PLAN DRIFT GATE fields

```text
PLAN DRIFT GATE

* verdict: pass | warning | block
* file drift:
* behavior drift:
* object-shape drift:
* CLI drift:
* frontend drift:
* validation drift:
* semantic drift:
* future-scope drift:
* accepted deviations:
* blockers:
```

### File drift

Check:

```text
planned files vs changed files
```

Evidence:

```bash
git status --short
git diff --name-only
```

Block if:

```text
any changed file is outside PLAN.md selected paths
untracked files are not read
docs/schemas/agents/deps changed unexpectedly
frontend files changed when frontend was deferred
```

### Behavior drift

Check:

```text
planned behavior vs implemented behavior
```

Block if:

```text
implementation adds future behavior
implementation changes contract semantics
implementation adds autonomous action not selected
implementation performs evaluation/finalization not selected
```

### Object-shape drift

Check:

```text
planned objects, fields, statuses, reason codes vs implementation
```

Block if:

```text
fields renamed without plan support
statuses changed
reason codes missing
extra statuses added
object semantics changed
```

### CLI drift

Check:

```text
planned command name, arguments, output, exit code semantics vs implementation
```

Block if:

```text
new command added without PLAN.md
argument shape differs
stdout/stderr differs materially
exit codes differ
CLI uses a different entrypoint pattern
```

### Frontend drift

Check:

```text
whether frontend was selected or deferred
```

Block if:

```text
frontend/browser/app files changed while frontend was deferred
```

### Backlog/persistence drift

For continuity/self-improvement projects, check:

```text
whether persistence/queue/store behavior was selected
```

Block if:

```text
queue or storage added without explicit plan
```

### Validation drift

Check:

```text
exact PLAN.md commands vs commands executed
```

Block if:

```text
validation skipped
validation substituted
combined tests weakened
focused tests omitted
exit codes not recorded
outputs not recorded
```

### Semantic drift

Check meaning, not only file lists.

Examples:

```text
hash derivation changed from canonical JSON to raw dict repr
created_at made nondeterministic despite deterministic plan
resume_prompt includes hidden reasoning despite explicit rejection
runtime object evaluates proof when plan says only reference it
```

### Future-scope drift

Block if implementation adds things planned for future PRs:

```text
frontend UI
backlog store
provider calls
model switching
benchmark runner
autonomous repair
automatic PR creation
gate finalization
proof evaluation
schema migration
dependency changes
```

---

## Evidence completeness rules

### Files read rule

```text
Any claim about a file requires that file in FILES READ.
```

Examples:

Cannot claim:

```text
No frontend files changed.
```

unless snapshot/diff evidence supports it.

Cannot claim:

```text
Prior PR compatibility preserved.
```

unless prior PLAN.md and precommit-review artifacts were read.

Cannot claim:

```text
No provider calls introduced.
```

unless relevant implementation files were read and grep/test evidence supports it.

### Prior gate evidence rule

If a PR depends on prior PRs, review must read both:

```text
.project-memory/pr/<prior>/PLAN.md
.project-memory/pr/<prior>/reviews/precommit-review.yml
```

For source-level compatibility, also read relevant implementation/test files.

### Validation evidence rule

A validation claim requires:

```text
exact command
exit code
short output
```

Bad:

```text
Validation passed.
```

Good:

```text
- python -m compileall -f services/core/src services/api/src
  - exit_code: 0
  - output: no syntax errors reported
```

### Snapshot evidence rule

Every precommit-review must include:

```text
HEAD
git status --short
git diff --name-only
```

Without snapshot, review cannot prove dirty-tree scope.

### Claim-to-evidence consistency

Every boundary confirmation must be supported.

Bad:

```text
confirm: no dependency changes made
```

without reading snapshot/diff or relevant files.

Good:

```text
confirm: no dependency changes made
```

when `git status --short` and `git diff --name-only` show no dependency files changed.

---

## Dirty-tree discipline

### Why dirty tree matters

Agents can accidentally leave files modified, generate artifacts in wrong places, or silently change unrelated files.

So every gate checks dirty tree.

### Planning gate allowed dirty tree

Allowed:

```text
?? .project-memory/pr/<slug>/PLAN.md
?? .project-memory/pr/<slug>/reviews/plan-review.yml
```

Possibly represented as:

```text
?? .project-memory/pr/<slug>/
```

In that case, reviewer must inspect contents:

```bash
find .project-memory/pr/<slug> -maxdepth 4 -type f | sort
```

### Implementation gate allowed dirty tree

Allowed only if PLAN.md selected these files:

```text
M services/.../<existing_file>.py
?? services/.../<new_module>.py
?? services/.../test_new_module.py
?? .project-memory/pr/<slug>/reviews/precommit-review.yml
```

Block if unexpected:

```text
ROADMAP.md
.project-memory/post-*/**
docs/**
schemas/**
agents/**
package files
frontend files when deferred
Docker files
CI files
```

---

## Drift taxonomy

### 1. File drift

Agent changes files outside selected scope.

Example:

```text
PLAN selected runtime module and tests.
Implementation also changed README and schema.
```

### 2. Behavior drift

Agent implements behavior that was not planned.

Example:

```text
PLAN selected evidence reference creation.
Implementation also evaluates evidence and returns pass/fail.
```

### 3. Object-shape drift

Agent changes fields/statuses/reason codes.

Example:

```text
PLAN selected status: created | rejected.
Implementation adds status: approved.
```

### 4. CLI drift

Agent changes command interface beyond plan.

Example:

```text
PLAN selected `tool doctor continuity --input <path>`.
Implementation adds `tool auto-fix`.
```

### 5. Validation drift

Agent skips or weakens tests.

Example:

```text
PLAN required combined regression.
Review ran only focused test.
```

### 6. Semantic drift

Agent keeps names but changes meaning.

Example:

```text
Field named `evidence_ref` stores plain narrative instead of admissible evidence reference.
```

### 7. Future-scope drift

Agent implements next PR early.

Example:

```text
PLAN says UI deferred.
Implementation adds frontend panel.
```

### 8. Evidence drift

Review claims more than it observed.

Example:

```text
Review says prior gate passed but did not read prior precommit-review.yml.
```

### 9. Process drift

Agent performs wrong mode.

Example:

```text
plan-review runs correction-only prompt instead of full review.
precommit-review reports missing validation without attempting to run it.
implementation writes review artifact.
```

---

## Prompt design principles

### 1. Start with identity and mode

Every prompt begins with:

```text
Task: PR <number> — <title>
Agent: planner | plan-review | implementation | precommit-review
Mode: planning only | review PLAN.md only | implementation | full implementation review
Branch: <branch-name>
```

This prevents role confusion.

### 2. Declare exact write target

Use:

```text
Write only:
* <exact path>
```

For implementation:

```text
Do not write review artifacts.
```

For review:

```text
Write only precommit-review.yml.
Do not modify implementation files.
```

### 3. Declare forbidden writes

Explicitly list forbidden paths.

Do not rely on “be careful.”

### 4. Declare required reads

List exact files.

Include prior artifacts when needed.

### 5. Declare allowed commands and forbidden commands

For planning/review:

```text
Allowed read-only commands:
* git rev-parse --verify HEAD
* git status --short
* git diff --name-only
* find ...
* grep ...
* date -u ...
```

Forbidden:

```text
git add
git commit
git push
git reset
git checkout
git switch
git merge
git rebase
git clean
git log
gh release
docker
docker compose
rm
mv
sudo
chmod
chown
pip install
python -m pip install
```

### 6. Give stop conditions

Stop conditions prevent improvisation.

### 7. Require final output format

If final output format is not specified, agents invent structure.

### 8. Include boundary confirmations

Boundary confirmations force agent to explicitly state:

```text
what it did not do
what it deferred
what it checked
what remains forbidden
```

But confirmations are only valid if supported by evidence.

---

## Universal prompt template: planner

```text
Task: PR <number> — <title> Plan

Agent: planner

Mode: planning only

Branch: <branch>

Goal:
Plan <one coherent executable-first capability>.

Context:
<short prior PR sequence or relevant architecture context>

Purpose:
<why this PR is next>

Core principle:
Agent output is not proof. Runtime-captured or explicitly observed evidence is proof.

Anti-drift principle:
The approved PLAN.md will be the implementation contract.

Write only:
* .project-memory/pr/<slug>/PLAN.md

Do not write code.
Do not write tests.
Do not write review artifacts.
Do not modify roadmap/docs/schemas/agents/deps unless this PR explicitly selects them.

Required reads:
* <exact files>

Allowed read-only commands:
* git rev-parse --verify HEAD
* git status --short
* git diff --name-only
* find ...
* grep ...
* date -u +%Y-%m-%dT%H:%M:%SZ

Forbidden commands:
* git add
* git commit
* git push
* ...

Planning requirements:
PLAN.md must define:
* exact implementation files
* exact test files
* object/function shape
* statuses
* reason codes
* rejection behavior
* validation commands
* Plan Drift Gate requirements
* stop conditions
* deferred capabilities

Do not plan:
* future PR behavior
* autonomous code edits
* git mutation
* provider/LLM calls
* shell command execution
* network
* Docker
* schema/dependency changes unless explicitly selected

Final output:
PLAN written: yes | no

decisions made:
* implementation files:
* test files:
* object shape:
* reason codes:
* validation commands:
* Plan Drift Gate requirements:
* blockers:
* warnings:

files read:
files written:
files intentionally ignored:

boundary confirmations:
* confirm: only PLAN.md written
* confirm: no code written
* confirm: no tests written
* confirm: no review artifact written
* confirm: exact implementation paths selected
* confirm: exact test paths selected
* confirm: Plan Drift Gate required
* confirm: no git mutation commands run
```

---

## Universal prompt template: plan-review

```text
Task: PR <number> — <title> Plan Review

Agent: plan-review

Mode: review PLAN.md only

Branch: <branch>

Review target:
* .project-memory/pr/<slug>/PLAN.md

Write only:
* .project-memory/pr/<slug>/reviews/plan-review.yml

Review goal:
Determine whether PLAN.md safely plans <capability>.

Do not modify PLAN.md.
Do not write implementation code.
Do not write tests.
Do not modify roadmap/docs/schemas/agents/deps.
Do not run git mutation commands.

Required reads:
* .project-memory/pr/<slug>/PLAN.md
* .project-memory/review-artifact.schema.yml
* <prior PLAN.md files>
* <prior precommit-review.yml files>
* <relevant source/test files>

Allowed read-only commands:
* git rev-parse --verify HEAD
* git status --short
* git diff --name-only
* find .project-memory/pr/<slug> -maxdepth 4 -type f | sort
* git diff -- .project-memory/pr/<slug>/PLAN.md
* grep ...
* date -u +%Y-%m-%dT%H:%M:%SZ

Dirty-tree rule:
The PR planning directory is allowed only if it contains PLAN.md and this plan-review artifact.

Checklist:
* PLAN.md exists
* PLAN.md is planning-only
* exact implementation files selected
* exact test files selected
* PR is executable-first
* PR is not docs-only/schema-only/frontend-only/packaging-only
* validation strategy complete
* deferred capabilities explicit
* Plan Drift Gate required
* no unsafe autonomy planned

Final output:
REVIEW ARTIFACT WRITTEN: yes | no
VERDICT: approve | warning | block

BLOCKERS

WARNINGS

VALIDATION

FILES READ

FILES WRITTEN

SNAPSHOT DELTA

SCOPE CHECK

DEPENDENCY CHECK

VALIDATION STRATEGY CHECK

EVIDENCE COMPLETENESS CHECK

CLAIM-TO-EVIDENCE CONSISTENCY CHECK

DIRTY-TREE CHECK

BOUNDARY CONFIRMATIONS
```

---

## Universal prompt template: implementation

```text
Task: PR <number> — <title> Implementation

Agent: implementation

Mode: implementation

Branch: <branch>

Use this approved PLAN.md as the full implementation contract:
* .project-memory/pr/<slug>/PLAN.md

Plan-review artifact:
* .project-memory/pr/<slug>/reviews/plan-review.yml

Goal:
Implement exactly what PLAN.md approved.

Do not re-plan.
Do not expand scope.
Do not write review artifacts.
Do not modify PLAN.md.
Do not modify plan-review.yml.
Do not modify roadmap/docs/schemas/agents/deps unless PLAN.md selected them.

Anti-drift rule:
Working code is not enough if it drifts from PLAN.md.

Expected implementation/test paths:
* <exact selected files>

Implementation requirements:
* <runtime objects>
* <fields>
* <statuses>
* <reason codes>
* <rejection behavior>
* <CLI behavior if selected>
* <artifact format if selected>

Do not implement:
* automatic code edits
* commits/push/PR creation
* provider/model calls
* network
* Docker
* arbitrary shell execution
* proof evaluation unless selected
* gate finalization unless selected
* future PR behavior

Testing requirements:
* <focused tests>
* <regression tests>

Validation:
Run exact validation commands from PLAN.md.

PLAN DRIFT CHECK:
* planned files vs changed files:
* planned objects vs implemented objects:
* planned fields vs implemented fields:
* planned reason codes vs implemented reason codes:
* planned CLI shape vs implemented CLI shape:
* planned validation vs executed validation:
* future behavior avoided:
* deviations:

Final output:
IMPLEMENTATION COMPLETE: yes | no

FILES CHANGED

BEHAVIOR IMPLEMENTED

TESTS ADDED OR UPDATED

VALIDATION RUN

VALIDATION RESULTS

DIFF SUMMARY

PLAN COMPLIANCE

PLAN DRIFT CHECK

BLOCKERS

WARNINGS

BOUNDARY CONFIRMATIONS
```

---

## Universal prompt template: precommit-review

```text
Task: PR <number> — <title> Precommit Review

Agent: precommit-review

Mode: full implementation review

Branch: <branch>

Use approved PLAN.md as contract:
* .project-memory/pr/<slug>/PLAN.md

Use plan-review artifact:
* .project-memory/pr/<slug>/reviews/plan-review.yml

Write only:
* .project-memory/pr/<slug>/reviews/precommit-review.yml

This is not a correction task.
This is not a missing-evidence report.
Do not ask for confirmation.
Do not stop after saying validation is missing.
You must attempt required read-only snapshot, grep, and validation commands now.

Do not modify implementation files.
Do not modify tests.
Do not modify PLAN.md.
Do not modify plan-review.yml.
Do not modify roadmap/docs/schemas/agents/deps.
Do not run git mutation commands.
Do not run Docker commands.

Required first actions:
* git rev-parse --verify HEAD
* git status --short
* git diff --name-only

Then read every changed file from status/diff, including untracked files.

Required reads:
* PLAN.md
* plan-review.yml
* review schema
* prior PR PLAN/precommit artifacts
* all changed files
* all relevant source/test files

Safety greps:
* grep -R -n "PLACEHOLDER" ... || true
* grep -R -n "subprocess\|os.system\|shell=True\|docker\|requests\|urllib\|openai\|anthropic\|git commit\|git push\|gh pr create" ... || true

Validation:
Run exact PLAN.md validation commands.
Record command strings, exit codes, and short outputs.

PLAN DRIFT GATE:
* verdict: pass | warning | block
* file drift:
* behavior drift:
* object-shape drift:
* CLI drift:
* frontend drift:
* validation drift:
* semantic drift:
* future-scope drift:
* accepted deviations:
* blockers:

Hard pass requirements:
* PLAN DRIFT GATE pass or acceptable warning
* all required validation commands pass
* no validation skipped
* every changed file read
* every claim backed by evidence
* dirty tree contains only expected files plus precommit artifact
* no unsafe autonomy introduced

Final output:
REVIEW ARTIFACT WRITTEN: yes | no
VERDICT: pass | warning | block

BLOCKERS

WARNINGS

VALIDATION

FILES READ

FILES WRITTEN

SNAPSHOT DELTA

PLAN DRIFT GATE

SCOPE CHECK

DEPENDENCY CHECK

RUNTIME OBJECT CHECK

AUTONOMY SAFETY CHECK

VALIDATION COMPLETENESS CHECK

EVIDENCE COMPLETENESS CHECK

CLAIM-TO-EVIDENCE CONSISTENCY CHECK

DIFF COMPLETENESS CHECK

DIRTY-TREE CHECK

BOUNDARY CONFIRMATIONS
```

---

## Handling failed reviews

### Case 1: Review blocks because real issue found

Example:

```text
Tests failed.
Unexpected file changed.
PLAN DRIFT GATE block.
Implementation added provider call.
```

Action:

```text
Do not commit.
Fix implementation or plan, depending on issue.
Rerun implementation/precommit-review.
```

### Case 2: Review blocks because reviewer did not execute validation

Example:

```text
VERDICT: block
Required validation commands were not executed.
Please confirm if you want me to run them.
```

This is process drift.

Action:

```text
Do not commit.
Rerun full precommit-review with explicit instruction:
Do not ask for confirmation. Execute validation now.
```

### Case 3: Review artifact has internal inconsistency

Example:

```text
VERDICT: warning
BLOCKERS contains a non-blocker
```

Action:

```text
Run artifact correction only.
Do not redo full review unless evidence is missing.
```

### Case 4: Agent used wrong task context

Example:

```text
PR 0008 review reads PR 0007 as target.
Correction command from old PR appears in validation.
```

Action:

```text
Rerun full review, not correction.
Explicitly say: this is not prior correction task.
```

---

## Final PR commit and PR body

After precommit-review passes:

```bash
git status --short
git diff --name-only

git add <exact implementation files> \
        <exact test files> \
        .project-memory/pr/<slug>/reviews/precommit-review.yml

git status --short

git commit -m "feat(<area>): <short feature>"

git status --short
git rev-list --count main..HEAD

git push -u origin <branch>

gh pr create \
  --base main \
  --head <branch> \
  --title "feat(<area>): <short feature>" \
  --body-file /tmp/pr-body.md \
  --reviewer <reviewer> \
  --assignee <assignee>
```

PR body structure:

```markdown
## Summary

## Changed

## Behavior

## Validation

## Next step
```

Validation section must include exact numbers:

```text
focused tests: N passed
combined regression: N passed
task/service check returned ready
Plan Drift Gate passed
```

---

## Continuity layer

A strong workflow must preserve thread across sessions.

Each transition should answer:

```text
Where are we?
What was the goal?
What was approved?
What evidence exists?
What is still blocked?
What files are in scope?
What files are out of scope?
What would count as drift?
What is the next safe action?
What is deferred?
```

Recommended continuity packet fields:

```text
project_state_ref
current_pr
current_goal
approved_plan_ref
latest_review_status
latest_validation_status
evidence_refs
known_drift_risks
deferred_capabilities
next_safe_action
blocked_actions
files_in_scope
files_out_of_scope
resume_summary
resume_prompt
phase_identity
run_identity
requires_human_review
```

Resume prompt must be deterministic and template-based. It must not contain hidden chain-of-thought.

Good resume prompt includes:

```text
current objective
required reads
evidence refs
files in scope
files out of scope
drift risks
next safe action
forbidden actions
```

Bad resume prompt:

```text
Continue where we left off and use your judgment.
```

---

## Recommended naming conventions

Branches:

```text
0001-short-feature-name
0002-next-capability
0003-runtime-object
```

Planning commits:

```text
chore(<area>): plan <feature>
```

Implementation commits:

```text
feat(<area>): add <feature>
fix(<area>): correct <behavior>
chore(<area>): update <non-runtime-support>
```

Artifacts:

```text
.project-memory/pr/<slug>/PLAN.md
.project-memory/pr/<slug>/reviews/plan-review.yml
.project-memory/pr/<slug>/reviews/precommit-review.yml
```

---

## Universal anti-drift checklist

Before accepting any gate, ask:

```text
Is this the right PR?
Is this the right role?
Is this the right mode?
Was the correct target file read?
Were all changed files read?
Were untracked files included?
Was git snapshot recorded?
Were exact validation commands run?
Were exit codes recorded?
Is PLAN DRIFT GATE present?
Does PLAN DRIFT GATE pass?
Are blockers empty for pass/warning?
Is every claim supported by FILES READ or VALIDATION?
Did review write only the review artifact?
Did implementation avoid review artifacts?
Did planning avoid code/tests?
Are future capabilities deferred?
Are unsafe autonomy paths rejected?
Is the next safe action explicit?
```

If any answer is no, do not commit.

---

## The minimal trust model

A project using agents should trust only this chain:

```text
Intent -> PLAN.md -> plan-review -> implementation -> validation -> precommit-review -> commit -> PR
```

Do not trust:

```text
agent confidence
large context window
smooth explanation
claims of pass
claims of no drift
claims of no changes
```

Trust:

```text
files read
snapshots
validation outputs
exit codes
plan-review artifacts
precommit-review artifacts
explicit drift checks
bounded commits
```

---

## Most common failure modes and fixes

### Failure: Agent fixes one function and breaks neighbors

Cause:

```text
No bounded PLAN.md or file drift check.
```

Fix:

```text
Select exact files.
Run focused and regression tests.
Precommit-review compares planned files vs changed files.
```

### Failure: Agent forgets strategy after long context

Cause:

```text
Context lives inside model instead of artifacts.
```

Fix:

```text
Maintain continuity packet, PLAN.md, review artifacts, handoff summaries.
```

### Failure: Review passes without running tests

Cause:

```text
Narrative review instead of evidence review.
```

Fix:

```text
Validation completeness required. No command/exit code/output = no pass.
```

### Failure: Agent asks for confirmation instead of executing review

Cause:

```text
Prompt allows missing-evidence report pattern.
```

Fix:

```text
State: do not ask for confirmation; execute validation now; report missing only after attempted execution.
```

### Failure: Old PR context contaminates new review

Cause:

```text
Task drift from previous chat/window.
```

Fix:

```text
Prompt says exact PR, exact branch, exact target file, not correction, not previous task.
```

### Failure: Warning artifact contains blockers

Cause:

```text
Verdict semantics drift.
```

Fix:

```text
Artifact correction only: warning must have empty BLOCKERS.
```

---

## Golden rules

```text
1. PLAN.md is the contract.
2. Review artifacts are evidence gates, not essays.
3. Do not trust claims without files read and validation output.
4. Every changed file must be read.
5. Every required command must have exit code and output.
6. PLAN DRIFT GATE is mandatory before commit.
7. Dirty tree must be explained.
8. Future work must stay future work.
9. Agents do not mutate git in planning/review/implementation modes.
10. Continuity must be explicit, durable, reviewable, and resumable.
```

---

## Short onboarding prompt for a new chat window

Use this when opening a new window:

```text
You are operating as the orchestration brain for this project.

Use the project workflow from `universal_agent_workflow_anti_drift_manual.md`.

The core process is:
1. planner writes only PLAN.md
2. plan-review writes only plan-review.yml
3. after accepted plan-review, human commits planning artifacts
4. implementation changes only PLAN.md-approved files
5. precommit-review writes only precommit-review.yml and must run validation
6. after precommit pass, human commits code and opens PR

Never treat agent claims as evidence.
Use files read, git snapshot, validation commands, exit codes, and review artifacts.

Approved PLAN.md is the implementation contract.
Working code is insufficient if it drifts from PLAN.md.

Precommit-review must include PLAN DRIFT GATE with file, behavior, object-shape, CLI, frontend, validation, semantic, and future-scope drift checks.

Do not accept pass if validation is missing, skipped, or only narrated.
Do not accept warning if BLOCKERS is non-empty.
Do not accept claims about files not listed in FILES READ.
Do not allow agents to run git mutation commands.

When asked for the next step, produce the two prompts needed for the current stage:
- planner + plan-review before planning gate
- implementation + precommit-review after plan-review is accepted

Keep scope small, executable-first, and evidence-backed.
```

---

## Short reviewer mantra

```text
Not in FILES READ = not observed.
No command output = not validated.
No PLAN DRIFT GATE = no pass.
Unexpected dirty tree = no commit.
Future scope implemented early = drift.
Warning with blockers = invalid artifact.
```

---

## Short implementer mantra

```text
Read PLAN.md.
Change only selected files.
Implement only selected behavior.
Test exactly what PLAN.md requires.
Do not write review artifacts.
Do not touch future scope.
Report deviations honestly.
```

---

## Short planner mantra

```text
Make the future implementation boring.
Exact files.
Exact behavior.
Exact tests.
Exact validation.
Exact stop conditions.
Explicit deferred work.
```

---

## Short continuity mantra

```text
The model may forget.
The artifacts must not.
```
