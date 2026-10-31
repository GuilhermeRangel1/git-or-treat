import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import {
  applyUCPeriod,
  applyUCSearch,
  parseUC360SearchParams,
  selectUCHistory,
} from "./uc360-state";
import {
  useUCOverview,
  useUCSearch,
  useUCHistory,
  useUCSeries,
} from "./useUC360";
import UC360Detail from "./UC360Detail";
import UC360SearchPanel from "./UC360SearchPanel";
export default function UC360Page() {
  const { ucId: routeUCId } = useParams<{ ucId: string }>();
  const navigate = useNavigate();
  const [params, setParams] = useSearchParams();
  const state = parseUC360SearchParams(params);
  const selectedUCId = routeUCId ?? state.uc;
  const [historyDraft, setHistoryDraft] = useState({
    applied: state.section,
    open: Boolean(state.section),
  });
  const historyOpen =
    historyDraft.applied === state.section
      ? historyDraft.open
      : Boolean(state.section);
  const historyDisclosureRef = useRef<HTMLDetailsElement>(null);
  const currentSearch = params.toString();
  const hasDuplicatedUC = state.invalid.some((message) =>
    message.includes("uc duplicado"),
  );
  function setHistoryOpen(open: boolean) {
    setHistoryDraft({ applied: state.section, open });
  }
  useEffect(() => {
    if (!routeUCId && state.uc) {
      const legacyParams = new URLSearchParams(currentSearch);
      if (!hasDuplicatedUC) legacyParams.delete("uc");
      const search = legacyParams.toString();
      navigate(
        `/uc-360/${encodeURIComponent(state.uc)}${search ? `?${search}` : ""}`,
        { replace: true },
      );
    }
  }, [currentSearch, hasDuplicatedUC, navigate, routeUCId, state.uc]);
  const search = useUCSearch(
    state.q,
    state.searchPage,
    !state.invalid.length && Boolean(state.q) && !selectedUCId,
  );
  const overview = useUCOverview(
    selectedUCId,
    state.start,
    state.end,
    !state.invalid.length,
  );
  const history = useUCHistory(
    selectedUCId,
    state.section || "consumption",
    state.start,
    state.end,
    state.historyPage,
    !state.invalid.length,
  );
  const series = useUCSeries(
    selectedUCId,
    overview.data?.data.period.start ?? "",
    overview.data?.data.period.end ?? "",
    !state.invalid.length && Boolean(overview.data),
  );
  function submitSearch(query: string) {
    const searchParams = applyUCSearch(params, query);
    navigate(`/uc-360?${searchParams.toString()}`);
  }
  function openHistorySection(section: Parameters<typeof selectUCHistory>[1]) {
    setHistoryOpen(true);
    setParams(selectUCHistory(params, section));
    requestAnimationFrame(() => {
      const disclosure = historyDisclosureRef.current;
      if (disclosure && "scrollIntoView" in disclosure) {
        const reduceMotion =
          typeof window.matchMedia === "function" &&
          window.matchMedia("(prefers-reduced-motion: reduce)").matches;
        disclosure.scrollIntoView({
          behavior: reduceMotion ? "auto" : "smooth",
          block: "start",
        });
      }
    });
  }
  return (
    <div
      className={`grid w-full min-w-0 ${selectedUCId ? "mt-0 gap-6" : "mt-6 gap-4"}`}
    >
      {!selectedUCId && (
        <UC360SearchPanel
          query={state.q}
          page={state.searchPage}
          results={search.data}
          isFetching={search.isFetching}
          error={search.error}
          onSearch={submitSearch}
          onRetry={() => void search.refetch()}
          onPageChange={(page) => {
            const next = new URLSearchParams(params);
            next.set("search_page", String(page));
            setParams(next);
          }}
          onSelect={(ucId) => {
            const detailParams = new URLSearchParams();
            if (state.start && state.end) {
              detailParams.set("start", state.start);
              detailParams.set("end", state.end);
            }
            const search = detailParams.toString();
            navigate(
              `/uc-360/${encodeURIComponent(ucId)}${search ? `?${search}` : ""}`,
            );
          }}
        />
      )}
      {state.invalid.length > 0 && (
        <div
          role="alert"
          className="grid gap-2 rounded-lg border border-danger p-3 text-sm text-danger"
        >
          {state.invalid.join(" ")} Os dados não foram consultados.
          <button
            type="button"
            className="w-fit underline"
            onClick={() => {
              const clean = new URLSearchParams();
              if (routeUCId)
                navigate(`/uc-360/${encodeURIComponent(routeUCId)}`);
              else if (state.uc)
                navigate(`/uc-360/${encodeURIComponent(state.uc)}`);
              else setParams(clean);
            }}
          >
            Limpar parâmetros inválidos
          </button>
        </div>
      )}
      {selectedUCId && (
        <UC360Detail
          unit={{
            id: selectedUCId,
            overview: {
              data: overview.data,
              pending: overview.isPending,
              fetching: overview.isFetching,
              error: overview.error,
            },
            history: {
              data:
                history.data?.metadata.source.version ===
                overview.data?.metadata.source.version
                  ? history.data
                  : undefined,
              pending: history.isPending,
              error:
                history.data &&
                overview.data &&
                history.data.metadata.source.version !==
                  overview.data.metadata.source.version
                  ? new Error(
                      "A publicação do histórico mudou; atualize os dados.",
                    )
                  : history.error,
            },
            series: {
              data:
                series.data?.version === overview.data?.metadata.source.version
                  ? series.data
                  : undefined,
              pending: series.isPending || series.isFetching,
              error:
                series.data &&
                overview.data &&
                series.data.version !== overview.data.metadata.source.version
                  ? new Error("A publicação da série mudou.")
                  : series.error,
            },
            filters: {
              start: state.start,
              end: state.end,
              section: state.section,
              historyPage: state.historyPage,
              invalid: state.invalid.length > 0,
              historyOpen,
            },
          }}
          disclosureRef={historyDisclosureRef}
          actions={{
            onOverviewRetry: () => void overview.refetch(),
            onHistoryRetry: () => {
              void overview.refetch();
              void history.refetch();
            },
            onSeriesRetry: () => {
              void overview.refetch();
              void series.refetch();
            },
            onNewSearch: () => navigate("/uc-360"),
            onHistoryOpen: setHistoryOpen,
            onSelectHistory: openHistorySection,
            onHistorySection: (section) =>
              setParams(selectUCHistory(params, section)),
            onHistoryPage: (page) => {
              const next = new URLSearchParams(params);
              next.set("history_page", String(page));
              setParams(next);
            },
            onPeriodApply: (start, end) =>
              setParams(applyUCPeriod(params, start, end)),
          }}
        />
      )}
      {!selectedUCId && !state.q && (
        <p className="px-1 text-xs text-muted">
          Nenhuma UC selecionada. Os dados de atendimento serão exibidos após
          selecionar uma unidade nos resultados.
        </p>
      )}
    </div>
  );
}
