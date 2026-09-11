import { useEffect, useMemo, useState } from "react";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  BarChart3,
  BookOpen,
  Braces,
  Check,
  ChevronRight,
  ClipboardCheck,
  Clock3,
  GitCompareArrows,
  Inbox,
  LoaderCircle,
  MapPin,
  Menu,
  Plus,
  RefreshCw,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  X,
} from "lucide-react";
import { ApiError, api, normalizeTriageResponse } from "./api";
import type {
  Category,
  ComparisonResponse,
  Department,
  Notice,
  Provider,
  RiskMatrixDocument,
  ReviewDecision,
  TriageProposal,
  TriageRun,
  Urgency,
  View,
} from "./types";

const NAV: Array<{ id: View; label: string; hint: string; icon: typeof Plus }> = [
  { id: "new", label: "Nuevo aviso", hint: "Clasificar", icon: Plus },
  { id: "inbox", label: "Bandeja", hint: "Revisar", icon: Inbox },
  { id: "dashboard", label: "Panel", hint: "Supervisar", icon: BarChart3 },
  { id: "matrix", label: "Matriz", hint: "Consultar", icon: BookOpen },
  { id: "compare", label: "Comparación", hint: "Evaluar", icon: GitCompareArrows },
];

const providerNames: Record<Provider, string> = { local: "Ollama · local", external: "Gemini · externo" };
const categories: Category[] = [
  "riesgo_electrico",
  "caidas_obstaculos",
  "incendio",
  "maquinaria",
  "sustancias_peligrosas",
  "problemas_estructurales",
  "falta_epi",
  "ergonomia",
  "otros",
];
const urgencies: Urgency[] = ["baja", "media", "alta", "critica"];
const departments: Department[] = ["prevencion", "mantenimiento", "seguridad", "limpieza"];
const optionLabel = (value: string) => value.replaceAll("_", " ");

const urgencyTone = (urgency: string) => {
  const value = urgency.toLowerCase();
  if (value.includes("inmed") || value.includes("alta") || value.includes("crít")) return "danger";
  if (value.includes("media") || value.includes("prior")) return "warning";
  return "safe";
};

const formatDate = (value?: string) => {
  if (!value) return "Ahora";
  const date = new Date(value);
  return Number.isNaN(date.valueOf())
    ? value
    : new Intl.DateTimeFormat("es-ES", { dateStyle: "medium", timeStyle: "short" }).format(date);
};

function StatusMessage({ error }: { error: unknown }) {
  if (!error) return null;
  const apiError = error instanceof ApiError ? error : null;
  return (
    <div className="message error" role="alert">
      <AlertTriangle size={18} aria-hidden="true" />
      <div>
        <strong>{error instanceof Error ? error.message : "Ha ocurrido un error."}</strong>
        {apiError?.requestId && <small>Referencia: {apiError.requestId}</small>}
      </div>
    </div>
  );
}

