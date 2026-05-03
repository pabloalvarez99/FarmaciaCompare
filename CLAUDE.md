# FarmaciaCompare — CLAUDE.md

## Prioridad del proyecto

- **Activo**: `apps/web` (Next.js 14 App Router, deploy Vercel) — superficie pública usuario.
- **Activo**: `services/api-gateway` (NestJS) — backend principal, endpoints REST + auth + Prisma.
- **Activo secundario**: `apps/admin`, `apps/dashboard` — paneles internos, baja prioridad.
- **Pausado / experimental**: `mobile/`, `services/price-service/` — no romper, no expandir salvo pedido explícito.
- **Default código nuevo**: features usuario → `apps/web` + `services/api-gateway`. Tipos compartidos → `packages/shared-types`. Schema → `packages/database` (Prisma).

## Bitácora obligatoria

- Archivo único de contexto durable: `bitacora.md` en root.
- Actualizar al **final de sesión**, **post-deploy**, y tras **cambio significativo** (feature, fix usuario-visible, refactor estructural, migración DB).
- Formato: entradas con fecha ISO (`## 2026-05-03`), bullets cortos, link a commit/PR/deploy.
- NO duplicar lo que ya está en git log — registrar **por qué**, decisiones, estado actual, próximo paso.

## Ciclo de cierre obligatorio

Orden fijo, sin pedir confirmación, tras feature/fix/refactor visible:

1. **Actualizar `bitacora.md`** — qué cambió, por qué.
2. **Verificar** — `pnpm turbo typecheck` (o `pnpm -w tsc --noEmit` si no hay task), `pnpm turbo test` para paquetes con tests, `pnpm turbo lint`.
3. **Commit** — Conventional Commits, scope claro (`feat(web):`, `fix(api):`, `refactor(db):`), incluir `Co-Authored-By: Claude <noreply@anthropic.com>`.
4. **Push** a `master`.
5. **Deploy** si toca `apps/web` u otra app con deploy automático Vercel — verificar trigger.
6. **Segunda pasada bitácora** — agregar URL deploy / commit SHA / estado verificado.

NO aplica a: WIP intermedio, lectura/exploración, debug puro sin cambio funcional.

## Workflow

- **Plan mode** para tareas 3+ pasos o decisión arquitectural. Re-planificar si algo se desvía.
- **Subagentes** para research paralelo, exploración monorepo, análisis cross-package — mantener contexto principal limpio.
- **Verificación antes de done** — typecheck + test + lint pasan antes de commit. Probar UI en browser para cambios visibles `apps/web`.
- **Root cause sobre parche** — leer error exacto, encontrar causa, arreglar una vez. No try/catch silenciador, no `as any` evasivo.

## Core principles

- **Simplicity first** — cambio mínimo necesario. No abstracciones especulativas.
- **No laziness** — estándar staff engineer. Cero TODO para "después".
- **Minimal impact** — tocar solo lo necesario. Diff chico, revisable.

## Stack overview

**Monorepo**: Turborepo + pnpm 9, Node ≥20.

**Apps** (`apps/`):
- `web/` — Next.js 14 App Router, React 18, Tailwind, shadcn-style (Radix), TanStack Query, Zustand, react-hook-form + zod. Deploy Vercel.
- `admin/`, `dashboard/` — paneles Next.js internos.

**Services** (`services/`):
- `api-gateway/` — NestJS 10, Prisma 5, Passport JWT, Helmet, Throttler, ioredis, Elasticsearch, AWS S3 presign.
- `price-service/` — experimental, no expandir.

**Packages** (`packages/`):
- `database/` — Prisma schema + client (`@farmacia/database`).
- `shared-types/` — tipos cross-app.
- `config/` — config compartida.

**Mobile** (`mobile/`) — pausado.

**Comandos clave** (root):
```bash
pnpm dev              # turbo dev — todos los apps
pnpm build            # turbo build
pnpm test             # turbo test
pnpm lint             # turbo lint
pnpm db:generate      # prisma generate
pnpm db:push          # prisma db push (dev)
pnpm db:migrate       # prisma migrate
```

