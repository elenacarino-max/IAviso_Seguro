"""Dashboard Streamlit conectado exclusivamente a la API de IAviso Seguro."""

from __future__ import annotations

import os
from collections import Counter
from collections.abc import Mapping
from typing import Any

import streamlit as st

from frontend.api_client import ApiClientError, IAvisoApiClient

_CATEGORIES = (
    "riesgo_electrico",
    "caidas_obstaculos",
    "incendio",
    "maquinaria",
    "sustancias_peligrosas",
    "problemas_estructurales",
    "falta_epi",
    "ergonomia",
    "otros",
)
_URGENCIES = ("baja", "media", "alta", "critica")
_DEPARTMENTS = ("prevencion", "mantenimiento", "seguridad", "limpieza")
_URGENCY_TEXT = {
    "baja": "BAJA — seguimiento preventivo",
    "media": "MEDIA — atención programada",
    "alta": "ALTA — atención prioritaria",
    "critica": "CRÍTICA — aplicar el protocolo de emergencia",
}


@st.cache_resource
def _api_client(base_url: str) -> IAvisoApiClient:
    return IAvisoApiClient(base_url)


def _show_api_error(error: ApiClientError) -> None:
    suffix = f" ({error.code})" if error.code else ""
    st.error(f"{error}{suffix}")


def _show_urgency(value: object) -> None:
    urgency = str(value or "desconocida")
    message = f"Urgencia: {_URGENCY_TEXT.get(urgency, urgency.upper())}"
    if urgency == "critica":
        st.error(message)
    elif urgency == "alta":
        st.warning(message)
    elif urgency == "media":
        st.info(message)
    else:
        st.success(message)


def _show_metrics(metrics: object) -> None:
    if not isinstance(metrics, Mapping):
        st.caption("Métricas no disponibles.")
        return
    values = {
        "Modelo": metrics.get("model") or "desconocido",
        "Latencia (ms)": metrics.get("latency_ms"),
        "Intentos proveedor": metrics.get("provider_attempts"),
        "Reparaciones": metrics.get("repair_attempts"),
        "Tokens entrada": metrics.get("input_tokens"),
        "Tokens salida": metrics.get("output_tokens"),
        "Coste API": (
            f"{metrics.get('api_cost')} {metrics.get('api_cost_currency') or ''}".strip()
            if metrics.get("api_cost") is not None
            else "desconocido"
        ),
        "Coste computacional": (
            metrics.get("computational_cost")
            if metrics.get("computational_cost") is not None
            else "desconocido"
        ),
    }
    st.dataframe(
        [{"Métrica": key, "Valor": value} for key, value in values.items()],
        hide_index=True,
        use_container_width=True,
    )


def _show_result(result: Mapping[str, Any], *, show_metrics: bool = True) -> None:
    _show_urgency(result.get("urgency"))
    left, right = st.columns(2)
    left.metric("Categoría", str(result.get("category", "desconocida")))
    right.metric("Departamento", str(result.get("department", "desconocido")))
    st.write(f"**Resumen:** {result.get('summary', 'No disponible')}")
    st.write(f"**Justificación:** {result.get('justification', 'No disponible')}")
    if show_metrics:
        with st.expander("Modelo y métricas", expanded=False):
            _show_metrics(result.get("metrics"))