function App() {
  const [view, setView] = useState<View>("new");
  const [menuOpen, setMenuOpen] = useState(false);
  const [apiOnline, setApiOnline] = useState<boolean | null>(null);
  const [pendingCount, setPendingCount] = useState(0);
  const [riskMatrix, setRiskMatrix] = useState<RiskMatrixDocument | null>(null);
  const [riskMatrixError, setRiskMatrixError] = useState<unknown>(null);

  const navigate = (next: View) => {
    setView(next);
    setMenuOpen(false);
  };

  useEffect(() => {
    void api.health().then(setApiOnline);
    void api
      .listNotices()
      .then((notices) =>
        setPendingCount(
          notices.flatMap((notice) => notice.triage_runs).filter((run) => run.status === "pending_review").length,
        ),
      )
      .catch(() => undefined);
  }, [view]);

  useEffect(() => {
    void api.getRiskMatrix().then(setRiskMatrix).catch(setRiskMatrixError);
  }, []);

  return (
    <div className="app-shell">
      <aside className={`sidebar ${menuOpen ? "open" : ""}`} aria-label="Navegación principal">
        <button className="mobile-close" onClick={() => setMenuOpen(false)} aria-label="Cerrar menú">
          <X size={20} />
        </button>
        <div className="brand">
          <div className="brand-mark"><ShieldCheck size={26} /></div>
          <div><strong>IAviso</strong><span>Seguro</span></div>
        </div>
        <div className="rail-label">Centro preventivo</div>
        <nav>
          {NAV.map((item) => {
            const Icon = item.icon;
            return (
              <button
                key={item.id}
                className={view === item.id ? "active" : ""}
                onClick={() => navigate(item.id)}
                aria-current={view === item.id ? "page" : undefined}
              >
                <Icon size={20} />
                <span><strong>{item.label}</strong><small>{item.hint}</small></span>
                {item.id === "inbox" && pendingCount > 0 ? <b className="count">{pendingCount}</b> : <ChevronRight size={17} />}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-note">
          <UserRoundCheck size={20} />
          <p><strong>Decisión humana</strong>La IA propone. Un técnico siempre valida.</p>
        </div>
        <div className={`connection ${apiOnline === true ? "online" : apiOnline === false ? "offline" : "checking"}`}>
          <i />
          {apiOnline === true ? "API conectada" : apiOnline === false ? "API sin conexión" : "Comprobando API"}
        </div>
      </aside>

      {menuOpen && <button className="scrim" onClick={() => setMenuOpen(false)} aria-label="Cerrar navegación" />}

      <main>
        <header className="topbar">
          <button className="menu-button" onClick={() => setMenuOpen(true)} aria-label="Abrir menú"><Menu /></button>
          <div>
            <span>Entorno de demostración</span>
            <strong>Prevención laboral · datos sintéticos</strong>
          </div>
          <div className="human-badge"><span>HITL</span> Revisión obligatoria</div>
        </header>
        {view === "new" && <NewNotice riskMatrix={riskMatrix} onCreated={() => navigate("inbox")} />}
        {view === "inbox" && <InboxView riskMatrix={riskMatrix} onPendingChange={setPendingCount} />}
        {view === "dashboard" && <Dashboard />}
        {view === "matrix" && <MatrixView matrix={riskMatrix} error={riskMatrixError} />}
        {view === "compare" && <Comparison riskMatrix={riskMatrix} />}
      </main>
    </div>
  );
}

function PageIntro({ eyebrow, title, children }: { eyebrow: string; title: string; children: React.ReactNode }) {
  return (
    <div className="page-intro">
      <span>{eyebrow}</span>
      <h1>{title}</h1>
      <p>{children}</p>
    </div>
  );
}

function NewNotice({ riskMatrix, onCreated }: { riskMatrix: RiskMatrixDocument | null; onCreated: () => void }) {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [provider, setProvider] = useState<Provider>("local");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [result, setResult] = useState<TriageRun | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const response = await api.createTriage({ text: text.trim(), provider, location: location.trim() || null });
      setResult(normalizeTriageResponse(response));
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  };

  return (
    <section className="page-content">
      <PageIntro eyebrow="01 · Captura" title="Describe el riesgo. La decisión sigue siendo humana.">
        Convierte una observación libre en una propuesta estructurada, trazable y lista para revisión técnica.
      </PageIntro>

      <div className="new-layout">
        <form className="work-card report-form" onSubmit={submit}>
          <div className="card-heading">
            <div className="step-number">01</div>
            <div><h2>Nuevo aviso preventivo</h2><p>No incluyas nombres ni datos personales.</p></div>
          </div>

          <label className="field">
            <span>¿Qué has observado?</span>
            <textarea
              aria-label="¿Qué has observado?"
              value={text}
              onChange={(event) => setText(event.target.value)}
              minLength={1}
              maxLength={4000}
              required
              placeholder="Ej.: Cable atravesando una zona de paso junto al almacén. Dos personas han tropezado esta mañana…"
            />
            <small>{text.length}/4000</small>
          </label>

          <label className="field">
            <span><MapPin size={16} /> Ubicación <em>opcional</em></span>
            <input value={location} onChange={(event) => setLocation(event.target.value)} maxLength={200} placeholder="Edificio, planta o zona" />
          </label>

          <fieldset className="provider-picker">
            <legend>Motor de análisis</legend>
            {(["local", "external"] as Provider[]).map((value) => (
              <label key={value} className={provider === value ? "selected" : ""}>
                <input type="radio" name="provider" value={value} checked={provider === value} onChange={() => setProvider(value)} />
                <span className="provider-icon">{value === "local" ? <Activity /> : <Sparkles />}</span>
                <span><strong>{providerNames[value]}</strong><small>{value === "local" ? "Privacidad y control local" : "Referencia comparativa externa"}</small></span>
                <i>{provider === value && <Check size={15} />}</i>
              </label>
            ))}
          </fieldset>

          <StatusMessage error={error} />
          <button className="primary-action" disabled={loading || text.trim().length < 1}>
            {loading ? <><LoaderCircle className="spin" /> Analizando aviso…</> : <>Generar propuesta <ArrowRight /></>}
          </button>
        </form>

        <aside className="context-panel">
          <div className="signal-graphic" aria-hidden="true">
            <span className="pulse p1" /><span className="pulse p2" /><span className="pulse p3" />
            <ShieldCheck />
          </div>
          <span className="context-kicker">Cómo funciona</span>
          <h2>Una señal entra. Una persona decide.</h2>
          <ol>
            <li><span>1</span><p><strong>Describe</strong> el peligro observado.</p></li>
            <li><span>2</span><p><strong>La IA consulta</strong> la matriz de riesgo.</p></li>
            <li><span>3</span><p><strong>Un técnico revisa</strong> antes de aceptar.</p></li>
          </ol>
          <div className="emergency-note"><AlertTriangle /><p><strong>¿Existe peligro inmediato?</strong> Sigue el protocolo de emergencias. Esta aplicación no lo sustituye.</p></div>
        </aside>
      </div>

      {result && (
        <div className="result-banner" role="status">
          <div><Check /><span><strong>Propuesta creada</strong>Queda pendiente de validación humana.</span></div>
          <div className={`urgency ${urgencyTone(result.proposal.urgency)}`}>{result.proposal.urgency}</div>
          <div className="result-fields">
            <p><b>Categoría</b>{optionLabel(result.proposal.category)}</p>
            <p><b>Departamento</b>{optionLabel(result.proposal.department)}</p>
            <p><b>Resumen</b>{result.proposal.summary}</p>
          </div>
          <ProposalExplanation proposal={result.proposal} riskMatrix={riskMatrix} />
          <button onClick={onCreated}>Abrir bandeja <ArrowRight size={17} /></button>
        </div>
      )}
    </section>
  );
}

function InboxView({ riskMatrix, onPendingChange }: { riskMatrix: RiskMatrixDocument | null; onPendingChange: (value: number) => void }) {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [selected, setSelected] = useState<{ notice: Notice; run: TriageRun } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const next = await api.listNotices();
      setNotices(next);
      const count = next.flatMap((notice) => notice.triage_runs).filter((run) => run.status === "pending_review").length;
      onPendingChange(count);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, []);
  const pending = useMemo(
    () => notices.flatMap((notice) => notice.triage_runs.filter((run) => run.status === "pending_review").map((run) => ({ notice, run }))),
    [notices],
  );

  return (
    <section className="page-content">
      <div className="intro-row">
        <PageIntro eyebrow="02 · Revisión" title="Bandeja de decisión técnica">
          Examina la propuesta original y deja una decisión humana trazable.
        </PageIntro>
        <button className="secondary-action" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "spin" : ""} /> Actualizar</button>
      </div>
      <StatusMessage error={error} />
      <div className="inbox-layout">
        <div className="queue">
          <div className="queue-head"><span>Pendientes</span><b>{pending.length}</b></div>
          {loading && <Empty icon={<LoaderCircle className="spin" />} title="Consultando avisos" text="Recuperando la bandeja desde la API…" />}
          {!loading && !error && pending.length === 0 && <Empty icon={<ClipboardCheck />} title="Bandeja al día" text="No hay propuestas pendientes de revisión." />}
          {pending.map(({ notice, run }) => (
            <button key={run.triage_run_id} className={`queue-item ${selected?.run.triage_run_id === run.triage_run_id ? "selected" : ""}`} onClick={() => setSelected({ notice, run })}>
              <div className="queue-top"><span className={`urgency ${urgencyTone(run.proposal.urgency)}`}>{run.proposal.urgency}</span><small>{formatDate(run.created_at ?? notice.created_at)}</small></div>
              <strong>{run.proposal.category}</strong>
              <p>{notice.text}</p>
              <footer><span><MapPin size={14} /> {notice.location || "Sin ubicación"}</span><span>{run.provider}</span></footer>
            </button>
          ))}
        </div>
        <div className="review-stage">
          {selected ? <ReviewPanel key={selected.run.triage_run_id} {...selected} riskMatrix={riskMatrix} onDone={() => { setSelected(null); void load(); }} /> : <Empty icon={<UserRoundCheck />} title="Selecciona una propuesta" text="Aquí podrás contrastar la observación y registrar tu decisión." />}
        </div>
      </div>
    </section>
  );
}

function ReviewPanel({ notice, run, riskMatrix, onDone }: { notice: Notice; run: TriageRun; riskMatrix: RiskMatrixDocument | null; onDone: () => void }) {
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [category, setCategory] = useState(run.proposal.category);
  const [urgency, setUrgency] = useState(run.proposal.urgency);
  const [department, setDepartment] = useState(run.proposal.department);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.reviewNotice(notice.notice_id, {
        expected_version: run.version,
        decision,
        reviewer: reviewer.trim(),
        comment: comment.trim(),
        ...(decision === "modified" ? { category, urgency, department } : {}),
      });
      onDone();
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  };

  return (
    <form className="review-panel" onSubmit={submit}>
      <div className="review-heading"><span>Propuesta original</span><small>v{run.version} · {run.provider}</small></div>
      <h2>{run.proposal.category}</h2>
      <div className="review-meta"><span className={`urgency ${urgencyTone(run.proposal.urgency)}`}>{run.proposal.urgency}</span><span>{run.proposal.department}</span></div>
      <blockquote>{run.proposal.summary}</blockquote>
      <ProposalExplanation proposal={run.proposal} riskMatrix={riskMatrix} />
      <div className="original-notice"><span>Observación recibida</span><p>{notice.text}</p></div>

      <fieldset className="decision-picker">
        <legend>Decisión</legend>
        {(["approved", "modified", "rejected"] as ReviewDecision[]).map((value) => (
          <label key={value} className={decision === value ? `selected ${value}` : ""}>
            <input type="radio" name="decision" checked={decision === value} onChange={() => setDecision(value)} />
            {value === "approved" ? "Aprobar" : value === "modified" ? "Corregir" : "Rechazar"}
          </label>
        ))}
      </fieldset>

      {decision === "modified" && (
        <div className="correction-grid">
          <label>Categoría<select value={category} onChange={(e) => setCategory(e.target.value as Category)} required>{categories.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
          <label>Urgencia<select value={urgency} onChange={(e) => setUrgency(e.target.value as Urgency)} required>{urgencies.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
          <label>Departamento<select value={department} onChange={(e) => setDepartment(e.target.value as Department)} required>{departments.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
        </div>
      )}
      <div className="reviewer-grid">
        <label>Técnico revisor<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} required minLength={2} placeholder="Nombre o identificador" /></label>
        <label>Comentario<textarea value={comment} onChange={(e) => setComment(e.target.value)} required minLength={3} placeholder="Motivo breve y verificable" /></label>
      </div>
      <StatusMessage error={error} />
      <button className="primary-action" disabled={loading || !reviewer.trim() || !comment.trim()}>{loading ? <><LoaderCircle className="spin" /> Guardando…</> : <>Registrar decisión <Check /></>}</button>
    </form>
  );
}

function Dashboard() {
  const [notices, setNotices] = useState<Notice[]>([]);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.listNotices().then(setNotices).catch(setError).finally(() => setLoading(false));
  }, []);

  const runs = notices.flatMap((notice) => notice.triage_runs);
  const pending = runs.filter((run) => run.status === "pending_review").length;
  const approved = runs.filter((run) => run.status === "approved").length;
  const modified = runs.filter((run) => run.status === "modified").length;
  const rejected = runs.filter((run) => run.status === "rejected").length;
  const reviewed = runs.length - pending;
  const metrics: Record<string, number> = {
    total_notices: notices.length,
    total: runs.length,
    pending_review: pending,
    approved,
    modified,
    rejected,
    reviewed,
    approval_rate: reviewed ? (approved + modified) / reviewed : 0,
  };
  const cards = [
    ["Avisos procesados", metrics.total_notices ?? metrics.total ?? 0, Activity],
    ["Pendientes", metrics.pending_review ?? metrics.pending ?? 0, Clock3],
    ["Revisados", metrics.reviewed ?? metrics.total_reviewed ?? 0, ClipboardCheck],
    ["Tasa de validación", `${Math.round(Number(metrics.approval_rate ?? metrics.validation_rate ?? 0) * (Number(metrics.approval_rate ?? 0) <= 1 ? 100 : 1))}%`, ShieldCheck],
  ] as const;

  return (
    <section className="page-content">
      <PageIntro eyebrow="03 · Supervisión" title="Lectura operativa del prototipo">Métricas agregadas para vigilar el flujo, no para automatizar decisiones preventivas.</PageIntro>
      <StatusMessage error={error} />
      {loading ? <Empty icon={<LoaderCircle className="spin" />} title="Calculando indicadores" text="Consultando datos agregados…" /> : (
        <>
          <div className="metrics-grid">
            {cards.map(([label, value, Icon], index) => <article key={label} className={`metric-card m${index + 1}`}><Icon /><span>{label}</span><strong>{value}</strong><small>Datos registrados en la API</small></article>)}
          </div>
          <div className="dashboard-lower">
            <article className="work-card chart-card">
              <div className="card-heading"><div><h2>Estado del flujo</h2><p>Distribución disponible en este momento.</p></div></div>
              <div className="flow-bars">
                {["pending_review", "approved", "modified", "rejected"].map((key, index) => {
                  const value = Number(metrics[key] ?? 0);
                  const total = Math.max(1, Number(metrics.total ?? metrics.total_notices ?? 0));
                  return <div key={key}><span>{key.replace("pending_review", "Pendientes").replace("approved", "Aprobados").replace("modified", "Corregidos").replace("rejected", "Rechazados")}</span><i><b style={{ width: `${Math.min(100, value / total * 100)}%` }} className={`bar-${index}`} /></i><strong>{value}</strong></div>;
                })}
              </div>
            </article>
            <aside className="principle-card"><ShieldCheck /><span>Principio de control</span><h2>Propuesta ≠ decisión</h2><p>La salida del modelo permanece separada de la clasificación validada para conservar la trazabilidad.</p></aside>
          </div>
        </>
      )}
    </section>
  );
}

