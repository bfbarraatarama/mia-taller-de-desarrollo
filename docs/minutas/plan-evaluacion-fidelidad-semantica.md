# Plan: evaluating semantic recall under additional splitting

## Goal and scope

Compare how many AMI reference-minute items are recovered in a final generated
minute when the same transcript is processed normally versus with additional,
balanced splits. This is a scoped experiment for issue #17, not a complete
evaluation of semantic fidelity.

The experiment measures **reference-item recall**, not precision, hallucinations,
contradictions, redundancy, or the full treatment of information distributed
across blocks. Human review of the new experiment is optional. Improving the
minutes generator is outside this plan.

## 1. Data preparation

1. Select the three longest meetings in
   [`reuniones.csv`](../../hito-2/muestra/ami/reuniones.csv) that have reference
   minutes: TS3007b (55.9 minutes), TS3006d (50.1), and TS3004c (49.4), based
   on `duracion_s`. Verify that turn and reference-item records are available.
   Record the selection rule, IDs, durations, word counts, and source hashes.
2. Reuse
   [`preparar_reunion_ami`](../../evaluacion/modular/traduccion.py) to translate
   turns and reference items and produce the minutes-module input contract.
   Preserve the English originals, translations, meeting roles, timestamps, and
   translation-model revision. Validate the output using the existing input
   reader. Record any discarded turns and translation limitations; do not
   silently replace empty or invalid data.
3. Freeze the resulting inputs, reference items and their hashes before running
   either condition. Both conditions must use exactly the same translated
   transcript and reference items. These are machine translations, not
   human-validated Spanish ground truth.

## 2. Experiment conditions

Run both conditions with the same minutes model, version, prompts, sections,
configuration, and transcript. Initially use the existing default
`qwen2.5-7b`, with the four AMI-compatible sections `resumen`, `decisiones`,
`problemas`, and `acciones`. Do not change the context limit, block budget or
consolidation rules between conditions.

### Baseline: normal processing

Submit the complete transcript to the existing minutes generator. It may
automatically split the input and may further subdivide blocks after model
limit errors. Record the **actual successful extraction blocks**, in order,
including any repeated context or intervention fragments. A format retry is
not another successful block.

The existing manifest reports counts but not the boundaries needed to replay
the blocks. Add a minimal, explicitly enabled experiment trace to the minutes
path, or an equivalent reusable hook, capturing block membership and text
offsets without changing ordinary generation. Do not rely on reconstructing
actual blocks from the initial count or from a separate dry run: runtime
subdivisions can change them. Validate the trace against what the extractor
actually received.

### Forced condition: split each actual baseline block

For each successful baseline block, split its ordered input into two nonempty
children, then extract each child and pass all resulting partial minutes, in
order, through the **same production consolidation path**. Produce one final
minute for the entire meeting. This also applies if the baseline used only one
block: the forced condition must still use at least two.

- Measure balance by Unicode characters of intervention text, excluding JSON
  and metadata. Choose the intervention boundary closest to half the block's
  text; break ties by choosing the earlier boundary. Each child must contain
  between 40% and 60% of the block's text, inclusive.
- Preserve the original intervention IDs, timestamps, speaker metadata, text,
  order, and any intervention fragments already present in the baseline block.
  Keep the baseline's context occurrences exactly as received; do not introduce
  extra overlap when splitting. The ordered concatenation of the two children
  must reproduce the baseline block's ordered occurrences exactly.
- Do not call `generar_minuta` independently on each half and concatenate the
  outputs: that could reassign IDs and bypass the real consolidation process.
  Instead, introduce a small, explicitly opt-in way to supply the validated
  extraction block plan to the existing extraction/consolidation flow. Default
  behavior must remain unchanged.
- If an actual baseline block has no valid intervention boundary satisfying
  the 40–60% rule, report the block and fail that meeting's comparison. Do not
  split inside an intervention merely to claim success or silently relax the
  balance. In particular, a one-intervention block cannot be forced this way.
  Baseline limit recovery may already have split an intervention; preserve
  those fragments but do not add a new intra-intervention split. A boundary
  between adjacent fragments of the same original intervention is not valid.
- Keep the existing limit-recovery behavior. Record any additional forced-run
  subdivisions and retries. A comparison is valid only if every baseline
  block has two valid children, every child is successfully processed (possibly
  after normal limit recovery), and the forced run has **strictly more
  successful extraction blocks** than the baseline. Fail explicitly otherwise.

