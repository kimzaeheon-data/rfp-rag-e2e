import { useState } from "react";
import { useChat } from "./useChat";

// 새 디자인(Tailwind) 적용 화면. 기능(상태·API·localStorage)은 useChat 훅에서 그대로 가져와 연결한다.
// 색·폰트·Tailwind는 public/index.html에서 주입한다(디자인 값 변경은 그쪽에서).

// 답변 본문에 섞여 나오는 [출처: ...] 표기 제거(출처는 아래 참고 문서에서 별도 표시하므로 중복)
function stripSourceTags(text) {
  if (!text) return text;
  return text
    .replace(/\[출처:[^\]]*\]/g, "")   // 대괄호형 [출처: ...]
    .replace(/^출처:.*$/gm, "")        // 대괄호 없는 출처: ... (줄 단위)
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

// 예산 숫자를 읽기 좋게(원 단위 콤마)
function formatBudget(v) {
  if (v == null || v === "") return null;
  const n = Number(v);
  return Number.isNaN(n) ? String(v) : n.toLocaleString("ko-KR") + "원";
}

// 검색된 청크(sources)를 doc_id 단위로 묶는다. 같은 문서의 여러 청크를 한 문서로 표시하기 위함.
function groupByDoc(sources) {
  const map = new Map();
  (sources || []).forEach((src) => {
    const key = src.doc_id || src.file_name;
    if (!map.has(key)) {
      map.set(key, {
        doc_id: src.doc_id,
        file_name: src.file_name,
        project_name: src.project_name,
        agency: src.agency,
        budget_amount: src.budget_amount,
        announcement_date: src.announcement_date,
        bid_end: src.bid_end,
        chunks: [],
      });
    }
    map.get(key).chunks.push({ section: src.section, content: src.content });
  });
  return Array.from(map.values());
}

// 답변이 참조한 공고(project_name) 기반 추천 질문 3개(고정 템플릿, LLM 미사용).
// project_name이 없으면 지시어("이 사업")로 폴백한다.
function buildSuggestions(projectName) {
  const label = projectName || "이 사업";
  return [
    `${label} 입찰 마감일 언제야?`,
    `${label} 예산 얼마야?`,
    `${label} 요구사항 전부 뽑아줘`,
  ];
}

// 라우트 C 체크리스트 화면 표출 상한(가독성). 파일 내보내기(CSV)는 전체를 담으므로 이 값과 무관.
const CHECKLIST_RENDER_LIMIT = 30;

// 검증 완료로 인정하는 evidence status. 이 외(unverified_evidence, out_of_scope_source 등)는 검토 필요.
const VERIFIED_STATUSES = ["strict_verified", "relocated_verified", "cross_chunk_verified"];

// 항목 단위 신뢰 판정: evidence가 하나라도 미검증이면 "검토 필요", 전부 검증되면 "원문 검증됨".
// evidence가 없으면 근거 없음이므로 검토 필요로 본다.
function itemVerified(it) {
  const evs = it.evidence || [];
  if (evs.length === 0) return false;
  return evs.every((ev) => VERIFIED_STATUSES.includes(ev.status));
}

// 신뢰 배지 렌더(원문 검증됨 / 검토 필요). 도혁님 라우트 C 검증 스토리를 UI로 노출.
function TrustBadge({ verified }) {
  return verified ? (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 rounded-full px-2 py-0.5">
      <span className="material-symbols-outlined text-[13px]">verified</span>
      원문 검증됨
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 border border-amber-200 rounded-full px-2 py-0.5">
      <span className="material-symbols-outlined text-[13px]">flag</span>
      검토 필요
    </span>
  );
}