function ProposalExplanation({
  proposal,
  riskMatrix,
  compact = false,
}: {
  proposal: TriageProposal;
  riskMatrix: RiskMatrixDocument | null;
  compact?: boolean;
}) {
  const rule = Array.isArray(riskMatrix?.rules)
    ? riskMatrix.rules.find((candidate) => candidate.category === proposal.category)
    : undefined;

  return (
    <section className={`explanation-panel ${compact ? "compact" : ""}`} aria-label="Explicación del modelo">
      <div className="explanation-heading">
        <Sparkles size={17} aria-hidden="true" />
        <div><strong>Explicación del modelo</strong><small>Justificación verificable, no decisión automática</small></div>
      </div>
      <p>{proposal.justification || "El proveedor no incluyó una justificación textual."}</p>
      <div className="reasoning-trace">
        <div><span>1</span><p><strong>Acción</strong> consultar_matriz_riesgos</p></div>
        <div><span>2</span><p><strong>Regla aplicada</strong> {rule?.rule_id ?? `categoría ${optionLabel(proposal.category)}`}</p></div>
        <div><span>3</span><p><strong>Evidencia</strong> {rule?.evidence ?? "La matriz no estaba disponible para ampliar la evidencia."}</p></div>
      </div>
      <details className="json-panel">
        <summary><Braces size={16} /> Ver JSON estructurado</summary>
        <pre>{JSON.stringify(proposal, null, 2)}</pre>
      </details>
    </section>
  );
}