Trace successful block boundaries, text sizes and parent/child relationships;
record baseline and forced counts, extraction subdivisions, consolidation
levels, local-union reasons, calls, token usage when available, elapsed time,
input/output hashes and model/configuration versions. Store the trace with the
experiment artifacts, subject to the same confidentiality rules as transcripts.
This controls and verifies additional splitting; it does not isolate a single
cut, and changed context and consolidation paths can affect the result.

## 3. Evaluation rows

Create one row per reference item and condition, keyed by meeting, condition,
and stable AMI `item_id`. Follow the existing
[`planillas`](../../evaluacion/modular/resultados/planillas/) CSV structure and
retain `reunion`, `tipo`, `item_id`, `referencia`, `referencia_original`,
`recuperado`, and `observaciones`. Add at least `condicion`, `cita`, and an
explicit evaluation status.

`recuperado` is `sí` or `no` only for evaluable items; leave it blank for
`no_evaluable` or `incierto`, with an explanation. Ask the judge for exact,
searchable quotes for positive judgments, but do not mechanically verify them
or reject a label because citations are absent or inaccurate. Citations are
unverified aids for inspection, not proof. Store the reference and output
hashes so the rows cannot silently be matched to a different run.

## 4. LLM judge and independent evaluation

Use **M-Prometheus 3B locally in Ollama**, using the
[`M-Prometheus-3B.i1-Q4_K_M.gguf` quantization](https://huggingface.co/mradermacher/M-Prometheus-3B-i1-GGUF)
of [`Unbabel/M-Prometheus-3B`](https://huggingface.co/Unbabel/M-Prometheus-3B).
The upstream model is designed for multilingual evaluation. It is fine-tuned
from Qwen 2.5 3B, but is a distinct model from the default Qwen 2.5 7B minutes
generator. The earlier restriction is against using the same model for both
roles, not against sharing a model family.

Import the specified GGUF into local Ollama beforehand under
`m-prometheus-3b-i1:q4_k_m` using an Ollama Modelfile with the model's
appropriate chat template. This is a local alias, not a claim that the name is
published in the Ollama registry. Pin and record the GGUF source repository
revision, filename and SHA-256, Modelfile/template, local Ollama model digest,
Ollama version and effective parameters. Fail clearly if the expected model is
unavailable or its digest changes; never download or substitute a model
implicitly. Both judge and minutes generation use loopback Ollama only.
The generation model must not be the judge model.

Create a versioned prompt and rubric **in Spanish**, including system
instructions, and a structured response schema. For each target item, the
judge receives its reference text and the complete target Markdown, plus one
example pair: the complete example Markdown and its CSV's `referencia` and
human `recuperado` columns for every binary-marked item. Do not send the target
human label. Request `sí`, `no`, `incierto`, or `no_evaluable`, optional exact
quote(s), and a brief reason. The script associates each response with the
target `item_id`; do not ask the model to return it. Validate response schema
and labels, but not citation presence or correspondence to the Markdown.
Surface provider and validation failures and never turn them into negative
judgments. Use bounded, explicit retries if necessary.

Rubric to include in the Spanish prompt:

- Marcá `sí` solo si la minuta expresa el significado esencial del ítem de
  referencia; un tema relacionado o palabras compartidas no bastan. Una
  paráfrasis equivalente cuenta.
- Para una acción, deben conservarse la acción y, si figura en la referencia,
  su responsable o rol. El rol puede aparecer en el texto aunque el campo
  estructurado esté vacío. No infieras un responsable ausente.
- Si falta un detalle esencial, marcá `no`; si la correspondencia es ambigua,
  `incierto`. Usá `no_evaluable` solo si la referencia no puede evaluarse
  razonablemente y explicá por qué.
- Buscá en toda la minuta, no solo en la sección homónima. Para `sí`, intentá
  citar el texto pertinente tal como aparece en la minuta; la cita es una ayuda
  para la revisión, no una prueba automática de corrección.

### Standalone evaluation of the judge

Run `evaluar_juez` independently of the main minutes experiment. For each of
the three existing CSV/Markdown pairs, use that entire pair as the example and
judge every item in the other two pairs. Thus every held-out
item receives exactly two predictions, each using a different meeting as the
example, and no item is judged using its own meeting as an example.

Combine the two predictions by most frequent label; a tie becomes `incierto`.
Output the individual predictions and one aggregated row per held-out item,
including `recuperado_humano` and `recuperado_juez`. Compare to the human label
and report confusion counts, accuracy, precision, recall and F1 for `sí`,
per-meeting and per-category counts, abstentions, and disagreements. See
section 7 for denominators and missing-data handling. TS3009a contains a blank
human mark: still produce its two predictions and aggregate, but report it
separately, never treat it as `no` or include it as a labeled example or in
binary metrics.

The script uses the frozen prompt as supplied; it does not automatically
choose a rubric, tune it against ground truth, or depend on the main pipeline.
Do not overwrite the supplied CSVs, Markdown files or human workbooks. Report
judge performance as a separate estimate, not proof of reliability on long
meetings. The existing modular evaluation chose human marking rather than an
LLM judge; this experiment does not replace that protocol.

### Judging the new minutes

For each new reference item and condition, make three independent judge calls,
one per example pair, using the same fixed Spanish prompt and model. Save all
three responses, then choose the most frequent of their four labels. A tie
for highest count becomes `incierto`; for example, three different labels
also yield `incierto`. A failed or invalid call is an error, not a vote: mark
the item incomplete and do not calculate a majority from fewer than three.
The main experiment does not run or require the standalone judge evaluation.

## 5. Recall and comparison

For each meeting and condition, calculate:

`recall = recovered items / evaluable items`

Also report recovered/evaluable counts and recall per reference category.
Report `no_evaluable`, `incierto`, failed judgments and total reference items
separately. Never count them as `no` or silently drop them. Do not compute a
percentage when the denominator is zero.

For a valid paired delta, use the **same reference-item IDs evaluable in both
conditions**; report their count and the items excluded from that paired
denominator. Calculate `forced recall − baseline recall` in percentage points
on that shared set, both overall and per category when the denominator is
nonzero. Include per-item transitions (`sí→no`, `no→sí`, etc.) and citations
so changes are inspectable. Do not claim a causal effect of splitting alone:
model variability, context exposure and consolidation may also affect outcomes.
Record any repeated runs separately; do not assume deterministic model output.

## 6. Implementation layout

The implementation follows the repository's Spanish identifiers and Python,
CLI and testing conventions. Keep this experiment separate from the modular
evaluation of issue #13. See the [usage guide](../../evaluacion/fidelidad_minutas/README.md)
for prerequisites and executable commands.

| Path | Responsibility |
|---|---|
| `evaluacion/fidelidad_minutas/__init__.py` | Package marker; no side effects. |
| `evaluacion/fidelidad_minutas/__main__.py` | Parse and dispatch the CLI below; print concise progress and actionable errors. |
| `evaluacion/fidelidad_minutas/preparacion.py` | Deterministically select the meetings, verify input tables, reuse AMI translation, validate and hash frozen inputs. |
| `evaluacion/fidelidad_minutas/fragmentacion.py` | Serialize and deserialize traces and expose the shared balanced child-block planning function. |
| `evaluacion/fidelidad_minutas/inferencia.py` | Run both conditions through the minutes module, persist traces and check the comparison invariants. |
| `evaluacion/fidelidad_minutas/juez.py` | Load examples, build judge requests, enforce the fixed local judge and validate responses; aggregate votes. |
| `evaluacion/fidelidad_minutas/evaluar_juez.py` | Independent CLI for leave-one-meeting-out judge evaluation; read human-reviewed pairs without changing them. |
| `evaluacion/fidelidad_minutas/metricas.py` | Pure calculations for per-condition recall, matched-item deltas, transitions and judge-evaluation metrics. |
| `evaluacion/fidelidad_minutas/prompts/juez_v1.md` | Versioned Spanish judge prompt and rubric; hash its exact bytes. |
| `src/minutas/experimento.py` | Define experiment traces, select balanced cuts, validate forced plans and track original text offsets. |
| `src/minutas/generacion.py` | Add the minimal opt-in trace and validated extraction-plan integration described below. Keep normal callers unchanged and reuse the existing extraction, error recovery, and consolidation code. |
| `tests/evaluacion/test_fidelidad_preparacion.py` | Selection, input preparation, manifests and validation. |
| `tests/evaluacion/test_fidelidad_fragmentacion.py` | Trace and splitting contracts, including failure cases. |
| `tests/evaluacion/test_fidelidad_inferencia.py` | Paired execution and its invariants using a simulated provider. |
| `tests/evaluacion/test_fidelidad_juez.py` | Judge schema, voting, safeguards, citations and independent evaluation. |
| `tests/evaluacion/test_fidelidad_metricas.py` | Recall, matched deltas and judge-evaluation calculations. |

Use the existing Ollama client and local-destination safeguards in
`src.minutas.proveedores` where practical. M-Prometheus is not in the minutes
model's closed catalog: do not register it as a minutes model just to use it
as judge. Provide an evaluation-only client setup using the same loopback,
no-proxy and no-redirect safeguards. Do not send judge or generation data to
remote Ollama or Bedrock. Check the **resolved technical model identity and
digest** to prevent using the judge as the generation model before sending data.

### Reproducibility

All stages other than model inference and judging must be programmatic and
deterministic for identical saved inputs and configuration. Use stable
iteration and ordering (including meeting selection ties resolved by meeting
ID), fixed serialization and explicit rounding. No human action is required
in the main pipeline beyond launching commands; optional human review is
separate. Freeze the resulting inputs, actual baseline trace, model responses,
and hashes so subsequent split planning and reports can be rerun from saved
artifacts without repeating model calls.

Use CPU for MarianMT, its pinned revision and no sampling; record Python,
library and model versions, device and translation parameters. Fix random
seeds to `0` for Python, NumPy and PyTorch where used, and enable deterministic
PyTorch algorithms; report an unsupported deterministic operation as an error,
not a silent fallback. Run Ollama generation and judging with temperature `0`
and seed `0`, using identical generation settings in both conditions; record
all effective options, model digests, Ollama version and hardware. The existing
Ollama minutes adapter already sends seed `0`; preserve default behavior for
other callers.

Seeds and temperature do not guarantee bit-identical model results across
hardware, library versions or repeated inference. Fix the environment as far
as practical and report that limitation. Operational metadata such as
timestamps and durations may vary; deterministic calculations and reports
should not depend on them, and content hashes must refer to the actual bytes
saved rather than imply independently rerun files must match.

### Minutes-module integration

Use the explicitly opt-in typed experiment interface in
`src/minutas/experimento.py`, integrated into `src/minutas/generacion.py`:
one mode observes actual successful extraction blocks; another consumes a
validated forced block plan. It must not be enabled
by the normal API, CLI or GUI. Leave the existing `generar_minuta` behavior,
outputs and privacy policy unchanged for ordinary calls. Both modes use the
same `pedir`, `extraer`, evidence validation, consolidation and publication
path. Refactor shared logic only as needed; do not create an alternate minutes
generator.

Assign intervention IDs **once**, from the complete transcript via the
existing `leer_transcripcion` path. A trace occurrence contains its original
intervention ID and zero-based, end-exclusive character offsets into the
normalized `Intervencion.texto` assigned that ID. A whole intervention uses
`[0, len(texto))`. Distinguish repeated occurrences of the same ID: baseline
context overlap is intentional and must not be deduplicated. Metadata is
looked up from the original intervention, not reconstructed from a partial
transcript.

Store a versioned trace JSON with `version`, `sha256_entrada`,
`sha256_configuracion`, and an ordered `bloques` array. Each block contains a
stable `bloque_id`, ordered `ocurrencias` (`id_intervencion`, `inicio_texto`,
`fin_texto`), `caracteres_texto`, and, for forced blocks, `padre_id` and
`lado` (`izquierda` or `derecha`). Include the actual successful leaf blocks
after runtime limit recovery, not failed attempts. Retain the original
planned child-to-leaf relationship separately if recovery subdivides a child.

Validate IDs, bounds, substring reconstruction, nonempty blocks, counts and
input/configuration hashes before accepting a trace or plan. The trace must
reconstruct the exact occurrence sequence submitted in each successful
extraction call. The forced plan must contain exactly two balanced, ordered
children per baseline successful block before runtime recovery; their
concatenated occurrences must equal that parent, including duplicated context.
After recovery, verify every planned child was fully processed and the total
successful leaves exceed the baseline count. Report failure rather than
publishing a valid-looking comparison if any invariant fails.

## 7. Data and result contracts

Use UTF-8; JSON files are objects with `version_esquema: 1`, except the trace
format described above. Paths inside manifests are relative to the experiment
directory. SHA-256 values refer to file bytes, not Python object
representations. Never persist credentials, raw provider errors containing
secrets, or an authorization flag as reusable consent.

Default output root: `evaluacion/fidelidad_minutas/resultados/`. Accept an
explicit `--salida` on either CLI so users can choose another root. Add the
specific default results directory to `.gitignore`: inputs, traces, minutes,
and judge requests can contain meeting content. Do not ignore source code,
prompts, or tests. Each workflow has its own user-supplied `--ejecucion`
identifier; reject path separators. The first stage creates its workflow's
run directory and must fail if it exists. Later stages operate on that same
directory, verify their prerequisites, and must not overwrite outputs. To
rerun, choose a new identifier.

```text
evaluacion/fidelidad_minutas/resultados/
  evaluacion_juez/<ejecucion>/
    manifiesto.json
    predicciones.csv
    agregados.csv
    reporte.json
    reporte.md
  evaluacion_minutas/<ejecucion>/
    muestra/
      manifiesto.json
      ami/<reunion>/transcription.json
      ami/<reunion>/referencia_minuta.json
      ami/<reunion>/traduccion.json
    inferencia/<reunion>/
      baseline/{minutes.json,minutes.md,ejecucion_minutas.json,traza.json}
      forzada/{minutes.json,minutes.md,ejecucion_minutas.json,traza.json}
      plan_forzado.json
      comparacion.json
    evaluacion/<reunion>/
      {baseline,forzada}.csv
      {baseline,forzada}_predicciones.csv
    reporte.json
    reporte.md
```

The standalone `evaluacion_juez/` directory has no dependency on the main
experiment run or its artifacts.

`muestra/manifiesto.json` records selection rule and source hashes; each meeting
records duration, word count, item and valid/discarded turn counts, translation
model/revision/parameters, and hashes of its three prepared files.
`comparacion.json` records meeting, input/config hashes, baseline and forced
successful block counts, split-balance checks, completed/failed status and
failure reason. Existing `ejecucion_minutas.json` remains authoritative for
production generation counters; any experiment-specific details live in the
trace or comparison file.

Judge output for **one** item is a structured object:

```json
{
  "resultado": "sí",
  "citas": ["Texto pertinente de la minuta."],
  "observaciones": "Explicación breve."
}
```

`resultado` is exactly one of `sí`, `no`, `incierto`, `no_evaluable`.
`citas` is optional and may be empty for any result. Ask for exact quotations
for `sí`, but do not check them against the minute or require them for a
positive label. Save an array of strings when provided; if missing or malformed,
record `[]` and a citation-format warning without rejecting a valid label.
`observaciones` is nonempty for `incierto` and `no_evaluable`. The code supplies
the target item ID, meeting, condition, example-pair ID and hashes; the model
does not generate them. Send complete target and example minutes, the target
reference item and the example's binary-labeled references; never send the
target's human label. If the full request does not fit the judge's context,
fail explicitly instead of truncating either minute or silently removing
examples.

Each evaluation CSV has exactly these columns:

```text
reunion,condicion,tipo,item_id,referencia,referencia_original,estado,recuperado,cita,observaciones,sha256_referencia,sha256_minuta
```

`condicion` is `baseline` or `forzada`. For binary judge results, `estado` is
`evaluado` and `recuperado` is `sí` or `no`. For `incierto` and `no_evaluable`,
`estado` is that value and `recuperado` is blank. `cita` is a JSON array encoded
as one CSV field, collecting unverified citations from votes matching an
aggregated `sí`, or `[]` when none was supplied. A provider or
validation failure is `estado=error`, blank `recuperado`, `cita=[]`, and a
sanitized explanation; never save it as `no`. A complete successful report
requires every expected item/condition key exactly once and no errors. An
incomplete run may write diagnostics, but must be marked incomplete and exit
nonzero, not publish successful recall results.

The per-vote `predicciones.csv` files, in either workflow, contain
`reunion,condicion,item_id,ejemplo_reunion,resultado,cita,observaciones,estado`.
For the standalone evaluation `condicion` is empty. The standalone
`agregados.csv` has one row per target item, including blank human labels, with
`reunion,tipo,item_id,referencia,recuperado_humano,recuperado_juez`, where the
judge result may also be `incierto` or `no_evaluable`. Preserve raw votes,
example identities and errors for auditability; include error counts and fail
the workflow if any expected vote is missing or invalid.

Pair the supplied files by their common meeting ID:
`{id}.csv` with `{id}.minuta.md`. Record this intended pairing and freeze
the SHA-256 of both files before either workflow runs. Verify those hashes
before later stages and model calls, and fail if either file changed; filenames
identify the pair but do not prove historical review provenance. Never modify
the originals. Align human labels and predictions by `(reunion, item_id)`,
validate unique IDs and matching meeting fields, and exclude blank human marks
from examples and metric denominators while reporting their count.

For judge metrics use all human binary labels. Show a two-by-four confusion
table (human `sí`/`no` versus judge `sí`/`no`/`incierto`/`no_evaluable`).
Accuracy is exact binary matches divided by all human binary labels;
abstentions therefore count against accuracy without being reclassified as
`no`. For positive-class precision use human `sí` among judge `sí`, divided
by all judge `sí`; for recall use judge `sí` among human `sí`, divided by all
human `sí` (including abstentions in the denominator). F1 is the harmonic
mean of precision and recall. Report numerator, denominator and abstention
counts; a zero denominator is not measurable, not zero or a pass. Provider
or validation errors make the evaluation incomplete.

`reporte.json` records per-meeting and per-category totals, statuses, recall
numerators/denominators, matched-pair numerators/denominators, percentage-point
deltas, exclusions, transitions, and paths/hashes of supporting files. The
standalone judge `reporte.json` records its confusion table, metrics and
disagreements. In both workflows `reporte.md` is produced deterministically
from the corresponding `reporte.json` alone, and presents its figures and
limitations in human-readable form. Use full-precision counts for calculations;
round only displayed percentages.

## 8. Proposed CLI

Invoke from the repository root. Both CLIs require `--ejecucion ID` and accept
`--salida RUTA`. Main-pipeline stages read and verify the preceding stage's
hashes. Run the following commands after satisfying the prerequisites:

```bash
.venv/bin/python -m evaluacion.fidelidad_minutas.evaluar_juez --ejecucion juez-01
.venv/bin/python -m evaluacion.fidelidad_minutas preparar --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas inferir --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas juzgar --ejecucion prueba-01
.venv/bin/python -m evaluacion.fidelidad_minutas reportar --ejecucion prueba-01
```

- `evaluar_juez` runs the independent leave-one-meeting-out evaluation and
  writes its own predictions, aggregated labels and reports. It does not
  require or invoke any main-pipeline stage.
- `preparar` creates the run and its frozen sample; no inference or judging.
- `inferir` requires the frozen sample and produces both conditions with
  `qwen2.5-7b` on local Ollama. Reject remote destinations before constructing
  a client or sending data.
- `juzgar` requires completed inference and uses all three example pairs for
  each target item. It does not require the independent judge evaluation.
- `reportar` reads saved artifacts only; it performs no model calls. It checks
  identity, coverage and pair validity before computing.

`evaluar_juez` and `juzgar` accept `--planillas RUTA`, defaulting to
`evaluacion/modular/resultados/planillas/`, and never edit that directory.
Generation and judging accept only local Ollama destinations; there are no
remote-authorization flags. No implicit downloads or provider/model fallback.
Use exit code 0 for a successfully completed stage, 1 for an execution,
validation or incomplete-artifact failure, and argparse's 2 for invalid CLI
arguments.

## 9. Verification and rollout

1. Implement in the order: frozen sample and manifest; trace and forced-plan
   integration; paired inference; judge and its independent evaluation;
   metrics and report. Avoid duplicating production consolidation or
   modifying human files.
2. Add focused offline tests with simulated providers for baseline trace
   fidelity; balanced splitting and impossible cases; repeated context,
   intervention fragments, IDs and timestamps; runtime subdivision; forced
   count greater than baseline; production consolidation; and unchanged
   default behavior.
3. Test judge schema, acceptance of absent, malformed or inaccurate citations,
   local-only and distinct-model safeguards, example isolation, two- and
   three-vote aggregation and ties, blank and uncertain labels, non-evaluable
   items, mismatched IDs, zero denominators, paired deltas, independent judge
   execution, deterministic report rendering, and incomplete/failure handling.
4. Run `.venv/bin/python -m pytest -q -rs tests/evaluacion/test_fidelidad_*.py tests/minutas`
   after implementation. Then run a small authorized end-to-end pilot before
   the full three meetings. Check manifests, traces and denominators; treat
   citations as unverified.
   Document actual commands, prerequisites, costs, and limitations; do not
   claim the pilot or full experiment succeeded until it has been run.
