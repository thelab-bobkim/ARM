import { useState, useCallback } from "react";
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

  const onDrop = useCallback(async (files) => {
    const file = files[0];
    if (!file) return;
    setPreview(URL.createObjectURL(file));
    setStatus("uploading");

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

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-6">
      <h2 className="text-2xl font-bold text-gray-800">영수증 업로드</h2>

      {/* 드롭존 */}
      <div
        {...getRootProps()}
        className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors
          ${isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"}`}
      >
        <input {...getInputProps()} />
        <div className="text-5xl mb-3">📷</div>
        {isDragActive ? (
          <p className="text-blue-600 font-medium">영수증 사진을 여기에 놓으세요</p>
        ) : (
          <>
            <p className="text-gray-600 font-medium">영수증 사진을 드래그하거나 클릭하여 업로드</p>
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