function MatrixView({ matrix, error }: { matrix: RiskMatrixDocument | null; error: unknown }) {
  const rules = Array.isArray(matrix?.rules) ? matrix.rules : [];
  const urgencyCatalog = [...new Set(rules.map((rule) => rule.recommended_urgency))];
  const departmentCatalog = [...new Set(rules.map((rule) => rule.department))];

  return (
    <section className="page-content">
      <PageIntro eyebrow="04 · Referencia" title="Matriz de riesgos visible y auditable.">
        Consulta las mismas reglas que utiliza el motor para proponer categoría, urgencia y departamento.
      </PageIntro>
      <StatusMessage error={error} />
      {!matrix && !error && <Empty icon={<LoaderCircle className="spin" />} title="Cargando matriz" text="Consultando la configuración activa de la API…" />}
      {matrix && (
        <>
          <div className="matrix-overview work-card">
            <div><span>Versión activa</span><strong>{matrix.version}</strong></div>
            <div><span>Niveles de urgencia</span><strong>{urgencyCatalog.map(optionLabel).join(" · ")}</strong></div>
            <div><span>Departamentos</span><strong>{departmentCatalog.map(optionLabel).join(" · ")}</strong></div>
            <p>{matrix.disclaimer}</p>
            <p className="location-note"><MapPin size={16} /> La ubicación es contexto libre opcional; el briefing no define un catálogo cerrado de zonas.</p>
          </div>
          <div className="matrix-grid">
            {rules.map((rule) => (
              <article className="matrix-card" key={rule.rule_id}>
                <header><small>{rule.rule_id}</small><span className={`urgency ${urgencyTone(rule.recommended_urgency)}`}>{rule.recommended_urgency}</span></header>
                <h2>{optionLabel(rule.category)}</h2>
                <div className="matrix-department"><UserRoundCheck size={16} /> {optionLabel(rule.department)}</div>
                <h3>Condiciones orientativas</h3>
                <ul>{rule.conditions.map((condition) => <li key={condition}>{condition}</li>)}</ul>
                <p><strong>Evidencia:</strong> {rule.evidence}</p>
              </article>
            ))}
          </div>
        </>
      )}
    </section>
  );
}

