import { useState, useRef, useEffect } from "react";

// .env의 REACT_APP_API_URL을 읽음. 없으면 로컬 백엔드로 fallback (하드코딩 방지)
const API_URL = process.env.REACT_APP_API_URL || "http://localhost:8000";

// 세션 히스토리 최대 보관 개수. 넘으면 가장 오래된 것부터 버린다.
const MAX_SESSIONS = 20;

// 현재 대화(messages)를 세션 목록에 반영해 반환한다(생성시각 기준 최신순, 상한 적용).
// - activeId가 있으면(로드했던 세션) 그 세션을 '제자리에서 내용만 갱신'해 위치를 고정한다.
// - 없으면(새 대화) createdAt를 새로 부여해 새 세션으로 추가한다.
// 대화가 비어있으면 저장하지 않고 그대로 반환. 제목은 첫 사용자 질문(없으면 "새 대화").
function saveCurrent(sessions, messages, activeId) {
  if (!messages || messages.length === 0) return sessions;
  const firstUser = messages.find((m) => m.role === "user");
  const title = firstUser ? firstUser.content.slice(0, 40) : "새 대화";

  let next;
  const existing = activeId != null && sessions.some((s) => s.id === activeId);
  if (existing) {
    // 로드했던 세션: createdAt(정렬 기준) 유지한 채 내용만 갱신 → 위치 고정
    next = sessions.map((s) => (s.id === activeId ? { ...s, title, messages } : s));
  } else {
    // 새 대화: 고정 createdAt를 부여해 새 세션 생성
    const now = Date.now();
    next = [{ id: now.toString(), createdAt: now, title, messages }, ...sessions];
  }
  // 생성시각 기준 최신순 정렬(클릭해도 위치 불변) + 상한
  return next.sort((a, b) => b.createdAt - a.createdAt).slice(0, MAX_SESSIONS);
}

