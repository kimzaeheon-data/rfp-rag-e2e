import { useState } from "react";
import { useChat } from "./useChat";

// 새 디자인(Tailwind) 적용 화면. 기능(상태·API·localStorage)은 useChat 훅에서 그대로 가져와 연결한다.
// 색·폰트·Tailwind는 public/index.html에서 주입한다(디자인 값 변경은 그쪽에서).

// 답변 본문에 섞여 나오는 [출처: ...] 표기 제거(출처는 아래 참고 문서에서 별도 표시하므로 중복)
function stripSourceTags(text) {
  if (!text) return text;
  return text.replace(/\[출처:[^\]]*\]/g, "").replace(/\n{3,}/g, "\n\n").trim();
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
                      <p className="text-[15px] text-on-surface leading-loose whitespace-pre-wrap">{stripSourceTags(msg.content)}</p>

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