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
  History,
  Inbox,
  LoaderCircle,
  MapPin,
  Menu,
  Plus,
  RefreshCw,
  Search,
  ShieldCheck,
  Sparkles,
  UserRoundCheck,
  X,
} from "lucide-react";
import { ApiError, api } from "./api";
import type {
  AuditEventRecord,
  CatalogsResponse,
  Category,
  ComparisonProviderResult,
  ComparisonReviewRecord,
  ComparisonResponse,
  Department,
  EvaluationReport,
  HealthResponse,
  KnowledgeBaseSummary,
  KnowledgeEvidence,
  MetricsSummary,
  NoticeRecord,
  NoticePage,
  NoticeQuery,
  Provider,
  ProposalStatus,
  RiskMatrixDocument,
  ReviewDecision,
  TriageProposal,
  TriageProposalResponse,
  TriageRunRecord,
  Urgency,
  View,
} from "./types";

const NAV: Array<{ id: View; label: string; hint: string; icon: typeof Plus }> = [
  { id: "new", label: "Nuevo aviso", hint: "Clasificar", icon: Plus },
  { id: "inbox", label: "Bandeja", hint: "Revisar", icon: Inbox },
  { id: "history", label: "Registro", hint: "Consultar", icon: History },
  { id: "dashboard", label: "Panel", hint: "Supervisar", icon: BarChart3 },
  { id: "matrix", label: "Matriz", hint: "Consultar", icon: BookOpen },
  { id: "compare", label: "Comparación", hint: "Evaluar", icon: GitCompareArrows },
];

const providerNames: Record<Provider, string> = { local: "Ollama · local", external: "Gemini · externo" };
const providers = ["local", "external"] satisfies readonly Provider[];
const reviewDecisions = ["approved", "modified", "rejected"] satisfies readonly ReviewDecision[];
const statusLabels: Record<ProposalStatus, string> = {
  pending_review: "Pendiente",
  approved: "Aprobado",
  modified: "Corregido",
  rejected: "Rechazado",
};

const serviceFallbacks = [
  { id: "api", label: "API FastAPI" },
  { id: "ollama", label: "Ollama" },
  { id: "gemini", label: "Gemini" },
  { id: "sqlite", label: "SQLite" },
] as const;
// Debe reflejar backend.schemas.triage.NoticeText. Una sola constante evita
// que los formularios de alta y comparación vuelvan a divergir.
const NOTICE_TEXT_MAX_LENGTH = 4000;
type CatalogValue = Category | Urgency | Department;
const optionLabels = {
  riesgo_electrico: "Riesgo eléctrico",
  caidas_obstaculos: "Caídas y obstáculos",
  incendio: "Incendio",
  maquinaria: "Maquinaria",
  sustancias_peligrosas: "Sustancias peligrosas",
  problemas_estructurales: "Problemas estructurales",
  falta_epi: "Falta de EPI",
  ergonomia: "Ergonomía",
  otros: "Otros",
  baja: "Baja",
  media: "Media",
  alta: "Alta",
  critica: "Crítica",
  prevencion: "Prevención",
  mantenimiento: "Mantenimiento",
  seguridad: "Seguridad",
  limpieza: "Limpieza",
} satisfies Record<CatalogValue, string>;
const optionLabel = (value: CatalogValue) => optionLabels[value];