**Deploy**: `apps/web` → Vercel (auto via push a `master`). API gateway → manual / propio.

## Workflow Orchestration (legacy)

### 1. Plan Node Default
- Enter plan mode for ANY non-trivial task (3+ steps or architectural decisions)
- If something goes sideways, STOP and re-plan immediately - don't keep pushing
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Subagent Strategy
- Use subagents liberally to keep main context window clean
- Offload research, exploration, and parallel analysis to subagents
- For complex problems, throw more compute at it via subagents
- One task per subagent for focused execution

### 3. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until mistake rate drops
- Review lessons at session start for relevant project

### 4. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 5. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes - don't over-engineer
- Challenge your own work before presenting it

### 6. Autonomous Bug Fixing
- When given a bug report: just fix it. Don't ask for hand-holding
- Point at logs, errors, failing tests - then resolve them
- Zero context switching required from the user
- Go fix failing CI tests without being told how

## Task Management

1. **Plan First**: Write plan to `tasks/todo.md` with checkable items
2. **Verify Plan**: Check in before starting implementation
3. **Track Progress**: Mark items complete as you go
4. **Explain Changes**: High-level summary at each step
5. **Document Results**: Add review section to `tasks/todo.md`
6. **Capture Lessons**: Update `tasks/lessons.md` after corrections

## CLI Rules

- Lee archivos antes de editar; no re-leer salvo cambio.
- Skip files >100KB salvo necesario.
- Prefer CLI directo (`gh`, `git`, `pnpm`, `turbo`, `prisma`) sobre MCP equivalents.
- Errores: citar mensaje exacto, root cause, fix una vez. No retry ciego.
- Output: sin saludos / recaps / sign-offs. Code blocks con language tag. Edits = solo líneas cambiadas.
- Accuracy: nunca adivinar APIs / versiones / flags / SHAs / package names — leer código o docs.
- Batch reads/edits relacionados en una sola operación.

## Obsidian Mind Vault

Segundo cerebro compartido entre proyectos. Path: `C:\Users\Administrator\Documents\obsidian-mind\`.

**Mapa**:
- `brain/Gotchas.md` — trampas reproducibles, errores con costo. Header `## FarmaciaCompare — <tema>`.
- `brain/Patterns.md` — patrones reutilizables (>2 usos).
- `brain/Key Decisions.md` — decisiones irreversibles + razón.
- `brain/North Star.md` — objetivo a largo plazo.
- `brain/Skills.md` — habilidades adquiridas.
- `brain/Memories.md` — recuerdos cross-proyecto.
- `reference/FarmaciaCompare Architecture.md` — snapshot arquitectura (también `Tu Farmacia Architecture.md` legacy + `tu-farmacia-*.md`).
- `work/active/<feature>.md` — features en curso.
- `work/archive/` — features cerrados.
- `work/incidents/` — postmortems.

**Protocolo inicio sesión**:
1. Leer `brain/Gotchas.md` filtrando `## FarmaciaCompare — *`.
2. Leer `brain/Key Decisions.md` si toca arquitectura / DB / auth / deploy.
3. Leer `work/active/<feature>.md` si feature continúa.

**Cierre sesión** (APPEND, nunca sobrescribir):
- Trampas nuevas → `Gotchas.md`.
- Decisiones irreversibles → `Key Decisions.md`.
- Patrones >2 usos → `Patterns.md`.
- Features abiertos → `work/active/`.
- Cambios estructurales → `reference/FarmaciaCompare Architecture.md`.

**Formato caveman comprimido**: bullet/línea. Sin artículos. `X → Y` para causalidad. Abreviaciones (DB, fn, req, res, auth, impl). Errores exactos en backticks.

**Reglas**:
- APPEND, no sobrescribir.
- Header `## FarmaciaCompare — <tema>` separa contextos cross-proyecto.
- Verificar antes de citar — vault puede estar stale (vault refleja momento de escritura, no estado actual).
- No duplicar bitácora — vault = cross-proyecto, bitácora = este repo.
- Paths con espacios entre comillas dobles.