// 채팅 기능(상태 + 로직)을 모아둔 커스텀 훅
// 화면(App.js)은 이 훅에서 값/함수를 받아다 쓰기만 하면 됨
// → 화면 디자인을 바꿔도 이 훅은 그대로 재사용 가능
export function useChat() {
  // messages 초기값: localStorage에 저장된 대화가 있으면 복원, 없으면 빈 배열
  // (새로고침해도 대화가 유지되도록 함)
  const [messages, setMessages] = useState(() => {
    const saved = localStorage.getItem("chat_messages");
    return saved ? JSON.parse(saved) : [];
  });

  // 지난 대화 세션 목록. New Chat/세션 전환 시 현재 대화가 여기 쌓인다(localStorage 보관).
  const [sessions, setSessions] = useState(() => {
    const saved = localStorage.getItem("chat_sessions");
    if (!saved) return [];
    // 이전 형식(createdAt 없음) 호환: 과거 id(Date.now 문자열)를 createdAt로 사용
    return JSON.parse(saved).map((s) => ({ ...s, createdAt: s.createdAt ?? Number(s.id) }));
  });

  // messages가 바뀔 때마다 localStorage에 저장 (새로고침 대비)
  useEffect(() => {
    localStorage.setItem("chat_messages", JSON.stringify(messages));
  }, [messages]);

  // sessions가 바뀔 때마다 localStorage에 저장 (탭/브라우저 닫아도 유지)
  useEffect(() => {
    localStorage.setItem("chat_sessions", JSON.stringify(sessions));
  }, [sessions]);

  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [maxHistory, setMaxHistory] = useState(10);
  // 검색 방식 토글(naive_rag: 빠름 / agentic_rag: 정확). 기본 agentic. /chat 요청에 실려 config.yaml보다 우선.
  const [retrieverType, setRetrieverType] = useState("agentic_rag");
  // 어느 메시지의 출처가 펼쳐져 있는지 (메시지 index를 담음)
  const [openSources, setOpenSources] = useState(null);

  // 세션 ID - 탭이 열려있는 동안 유지, New Chat 시 새로 발급
  const sessionId = useRef(`session_${Date.now()}`);
  // 현재 화면이 어떤 저장 세션에서 로드된 것인지(제자리 갱신용). 새 대화면 null.
  const activeSessionId = useRef(null);

  // 백엔드 /chat 호출 공통 처리 — 일반 질문(sendMessage)과 문서선택(selectDoc)이 함께 씀
  // userBubble: 화면에 먼저 띄울 사용자 메시지 / query: 백엔드로 보낼 질문
  // selectedDocId: 라우트 C 2단계에서 고른 문서 ID(일반 질문은 null)
  const submitToBackend = async (userBubble, query, selectedDocId) => {
    // 이전 대화이력을 백엔드 형식 [{role, content}]으로 변환(이번 질문 추가 전 상태 기준)
    // bot → assistant로 변환. 방금 띄운 userBubble은 query로 따로 가므로 history에서 제외됨.
    const history = messages.map((m) => ({
      role: m.role === "bot" ? "assistant" : "user",
      content: m.content,
    }));

    setMessages((prev) => [...prev, userBubble]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        // query + history + max_history + selected_doc_id(라우트 C 2단계) 전송
        body: JSON.stringify({
          query: query,
          history: history,
          max_history: maxHistory,
          selected_doc_id: selectedDocId,
          retriever_type: retrieverType,
        }),
      });

      const data = await res.json();

      // 봇 메시지로 추가 (answer 본문 + sources/chunks + candidateDocs를 함께 저장)
      // candidateDocs: 라우트 C 1단계 후보 문서(있으면 App.js가 선택 버튼으로 렌더)
      setMessages((prev) => [
        ...prev,
        {
          role: "bot",
          content: data.answer,
          elapsed: data.elapsed_sec,
          sources: data.sources,
          chunks: data.retrieved_chunks,
          candidateDocs: data.candidate_docs,
          checklistItems: data.checklist_items,   // 라우트 C 구조화 항목(카드 렌더·배지·CSV용)
        },
      ]);
    } catch (e) {
      console.error("에러 내용:", e);
      setMessages((prev) => [...prev, { role: "bot", content: "서버 연결 실패" }]);
    } finally {
      setLoading(false);
    }
  };

  // AI 응답 생성 함수 - 입력창의 질문을 보냄(일반 질문, 문서선택 아님 → selected_doc_id=null)
  const sendMessage = () => {
    if (!input.trim()) return;
    const q = input;
    setInput("");
    submitToBackend({ role: "user", content: q }, q, null);
  };

  // 추천 질문 버튼 클릭 등 — 입력창을 거치지 않고 질문 문자열을 바로 전송(일반 질문 경로).
  const sendQuestion = (text) => {
    if (!text || !text.trim()) return;
    submitToBackend({ role: "user", content: text }, text, null);
  };

  // 라우트 C 2단계 - 후보 문서 클릭 시 호출. 고른 문서로 체크리스트를 요청한다.
  // docLabel: 화면 표시용 문서명 / originalQuery: 후보를 유발한 원 질문(재전송)
  const selectDoc = (docId, docLabel, originalQuery) => {
    submitToBackend(
      { role: "user", content: `📄 ${docLabel} 선택` },
      originalQuery || docLabel,
      docId,
    );
  };

  // New Chat: 현재 대화를 세션으로 보관(비어있으면 무시) 후 화면 초기화 + 새 세션 ID 발급
  const startNewChat = () => {
    setSessions((prev) => saveCurrent(prev, messages, activeSessionId.current));
    setMessages([]);   // messages useEffect가 localStorage도 비움
    activeSessionId.current = null;   // 새 대화 시작이므로 활성 세션 없음
    sessionId.current = `session_${Date.now()}`;
  };

  // 사이드바 세션 클릭 → 그 대화를 화면에 복원. 진행 중이던 현재 대화는 먼저 세션으로 보관.
  const loadSession = (id) => {
    const saved = saveCurrent(sessions, messages, activeSessionId.current);  // 현재 대화 제자리 보관
    const target = saved.find((s) => s.id === id);
    if (!target) return;
    setSessions(saved);                       // 목록 순서 유지(대상 제거하지 않음)
    setMessages(target.messages);             // 화면을 그 대화로 복원
    activeSessionId.current = id;             // 이후 이 세션을 제자리 갱신하도록 기억
    sessionId.current = `session_${Date.now()}`;
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter") sendMessage();
  };

  // 화면(App.js)에서 쓸 값과 함수를 한 묶음으로 반환
  return {
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
  };
}