const catalogValue = <T extends string>(value: string, catalog: readonly T[]): T => {
  const match = catalog.find((item) => item === value);
  if (match === undefined) throw new Error("El valor seleccionado no pertenece al catálogo activo.");
  return match;
};

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
  const [health, setHealth] = useState<HealthResponse | null | undefined>(undefined);
  const [pendingCount, setPendingCount] = useState(0);
  const [riskMatrix, setRiskMatrix] = useState<RiskMatrixDocument | null>(null);
  const [riskMatrixError, setRiskMatrixError] = useState<unknown>(null);
  const [knowledgeBase, setKnowledgeBase] = useState<KnowledgeBaseSummary | null>(null);
  const [knowledgeBaseError, setKnowledgeBaseError] = useState<unknown>(null);
  const [catalogs, setCatalogs] = useState<CatalogsResponse | null>(null);
  const [catalogsError, setCatalogsError] = useState<unknown>(null);

  const navigate = (next: View) => {
    setView(next);
    setMenuOpen(false);
  };

  useEffect(() => {
    void api.health().then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    void api
      .listNotices({ status: "pending_review", page: 1, limit: 1 })
      .then((page) => setPendingCount(page.total))
      .catch(() => undefined);
  }, [view]);

  useEffect(() => {
    void api.getRiskMatrix().then(setRiskMatrix).catch(setRiskMatrixError);
    void api.getKnowledgeBase().then(setKnowledgeBase).catch(setKnowledgeBaseError);
    void api.getCatalogs().then(setCatalogs).catch(setCatalogsError);
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
        <div className="service-health" aria-label="Estado de servicios">
          <div className="rail-label">Servicios</div>
          {(health?.services ?? serviceFallbacks.map((service) => ({
            ...service,
            status: health === undefined ? "checking" : "unavailable",
            detail: health === undefined
              ? "comprobando"
              : service.id === "api" ? "sin conexión" : "estado desconocido",
          }))).map((service) => (
            <div className={`service-row ${service.status}`} key={service.id}>
              <i aria-hidden="true" />
              <span>
                {service.label}
                {service.detail && <small> · {service.detail}</small>}
              </span>
            </div>
          ))}
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
        {view === "inbox" && <InboxView key="inbox" mode="pending" riskMatrix={riskMatrix} catalogs={catalogs} catalogsError={catalogsError} onPendingChange={setPendingCount} />}
        {view === "history" && <InboxView key="history" mode="history" riskMatrix={riskMatrix} catalogs={catalogs} catalogsError={catalogsError} onPendingChange={setPendingCount} />}
        {view === "dashboard" && <Dashboard />}
        {view === "matrix" && (
          <MatrixView
            matrix={riskMatrix}
            error={riskMatrixError}
            knowledgeBase={knowledgeBase}
            knowledgeError={knowledgeBaseError}
          />
        )}
        {view === "compare" && <Comparison riskMatrix={riskMatrix} catalogs={catalogs} catalogsError={catalogsError} />}
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
  const [result, setResult] = useState<TriageProposalResponse | null>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.createTriage({ text: text.trim(), provider, location: location.trim() || null }));
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
              maxLength={NOTICE_TEXT_MAX_LENGTH}
              required
              placeholder="Ej.: Cable atravesando una zona de paso junto al almacén. Dos personas han tropezado esta mañana…"
            />
            <small>{text.length}/{NOTICE_TEXT_MAX_LENGTH}</small>
          </label>

          <label className="field">
            <span><MapPin size={16} /> Ubicación <em>opcional</em></span>
            <input value={location} onChange={(event) => setLocation(event.target.value)} maxLength={200} placeholder="Edificio, planta o zona" />
          </label>

          <fieldset className="provider-picker">
            <legend>Motor de análisis</legend>
            {providers.map((value) => (
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
          <div className={`urgency ${urgencyTone(result.urgency)}`}>{optionLabel(result.urgency)}</div>
          <div className="result-fields">
            <p><b>Categoría</b>{optionLabel(result.category)}</p>
            <p><b>Departamento</b>{optionLabel(result.department)}</p>
            <p><b>Resumen</b>{result.summary}</p>
          </div>
          <ProposalExplanation proposal={result} riskMatrix={riskMatrix} evidence={result.metrics.evidence ?? []} />
          <button onClick={onCreated}>Abrir bandeja <ArrowRight size={17} /></button>
        </div>
      )}
    </section>
  );
}

