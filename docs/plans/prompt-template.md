# Prompt template — how to hand work to an agent (Cursor/Claude)

Fill this in when you want an agent to build or change something. The whole point: keep the
prompt **short and imperative** by *pointing at* the durable docs instead of restating them.
If you find yourself pasting a rule or a schema into the prompt, stop — it already lives in a
`CONV-*` or in ARCHITECTURE, and the prompt should reference it by ID/link.

---

## Where things live (so you know what to reference, not restate)

| You want to say... | It lives in... | Reference it as... |
|---|---|---|
| a rule that spans domains (auth, pagination, ingredient model…) | `docs/plans/_conventions.md` | its `CONV-*` ID |
| what the system currently *is* (schema, endpoints, flow) | `docs/ARCHITECTURE.md` | "ARCHITECTURE §N" |
| the work + why, for one domain | `docs/plans/<domain>.plan.md` | the `todos:` id |
| how code must be written here | `.cursor/rules/*.mdc` | (auto-loaded by Cursor) |

Rule of thumb: **one home per fact.** If the prompt needs a fact that has no home yet, that's a
signal to add it to a `CONV-*` or ARCHITECTURE *first*, then reference it — don't let the only
copy live in a throwaway prompt.

---

## The prompt (copy, fill the blanks, delete the guidance)

```
<one-line goal>. Do it in <N> ordered commits — do not start a step until the
previous one's tests pass.

Read first (reference these by ID/link; do NOT restate their contents anywhere):
- .cursor/rules/project.mdc  → "Documentation map" + "Conventions & plan governance"
- docs/plans/_conventions.md → <CONV-IDS THIS WORK MUST FOLLOW>
- docs/plans/<domain>.plan.md → todos <ids you're implementing>
- docs/ARCHITECTURE.md §<n>   → <entries this work touches / any "target" markers to flip>

Commit 1 — <name>:
- <imperative step>
- <imperative step>
- Tests: <the behavior that proves it>

Commit 2 — <name>:
- ...

Sync docs as part of the work (governance in project.mdc):
- Flip any ARCHITECTURE "target (not yet built)" markers you satisfy to current.
- Update the affected plan's todos: mark done / add a new entry for new scope / note a deviation.
- Do not restate a CONV — link it.

If anything you build would contradict a CONV-*, STOP and ask whether to change the
convention or the code — do not reconcile silently.
```

---

## Two modes (both keep the plan files — they don't compete)

- **New domain / greenfield:** write a *thin* `<domain>.plan.md` first (todos + rationale +
  `CONV-*` refs — never restated rules), then prompt `"implement <domain>.plan.md following its
  referenced CONVs."` The plan is the design artifact; the prompt just triggers it.
- **Change to an existing domain:** usually don't pre-edit the plan. Prompt the change directly
  (the template above), referencing CONVs, and let governance make the agent fold the delta back
  into the plan's `todos:`.

The prompt is **ephemeral** (a work order, thrown away). The plan is **durable** (todos = live
status, body = rationale). The prompt drives; the plan remembers.

---

## Before you send it — 30-second checklist

- [ ] Every decision the agent needs is a `CONV-*` or an ARCHITECTURE entry it can read — not
      inlined prose in this prompt.
- [ ] Steps are ordered by dependency (model/schema → consumers). The consumer that *proves* the
      model goes last.
- [ ] The prompt tells the agent to update plans + ARCHITECTURE as it works.
- [ ] There's a "stop and ask on CONV conflict" line.
- [ ] If this introduces a new cross-cutting decision, you added the `CONV-*` (and a Changelog
      line) *before* prompting — not as a side effect of the build.