function Comparison({ riskMatrix }: { riskMatrix: RiskMatrixDocument | null }) {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true); setError(null); setResult(null);
    try { setResult(await api.compare(text.trim(), location.trim() || null)); }
    catch (caught) { setError(caught); }
    finally { setLoading(false); }
  };

  const runs = result?.results ?? [];
  return (
    <section className="page-content">
      <PageIntro eyebrow="05 · Evaluación" title="Mismo caso. Dos proveedores. Una comparación justa.">Ejecuta el caso sintético con los dos motores y contrasta calidad, latencia, tokens y coste.</PageIntro>
      <form className="compare-form work-card" onSubmit={submit}>
        <label className="field"><span>Caso sintético</span><textarea aria-label="Caso sintético" value={text} onChange={(e) => setText(e.target.value)} required minLength={1} maxLength={4000} placeholder="Describe un riesgo sin datos personales…" /></label>
        <label className="field compact"><span><MapPin size={16} /> Ubicación <em>opcional</em></span><input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={200} placeholder="Zona de prueba" /></label>
        <button className="primary-action" disabled={loading || text.trim().length < 1}>{loading ? <><LoaderCircle className="spin" /> Comparando…</> : <><GitCompareArrows /> Ejecutar ambos motores</>}</button>
      </form>
      <StatusMessage error={error} />
      {result && (
        <div className="comparison-grid">
          {runs.map((raw, index) => {
            if (!raw.result) {
              return <article className="comparison-card" key={raw.provider}><header><span>{index === 0 ? <Activity /> : <Sparkles />}</span><div><small>Proveedor</small><h2>{raw.provider}</h2></div></header><div className="message error" role="alert"><AlertTriangle /><div><strong>No se obtuvo una propuesta válida.</strong><small>Código: {raw.error_code ?? "provider_error"}</small></div></div></article>;
            }
            const run = normalizeTriageResponse(raw);
            const metrics = raw.metrics;
            const cost = metrics.api_cost === null ? "—" : `${metrics.api_cost}${metrics.api_cost_currency ? ` ${metrics.api_cost_currency}` : ""}`;
            return <article className="comparison-card" key={raw.provider}><header><span>{index === 0 ? <Activity /> : <Sparkles />}</span><div><small>Proveedor</small><h2>{run.provider}</h2></div></header><div className={`urgency ${urgencyTone(run.proposal.urgency)}`}>{run.proposal.urgency}</div><h3>{optionLabel(run.proposal.category)}</h3><p>{run.proposal.summary}</p><p className="comparison-department"><strong>Departamento:</strong> {optionLabel(run.proposal.department)}</p><ProposalExplanation proposal={run.proposal} riskMatrix={riskMatrix} compact /><dl><div><dt>Latencia</dt><dd>{metrics.latency_ms} ms</dd></div><div><dt>Tokens</dt><dd>{metrics.total_tokens ?? "—"}</dd></div><div><dt>Coste</dt><dd>{cost}</dd></div></dl></article>;
          })}
        </div>
      )}
      {!result && !loading && <div className="comparison-placeholder"><div><Activity /><span className="bridge" /><Sparkles /></div><h2>Preparado para comparar</h2><p>El resultado no crea dos avisos: conserva una única evaluación reproducible del mismo caso.</p></div>}
    </section>
  );
}

function Empty({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="empty-state"><span>{icon}</span><h3>{title}</h3><p>{text}</p></div>;
}

export default App;
