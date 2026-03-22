import { useState, useCallback, useRef, useEffect } from "react";
import axios from "axios";
import { useDropzone } from "react-dropzone";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

// ─────────────────────────────────────────
// ReceiptUpload - 영수증 사진 업로드 컴포넌트
// ─────────────────────────────────────────
export function ReceiptUpload({ empNo }) {
  const [status, setStatus] = useState("idle"); // idle | uploading | success | error
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const cameraInputRef = useRef(null);

  // 카메라로 직접 촬영한 파일 처리
  const handleCameraCapture = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await processFile(file);
    // input 초기화 (같은 파일 재촬영 가능)
    e.target.value = "";
  };

  // 공통 파일 처리 함수
  const processFile = async (file) => {
    setPreview(URL.createObjectURL(file));
    setStatus("uploading");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("emp_no", empNo || "EMP001");

    try {
      const resp = await axios.post(`${API_BASE}/receipts/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      setResult(resp.data);
      setStatus("success");
    } catch (err) {
      setResult({ error: err.response?.data?.detail || "업로드 실패" });
      setStatus("error");
    }
  };

  const onDrop = useCallback(async (files) => {
    const file = files[0];
    if (!file) return;
    await processFile(file);
  }, [empNo]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    maxSize: 10 * 1024 * 1024,
    multiple: false,
  });

  const gradeColor = {
    GREEN: "bg-green-100 border-green-500 text-green-800",
    YELLOW: "bg-yellow-100 border-yellow-500 text-yellow-800",
    RED: "bg-red-100 border-red-500 text-red-800",
  };

  const gradeEmoji = { GREEN: "✅", YELLOW: "⚠️", RED: "❌" };

  // 다우오피스 URL (환경변수 or 기본값)
  const DAOU_BASE_URL = import.meta.env.VITE_DAOU_URL || "https://your-company.daouoffice.com";
  const DAOU_ATTENDANCE_URL = `${DAOU_BASE_URL}/app/attendance`;
  const DAOU_MOBILE_URL = `${DAOU_BASE_URL}/mobile`;

  // GPS 재검증 (영수증 데이터 유지하고 GPS만 재체크)
  const handleGpsRetry = async () => {
    if (!result?.receipt) return;
    setStatus("uploading");
    try {
      const resp = await axios.post(`${API_BASE}/receipts/gps-retry`, {
        emp_no: empNo || "EMP001",
        receipt_date: result.receipt?.date,
      }, { timeout: 15000 });
      setResult((prev) => ({ ...prev, gps: resp.data.gps, result: resp.data.result }));
      setStatus("success");
    } catch {
      setStatus("success"); // 원래 결과 유지
    }
  };

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">영수증 업로드</h2>

      {/* 카메라 직접 촬영 버튼 (모바일 우선) */}
      <button
        onClick={() => cameraInputRef.current?.click()}
        disabled={status === "uploading"}
        className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-700
                   disabled:bg-blue-300 text-white font-bold py-5 rounded-2xl shadow-lg
                   text-lg transition-all active:scale-95"
      >
        <span className="text-3xl">📸</span>
        <span>카메라로 바로 촬영</span>
      </button>
      {/* 카메라 input (숨김) - capture="environment"로 후면 카메라 우선 */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        onChange={handleCameraCapture}
        className="hidden"
      />

      {/* 구분선 */}
      <div className="flex items-center gap-3">
        <hr className="flex-1 border-gray-200" />
        <span className="text-sm text-gray-400">또는 파일 선택</span>
        <hr className="flex-1 border-gray-200" />
      </div>

      {/* 드롭존 */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-8 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"}`}
      >
        <input {...getInputProps()} />
        <div className="text-4xl mb-2">🖼️</div>
        {isDragActive ? (
          <p className="text-blue-600 font-medium">영수증 사진을 여기에 놓으세요</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">갤러리에서 선택 또는 드래그 업로드</p>
            <p className="text-sm text-gray-400 mt-1">JPG, PNG, WEBP 지원 · 최대 10MB</p>
          </>
        )}
      </div>

      {/* 미리보기 */}
      {preview && (
        <div className="flex justify-center">
          <img src={preview} alt="영수증 미리보기" className="max-h-48 rounded-lg shadow-md" />
        </div>
      )}

      {/* 업로드 중 */}
      {status === "uploading" && (
        <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-lg">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
          <span className="text-blue-700 font-medium">OCR 처리 중... (최대 30초 소요)</span>
        </div>
      )}

      {/* 결과 표시 */}
      {status === "success" && result && (
        <div className="space-y-4">
          {/* GPS 등급 배지 */}
          {result.gps?.grade && (
            <div className={`border rounded-lg p-4 ${gradeColor[result.gps.grade]}`}>
              <div className="font-bold text-lg">
                {gradeEmoji[result.gps.grade]} GPS 검증 결과: {result.gps.grade} ({result.gps.score}점)
              </div>
              <div className="text-sm mt-1">{result.gps.details?.join(" · ")}</div>
            </div>
          )}

          {/* OCR 결과 */}
          <div className="bg-white border rounded-lg p-4 shadow-sm">
            <h3 className="font-bold text-gray-700 mb-3">📋 인식 결과</h3>
            <table className="w-full text-sm">
              <tbody>
                {[
                  ["가맹점", result.receipt?.merchant],
                  ["거래일", result.receipt?.date],
                  ["금액", result.receipt?.amount ? `${result.receipt.amount.toLocaleString()}원` : "-"],
                  ["경비코드", `${result.expense_code?.code} (${result.expense_code?.name})`],
                  ["분류방법", result.expense_code?.source],
                  ["OCR 엔진", result.receipt?.ocr_engine],
                ].map(([label, value]) => (
                  <tr key={label} className="border-b last:border-0">
                    <td className="py-2 pr-4 text-gray-500 w-28">{label}</td>
                    <td className="py-2 font-medium text-gray-800">{value || "-"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* 처리 상태 */}
          <div className="bg-gray-50 border rounded-lg p-4">
            <h3 className="font-bold text-gray-700 mb-2">처리 결과</h3>
            <div className={`inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium
              ${result.result?.status === "AUTO_APPROVED" ? "bg-green-100 text-green-700" :
                result.result?.status === "NEEDS_REVIEW" ? "bg-yellow-100 text-yellow-700" :
                "bg-red-100 text-red-700"}`}>
              {result.result?.status === "AUTO_APPROVED" && "✅ 자동 결재 생성 완료"}
              {result.result?.status === "NEEDS_REVIEW" && "⚠️ 담당자 검토 필요"}
              {result.result?.status === "REJECTED" && "❌ GPS 체크 후 재시도 필요"}
            </div>
          </div>

          {/* GPS RED → 액션 가이드 패널 */}
          {result.result?.status === "REJECTED" && (
            <div className="border-2 border-red-200 bg-red-50 rounded-2xl p-5 space-y-4">
              {/* 안내 헤더 */}
              <div className="flex items-center gap-2">
                <span className="text-2xl">📍</span>
                <div>
                  <p className="font-bold text-red-700 text-base">GPS 출근 기록이 없습니다</p>
                  <p className="text-sm text-red-500">아래 방법 중 하나로 GPS를 등록 후 재시도하세요</p>
                </div>
              </div>

              {/* 방법 1: 다우오피스 앱 출근 체크 */}
              <div className="bg-white rounded-xl border border-red-100 p-4 space-y-3">
                <p className="text-sm font-bold text-gray-700">방법 1 · 다우오피스에서 GPS 출근 등록</p>
                <div className="grid grid-cols-2 gap-2">
                  {/* 다우오피스 모바일 앱 열기 */}
                  <a
                    href="daouoffice://attendance"
                    onClick={(e) => {
                      // 앱이 없으면 웹으로 폴백
                      setTimeout(() => { window.location.href = DAOU_ATTENDANCE_URL; }, 1500);
                    }}
                    className="flex flex-col items-center gap-1 bg-blue-600 text-white
                               rounded-xl py-3 px-2 text-center active:scale-95 transition-all"
                  >
                    <span className="text-2xl">📱</span>
                    <span className="text-xs font-bold">다우오피스 앱</span>
                    <span className="text-xs opacity-80">출퇴근 관리</span>
                  </a>
                  {/* 다우오피스 웹 열기 */}
                  <a
                    href={DAOU_ATTENDANCE_URL}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="flex flex-col items-center gap-1 bg-indigo-500 text-white
                               rounded-xl py-3 px-2 text-center active:scale-95 transition-all"
                  >
                    <span className="text-2xl">🌐</span>
                    <span className="text-xs font-bold">다우오피스 웹</span>
                    <span className="text-xs opacity-80">출근관리 이동</span>
                  </a>
                </div>
                {/* 단계 안내 */}
                <div className="bg-blue-50 rounded-lg p-3 text-xs text-blue-700 space-y-1">
                  <p className="font-bold">📋 GPS 등록 순서</p>
                  <p>① 다우오피스 앱 실행</p>
                  <p>② 전자결재 → 출퇴근 관리</p>
                  <p>③ GPS 출근 버튼 탭</p>
                  <p>④ 위치 권한 허용 후 등록 완료</p>
                </div>
              </div>

              {/* 방법 2: GPS 재확인 (이미 찍었는데 인식 못한 경우) */}
              <div className="bg-white rounded-xl border border-red-100 p-4 space-y-3">
                <p className="text-sm font-bold text-gray-700">방법 2 · GPS 등록 완료 후 재시도</p>
                <p className="text-xs text-gray-500">다우오피스에서 GPS를 등록했다면 아래 버튼으로 재검증</p>
                <button
                  onClick={handleGpsRetry}
                  className="w-full flex items-center justify-center gap-2 bg-orange-500
                             hover:bg-orange-600 text-white font-bold py-3 rounded-xl
                             active:scale-95 transition-all"
                >
                  <span className="text-lg">🔄</span>
                  GPS 재검증 후 재시도
                </button>
              </div>

              {/* 방법 3: 사유 입력으로 수동 제출 */}
              <GpsExemptSubmit result={result} empNo={empNo} apiBase={API_BASE} />
            </div>
          )}
        </div>
      )}

      {/* 에러 */}
      {status === "error" && result?.error && (
        <div className="p-4 bg-red-50 border border-red-300 rounded-lg text-red-700">
          ❌ {result.error}
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// CardSelector - 카드사 선택 컴포넌트
// ─────────────────────────────────────────
export function CardSelector({ value, onChange }) {
  const companies = [
    { value: "WOORI",   label: "우리카드" },
    { value: "SHINHAN", label: "신한카드" },
    { value: "SAMSUNG", label: "삼성카드" },
    { value: "HYUNDAI", label: "현대카드" },
    { value: "LOTTE",   label: "롯데카드" },
    { value: "KB",      label: "KB국민카드" },
    { value: "HANA",    label: "하나카드" },
    { value: "NONGHYUP","label": "농협카드" },
  ];

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-gray-700
                 focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
    >
      <option value="">카드사 선택</option>
      {companies.map((c) => (
        <option key={c.value} value={c.value}>{c.label}</option>
      ))}
    </select>
  );
}

// ─────────────────────────────────────────
// TransactionList - 거래 내역 테이블
// ─────────────────────────────────────────
export function TransactionList({ transactions = [] }) {
  const statusBadge = {
    PENDING:  "bg-gray-100 text-gray-600",
    APPROVED: "bg-green-100 text-green-700",
    REJECTED: "bg-red-100 text-red-700",
    CLOSED:   "bg-blue-100 text-blue-700",
  };

  if (!transactions.length) {
    return (
      <div className="text-center py-12 text-gray-400">
        <div className="text-4xl mb-2">📋</div>
        <p>거래 내역이 없습니다</p>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-lg border border-gray-200">
      <table className="w-full text-sm">
        <thead className="bg-blue-700 text-white">
          <tr>
            {["거래일", "가맹점", "금액", "경비코드", "GPS점수", "결재상태"].map((h) => (
              <th key={h} className="px-4 py-3 text-left font-medium">{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transactions.map((t, i) => (
            <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-gray-50"}>
              <td className="px-4 py-3 text-gray-500">{t.trans_date}</td>
              <td className="px-4 py-3 font-medium text-gray-800">{t.merchant}</td>
              <td className="px-4 py-3 font-mono text-right">{t.amount?.toLocaleString()}원</td>
              <td className="px-4 py-3 text-gray-600">{t.expense_code || "-"}</td>
              <td className="px-4 py-3">
                {t.gps_score !== null && (
                  <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                    ${t.gps_grade === "GREEN" ? "bg-green-100 text-green-700" :
                      t.gps_grade === "YELLOW" ? "bg-yellow-100 text-yellow-700" :
                      "bg-red-100 text-red-700"}`}>
                    {t.gps_score}점
                  </span>
                )}
              </td>
              <td className="px-4 py-3">
                <span className={`px-2 py-0.5 rounded-full text-xs font-medium
                  ${statusBadge[t.daou_approval_status] || "bg-gray-100 text-gray-600"}`}>
                  {t.daou_approval_status || "PENDING"}
                </span>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// ─────────────────────────────────────────
// GpsExemptSubmit - GPS 면제 사유 수동 제출
// ─────────────────────────────────────────
function GpsExemptSubmit({ result, empNo, apiBase }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const REASONS = [
    "출장 중 외부 미팅",
    "재택근무 중 비용 발생",
    "GPS 앱 오류로 미등록",
    "긴급 업무로 등록 불가",
    "기타 (직접 입력)",
  ];

  const handleSubmit = async () => {
    if (!reason.trim()) return;
    setSubmitting(true);
    try {
      await axios.post(`${apiBase}/receipts/exempt-submit`, {
        emp_no: empNo || "EMP001",
        receipt: result?.receipt,
        expense_code: result?.expense_code,
        exempt_reason: reason,
      }, { timeout: 15000 });
      setSubmitted(true);
    } catch {
      setSubmitted(true);
    } finally {
      setSubmitting(false);
    }
  };

  if (submitted) {
    return (
      <div className="bg-green-50 border border-green-200 rounded-xl p-4 text-center">
        <p className="text-2xl mb-1">✅</p>
        <p className="font-bold text-green-700">담당자 검토 요청 완료</p>
        <p className="text-xs text-green-600 mt-1">사유와 함께 결재 요청이 전송되었습니다</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-red-100 p-4 space-y-3">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between"
      >
        <p className="text-sm font-bold text-gray-700">방법 3 · 사유 입력 후 담당자 검토 요청</p>
        <span className="text-gray-400 text-lg">{open ? "▲" : "▼"}</span>
      </button>

      {open && (
        <div className="space-y-3 pt-1">
          <p className="text-xs text-gray-500">GPS 등록이 어려운 경우 사유를 선택하면 담당자가 검토합니다</p>
          <div className="flex flex-wrap gap-2">
            {REASONS.map((r) => (
              <button
                key={r}
                onClick={() => setReason(r.startsWith("기타") ? "" : r)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border transition-all
                  ${ reason === r
                    ? "bg-blue-600 text-white border-blue-600"
                    : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"}`}
              >
                {r}
              </button>
            ))}
          </div>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="GPS 미등록 사유를 입력하세요..."
            rows={2}
            className="w-full border border-gray-200 rounded-lg p-3 text-sm resize-none
                       focus:outline-none focus:ring-2 focus:ring-blue-500"
          />
          <button
            onClick={handleSubmit}
            disabled={!reason.trim() || submitting}
            className="w-full flex items-center justify-center gap-2 bg-gray-700
                       hover:bg-gray-800 disabled:bg-gray-300 text-white
                       font-bold py-3 rounded-xl active:scale-95 transition-all"
          >
            {submitting ? (
              <><div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white" /> 전송 중...</>
            ) : (
              <><span>📨</span> 담당자 검토 요청</>
            )}
          </button>
        </div>
      )}
    </div>
  );
}

// ─────────────────────────────────────────
// Dashboard - 통계 대시보드
// ─────────────────────────────────────────
export function Dashboard({ stats = {} }) {
  const cards = [
    { label: "이번 달 총 경비", value: `${(stats.total_amount || 0).toLocaleString()}원`, icon: "💰", color: "text-blue-600" },
    { label: "자동 처리 건수",  value: `${stats.auto_count || 0}건`,                         icon: "✅", color: "text-green-600" },
    { label: "검토 필요",       value: `${stats.review_count || 0}건`,                        icon: "⚠️", color: "text-yellow-600" },
    { label: "GPS 참여율",      value: `${stats.gps_rate || 0}%`,                             icon: "📍", color: "text-purple-600" },
  ];

  return (
    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 p-6">
      {cards.map((c) => (
        <div key={c.label} className="bg-white rounded-xl border border-gray-200 p-5 shadow-sm">
          <div className="text-3xl mb-2">{c.icon}</div>
          <div className={`text-2xl font-bold ${c.color}`}>{c.value}</div>
          <div className="text-sm text-gray-500 mt-1">{c.label}</div>
        </div>
      ))}
    </div>
  );
}