def _new_notice(client: IAvisoApiClient) -> None:
    st.header("Nuevo aviso")
    st.caption("Describe una situación observada. No incluyas datos personales.")
    with st.form("new-notice"):
        text = st.text_area(
            "Descripción del riesgo",
            height=140,
            max_chars=4000,
            placeholder="Ejemplo: hay agua derramada sin señalizar en el pasillo.",
        )
        location = st.text_input("Ubicación opcional", max_chars=200)
        provider = st.radio(
            "Proveedor",
            ("local", "external"),
            format_func=lambda value: (
                "Local · Ollama" if value == "local" else "Externo · Gemini"
            ),
            horizontal=True,
        )
        submitted = st.form_submit_button(
            "Crear propuesta para revisión",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        try:
            st.session_state["last_proposal"] = client.create_triage(
                text=text,
                location=location.strip() or None,
                provider=provider,
            )
        except ApiClientError as error:
            _show_api_error(error)

    proposal = st.session_state.get("last_proposal")
    if isinstance(proposal, Mapping):
        st.subheader("Propuesta pendiente de revisión")
        st.caption(
            f"Estado: {proposal.get('status')} · "
            f"Proveedor: {proposal.get('provider')}"
        )
        _show_result(proposal)


def _pending_notices(client: IAvisoApiClient) -> None:
    st.header("Bandeja de revisión")
    try:
        notices = client.list_notices()
    except ApiClientError as error:
        _show_api_error(error)
        return

    pending = [
        (notice, run)
        for notice in notices
        for run in notice.get("triage_runs", [])
        if isinstance(run, Mapping) and run.get("status") == "pending_review"
    ]
    if not pending:
        st.info("No hay propuestas pendientes de revisión.")
        return

    for notice, run in pending:
        notice_id = str(notice.get("id"))
        run_id = str(run.get("id"))
        with st.expander(
            f"{notice.get('location') or 'Sin ubicación'} · {notice_id[:8]}",
            expanded=False,
        ):
            st.write(f"**Aviso:** {notice.get('text')}")
            proposal = run.get("proposal")
            if isinstance(proposal, Mapping):
                enriched = dict(proposal)
                enriched["metrics"] = run.get("metrics")
                _show_result(enriched)

            decision = st.radio(
                "Decisión",
                ("approved", "modified", "rejected"),
                format_func=lambda value: {
                    "approved": "Aprobar",
                    "modified": "Modificar",
                    "rejected": "Rechazar",
                }[value],
                horizontal=True,
                key=f"decision-{run_id}",
            )
            with st.form(f"review-{run_id}"):
                reviewer = st.text_input(
                    "Nombre de la persona revisora",
                    max_chars=200,
                )
                comment = st.text_area(
                    "Comentario de revisión",
                    max_chars=2000,
                )
                category = urgency = department = None
                if decision == "modified" and isinstance(proposal, Mapping):
                    category = st.selectbox(
                        "Categoría final",
                        _CATEGORIES,
                        index=_option_index(
                            _CATEGORIES,
                            proposal.get("category"),
                        ),
                    )
                    urgency = st.selectbox(
                        "Urgencia final",
                        _URGENCIES,
                        index=_option_index(
                            _URGENCIES,
                            proposal.get("urgency"),
                        ),
                    )
                    department = st.selectbox(
                        "Departamento final",
                        _DEPARTMENTS,
                        index=_option_index(
                            _DEPARTMENTS,
                            proposal.get("department"),
                        ),
                    )
                submitted = st.form_submit_button(
                    "Registrar revisión",
                    type="primary",
                )
            if submitted:
                try:
                    client.review_notice(
                        notice_id,
                        decision=decision,
                        reviewer=reviewer,
                        comment=comment,
                        expected_version=int(run.get("version", 0)),
                        category=category,
                        urgency=urgency,
                        department=department,
                    )
                except ApiClientError as error:
                    _show_api_error(error)
                else:
                    st.success("Revisión registrada correctamente.")
                    st.rerun()


def _overview(client: IAvisoApiClient) -> None:
    st.header("Panel general")
    try:
        notices = client.list_notices()
    except ApiClientError as error:
        _show_api_error(error)
        return

    runs = [
        run
        for notice in notices
        for run in notice.get("triage_runs", [])
        if isinstance(run, Mapping)
    ]
    pending = sum(run.get("status") == "pending_review" for run in runs)
    reviewed = len(runs) - pending
    first, second, third = st.columns(3)
    first.metric("Avisos", len(notices))
    second.metric("Pendientes", pending)
    third.metric("Revisados", reviewed)

    urgencies = Counter(
        str(proposal.get("urgency"))
        for run in runs
        if isinstance((proposal := run.get("proposal")), Mapping)
    )
    st.subheader("Propuestas por urgencia")
    if urgencies:
        st.bar_chart(
            {"Propuestas": [urgencies.get(level, 0) for level in _URGENCIES]},
            x_label="Nivel: baja, media, alta, crítica",
            y_label="Número de propuestas",
        )
        st.caption(
            "Orden de las barras: baja, media, alta y crítica. "
            "El gráfico resume propuestas, no decisiones profesionales."
        )
    else:
        st.info("Todavía no hay datos para mostrar.")


def _comparison(client: IAvisoApiClient) -> None:
    st.header("Comparación de proveedores")
    st.caption(
        "La misma entrada se procesa una vez con cada proveedor y no crea avisos."
    )
    with st.form("comparison"):
        text = st.text_area(
            "Descripción común",
            height=120,
            max_chars=4000,
        )
        location = st.text_input("Ubicación opcional", max_chars=200)
        submitted = st.form_submit_button(
            "Comparar local y externo",
            type="primary",
            use_container_width=True,
        )
    if submitted:
        try:
            st.session_state["last_comparison"] = client.compare(
                text=text,
                location=location.strip() or None,
            )
        except ApiClientError as error:
            _show_api_error(error)

    comparison = st.session_state.get("last_comparison")
    if not isinstance(comparison, Mapping):
        return
    results = comparison.get("results")
    if not isinstance(results, list):
        st.error("La comparación recibida no es válida.")
        return
    columns = st.columns(2)
    for column, item in zip(columns, results, strict=False):
        if not isinstance(item, Mapping):
            continue
        with column:
            st.subheader(
                "Proveedor local"
                if item.get("provider") == "local"
                else "Proveedor externo"
            )
            result = item.get("result")
            if isinstance(result, Mapping):
                _show_result(result, show_metrics=False)
            else:
                st.error(
                    "Sin resultado. "
                    f"Código: {item.get('error_code') or 'desconocido'}"
                )
            _show_metrics(item.get("metrics"))


def _option_index(options: tuple[str, ...], value: object) -> int:
    try:
        return options.index(str(value))
    except ValueError:
        return 0


def main(client: IAvisoApiClient | None = None) -> None:
    st.set_page_config(
        page_title="IAviso Seguro",
        page_icon="🦺",
        layout="wide",
    )
    st.title("IAviso Seguro")
    st.warning(
        "Prototipo académico. Toda clasificación requiere revisión profesional. "
        "Ante peligro inmediato, aplica el protocolo de emergencia del centro."
    )
    active_client = client or _api_client(
        os.getenv("API_BASE_URL", "http://127.0.0.1:8000")
    )
    page = st.sidebar.radio(
        "Navegación",
        ("Nuevo aviso", "Pendientes", "Panel general", "Comparación"),
    )
    st.sidebar.caption("La interfaz se comunica exclusivamente con la API.")
    if page == "Nuevo aviso":
        _new_notice(active_client)
    elif page == "Pendientes":
        _pending_notices(active_client)
    elif page == "Panel general":
        _overview(active_client)
    else:
        _comparison(active_client)


if __name__ == "__main__":
    main()
