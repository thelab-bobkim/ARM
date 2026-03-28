import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import axios from "axios";
import { useDropzone } from "react-dropzone";

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const DAOU_BASE_URL = import.meta.env.VITE_DAOU_URL || "https://api.daouoffice.com";
const DAOU_ATTENDANCE_URL = `${DAOU_BASE_URL}/app/attendance`;

function isMobileDevice() {
  return /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
}

function useCurrentLocation() {
  const [location, setLocation] = useState(null);
  const [locStatus, setLocStatus] = useState("idle");

  const request = () => {
    if (!navigator.geolocation) {
      setLocStatus("denied");
      return;
    }
    setLocStatus("requesting");
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setLocation({
          lat: pos.coords.latitude,
          lng: pos.coords.longitude,
          accuracy: Math.round(pos.coords.accuracy),
        });
        setLocStatus("granted");
      },
      () => setLocStatus("denied"),
      { enableHighAccuracy: true, timeout: 8000, maximumAge: 60000 }
    );
  };

  useEffect(() => {
    request();
  }, []);

  return { location, locStatus, requestLocation: request };
}

export function ReceiptUpload({ profile, onProfileRefresh }) {
  const [status, setStatus] = useState("idle");
  const [result, setResult] = useState(null);
  const [preview, setPreview] = useState(null);
  const cameraInputRef = useRef(null);
  const { location, locStatus, requestLocation } = useCurrentLocation();

  const gpsBadge = {
    idle: { text: "위치 준비 중", color: "bg-gray-100 text-gray-500", icon: "📍" },
    requesting: { text: "위치 수집 중...", color: "bg-blue-100 text-blue-600", icon: "🔄" },
    granted: { text: `GPS 준비 완료 (±${location?.accuracy ?? "?"}m)`, color: "bg-green-100 text-green-700", icon: "✅" },
    denied: { text: "위치 권한 없음", color: "bg-yellow-100 text-yellow-700", icon: "⚠️" },
  }[locStatus] || { text: "", color: "", icon: "" };

  const processFile = async (file) => {
    if (!profile?.empNo) {
      setStatus("error");
      setResult({ error: "먼저 설정 탭에서 사용자 프로필을 저장해주세요." });
      return;
    }

    setPreview(URL.createObjectURL(file));
    setStatus("uploading");
    setResult(null);

    const formData = new FormData();
    formData.append("file", file);
    formData.append("emp_no", profile.empNo);
    formData.append("employee_name", profile.employeeName || "");
    formData.append("department", profile.department || "");
    formData.append("project_code", profile.projectCode || "");
    if (location?.lat && location?.lng) {
      formData.append("capture_lat", String(location.lat));
      formData.append("capture_lng", String(location.lng));
    }

    try {
      const resp = await axios.post(`${API_BASE}/receipts/upload`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
        timeout: 60000,
      });
      setResult(resp.data);
      setStatus("success");
      onProfileRefresh?.();
    } catch (err) {
      setResult({ error: err.response?.data?.detail || "업로드 실패" });
      setStatus("error");
    }
  };

  const onDrop = useCallback(async (files) => {
    const file = files?.[0];
    if (!file) return;
    await processFile(file);
  }, [profile, location]);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { "image/*": [".jpg", ".jpeg", ".png", ".webp"] },
    maxSize: 10 * 1024 * 1024,
    multiple: false,
  });

  const handleCameraCapture = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    await processFile(file);
    e.target.value = "";
  };

  const handleGpsRetry = async () => {
    if (!result?.receipt?.date || !profile?.empNo) return;
    try {
      const resp = await axios.post(`${API_BASE}/receipts/gps-retry`, {
        emp_no: profile.empNo,
        receipt_date: result.receipt.date,
      });
      setResult((prev) => ({ ...prev, gps: resp.data.gps, result: resp.data.result }));
    } catch {}
  };

  const statusLabel = {
    AUTO_APPROVED: "✅ 자동 처리 완료",
    NEEDS_REVIEW: "⚠️ 담당자 검토 필요",
    REJECTED: "❌ GPS 확인 필요",
    RETRY_READY: "🔄 재검증 준비 완료",
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-gray-800">영수증 업로드</h2>
            <p className="text-sm text-gray-500 mt-1">촬영 위치 GPS와 OCR 인식 결과를 함께 저장합니다.</p>
          </div>
          <div className="text-sm text-gray-500">
            {profile?.employeeName || "이름 미설정"} · {profile?.department || "부서 미설정"} · {profile?.projectCode || "프로젝트 미설정"}
          </div>
        </div>

        {!profile?.empNo && (
          <div className="rounded-xl bg-amber-50 border border-amber-200 px-4 py-3 text-sm text-amber-700">
            설정 탭에서 다우오피스 ID/사번을 저장한 뒤 사용해주세요.
          </div>
        )}

        <div className={`flex items-center justify-between px-4 py-2.5 rounded-xl text-sm font-medium ${gpsBadge.color}`}>
          <span>{gpsBadge.icon} {gpsBadge.text}</span>
          <button onClick={requestLocation} className="text-xs underline font-bold">위치 새로고침</button>
        </div>

        <button
          onClick={() => {
            if (locStatus === "idle" || locStatus === "denied") requestLocation();
            cameraInputRef.current?.click();
          }}
          disabled={status === "uploading"}
          className="w-full flex items-center justify-center gap-3 bg-blue-600 hover:bg-blue-700 disabled:bg-blue-300 text-white font-bold py-5 rounded-2xl shadow-lg text-lg"
        >
          <span className="text-3xl">📸</span>
          <div className="text-left">
            <div>카메라로 바로 촬영</div>
            <div className="text-xs font-normal opacity-80">
              {locStatus === "granted" ? `GPS 자동 첨부 (±${location?.accuracy}m)` : "권한 허용 후 GPS 자동 첨부"}
            </div>
          </div>
        </button>

        <input
          ref={cameraInputRef}
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleCameraCapture}
          className="hidden"
        />

        <div className="flex items-center gap-3">
          <hr className="flex-1 border-gray-200" />
          <span className="text-sm text-gray-400">또는 파일 선택</span>
          <hr className="flex-1 border-gray-200" />
        </div>

        <div
          {...getRootProps()}
          className={`border-2 border-dashed rounded-2xl p-8 text-center cursor-pointer transition-colors ${
            isDragActive ? "border-blue-500 bg-blue-50" : "border-gray-300 hover:border-blue-400 hover:bg-gray-50"
          }`}
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

        {preview && (
          <div className="flex justify-center">
            <img src={preview} alt="영수증 미리보기" className="max-h-56 rounded-xl shadow-md" />
          </div>
        )}

        {status === "uploading" && (
          <div className="flex items-center gap-3 p-4 bg-blue-50 rounded-xl">
            <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600" />
            <span className="text-blue-700 font-medium">OCR 및 GPS 검증 처리 중입니다...</span>
          </div>
        )}

        {status === "success" && result && (
          <div className="space-y-4">
            {result.gps?.grade && (
              <div className={`border rounded-xl p-4 ${
                result.gps.grade === "GREEN"
                  ? "bg-green-50 border-green-200 text-green-800"
                  : result.gps.grade === "YELLOW"
                    ? "bg-yellow-50 border-yellow-200 text-yellow-800"
                    : "bg-red-50 border-red-200 text-red-800"
              }`}>
                <div className="font-bold text-lg">GPS 검증 결과: {result.gps.grade} ({result.gps.score}점)</div>
                <div className="text-sm mt-1">{(result.gps.details || []).join(" · ")}</div>
                <div className="text-xs mt-2 opacity-80">
                  검증 방식: {result.gps.mode === "REALTIME" ? "실시간 촬영 위치" : "다우 출근 GPS"}
                </div>
              </div>
            )}

            <div className="bg-white border rounded-xl p-4 shadow-sm">
              <h3 className="font-bold text-gray-700 mb-3">인식 결과</h3>
              <table className="w-full text-sm">
                <tbody>
                  {[
                    ["가맹점", result.receipt?.merchant],
                    ["거래일", result.receipt?.date],
                    ["금액", result.receipt?.amount ? `${result.receipt.amount.toLocaleString()}원` : "-"],
                    ["부가세", result.receipt?.vat ? `${result.receipt.vat.toLocaleString()}원` : "0원"],
                    ["경비코드", `${result.expense_code?.code || "-"} (${result.expense_code?.name || "-"})`],
                    ["분류방법", result.expense_code?.source || "-"],
                    ["OCR 엔진", result.receipt?.ocr_engine || "-"],
                  ].map(([label, value]) => (
                    <tr key={label} className="border-b last:border-0">
                      <td className="py-2 pr-4 text-gray-500 w-28">{label}</td>
                      <td className="py-2 font-medium text-gray-800">{value || "-"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="bg-gray-50 border rounded-xl p-4 space-y-2">
              <div className="font-bold text-gray-700">처리 결과</div>
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm font-medium bg-white border">
                {statusLabel[result.result?.status] || result.result?.status || "상태 없음"}
              </div>
              {result.receipt_image_url && (
                <div className="text-sm text-gray-600">
                  <a href={result.receipt_image_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline">
                    저장된 영수증 원본 열기
                  </a>
                </div>
              )}
            </div>

            {result.result?.status === "REJECTED" && (
              <div className="border-2 border-red-200 bg-red-50 rounded-2xl p-5 space-y-4">
                <div>
                  <p className="font-bold text-red-700">GPS 출근 기록이 필요합니다.</p>
                  <p className="text-sm text-red-500 mt-1">다우오피스에서 GPS 출근을 찍은 뒤 재검증하세요.</p>
                </div>
                <div className="grid md:grid-cols-2 gap-3">
                  <a
                    href={isMobileDevice() ? "daouoffice://attendance" : DAOU_ATTENDANCE_URL}
                    target="_blank"
                    rel="noreferrer"
                    className="bg-blue-600 text-white rounded-xl px-4 py-3 text-center font-medium"
                  >
                    다우오피스 열기
                  </a>
                  <button
                    onClick={handleGpsRetry}
                    className="bg-orange-500 hover:bg-orange-600 text-white rounded-xl px-4 py-3 text-center font-medium"
                  >
                    GPS 재검증
                  </button>
                </div>
                <GpsExemptSubmit result={result} empNo={profile.empNo} apiBase={API_BASE} />
              </div>
            )}
          </div>
        )}

        {status === "error" && result?.error && (
          <div className="p-4 bg-red-50 border border-red-300 rounded-xl text-red-700">
            ❌ {result.error}
          </div>
        )}
      </div>
    </div>
  );
}

export function CardSelector({ value, onChange }) {
  const companies = [
    { value: "WOORI", label: "우리카드" },
    { value: "SHINHAN", label: "신한카드" },
    { value: "SAMSUNG", label: "삼성카드" },
    { value: "HYUNDAI", label: "현대카드" },
    { value: "LOTTE", label: "롯데카드" },
    { value: "KB", label: "KB국민카드" },
    { value: "HANA", label: "하나카드" },
    { value: "NONGHYUP", label: "농협카드" },
  ];

  return (
    <select
      value={value}
      onChange={(e) => onChange(e.target.value)}
      className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-gray-700 bg-white"
    >
      <option value="">카드사 선택</option>
      {companies.map((company) => (
        <option key={company.value} value={company.value}>{company.label}</option>
      ))}
    </select>
  );
}

export function TransactionList({ transactions = [] }) {
  if (!transactions.length) {
    return (
      <div className="bg-white border rounded-2xl p-8 text-center text-gray-400 shadow-sm">
        <div className="text-4xl mb-2">💳</div>
        <p>조회된 거래가 없습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-white border rounded-2xl p-5 shadow-sm overflow-x-auto">
      <h2 className="text-lg font-bold text-gray-800 mb-4">거래 내역</h2>
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left text-gray-500 border-b">
            <th className="py-2 pr-3">거래일시</th>
            <th className="py-2 pr-3">가맹점</th>
            <th className="py-2 pr-3">금액</th>
            <th className="py-2 pr-3">부가세</th>
            <th className="py-2 pr-3">MCC</th>
            <th className="py-2 pr-3">승인번호</th>
            <th className="py-2">카드</th>
          </tr>
        </thead>
        <tbody>
          {transactions.map((item, index) => (
            <tr key={`${item.approval_no || index}-${item.trans_date}`} className="border-b last:border-0">
              <td className="py-3 pr-3 text-gray-600">{item.trans_date} {item.trans_time || ""}</td>
              <td className="py-3 pr-3 font-medium text-gray-800">{item.merchant}</td>
              <td className="py-3 pr-3 font-mono">{item.amount?.toLocaleString()}원</td>
              <td className="py-3 pr-3 text-gray-600">{item.vat?.toLocaleString()}원</td>
              <td className="py-3 pr-3 text-gray-600">{item.mcc_code || "-"}</td>
              <td className="py-3 pr-3 text-gray-600">{item.approval_no || "-"}</td>
              <td className="py-3 text-gray-600">{item.card_number_masked || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function statusChip(status) {
  const chips = {
    AUTO_APPROVED: "bg-green-100 text-green-700",
    NEEDS_REVIEW: "bg-yellow-100 text-yellow-700",
    REJECTED: "bg-red-100 text-red-700",
    APPROVED: "bg-green-100 text-green-700",
    PENDING: "bg-gray-100 text-gray-600",
  };
  return chips[status] || "bg-gray-100 text-gray-600";
}

export function ReceiptHistory({ profile }) {
  const [items, setItems] = useState([]);
  const [summary, setSummary] = useState({});
  const [loading, setLoading] = useState(false);
  const [adminView, setAdminView] = useState(false);
  const [message, setMessage] = useState("");
  const [selectedImage, setSelectedImage] = useState(null);

  const recentItems = useMemo(() => items.slice(0, 3), [items]);

  const fetchHistory = async () => {
    if (!profile?.empNo && !adminView) {
      setMessage("설정 탭에서 사용자 프로필을 저장해주세요.");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const resp = await axios.get(`${API_BASE}/receipts/history`, {
        params: {
          emp_no: profile?.empNo || undefined,
          admin_view: adminView,
          limit: 100,
        },
      });
      setItems(resp.data.items || []);
      setSummary(resp.data.summary || {});
      if (!(resp.data.items || []).length) {
        setMessage("표시할 영수증 이력이 없습니다.");
      }
    } catch (err) {
      setMessage(err.response?.data?.detail || "영수증 이력을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchHistory();
  }, [profile?.empNo, adminView]);

  const renderThumb = (item) => {
    if (!item.evidence_url || item.file_exists === false) {
      return (
        <div className="w-20 h-20 rounded-xl bg-gray-100 border flex items-center justify-center text-xs text-gray-400">
          파일없음
        </div>
      );
    }
    return (
      <img
        src={item.evidence_url}
        alt={item.merchant}
        className="w-20 h-20 object-cover rounded-xl border cursor-pointer"
        onClick={() => setSelectedImage(item)}
        onError={(e) => {
          e.currentTarget.style.display = "none";
          const placeholder = e.currentTarget.nextSibling;
          if (placeholder) placeholder.style.display = "flex";
        }}
      />
    );
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h2 className="text-lg font-bold text-gray-800">영수증 업로드 이력</h2>
            <p className="text-sm text-gray-500 mt-1">저장된 증빙 이미지와 GPS 판정 상태를 한 번에 확인합니다.</p>
          </div>
          <div className="flex gap-2 items-center">
            <label className="inline-flex items-center gap-2 text-sm text-gray-600">
              <input type="checkbox" checked={adminView} onChange={(e) => setAdminView(e.target.checked)} />
              admin view
            </label>
            <button onClick={fetchHistory} className="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200">
              새로고침
            </button>
          </div>
        </div>

        <div className="grid md:grid-cols-4 gap-4">
          <SummaryCard label="전체 건수" value={`${summary.count || 0}건`} icon="🧾" />
          <SummaryCard label="총 금액" value={`${(summary.total_amount || 0).toLocaleString()}원`} icon="💰" />
          <SummaryCard label="GREEN" value={`${summary.green_count || 0}건`} icon="✅" />
          <SummaryCard label="검토/반려" value={`${summary.review_count || 0}건`} icon="⚠️" />
        </div>

        {message && (
          <div className="rounded-xl bg-blue-50 text-blue-700 px-4 py-3 text-sm border border-blue-100">
            {message}
          </div>
        )}

        {loading && <div className="text-sm text-gray-500">불러오는 중...</div>}
      </div>

      {!!recentItems.length && (
        <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
          <h3 className="text-base font-bold text-gray-800">최근 3건</h3>
          <div className="grid md:grid-cols-3 gap-4">
            {recentItems.map((item) => (
              <div key={item.id} className="border rounded-xl p-4 space-y-3">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <div className="font-semibold text-gray-800">{item.merchant || "가맹점 없음"}</div>
                    <div className="text-xs text-gray-500 mt-1">{item.txn_date || "-"}</div>
                  </div>
                  <span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusChip(item.status)}`}>{item.status}</span>
                </div>
                <div className="text-sm text-gray-600">{item.amount?.toLocaleString()}원</div>
                <div onClick={() => item.file_exists && setSelectedImage(item)}>{renderThumb(item)}</div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div className="bg-white border rounded-2xl p-5 shadow-sm overflow-x-auto">
        <h3 className="text-base font-bold text-gray-800 mb-4">전체 목록</h3>
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-gray-500 border-b">
              <th className="py-2 pr-3">증빙</th>
              <th className="py-2 pr-3">사용자</th>
              <th className="py-2 pr-3">거래일</th>
              <th className="py-2 pr-3">가맹점</th>
              <th className="py-2 pr-3">금액</th>
              <th className="py-2 pr-3">GPS</th>
              <th className="py-2 pr-3">상태</th>
              <th className="py-2">원본</th>
            </tr>
          </thead>
          <tbody>
            {items.map((item) => (
              <tr key={item.id} className="border-b last:border-0 align-top">
                <td className="py-3 pr-3">
                  <div className="relative w-20 h-20">
                    {renderThumb(item)}
                    <div className="hidden w-20 h-20 rounded-xl bg-gray-100 border items-center justify-center text-xs text-gray-400 absolute inset-0">
                      파일없음
                    </div>
                  </div>
                </td>
                <td className="py-3 pr-3 text-gray-600">
                  <div>{item.employee_name || item.emp_no}</div>
                  <div className="text-xs text-gray-400 mt-1">{item.department || "-"}</div>
                  <div className="text-xs text-gray-400">{item.project_code || "-"}</div>
                </td>
                <td className="py-3 pr-3 text-gray-600">{item.txn_date || "-"}</td>
                <td className="py-3 pr-3 font-medium text-gray-800">{item.merchant || "-"}</td>
                <td className="py-3 pr-3 text-gray-700">{item.amount?.toLocaleString()}원<br /><span className="text-xs text-gray-400">VAT {item.vat?.toLocaleString() || 0}원</span></td>
                <td className="py-3 pr-3 text-gray-600">{item.gps_grade || "-"}<br /><span className="text-xs text-gray-400">{item.gps_score ?? "-"}점</span></td>
                <td className="py-3 pr-3"><span className={`px-2 py-1 rounded-full text-xs font-semibold ${statusChip(item.status)}`}>{item.status}</span></td>
                <td className="py-3">
                  {item.evidence_url ? (
                    <a href={item.evidence_url} target="_blank" rel="noreferrer" className="text-blue-600 hover:underline text-xs">
                      열기
                    </a>
                  ) : (
                    <span className="text-xs text-gray-400">-</span>
                  )}
                </td>
              </tr>
            ))}
            {!items.length && !loading && (
              <tr>
                <td colSpan={8} className="py-10 text-center text-gray-400">영수증 이력이 없습니다.</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedImage && (
        <div className="fixed inset-0 bg-black/70 z-50 flex items-center justify-center p-4" onClick={() => setSelectedImage(null)}>
          <div className="bg-white rounded-2xl shadow-2xl max-w-3xl w-full p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-4 mb-4">
              <div>
                <h4 className="font-bold text-gray-800">{selectedImage.merchant || "영수증 이미지"}</h4>
                <p className="text-sm text-gray-500 mt-1">{selectedImage.txn_date} · {selectedImage.amount?.toLocaleString()}원</p>
              </div>
              <button onClick={() => setSelectedImage(null)} className="text-gray-400 hover:text-gray-700">닫기</button>
            </div>
            <img src={selectedImage.evidence_url} alt={selectedImage.merchant} className="w-full max-h-[70vh] object-contain rounded-xl bg-gray-50" />
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryCard({ label, value, icon }) {
  return (
    <div className="border rounded-xl p-4 bg-gray-50">
      <div className="text-2xl">{icon}</div>
      <div className="text-xl font-bold text-gray-800 mt-2">{value}</div>
      <div className="text-sm text-gray-500 mt-1">{label}</div>
    </div>
  );
}

function GpsExemptSubmit({ result, empNo, apiBase }) {
  const [open, setOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const reasons = [
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
        emp_no: empNo,
        receipt: result?.receipt,
        expense_code: result?.expense_code,
        exempt_reason: reason,
      });
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
        <p className="font-bold text-green-700">담당자 검토 요청이 전송되었습니다.</p>
      </div>
    );
  }

  return (
    <div className="bg-white rounded-xl border border-red-100 p-4 space-y-3">
      <button onClick={() => setOpen((prev) => !prev)} className="w-full flex items-center justify-between">
        <span className="text-sm font-bold text-gray-700">사유 입력 후 담당자 검토 요청</span>
        <span className="text-gray-400">{open ? "▲" : "▼"}</span>
      </button>
      {open && (
        <div className="space-y-3 pt-1">
          <div className="flex flex-wrap gap-2">
            {reasons.map((item) => (
              <button
                key={item}
                onClick={() => setReason(item.startsWith("기타") ? "" : item)}
                className={`px-3 py-1.5 rounded-full text-xs font-medium border ${
                  reason === item ? "bg-blue-600 text-white border-blue-600" : "bg-white text-gray-600 border-gray-300"
                }`}
              >
                {item}
              </button>
            ))}
          </div>
          <textarea
            value={reason}
            onChange={(e) => setReason(e.target.value)}
            placeholder="GPS 미등록 사유를 입력하세요..."
            rows={2}
            className="w-full border border-gray-200 rounded-lg p-3 text-sm resize-none"
          />
          <button
            onClick={handleSubmit}
            disabled={!reason.trim() || submitting}
            className="w-full bg-gray-700 hover:bg-gray-800 disabled:bg-gray-300 text-white font-bold py-3 rounded-xl"
          >
            {submitting ? "전송 중..." : "담당자 검토 요청"}
          </button>
        </div>
      )}
    </div>
  );
}

export function Dashboard({ stats = {} }) {
  const cards = [
    { label: "이번 달 총 경비", value: `${(stats.total_amount || 0).toLocaleString()}원`, icon: "💰", color: "text-blue-600" },
    { label: "자동 처리 건수", value: `${stats.auto_count || 0}건`, icon: "✅", color: "text-green-600" },
    { label: "검토 필요", value: `${stats.review_count || 0}건`, icon: "⚠️", color: "text-yellow-600" },
    { label: "GPS GREEN 비율", value: `${stats.gps_rate || 0}%`, icon: "📍", color: "text-purple-600" },
  ];

  return (
    <div className="grid sm:grid-cols-2 xl:grid-cols-4 gap-4">
      {cards.map((card) => (
        <div key={card.label} className="bg-white rounded-2xl border border-gray-200 p-5 shadow-sm">
          <div className="text-3xl mb-2">{card.icon}</div>
          <div className={`text-2xl font-bold ${card.color}`}>{card.value}</div>
          <div className="text-sm text-gray-500 mt-1">{card.label}</div>
        </div>
      ))}
    </div>
  );
}