function InboxView({ mode, riskMatrix, catalogs, catalogsError, onPendingChange }: { mode: "pending" | "history"; riskMatrix: RiskMatrixDocument | null; catalogs: CatalogsResponse | null; catalogsError: unknown; onPendingChange: (value: number) => void }) {
  const initialQuery: NoticeQuery = mode === "pending"
    ? { status: "pending_review", page: 1, limit: 20 }
    : { closed: true, page: 1, limit: 20 };
  const [pageData, setPageData] = useState<NoticePage>({ items: [], page: 1, limit: 20, total: 0, pages: 0 });
  const [query, setQuery] = useState<NoticeQuery>(initialQuery);
  const [searchInput, setSearchInput] = useState("");
  const [selected, setSelected] = useState<{ notice: NoticeRecord; run: TriageRunRecord } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<unknown>(null);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      const [next, pending] = await Promise.all([
        api.listNotices(query),
        api.listNotices({ status: "pending_review", page: 1, limit: 1 }),
      ]);
      setPageData(next);
      onPendingChange(pending.total);
    } catch (caught) {
      setError(caught);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { void load(); }, [query]);
  const entries = useMemo(
    () => pageData.items.flatMap((notice) => notice.triage_runs.map((run) => ({ notice, run }))),
    [pageData.items],
  );
  const updateQuery = (change: Partial<NoticeQuery>) => {
    setSelected(null);
    setQuery((current) => ({ ...current, ...change, page: change.page ?? 1 }));
  };
  const resetFilters = () => {
    setSearchInput("");
    setSelected(null);
    setQuery(initialQuery);
  };
  const isHistory = mode === "history";
  const availableStatuses = isHistory ? reviewDecisions : ["pending_review"] as const;

  return (
    <section className="page-content">
      <div className="intro-row">
        <PageIntro eyebrow={isHistory ? "03 · Registro" : "02 · Revisión"} title={isHistory ? "Registro de decisiones cerradas" : "Bandeja de decisión técnica"}>
          {isHistory
            ? "Consulta los avisos cerrados, la decisión tomada y el departamento al que quedaron derivados."
            : "Examina la propuesta original y deja una decisión humana trazable."}
        </PageIntro>
        <button className="secondary-action" onClick={() => void load()} disabled={loading}><RefreshCw className={loading ? "spin" : ""} /> Actualizar</button>
      </div>
      <StatusMessage error={error} />
      <div className="inbox-filters work-card">
        <form className="inbox-search" onSubmit={(event) => { event.preventDefault(); updateQuery({ search: searchInput.trim() || undefined }); }}>
          <label><span>Buscar</span><div><Search size={16} /><input value={searchInput} onChange={(event) => setSearchInput(event.target.value)} maxLength={200} placeholder="Texto, ubicación, resumen o revisor…" /></div></label>
          <button className="secondary-action" type="submit">Buscar</button>
        </form>
        <div className="filter-grid">
          <label>Estado<select value={query.status ?? ""} disabled={!isHistory} onChange={(event) => updateQuery({ status: event.target.value ? catalogValue(event.target.value, availableStatuses) : undefined })}><option value="">{isHistory ? "Todos los cerrados" : "Pendiente"}</option>{availableStatuses.map((value) => <option key={value} value={value}>{statusLabels[value]}</option>)}</select></label>
          <label>Urgencia<select value={query.urgency ?? ""} onChange={(event) => updateQuery({ urgency: event.target.value && catalogs ? catalogValue(event.target.value, catalogs.urgencies) : undefined })}><option value="">Todas</option>{catalogs?.urgencies.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
          <label>Categoría<select value={query.category ?? ""} onChange={(event) => updateQuery({ category: event.target.value && catalogs ? catalogValue(event.target.value, catalogs.categories) : undefined })}><option value="">Todas</option>{catalogs?.categories.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
          <label>Motor<select value={query.provider ?? ""} onChange={(event) => updateQuery({ provider: event.target.value ? catalogValue(event.target.value, providers) : undefined })}><option value="">Todos</option>{providers.map((value) => <option key={value} value={value}>{providerNames[value]}</option>)}</select></label>
          <button className="filter-reset" type="button" onClick={resetFilters}>Restablecer</button>
        </div>
      </div>
      <div className="inbox-layout">
        <div className="queue">
          <div className="queue-head"><span>{isHistory ? "Avisos cerrados" : "Pendientes"}</span><b>{pageData.total}</b></div>
          {loading && <Empty icon={<LoaderCircle className="spin" />} title="Consultando avisos" text="Recuperando la bandeja desde la API…" />}
          {!loading && !error && entries.length === 0 && <Empty icon={<ClipboardCheck />} title="Sin resultados" text="No hay avisos que coincidan con los filtros activos." />}
          {entries.map(({ notice, run }) => {
            const final = run.review?.final_classification;
            const category = final?.category ?? run.proposal.category;
            const urgency = final?.urgency ?? run.proposal.urgency;
            const destination = final?.department ?? run.proposal.department;
            return <button key={run.id} className={`queue-item ${selected?.run.id === run.id ? "selected" : ""}`} onClick={() => setSelected({ notice, run })}>
              <div className="queue-top"><span className={`urgency ${urgencyTone(urgency)}`}>{optionLabel(urgency)}</span><small>{formatDate(run.created_at ?? notice.created_at)}</small></div>
              <strong>{optionLabel(category)}</strong>
              <p>{notice.text}</p>
              <footer><span><MapPin size={14} /> {notice.location || "Sin ubicación"}</span><span className={`status-chip ${run.status}`}>{statusLabels[run.status]}</span><span><UserRoundCheck size={14} /> {run.status === "rejected" ? "Destino propuesto" : isHistory ? "Derivado a" : "Destino"}: {optionLabel(destination)}</span><span>{providerNames[run.provider]}</span></footer>
            </button>;
          })}
          {!loading && pageData.total > 0 && <nav className="queue-pagination" aria-label="Paginación de avisos"><button type="button" disabled={pageData.page <= 1} onClick={() => updateQuery({ page: pageData.page - 1 })}>Anterior</button><span>Página {pageData.page} de {Math.max(pageData.pages, 1)}</span><button type="button" disabled={pageData.page >= pageData.pages} onClick={() => updateQuery({ page: pageData.page + 1 })}>Siguiente</button></nav>}
        </div>
        <div className="review-stage">
          {selected ? <ReviewPanel key={selected.run.id} {...selected} riskMatrix={riskMatrix} catalogs={catalogs} catalogsError={catalogsError} onDone={() => { setSelected(null); void load(); }} /> : <Empty icon={isHistory ? <History /> : <UserRoundCheck />} title={isHistory ? "Selecciona un aviso cerrado" : "Selecciona una propuesta"} text={isHistory ? "Aquí verás la propuesta, la decisión y el destino final del aviso." : "Aquí podrás contrastar la observación y registrar tu decisión."} />}
        </div>
      </div>
    </section>
  );
}

function ReviewPanel({ notice, run, riskMatrix, catalogs, catalogsError, onDone }: { notice: NoticeRecord; run: TriageRunRecord; riskMatrix: RiskMatrixDocument | null; catalogs: CatalogsResponse | null; catalogsError: unknown; onDone: () => void }) {
  const [decision, setDecision] = useState<ReviewDecision>("approved");
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [category, setCategory] = useState(run.proposal.category);
  const [urgency, setUrgency] = useState(run.proposal.urgency);
  const [department, setDepartment] = useState(run.proposal.department);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);
  const [auditEvents, setAuditEvents] = useState<AuditEventRecord[]>([]);
  const [auditError, setAuditError] = useState<unknown>(null);

  useEffect(() => {
    setAuditEvents([]);
    setAuditError(null);
    void api.getAuditEvents(notice.id).then(setAuditEvents).catch(setAuditError);
  }, [notice.id]);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await api.reviewNotice(notice.id, {
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
      <h2>{optionLabel(run.proposal.category)}</h2>
      <div className="review-meta"><span className={`urgency ${urgencyTone(run.proposal.urgency)}`}>{optionLabel(run.proposal.urgency)}</span><span className="routing-destination"><UserRoundCheck size={14} /> Destino propuesto: {optionLabel(run.proposal.department)}</span></div>
      <blockquote>{run.proposal.summary}</blockquote>
      <ProposalExplanation proposal={run.proposal} riskMatrix={riskMatrix} evidence={run.metrics?.evidence ?? []} />
      <div className="original-notice"><span>Observación recibida</span><p>{notice.text}</p></div>
      <AuditTimeline notice={notice} run={run} events={auditEvents} error={auditError} />

      {run.status === "pending_review" ? <>
        <fieldset className="decision-picker">
          <legend>Decisión</legend>
          {reviewDecisions.map((value) => (
            <label key={value} className={decision === value ? `selected ${value}` : ""}>
              <input type="radio" name="decision" checked={decision === value} onChange={() => setDecision(value)} />
              {value === "approved" ? "Aprobar" : value === "modified" ? "Corregir" : "Rechazar"}
            </label>
          ))}
        </fieldset>

        {decision === "modified" && catalogs && (
          <div className="correction-grid">
            <label>Categoría<select value={category} onChange={(e) => setCategory(catalogValue(e.target.value, catalogs.categories))} required>{catalogs.categories.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
            <label>Urgencia<select value={urgency} onChange={(e) => setUrgency(catalogValue(e.target.value, catalogs.urgencies))} required>{catalogs.urgencies.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
            <label>Departamento<select value={department} onChange={(e) => setDepartment(catalogValue(e.target.value, catalogs.departments))} required>{catalogs.departments.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
          </div>
        )}
        {decision === "modified" && !catalogs && <StatusMessage error={catalogsError ?? new Error("Cargando catálogos de clasificación…")} />}
        <div className="reviewer-grid">
          <label>Técnico revisor<input value={reviewer} onChange={(e) => setReviewer(e.target.value)} required minLength={2} placeholder="Nombre o identificador" /></label>
          <label>Comentario<textarea value={comment} onChange={(e) => setComment(e.target.value)} required minLength={3} placeholder="Motivo breve y verificable" /></label>
        </div>
        <StatusMessage error={error} />
        <button className="primary-action" disabled={loading || !reviewer.trim() || !comment.trim() || (decision === "modified" && !catalogs)}>{loading ? <><LoaderCircle className="spin" /> Guardando…</> : <>Registrar decisión <Check /></>}</button>
      </> : <div className={`review-completed ${run.status}`}>{run.status === "rejected" ? <X /> : <Check />}<div><strong>{statusLabels[run.status]}</strong><p>{run.review?.reviewer ?? "Revisión registrada"} · {run.review?.comment ?? "Sin comentario"}</p>{run.review?.final_classification ? <><p>Clasificación final: {optionLabel(run.review.final_classification.category)} · {optionLabel(run.review.final_classification.urgency)} · {optionLabel(run.review.final_classification.department)}</p><p className="final-destination">Derivado a {optionLabel(run.review.final_classification.department)}</p></> : <p className="final-destination">Aviso rechazado · sin derivación departamental</p>}</div></div>}
    </form>
  );
}

function AuditTimeline({ notice, run, events, error }: { notice: NoticeRecord; run: TriageRunRecord; events: AuditEventRecord[]; error: unknown }) {
  const reviewEvent = events.find((event) => event.event_type === "review_completed");
  const final = run.review?.final_classification;
  const changes = final ? [
    run.proposal.category !== final.category ? `Categoría: ${optionLabel(run.proposal.category)} → ${optionLabel(final.category)}` : null,
    run.proposal.urgency !== final.urgency ? `Urgencia: ${optionLabel(run.proposal.urgency)} → ${optionLabel(final.urgency)}` : null,
    run.proposal.department !== final.department ? `Departamento: ${optionLabel(run.proposal.department)} → ${optionLabel(final.department)}` : null,
  ].filter((value): value is string => value !== null) : [];

  return <section className="audit-timeline" aria-label="Línea temporal de auditoría">
    <div className="audit-title"><span>Auditoría HITL</span><strong>Línea temporal</strong></div>
    <ol>
      <li><time>{formatDate(notice.created_at)}</time><div><strong>Aviso recibido</strong><p>{notice.location || "Sin ubicación registrada"}</p></div></li>
      <li><time>{formatDate(run.created_at)}</time><div><strong>{providerNames[run.provider]} propone</strong><p>{optionLabel(run.proposal.category)} · {optionLabel(run.proposal.urgency)} · {optionLabel(run.proposal.department)}</p></div></li>
      {reviewEvent && <li><time>{formatDate(reviewEvent.created_at)}</time><div><strong>Revisado por {reviewEvent.actor || "persona técnica"}</strong><p>{reviewEvent.previous_status ? `${statusLabels[reviewEvent.previous_status]} → ` : ""}{statusLabels[reviewEvent.new_status]}</p></div></li>}
      {changes.length > 0 && <li className="audit-change"><time>{formatDate(run.review?.created_at)}</time><div><strong>Clasificación corregida</strong>{changes.map((change) => <p key={change}>{change}</p>)}</div></li>}
    </ol>
    {!events.length && !error && <small>Recuperando eventos de auditoría…</small>}
    <StatusMessage error={error} />
  </section>;
}

function Dashboard() {
  const [summary, setSummary] = useState<MetricsSummary | null>(null);
  const [error, setError] = useState<unknown>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    void api.getMetricsSummary().then(setSummary).catch(setError).finally(() => setLoading(false));
  }, []);

  const cards = summary ? [
    ["Avisos procesados", summary.total_notices, Activity, "Entradas persistidas"],
    ["IA aceptada", formatRate(summary.acceptance_rate), ShieldCheck, `${summary.approved} decisiones sin cambios`],
    ["IA corregida", formatRate(summary.correction_rate), ClipboardCheck, `${summary.modified} correcciones humanas`],
    ["Pendientes", summary.pending_review, Clock3, `${summary.reviewed} ya revisados`],
  ] as const : [];

  return (
    <section className="page-content">
      <PageIntro eyebrow="03 · Evaluación histórica" title="Qué modelo funciona mejor, medido con datos.">Rendimiento, estabilidad, coste y acuerdo con la revisión humana a partir de ejecuciones persistidas.</PageIntro>
      <StatusMessage error={error} />
      {loading ? <Empty icon={<LoaderCircle className="spin" />} title="Calculando indicadores" text="Consultando métricas agregadas en la API…" /> : (
        summary && <>
          <div className="metrics-grid">
            {cards.map(([label, value, Icon, note], index) => <article key={label} className={`metric-card m${index + 1}`}><Icon /><span>{label}</span><strong>{value}</strong><small>{note}</small></article>)}
          </div>
          <div className="provider-evaluation-grid">
            {summary.providers.map((provider) => {
              const cost = provider.mean_api_cost === null ? "—" : `${provider.mean_api_cost}${provider.api_cost_currency ? ` ${provider.api_cost_currency}` : ""}`;
              return <article className="provider-evaluation-card work-card" key={provider.provider}>
                <header><div className="provider-icon">{provider.provider === "local" ? <Activity /> : <Sparkles />}</div><div><span>Proveedor evaluado</span><h2>{providerNames[provider.provider]}</h2><small>{provider.models.join(" · ") || "Modelo no registrado"}</small></div><strong>{provider.runs}<small>ejecuciones</small></strong></header>
                <div className="provider-score-grid">
                  <div><span>Latencia media</span><strong>{formatDuration(provider.mean_latency_ms)}</strong></div>
                  <div><span>Con reparación</span><strong>{formatRate(provider.repair_rate)}</strong></div>
                  <div><span>Coincide humano</span><strong>{formatRate(provider.human_agreement_rate)}</strong><small>{provider.reviewed_runs} revisadas</small></div>
                  <div><span>JSON válido</span><strong>{formatRate(provider.json_valid_rate)}</strong><small>{provider.json_valid_observations} medidas</small></div>
                  <div><span>Tokens medios</span><strong>{provider.mean_total_tokens === null ? "—" : Math.round(provider.mean_total_tokens)}</strong><small>{provider.token_observations} medidas</small></div>
                  <div><span>Coste API medio</span><strong>{cost}</strong><small>{provider.cost_observations} medidas</small></div>
                </div>
                <footer><span>Éxito <b>{formatRate(provider.success_rate)}</b></span><span>Intentos medios <b>{formatNumber(provider.mean_provider_attempts)}</b></span><span>Reparaciones medias <b>{formatNumber(provider.mean_repair_attempts)}</b></span><span>temperature <b>{provider.temperatures.join(" / ") || "—"}</b></span><span>top_p <b>{provider.top_p_values.join(" / ") || "—"}</b></span></footer>
              </article>;
            })}
          </div>
          <p className="dashboard-definition"><ShieldCheck /> “Coincide humano” exige una aprobación sin cambios o coincidencia en los tres campos de una comparación revisada. Las ejecuciones incluyen avisos y comparaciones; los indicadores superiores corresponden solo al flujo de avisos.</p>
        </>
      )}
    </section>
  );
}

const formatDuration = (milliseconds: number | null) => milliseconds === null
  ? "—"
  : milliseconds >= 1000
    ? `${(milliseconds / 1000).toFixed(2)} s`
    : `${Math.round(milliseconds)} ms`;

const formatNumber = (value: number | null) => value === null ? "—" : value.toFixed(2);

function ProposalExplanation({
  proposal,
  riskMatrix,
  evidence = [],
  compact = false,
}: {
  proposal: TriageProposal;
  riskMatrix: RiskMatrixDocument | null;
  evidence?: KnowledgeEvidence[];
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
      {evidence.length > 0 && (
        <div className="rag-evidence" aria-label="Evidencia consultada">
          <div className="rag-evidence-heading">
            <BookOpen size={16} aria-hidden="true" />
            <div><strong>Evidencia consultada</strong><small>Fuentes recuperadas por el backend</small></div>
          </div>
          <ul>
            {evidence.map((source) => (
              <li key={`${source.source_type}:${source.source_id}`}>
                <span>{source.source_id}</span>
                <div>
                  <strong>{source.title}</strong>
                  <small>{source.section} · versión {source.version}</small>
                  <p>{source.excerpt}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
      <details className="json-panel">
        <summary><Braces size={16} /> Ver JSON estructurado</summary>
        <pre>{JSON.stringify(proposal, null, 2)}</pre>
      </details>
    </section>
  );
}

function MatrixView({
  matrix,
  error,
  knowledgeBase,
  knowledgeError,
}: {
  matrix: RiskMatrixDocument | null;
  error: unknown;
  knowledgeBase: KnowledgeBaseSummary | null;
  knowledgeError: unknown;
}) {
  const rules = Array.isArray(matrix?.rules) ? matrix.rules : [];
  const urgencyCatalog = [...new Set(rules.map((rule) => rule.recommended_urgency))];
  const departmentCatalog = [...new Set(rules.map((rule) => rule.department))];

  return (
    <section className="page-content">
      <PageIntro eyebrow="04 · Referencia" title="Matriz de riesgos visible y auditable.">
        Consulta las mismas reglas que utiliza el motor para proponer categoría, urgencia y departamento.
      </PageIntro>
      <StatusMessage error={error} />
      <StatusMessage error={knowledgeError} />
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
      <article className="knowledge-overview work-card">
        <header>
          <div className="knowledge-title">
            <span><BookOpen size={20} /></span>
            <div><small>Biblioteca documental</small><h2>RAG preventivo</h2></div>
          </div>
          <strong>{knowledgeBase ? `${knowledgeBase.document_count} fuentes · v${knowledgeBase.version}` : "Cargando corpus…"}</strong>
        </header>
        <div className="rag-flow" aria-label="Flujo de decisión y evidencia">
          <span>Matriz PRL</span><ArrowRight aria-hidden="true" />
          <span>RAG documental</span><ArrowRight aria-hidden="true" />
          <span>Modelo</span><ArrowRight aria-hidden="true" />
          <span>Revisión humana</span>
        </div>
        <p>
          <strong>La matriz clasifica y propone el departamento.</strong> El RAG no sustituye esas
          reglas: recupera documentos preventivos relacionados con la categoría ya validada para
          fundamentar la propuesta.
        </p>
        <div className="knowledge-storage">
          <Braces size={18} />
          <p><strong>Almacenamiento actual</strong><code>data/knowledge/prevention_docs.v1.json</code></p>
        </div>
        <p className="knowledge-ingestion">
          PDF y DOCX no se leen directamente todavía. Para incorporarlos hay que extraer el texto,
          dividirlo en fragmentos, añadir metadatos y regenerar el corpus versionado.
        </p>
        {knowledgeBase && (
          <details className="knowledge-sources">
            <summary>Ver inventario de fuentes</summary>
            <ul>
              {knowledgeBase.sources.map((source) => (
                <li key={source.source_id}>
                  <strong>{source.title}</strong>
                  <span>{source.source_id} · {source.section}</span>
                  <small>{source.categories.map(optionLabel).join(" · ")}</small>
                </li>
              ))}
            </ul>
            <p>{knowledgeBase.disclaimer}</p>
          </details>
        )}
      </article>
    </section>
  );
}

function Comparison({ riskMatrix, catalogs, catalogsError }: { riskMatrix: RiskMatrixDocument | null; catalogs: CatalogsResponse | null; catalogsError: unknown }) {
  const [text, setText] = useState("");
  const [location, setLocation] = useState("");
  const [result, setResult] = useState<ComparisonResponse | null>(null);
  const [humanReview, setHumanReview] = useState<ComparisonReviewRecord | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true); setError(null); setResult(null); setHumanReview(null);
    try {
      const comparison = await api.compare(text.trim(), location.trim() || null);
      setResult(comparison);
      setHumanReview(comparison.review);
    }
    catch (caught) { setError(caught); }
    finally { setLoading(false); }
  };

  const runs = result?.results ?? [];
  const localResult = runs.find((item) => item.provider === "local");
  const externalResult = runs.find((item) => item.provider === "external");
  return (
    <section className="page-content">
      <PageIntro eyebrow="05 · Evaluación" title="Mismo caso. Dos proveedores. Una comparación justa.">Ejecuta el caso sintético con los dos motores y contrasta calidad, latencia, tokens y coste.</PageIntro>
      <form className="compare-form work-card" onSubmit={submit}>
        <label className="field"><span>Caso sintético</span><textarea aria-label="Caso sintético" value={text} onChange={(e) => setText(e.target.value)} required minLength={1} maxLength={NOTICE_TEXT_MAX_LENGTH} placeholder="Describe un riesgo sin datos personales…" /></label>
        <label className="field compact"><span><MapPin size={16} /> Ubicación <em>opcional</em></span><input value={location} onChange={(e) => setLocation(e.target.value)} maxLength={200} placeholder="Zona de prueba" /></label>
        <button className="primary-action" disabled={loading || text.trim().length < 1}>{loading ? <><LoaderCircle className="spin" /> Comparando…</> : <><GitCompareArrows /> Ejecutar ambos motores</>}</button>
      </form>
      <StatusMessage error={error} />
      {result && (
        <>
          <div className="comparison-grid enriched">
            {localResult && <ProviderComparisonCard item={localResult} riskMatrix={riskMatrix} />}
            <ComparisonAnalysis results={runs} humanReview={humanReview} />
            {externalResult && <ProviderComparisonCard item={externalResult} riskMatrix={riskMatrix} />}
          </div>
          <ComparisonHumanReview comparison={result} review={humanReview} catalogs={catalogs} catalogsError={catalogsError} onReviewed={setHumanReview} />
        </>
      )}
      {!result && !loading && <div className="comparison-placeholder"><div><Activity /><span className="bridge" /><Sparkles /></div><h2>Preparado para comparar</h2><p>El resultado no crea dos avisos: conserva una única evaluación reproducible del mismo caso.</p></div>}
      <EvaluationBenchmark />
    </section>
  );
}

function ProviderComparisonCard({ item, riskMatrix }: { item: ComparisonProviderResult; riskMatrix: RiskMatrixDocument | null }) {
  if (!item.result) {
    return <article className="comparison-card" key={item.provider}><header><span>{item.provider === "local" ? <Activity /> : <Sparkles />}</span><div><small>Proveedor</small><h2>{providerNames[item.provider]}</h2></div></header><div className="message error" role="alert"><AlertTriangle /><div><strong>No se obtuvo una propuesta válida.</strong><small>Código: {item.error_code ?? "provider_error"}</small></div></div></article>;
  }
  const proposal = item.result;
  const metrics = item.metrics;
  const cost = metrics.api_cost === null ? "—" : `${metrics.api_cost}${metrics.api_cost_currency ? ` ${metrics.api_cost_currency}` : ""}`;
  return <article className="comparison-card"><header><span>{item.provider === "local" ? <Activity /> : <Sparkles />}</span><div><small>Proveedor</small><h2>{providerNames[item.provider]}</h2><em>{metrics.model ?? "Modelo no registrado"}</em></div></header><div className={`urgency ${urgencyTone(proposal.urgency)}`}>{optionLabel(proposal.urgency)}</div><h3>{optionLabel(proposal.category)}</h3><p>{proposal.summary}</p><p className="comparison-department"><strong>Departamento:</strong> {optionLabel(proposal.department)}</p><ProposalExplanation proposal={proposal} riskMatrix={riskMatrix} evidence={metrics.evidence ?? []} compact /><dl><div><dt>Latencia</dt><dd>{formatDuration(metrics.latency_ms)}</dd></div><div><dt>Reparaciones</dt><dd>{metrics.repair_attempts}</dd></div><div><dt>Tokens</dt><dd>{metrics.total_tokens ?? "—"}</dd></div><div><dt>Coste</dt><dd>{cost}</dd></div></dl></article>;
}

function ComparisonAnalysis({ results, humanReview }: { results: ComparisonProviderResult[]; humanReview: ComparisonReviewRecord | null }) {
  const local = results.find((item) => item.provider === "local");
  const external = results.find((item) => item.provider === "external");
  const both = local?.result && external?.result ? { local: local.result, external: external.result } : null;
  const fields = both ? [
    ["Categoría", both.local.category === both.external.category],
    ["Urgencia", both.local.urgency === both.external.urgency],
    ["Departamento", both.local.department === both.external.department],
  ] as const : [];
  const faster = local && external
    ? local.metrics.latency_ms <= external.metrics.latency_ms
      ? { provider: "local" as const, difference: external.metrics.latency_ms - local.metrics.latency_ms }
      : { provider: "external" as const, difference: local.metrics.latency_ms - external.metrics.latency_ms }
    : null;
  const fewerRepairs = local && external
    ? local.metrics.repair_attempts === external.metrics.repair_attempts
      ? null
      : local.metrics.repair_attempts < external.metrics.repair_attempts ? "local" as const : "external" as const
    : null;

  return <article className="comparison-analysis">
    <header><GitCompareArrows /><div><small>Comparación</small><h2>Lectura directa</h2></div></header>
    <div className="agreement-list">
      {fields.length ? fields.map(([label, matches]) => <div key={label}><span>{label}</span><strong className={matches ? "match" : "mismatch"}>{matches ? "✓ Coinciden" : "⚠ Discrepan"}</strong></div>) : <p>No hay dos resultados válidos para contrastar.</p>}
    </div>
    <div className="comparison-winners">
      <div><span>Más rápido</span><strong>{faster ? providerNames[faster.provider] : "—"}</strong><small>{faster ? `${formatDuration(faster.difference)} de diferencia` : "Sin datos"}</small></div>
      <div><span>Menos reparaciones</span><strong>{fewerRepairs ? providerNames[fewerRepairs] : "Empate"}</strong><small>{local?.metrics.repair_attempts ?? "—"} vs {external?.metrics.repair_attempts ?? "—"}</small></div>
      <div><span>Coste API</span><small>Ollama <b>{local?.metrics.api_cost ?? "—"}</b></small><small>Gemini <b>{external?.metrics.api_cost ?? "—"} {external?.metrics.api_cost_currency ?? ""}</b></small></div>
    </div>
    {humanReview && <div className="human-verdict"><span>Decisión humana</span><strong>{optionLabel(humanReview.category)} · {optionLabel(humanReview.urgency)}</strong>{results.map((item) => {
      const matches = item.result ? [item.result.category === humanReview.category, item.result.urgency === humanReview.urgency, item.result.department === humanReview.department].filter(Boolean).length : 0;
      return <div key={item.provider}><span>{providerNames[item.provider]}</span><b className={matches === 3 ? "match" : "mismatch"}>{matches === 3 ? "✓ 3/3" : `${matches}/3`}</b></div>;
    })}</div>}
  </article>;
}

function ComparisonHumanReview({ comparison, review, catalogs, catalogsError, onReviewed }: { comparison: ComparisonResponse; review: ComparisonReviewRecord | null; catalogs: CatalogsResponse | null; catalogsError: unknown; onReviewed: (value: ComparisonReviewRecord) => void }) {
  const seed = comparison.results.find((item) => item.result !== null)?.result;
  const [category, setCategory] = useState<Category>(seed?.category ?? "otros");
  const [urgency, setUrgency] = useState<Urgency>(seed?.urgency ?? "media");
  const [department, setDepartment] = useState<Department>(seed?.department ?? "prevencion");
  const [reviewer, setReviewer] = useState("");
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  if (review) return <div className="comparison-review-saved"><Check /><div><strong>Referencia humana registrada</strong><p>{optionLabel(review.category)} · {optionLabel(review.urgency)} · {optionLabel(review.department)}</p><small>{review.reviewer}: {review.comment}</small></div></div>;

  const submit = async (event: React.FormEvent) => {
    event.preventDefault();
    setLoading(true); setError(null);
    try { onReviewed(await api.reviewComparison(comparison.comparison_id, { category, urgency, department, reviewer: reviewer.trim(), comment: comment.trim() })); }
    catch (caught) { setError(caught); }
    finally { setLoading(false); }
  };

  return <form className="comparison-review-form work-card" onSubmit={submit}>
    <div className="card-heading"><div className="step-number">H</div><div><h2>Añadir decisión humana de referencia</h2><p>Permite medir cuál de los dos modelos coincide mejor en este caso.</p></div></div>
    {catalogs ? <div className="comparison-review-fields">
      <label>Categoría<select value={category} onChange={(event) => setCategory(catalogValue(event.target.value, catalogs.categories))}>{catalogs.categories.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
      <label>Urgencia<select value={urgency} onChange={(event) => setUrgency(catalogValue(event.target.value, catalogs.urgencies))}>{catalogs.urgencies.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
      <label>Departamento<select value={department} onChange={(event) => setDepartment(catalogValue(event.target.value, catalogs.departments))}>{catalogs.departments.map((value) => <option key={value} value={value}>{optionLabel(value)}</option>)}</select></label>
      <label>Persona revisora<input value={reviewer} onChange={(event) => setReviewer(event.target.value)} minLength={1} maxLength={200} required /></label>
      <label>Comentario<textarea value={comment} onChange={(event) => setComment(event.target.value)} minLength={1} maxLength={2000} required /></label>
    </div> : <StatusMessage error={catalogsError ?? new Error("Cargando catálogos de clasificación…")} />}
    <StatusMessage error={error} />
    <button className="primary-action" disabled={!catalogs || loading || !reviewer.trim() || !comment.trim()}>{loading ? <><LoaderCircle className="spin" /> Guardando referencia…</> : <><UserRoundCheck /> Registrar referencia humana</>}</button>
  </form>;
}

const formatRate = (value: number | null) => value === null ? "—" : `${Math.round(value * 100)}%`;

function EvaluationBenchmark() {
  const [report, setReport] = useState<EvaluationReport | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<unknown>(null);

  const run = async () => {
    setLoading(true);
    setError(null);
    try { setReport(await api.runEvaluation()); }
    catch (caught) { setError(caught); }
    finally { setLoading(false); }
  };

  return (
    <section className="benchmark-panel work-card" aria-labelledby="benchmark-title">
      <div className="benchmark-heading">
        <div className="benchmark-icon"><BarChart3 /></div>
        <div>
          <span>Benchmark etiquetado</span>
          <h2 id="benchmark-title">Calidad de clasificación medible</h2>
          <p>14 casos sintéticos × 2 proveedores. La exactitud se calcula contra categoría, urgencia y departamento esperados.</p>
        </div>
        <button className="secondary-action" type="button" onClick={run} disabled={loading}>
          {loading ? <><LoaderCircle className="spin" /> Ejecutando 28 inferencias…</> : <><RefreshCw /> Ejecutar benchmark</>}
        </button>
      </div>
      <StatusMessage error={error} />
      {report && (
        <>
          <div className="benchmark-meta">
            <span>Dataset {report.dataset_version}</span>
            <span>Generado {formatDate(report.generated_at)}</span>
          </div>
          <div className="benchmark-grid">
            {report.summaries.map((summary) => {
              const rates = [summary.category_accuracy, summary.urgency_accuracy, summary.department_accuracy].filter((value): value is number => value !== null);
              const overall = rates.length ? rates.reduce((total, value) => total + value, 0) / rates.length : null;
              const cost = summary.mean_api_cost === null ? "—" : `${summary.mean_api_cost}${summary.api_cost_currency ? ` ${summary.api_cost_currency}` : ""}`;
              return (
                <article className="benchmark-card" key={summary.provider}>
                  <header><div><small>Proveedor</small><h3>{providerNames[summary.provider]}</h3></div><strong>{formatRate(overall)}<small>calidad media</small></strong></header>
                  <div className="quality-bars">
                    {[
                      ["Categoría", summary.category_accuracy],
                      ["Urgencia", summary.urgency_accuracy],
                      ["Departamento", summary.department_accuracy],
                    ].map(([label, raw]) => {
                      const value = typeof raw === "number" ? raw : null;
                      return <div key={String(label)}><span>{label}</span><i><b style={{ width: `${(value ?? 0) * 100}%` }} /></i><strong>{formatRate(value)}</strong></div>;
                    })}
                  </div>
                  <dl>
                    <div><dt>Casos</dt><dd>{summary.cases}</dd></div>
                    <div><dt>JSON válido</dt><dd>{formatRate(summary.json_valid_rate)}</dd></div>
                    <div><dt>Latencia media</dt><dd>{summary.mean_latency_ms === null ? "—" : `${Math.round(summary.mean_latency_ms)} ms`}</dd></div>
                    <div><dt>Coste medio</dt><dd>{cost}</dd></div>
                  </dl>
                </article>
              );
            })}
          </div>
          <p className="benchmark-disclaimer"><ShieldCheck /> {report.disclaimer}</p>
        </>
      )}
      {!report && !loading && !error && <p className="benchmark-empty">El benchmark se ejecuta bajo demanda porque consulta ambos modelos y puede consumir tiempo y cuota de la API externa.</p>}
    </section>
  );
}

function Empty({ icon, title, text }: { icon: React.ReactNode; title: string; text: string }) {
  return <div className="empty-state"><span>{icon}</span><h3>{title}</h3><p>{text}</p></div>;
}

export default App;