// 라우트 C 구조화 항목을 카드 리스트로 렌더한다. 카테고리 + 항목 텍스트 + 신뢰 배지.
// (근거 펼침은 이후 단계에서 이 카드에 얹는다.)
// 체크리스트 항목 카드 1개. 클릭하면 근거(evidence)의 원문 인용(quote)을 펼쳐 하이라이트한다.
// (evidence가 없으면 펼칠 게 없으므로 클릭 비활성.)
function ChecklistItem({ item, index }) {
  const [open, setOpen] = useState(false);
  const evidences = item.evidence || [];
  const hasEvidence = evidences.length > 0;

  return (
    <div className="border border-outline-variant/40 rounded-xl bg-surface-container-low overflow-hidden">
      {/* 카드 헤더(클릭 시 근거 펼침) */}
      <button
        onClick={() => hasEvidence && setOpen(!open)}
        className={`w-full text-left px-4 py-3 flex items-start gap-2 ${hasEvidence ? "hover:bg-surface-container transition-colors cursor-pointer" : "cursor-default"}`}
      >
        <span className="text-[11px] font-bold text-on-surface-variant shrink-0 mt-0.5">{index + 1}.</span>
        <div className="flex-1">
          {/* 카테고리 칩 + 신뢰 배지(같은 줄) */}
          <div className="flex items-center gap-1.5 mb-1 flex-wrap">
            {item.category && (
              <span className="inline-block text-[10px] font-bold text-primary bg-primary/10 rounded px-1.5 py-0.5">
                {item.category}
              </span>
            )}
            <TrustBadge verified={itemVerified(item)} />
          </div>
          <p className="text-[13px] text-on-surface leading-relaxed">{item.text}</p>
        </div>
        {/* 펼침 화살표(근거 있을 때만) */}
        {hasEvidence && (
          <span className="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0 mt-0.5">
            {open ? "expand_less" : "expand_more"}
          </span>
        )}
      </button>

      {/* 근거 펼침: evidence의 원문 인용(quote)을 하이라이트로 표시 */}
      {open && hasEvidence && (
        <div className="px-4 pb-3 pt-1 space-y-2 border-t border-outline-variant/30">
          <p className="text-[10px] font-bold text-on-surface-variant uppercase tracking-wider pt-2">원문 근거</p>
          {evidences.map((ev, ei) => {
            const verified = VERIFIED_STATUSES.includes(ev.status);
            return (
              <div key={ei} className="text-[12px]">
                {/* 인용 원문(하이라이트) — 검증됨은 초록, 검토필요는 주황 배경 */}
                <span className={`inline ${verified ? "bg-emerald-100 text-emerald-900" : "bg-amber-100 text-amber-900"} rounded px-1 py-0.5 leading-relaxed`}>
                  “{ev.quote}”
                </span>
                {/* 근거 위치·상태 */}
                <div className="text-[10px] text-on-surface-variant mt-1">
                  {ev.chunk_id} · {verified ? "원문 검증됨" : "검토 필요"}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

// CSV 셀 이스케이프: 쉼표·따옴표·줄바꿈이 있으면 큰따옴표로 감싸고 내부 "는 ""로.
// =,+,-,@로 시작하면 엑셀이 수식으로 오인(#NAME? 등)하므로 앞에 작은따옴표를 붙여 텍스트로 강제.
function csvCell(v) {
  let s = v == null ? "" : String(v);
  if (/^[=+\-@]/.test(s)) s = "'" + s;
  return /[",\n]/.test(s) ? `"${s.replace(/"/g, '""')}"` : s;
}

// 체크리스트 전체 항목을 CSV 문자열로 변환한다(항목 1개 = 1행, 실무용 6컬럼).
// evidence가 여러 개면 근거 컬럼을 " | "로 합친다. 화면 표출(30건)과 무관하게 전체를 담는다.
function itemsToCsv(items) {
  const headers = ["번호", "카테고리", "항목", "검증상태", "근거원문", "근거위치"];
  const rows = items.map((it, i) => {
    const evs = it.evidence || [];
    return [
      i + 1,
      it.category || "",
      it.text || "",
      itemVerified(it) ? "원문 검증됨" : "검토 필요",
      evs.map((e) => e.quote).join(" | "),
      evs.map((e) => e.chunk_id).join(" | "),
    ].map(csvCell).join(",");
  });
  return [headers.join(","), ...rows].join("\n");
}

// CSV를 파일로 다운로드한다. 엑셀 한글 깨짐 방지를 위해 UTF-8 BOM을 앞에 붙인다.
function downloadChecklistCsv(items) {
  const csv = "\uFEFF" + itemsToCsv(items);   // \uFEFF = UTF-8 BOM
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "checklist.csv";
  a.click();
  URL.revokeObjectURL(url);
}

function renderChecklist(items) {
  const total = items.length;
  const shown = items.slice(0, CHECKLIST_RENDER_LIMIT);
  return (
    <div>
      {/* 헤더: 건수 안내 + CSV 내보내기(전체 항목) */}
      <div className="flex items-center justify-between mb-3 gap-2">
        <p className="text-[13px] font-semibold text-on-surface">
          추출한 준수 체크리스트 (총 {total}건{total > shown.length ? `, ${shown.length}건 표시` : ""})
        </p>
        <button
          onClick={() => downloadChecklistCsv(items)}
          className="inline-flex items-center gap-1 text-[11px] font-bold text-primary bg-primary/10 hover:bg-primary/20 transition-colors rounded-lg px-2.5 py-1.5 shrink-0"
        >
          <span className="material-symbols-outlined text-[15px]">download</span>
          CSV 내보내기 (전체 {total}건)
        </button>
      </div>
      <div className="space-y-2">
        {shown.map((it, i) => (
          <ChecklistItem key={i} item={it} index={i} />
        ))}
      </div>
    </div>
  );
}

function App() {
  const {
    messages,
    sessions,
    input, setInput,
    loading,
    maxHistory, setMaxHistory,
    retrieverType, setRetrieverType,
    openSources, setOpenSources,
    sendMessage,
    sendQuestion,
    selectDoc,
    startNewChat,
    loadSession,
    handleKeyDown,
  } = useChat();

  // 어떤 답변의 어떤 문서를 펼쳤는지: `${메시지idx}-${문서idx}` 형태로 저장
  const [openDoc, setOpenDoc] = useState(null);

  return (
    <div className="bg-background text-on-surface min-h-screen flex overflow-hidden">

      {/* ── 사이드바 ── */}
      <aside className="bg-surface-container-low w-[280px] h-screen fixed left-0 top-0 border-r border-outline-variant flex flex-col z-50 hidden md:flex">
        <div className="p-6">
          <button
            onClick={startNewChat}
            className="w-full py-3.5 bg-primary text-white rounded-xl font-bold flex items-center justify-center gap-2 shadow-lg shadow-primary/20 hover:scale-[1.02] active:scale-[0.98] transition-all"
          >
            <span className="material-symbols-outlined text-xl">add</span>
            New Chat
          </button>
        </div>

        {/* 대화 이력 제한 슬라이더 (maxHistory) */}
        <div className="px-6 pb-2">
          <p className="text-[11px] font-medium text-on-surface-variant uppercase tracking-widest mb-2">대화 이력 제한</p>
          <div className="flex items-center gap-3">
            <input
              type="range" min="0" max="20" value={maxHistory}
              onChange={(e) => setMaxHistory(Number(e.target.value))}
              className="flex-1"
            />
            <span className="text-xs font-bold text-on-surface min-w-[34px] text-right">{maxHistory}개</span>
          </div>
        </div>

        {/* 검색 방식 토글 (naive/agentic). route_a 검색에만 영향, route_c(체크리스트)는 무관. */}
        <div className="px-6 pb-4">
          <p className="text-[11px] font-medium text-on-surface-variant uppercase tracking-widest mb-2">검색 방식</p>
          <div className="flex gap-1 bg-surface-container rounded-xl p-1">
            <button
              onClick={() => setRetrieverType("naive_rag")}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${retrieverType === "naive_rag" ? "bg-primary text-white shadow-sm" : "text-on-surface-variant hover:text-on-surface"}`}
            >
              naive
            </button>
            <button
              onClick={() => setRetrieverType("agentic_rag")}
              className={`flex-1 py-2 rounded-lg text-xs font-bold transition-all ${retrieverType === "agentic_rag" ? "bg-primary text-white shadow-sm" : "text-on-surface-variant hover:text-on-surface"}`}
            >
              agentic
            </button>
          </div>
          <p className="text-[11px] text-on-surface-variant mt-2 leading-relaxed">
            {retrieverType === "naive_rag" ? "조금 더 빠른 응답 속도" : "조금 더 정확한 답변"}
          </p>
        </div>

        {/* 지난 대화 세션 목록. New Chat/세션 전환 시 쌓인다(localStorage, 최대 20). 클릭 시 복원. */}
        <div className="flex-1 px-4 overflow-y-auto">
          <p className="text-[11px] font-medium text-on-surface-variant uppercase tracking-widest px-2 mb-2">Chat History</p>
          {sessions.length === 0 ? (
            <div className="flex flex-col justify-center items-center text-center opacity-40 mt-10">
              <span className="material-symbols-outlined text-4xl mb-3 text-outline">forum</span>
              <p className="text-[11px] text-outline px-8 leading-relaxed">New Chat을 누르면 지난 대화가 여기에 쌓입니다.</p>
            </div>
          ) : (
            <div className="space-y-1">
              {sessions.map((ssn) => (
                <button
                  key={ssn.id}
                  onClick={() => loadSession(ssn.id)}
                  className="w-full text-left px-3 py-2.5 rounded-xl hover:bg-surface-container transition-colors flex items-center gap-2"
                >
                  <span className="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0">chat_bubble</span>
                  <span className="text-[12px] font-medium text-on-surface truncate">{ssn.title}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="p-6 border-t border-outline-variant/30">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-full bg-surface-container-highest flex items-center justify-center">
              <span className="material-symbols-outlined text-primary">auto_awesome</span>
            </div>
            <div>
              <p className="text-xs font-bold text-on-surface">RFPilot</p>
            </div>
          </div>
        </div>
      </aside>

      {/* ── 메인 ── */}
      <main className="flex-1 flex flex-col h-screen md:ml-[280px] bg-background relative overflow-hidden">

        {/* 헤더 */}
        <header className="pt-12 px-12 pb-6">
          <div className="flex items-end justify-between mb-10">
            <div>
              <h1 className="text-4xl font-black text-on-surface tracking-tight mb-2">RFPilot</h1>
              <p className="text-sm text-on-surface-variant max-w-2xl">RFP 문서에서 핵심 요구조건·대상기관·예산·제출방식을 빠르게 찾아드립니다. 궁금한 내용을 물어보세요.</p>
            </div>
          </div>
          <nav className="flex border-b border-outline-variant/30 gap-10">
            <button className="pb-4 active-tab-indicator text-primary font-bold text-sm flex items-center gap-2">
              <span className="material-symbols-outlined text-sm">chat_bubble</span>
              Chat Terminal
            </button>
          </nav>
        </header>

        {/* 채팅 워크스페이스 */}
        <section className="flex-1 flex flex-col overflow-hidden px-12">

          {/* 입력창 (상단) */}
          <div className="py-6">
            <div className="relative group">
              <div className="relative bg-white border border-outline-variant/50 rounded-[20px] flex items-center px-6 py-4 shadow-soft transition-all focus-within:border-primary focus-within:shadow-xl focus-within:shadow-primary/5">
                <span className="material-symbols-outlined text-on-surface-variant mr-3">search</span>
                <input
                  className="flex-1 bg-transparent border-none focus:ring-0 text-sm py-1 placeholder:text-outline"
                  placeholder="RFP 문서에 대해 무엇이든 물어보세요..."
                  value={input}
                  onChange={(e) => setInput(e.target.value)}
                  onKeyDown={handleKeyDown}
                />
                <button
                  onClick={sendMessage}
                  disabled={loading}
                  className="bg-primary text-white p-2 rounded-lg hover:bg-primary-container transition-all flex items-center justify-center disabled:opacity-40"
                >
                  <span className="material-symbols-outlined">arrow_upward</span>
                </button>
              </div>
            </div>
          </div>

          {/* 대화 내역 */}
          <div className="flex-1 overflow-y-auto chat-container-scroll space-y-8 pb-12 pt-4">
            {/* messages를 turn(질문+답변) 쌍으로 묶어 최신 턴이 위로 오도록 재정렬(쌍 안 순서는 유지).
                응답 대기 중이면 최신 질문 바로 아래에 로딩을 끼워넣는다. */}
            {(() => {
              const ordered = [];
              for (let i = 0; i < messages.length; i += 2) {
                const turn = [i, i + 1].filter((n) => n < messages.length);
                ordered.push(turn);
              }
              ordered.reverse();
              const items = [];
              ordered.forEach((turn, ti) => {
                turn.forEach((idx) => items.push({ msg: messages[idx], idx }));
                if (ti === 0 && loading && turn.length === 1) items.push({ loadingMarker: true });
              });
              return items;
            })().map((item) => {
              if (item.loadingMarker) {
                return (
                  <div key="loading" className="flex gap-5 items-start max-w-4xl">
                    <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shrink-0 shadow-lg shadow-primary/20">
                      <span className="material-symbols-outlined text-white text-xl">smart_toy</span>
                    </div>
                    <div className="bg-white border border-outline-variant/50 rounded-2xl px-5 py-4 shadow-soft text-sm text-on-surface-variant">
                      분석 중...
                    </div>
                  </div>
                );
              }
              const { msg, idx } = item;
              if (msg.role === "user") {
                /* 유저 질문 */
                return (
                  <div key={idx} className="flex gap-5 items-start max-w-4xl">
                    <div className="w-9 h-9 rounded-xl bg-on-surface flex items-center justify-center shrink-0 shadow-sm">
                      <span className="material-symbols-outlined text-white text-xl">person</span>
                    </div>
                    <div className="bg-surface-container-low border border-outline-variant/20 rounded-2xl px-5 py-4 shadow-sm">
                      <p className="text-sm font-medium text-on-surface leading-relaxed whitespace-pre-wrap">{msg.content}</p>
                    </div>
                  </div>
                );
              }
              /* 봇 응답 */
              const docs = groupByDoc(msg.sources);
              return (
                <div key={idx} className="flex gap-5 items-start max-w-4xl">
                  <div className="w-9 h-9 rounded-xl bg-primary flex items-center justify-center shrink-0 shadow-lg shadow-primary/20">
                    <span className="material-symbols-outlined text-white text-xl">smart_toy</span>
                  </div>
                  <div className="flex-1 space-y-4">
                    {/* 메타(응답 시간 · 문서 개수) */}
                    <div className="flex items-center gap-4 py-1">
                      {msg.elapsed != null && (
                        <div className="flex items-center gap-1.5 text-primary">
                          <span className="material-symbols-outlined text-[16px]">speed</span>
                          <span className="text-[11px] font-bold uppercase tracking-wider">응답 시간: {msg.elapsed}초</span>
                        </div>
                      )}
                      {docs.length > 0 && (
                        <>
                          <div className="h-1 w-1 rounded-full bg-outline-variant"></div>
                          <div className="flex items-center gap-1.5 text-on-surface-variant">
                            <span className="material-symbols-outlined text-[16px]">article</span>
                            <span className="text-[11px] font-bold uppercase tracking-wider">문서 {docs.length}건 참고</span>
                          </div>
                        </>
                      )}
                    </div>

                    {/* 응답 카드 */}
                    <div className="bg-white border border-outline-variant/50 rounded-2xl p-6 shadow-soft relative">
                      {/* 라우트 C 체크리스트(구조화 항목)면 카드 렌더, 아니면 기존 텍스트 답변 */}
                      {msg.checklistItems && msg.checklistItems.length > 0 ? (
                        renderChecklist(msg.checklistItems)
                      ) : (
                        <p className="text-[15px] text-on-surface leading-loose whitespace-pre-wrap">{stripSourceTags(msg.content)}</p>
                      )}

                      {/* 라우트 C 1단계: 후보 문서 선택 버튼. 클릭 시 해당 문서로 체크리스트 요청 */}
                      {msg.candidateDocs && msg.candidateDocs.length > 0 && (
                        <div className="mt-5 pt-4 border-t border-outline-variant/20">
                          <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant mb-2">
                            <span className="material-symbols-outlined text-[15px]">checklist</span>
                            <span className="font-semibold">체크리스트를 만들 공고 선택</span>
                          </div>
                          <div className="space-y-2">
                            {msg.candidateDocs.map((c, ci) => (
                              <button
                                key={ci}
                                onClick={() => selectDoc(c.doc_id, c.project_name || c.file_name || c.doc_id, messages[idx - 1]?.content)}
                                disabled={loading}
                                className="w-full text-left px-4 py-2.5 bg-surface-container-low hover:bg-surface-container transition-colors rounded-xl border border-outline-variant/40 flex items-center justify-between gap-2 disabled:opacity-40"
                              >
                                <span className="text-[12px] font-medium text-on-surface truncate">
                                  {c.project_name || c.file_name || c.doc_id}
                                </span>
                                <span className="material-symbols-outlined text-[18px] text-primary shrink-0">arrow_forward</span>
                              </button>
                            ))}
                          </div>
                        </div>
                      )}

                      {/* 참고 문서: 답변과 구분되게 작고 흐린 글씨로 상시 표시. 클릭 시 상세(메타+청크) 펼침 */}
                      {docs.length > 0 && (
                        <div className="mt-5 pt-4 border-t border-outline-variant/20">
                          <div className="flex items-center gap-1.5 text-[11px] text-on-surface-variant mb-2">
                            <span className="material-symbols-outlined text-[15px]">description</span>
                            <span className="font-semibold">참고 문서 {docs.length}건</span>
                          </div>
                          <div className="space-y-2">
                            {docs.map((doc, di) => {
                              const key = `${idx}-${di}`;
                              const isOpen = openDoc === key;
                              return (
                                <div key={di} className="border border-outline-variant/40 rounded-xl overflow-hidden">
                                  {/* 문서 헤더(클릭 시 상세 토글) */}
                                  <button
                                    onClick={() => setOpenDoc(isOpen ? null : key)}
                                    className="w-full text-left px-4 py-2.5 bg-surface-container-low hover:bg-surface-container transition-colors flex items-center justify-between gap-2"
                                  >
                                    <span className="text-[12px] font-medium text-on-surface-variant truncate">
                                      {doc.project_name || doc.file_name || doc.doc_id}
                                    </span>
                                    <span className="material-symbols-outlined text-[18px] text-on-surface-variant shrink-0">
                                      {isOpen ? "expand_less" : "expand_more"}
                                    </span>
                                  </button>

                                  {/* 문서 상세: 메타데이터(1회) + 검색된 청크들(섹션별) */}
                                  {isOpen && (
                                    <div className="px-4 py-3 bg-white text-xs text-on-surface-variant space-y-3">
                                      {/* 메타데이터 */}
                                      <div className="grid grid-cols-1 gap-1">
                                        {doc.agency && <div><span className="font-bold text-on-surface">발주기관</span> · {doc.agency}</div>}
                                        {formatBudget(doc.budget_amount) && <div><span className="font-bold text-on-surface">예산</span> · {formatBudget(doc.budget_amount)}</div>}
                                        {doc.announcement_date && <div><span className="font-bold text-on-surface">공개일</span> · {doc.announcement_date}</div>}
                                        {doc.bid_end && <div><span className="font-bold text-on-surface">입찰 마감</span> · {doc.bid_end}</div>}
                                        <div><span className="font-bold text-on-surface">파일</span> · {doc.file_name}</div>
                                      </div>
                                      {/* 검색된 청크(섹션별) */}
                                      <div className="pt-2 border-t border-outline-variant/20 space-y-3">
                                        {doc.chunks.map((ch, ci) => (
                                          <div key={ci}>
                                            {ch.section && <div className="font-bold text-on-surface mb-1">[{ch.section}]</div>}
                                            <div className="whitespace-pre-wrap leading-relaxed text-on-surface">{ch.content}</div>
                                          </div>
                                        ))}
                                      </div>
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      )}
                    </div>

                    {/* 추천 질문: 출처가 있는 일반 답변(route_a)에만. 체크리스트 응답엔 미표시. */}
                    {docs.length > 0 && !(msg.checklistItems && msg.checklistItems.length > 0) && (
                      <div className="flex flex-wrap gap-2">
                        {buildSuggestions(docs[0]?.project_name).map((q, qi) => (
                          <button
                            key={qi}
                            onClick={() => sendQuestion(q)}
                            disabled={loading}
                            className="text-[12px] font-medium text-on-surface-variant bg-surface-container-low hover:bg-surface-container border border-outline-variant/40 rounded-full px-3 py-1.5 transition-colors disabled:opacity-40"
                          >
                            {q}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      </main>
    </div>
  );
}

export default App;