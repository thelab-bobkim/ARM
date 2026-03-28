import { useEffect, useMemo, useState } from "react";
import axios from "axios";
import {
  CardSelector,
  Dashboard,
  ReceiptHistory,
  ReceiptUpload,
  TransactionList,
} from "./components";

const API_BASE = import.meta.env.VITE_API_URL || "/api";
const PROFILE_STORAGE_KEY = "arm_user_profile_v1";
const TAB_STORAGE_KEY = "arm_active_tab_v1";

function loadStoredProfile() {
  try {
    const raw = localStorage.getItem(PROFILE_STORAGE_KEY);
    if (!raw) {
      return {
        empNo: "",
        employeeName: "",
        department: "",
        projectCode: "",
      };
    }
    const parsed = JSON.parse(raw);
    return {
      empNo: parsed.empNo || "",
      employeeName: parsed.employeeName || "",
      department: parsed.department || "",
      projectCode: parsed.projectCode || "",
    };
  } catch {
    return {
      empNo: "",
      employeeName: "",
      department: "",
      projectCode: "",
    };
  }
}

function normalizeEmployeeId(value) {
  const trimmed = (value || "").trim();
  if (!trimmed) return "";
  return trimmed.includes("@") ? trimmed.split("@")[0] : trimmed;
}

function PWAInstallBanner({ onDismiss }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-blue-700 text-white px-4 py-3 flex items-center justify-between shadow-2xl">
      <div>
        <p className="font-bold text-sm">ARM 경비 앱 설치</p>
        <p className="text-blue-200 text-xs">홈 화면에 추가하면 모바일에서 더 편하게 사용할 수 있습니다.</p>
      </div>
      <div className="flex items-center gap-2">
        <button onClick={onDismiss} className="px-3 py-1 text-xs text-blue-200">닫기</button>
        <button
          onClick={() => window.armInstallPrompt?.prompt()}
          className="px-3 py-1 bg-white text-blue-700 rounded-lg text-xs font-bold"
        >
          설치
        </button>
      </div>
    </div>
  );
}

function MappingManager({ expenseCodes = [] }) {
  const [mappings, setMappings] = useState([]);
  const [loading, setLoading] = useState(false);
  const [search, setSearch] = useState("");
  const [message, setMessage] = useState("");
  const [form, setForm] = useState({
    id: null,
    merchant_pattern: "",
    expense_code: expenseCodes[0]?.code || "",
    expense_name: expenseCodes[0]?.name || "",
    mcc_code: "",
  });

  useEffect(() => {
    if (!form.expense_code && expenseCodes.length) {
      setForm((prev) => ({
        ...prev,
        expense_code: expenseCodes[0].code,
        expense_name: expenseCodes[0].name,
      }));
    }
  }, [expenseCodes, form.expense_code]);

  const fetchMappings = async (nextSearch = search) => {
    setLoading(true);
    setMessage("");
    try {
      const resp = await axios.get(`${API_BASE}/merchant-mappings`, {
        params: nextSearch ? { search: nextSearch } : {},
      });
      setMappings(resp.data || []);
    } catch (err) {
      setMessage(err.response?.data?.detail || "매핑 목록을 불러오지 못했습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMappings();
  }, []);

  const handleCodeChange = (code) => {
    const found = expenseCodes.find((item) => item.code === code);
    setForm((prev) => ({
      ...prev,
      expense_code: code,
      expense_name: found?.name || prev.expense_name,
    }));
  };

  const resetForm = () => {
    setForm({
      id: null,
      merchant_pattern: "",
      expense_code: expenseCodes[0]?.code || "",
      expense_name: expenseCodes[0]?.name || "",
      mcc_code: "",
    });
  };

  const submit = async () => {
    if (!form.merchant_pattern.trim() || !form.expense_code || !form.expense_name) {
      setMessage("가맹점명과 경비코드를 입력해주세요.");
      return;
    }
    setLoading(true);
    setMessage("");
    try {
      const payload = {
        merchant_pattern: form.merchant_pattern.trim(),
        expense_code: form.expense_code,
        expense_name: form.expense_name,
        mcc_code: form.mcc_code.trim() || null,
      };
      if (form.id) {
        await axios.put(`${API_BASE}/merchant-mappings/${form.id}`, payload);
        setMessage("매핑을 수정했습니다.");
      } else {
        await axios.post(`${API_BASE}/merchant-mappings`, payload);
        setMessage("매핑을 추가했습니다.");
      }
      resetForm();
      await fetchMappings();
    } catch (err) {
      setMessage(err.response?.data?.detail || "매핑 저장에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  const remove = async (mappingId) => {
    if (!window.confirm("이 매핑을 삭제할까요?")) return;
    setLoading(true);
    setMessage("");
    try {
      await axios.delete(`${API_BASE}/merchant-mappings/${mappingId}`);
      setMessage("매핑을 삭제했습니다.");
      await fetchMappings();
    } catch (err) {
      setMessage(err.response?.data?.detail || "매핑 삭제에 실패했습니다.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-5">
      <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
        <div>
          <h3 className="text-lg font-bold text-gray-800">경비코드 매핑 관리</h3>
          <p className="text-sm text-gray-500 mt-1">가맹점명을 수동 매핑해 자동 분류 정확도를 높일 수 있습니다.</p>
        </div>

        {message && (
          <div className="rounded-xl bg-blue-50 text-blue-700 px-4 py-3 text-sm border border-blue-100">
            {message}
          </div>
        )}

        <div className="grid md:grid-cols-2 gap-3">
          <input
            value={form.merchant_pattern}
            onChange={(e) => setForm((prev) => ({ ...prev, merchant_pattern: e.target.value }))}
            placeholder="가맹점명 키워드 (예: 스타벅스)"
            className="border border-gray-300 rounded-xl px-4 py-3 text-sm"
          />
          <input
            value={form.mcc_code}
            onChange={(e) => setForm((prev) => ({ ...prev, mcc_code: e.target.value }))}
            placeholder="MCC 코드 (선택)"
            className="border border-gray-300 rounded-xl px-4 py-3 text-sm"
          />
          <select
            value={form.expense_code}
            onChange={(e) => handleCodeChange(e.target.value)}
            className="border border-gray-300 rounded-xl px-4 py-3 text-sm bg-white"
          >
            {expenseCodes.map((item) => (
              <option key={item.code} value={item.code}>{item.code} · {item.name}</option>
            ))}
          </select>
          <input
            value={form.expense_name}
            onChange={(e) => setForm((prev) => ({ ...prev, expense_name: e.target.value }))}
            placeholder="경비코드명"
            className="border border-gray-300 rounded-xl px-4 py-3 text-sm"
          />
        </div>

        <div className="flex gap-2">
          <button
            onClick={submit}
            disabled={loading}
            className="px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
          >
            {form.id ? "매핑 수정" : "매핑 추가"}
          </button>
          <button
            onClick={resetForm}
            className="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200"
          >
            초기화
          </button>
        </div>
      </div>

      <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <h3 className="text-base font-bold text-gray-800">등록된 매핑</h3>
          <div className="flex gap-2">
            <input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="가맹점 검색"
              className="border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
            />
            <button
              onClick={() => fetchMappings(search)}
              className="px-4 py-2.5 bg-gray-100 text-gray-700 rounded-xl text-sm font-medium hover:bg-gray-200"
            >
              검색
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-gray-500 border-b">
                <th className="py-2 pr-3">가맹점</th>
                <th className="py-2 pr-3">경비코드</th>
                <th className="py-2 pr-3">MCC</th>
                <th className="py-2 pr-3">출처</th>
                <th className="py-2 pr-3">사용횟수</th>
                <th className="py-2">관리</th>
              </tr>
            </thead>
            <tbody>
              {mappings.map((item) => (
                <tr key={item.id} className="border-b last:border-0">
                  <td className="py-3 pr-3 font-medium text-gray-800">{item.merchant_pattern}</td>
                  <td className="py-3 pr-3 text-gray-700">{item.expense_code} · {item.expense_name}</td>
                  <td className="py-3 pr-3 text-gray-500">{item.mcc_code || "-"}</td>
                  <td className="py-3 pr-3 text-gray-500">{item.source}</td>
                  <td className="py-3 pr-3 text-gray-500">{item.use_count || 0}</td>
                  <td className="py-3 flex gap-2">
                    <button
                      onClick={() => setForm({
                        id: item.id,
                        merchant_pattern: item.merchant_pattern,
                        expense_code: item.expense_code,
                        expense_name: item.expense_name,
                        mcc_code: item.mcc_code || "",
                      })}
                      className="px-3 py-1.5 bg-blue-50 text-blue-700 rounded-lg text-xs font-medium"
                    >
                      수정
                    </button>
                    <button
                      onClick={() => remove(item.id)}
                      className="px-3 py-1.5 bg-red-50 text-red-700 rounded-lg text-xs font-medium"
                    >
                      삭제
                    </button>
                  </td>
                </tr>
              ))}
              {!mappings.length && !loading && (
                <tr>
                  <td colSpan={6} className="py-8 text-center text-gray-400">등록된 매핑이 없습니다.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

function App() {
  const [profile, setProfile] = useState(loadStoredProfile);
  const [activeTab, setActiveTab] = useState(localStorage.getItem(TAB_STORAGE_KEY) || "upload");
  const [transactions, setTransactions] = useState([]);
  const [txLoading, setTxLoading] = useState(false);
  const [stats, setStats] = useState({});
  const [expenseCodes, setExpenseCodes] = useState([]);
  const [features, setFeatures] = useState(null);
  const [notice, setNotice] = useState("");
  const [showInstallBanner, setShowInstallBanner] = useState(false);
  const [txnForm, setTxnForm] = useState({
    cardCompany: "WOORI",
    corpId: "",
    cardNumbers: "",
    fromDate: new Date(new Date().setDate(1)).toISOString().split("T")[0],
    toDate: new Date().toISOString().split("T")[0],
    saveToDb: true,
  });

  const normalizedProfile = useMemo(() => ({
    ...profile,
    empNo: normalizeEmployeeId(profile.empNo),
  }), [profile]);

  useEffect(() => {
    localStorage.setItem(PROFILE_STORAGE_KEY, JSON.stringify(normalizedProfile));
  }, [normalizedProfile]);

  useEffect(() => {
    localStorage.setItem(TAB_STORAGE_KEY, activeTab);
  }, [activeTab]);

  useEffect(() => {
    const handleInstallable = () => {
      if (!localStorage.getItem("arm-pwa-dismissed")) {
        setShowInstallBanner(true);
      }
    };
    window.addEventListener("pwa-installable", handleInstallable);
    return () => window.removeEventListener("pwa-installable", handleInstallable);
  }, []);

  const fetchExpenseCodes = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/expense-codes`);
      setExpenseCodes(resp.data || []);
    } catch {}
  };

  const fetchFeatures = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/system/features`);
      setFeatures(resp.data);
    } catch {}
  };

  const fetchStats = async (empNo = normalizedProfile.empNo) => {
    if (!empNo) {
      setStats({});
      return;
    }
    try {
      const resp = await axios.get(`${API_BASE}/dashboard/stats`, { params: { emp_no: empNo } });
      const approved = (resp.data.by_status || []).find((row) => row.status === "APPROVED" || row.status === "AUTO_APPROVED");
      const review = (resp.data.by_status || []).find((row) => row.status === "NEEDS_REVIEW" || row.status === "PENDING");
      setStats({
        total_amount: (resp.data.by_status || []).reduce((sum, row) => sum + (row.total_amount || 0), 0),
        auto_count: approved?.count || 0,
        review_count: review?.count || 0,
        gps_rate: resp.data.gps_rate || 0,
      });
    } catch {}
  };

  const syncProfileFromServer = async (empNo, syncDaou = false) => {
    const normalized = normalizeEmployeeId(empNo);
    if (!normalized) return;
    try {
      const resp = await axios.get(`${API_BASE}/user-profiles/${normalized}`, {
        params: syncDaou ? { sync_daou: true } : {},
      });
      const data = resp.data || {};
      setProfile((prev) => ({
        ...prev,
        empNo: normalized,
        employeeName: data.employee_name || prev.employeeName,
        department: data.department || prev.department,
        projectCode: data.project_code || prev.projectCode,
      }));
    } catch {}
  };

  useEffect(() => {
    fetchExpenseCodes();
    fetchFeatures();
  }, []);

  useEffect(() => {
    if (normalizedProfile.empNo) {
      syncProfileFromServer(normalizedProfile.empNo, false);
      fetchStats(normalizedProfile.empNo);
    }
  }, [normalizedProfile.empNo]);

  useEffect(() => {
    if (activeTab === "dashboard") {
      fetchStats();
    }
  }, [activeTab]);

  const updateProfileField = (field, value) => {
    setProfile((prev) => ({ ...prev, [field]: value }));
  };

  const saveProfile = async () => {
    const empNo = normalizeEmployeeId(profile.empNo);
    if (!empNo) {
      setNotice("다우오피스 ID 또는 사번을 먼저 입력해주세요.");
      return;
    }
    try {
      await axios.put(`${API_BASE}/user-profiles/${empNo}`, {
        daou_login_id: empNo,
        employee_name: profile.employeeName,
        department: profile.department,
        project_code: profile.projectCode,
        source: "MANUAL",
      });
      setNotice("프로필을 서버에 저장했습니다.");
      setProfile((prev) => ({ ...prev, empNo }));
      fetchStats(empNo);
    } catch (err) {
      setNotice(err.response?.data?.detail || "프로필 저장에 실패했습니다.");
    }
  };

  const syncDaouProfile = async () => {
    const empNo = normalizeEmployeeId(profile.empNo);
    if (!empNo) {
      setNotice("먼저 다우오피스 ID를 입력해주세요.");
      return;
    }
    try {
      const resp = await axios.post(`${API_BASE}/user-profiles/${empNo}/sync-daou`);
      const data = resp.data || {};
      setProfile((prev) => ({
        ...prev,
        empNo,
        employeeName: data.employee_name || prev.employeeName,
        department: data.department || prev.department,
        projectCode: data.project_code || prev.projectCode,
      }));
      setNotice("다우오피스 인사정보를 동기화했습니다.");
    } catch (err) {
      setNotice(err.response?.data?.detail || "다우오피스 동기화에 실패했습니다.");
    }
  };

  const fetchTransactions = async () => {
    if (!normalizedProfile.empNo) {
      setNotice("먼저 사용자 프로필을 저장해주세요.");
      setActiveTab("settings");
      return;
    }
    const cardNumbers = txnForm.cardNumbers
      .split(/[,\n]/)
      .map((item) => item.trim())
      .filter(Boolean);
    if (!cardNumbers.length) {
      setNotice("조회할 카드번호를 입력해주세요.");
      return;
    }
    setTxLoading(true);
    setNotice("");
    try {
      const resp = await axios.post(`${API_BASE}/transactions`, {
        card_company: txnForm.cardCompany,
        corp_id: txnForm.corpId,
        card_numbers: cardNumbers,
        from_date: txnForm.fromDate,
        to_date: txnForm.toDate,
        emp_no: normalizedProfile.empNo,
        employee_name: normalizedProfile.employeeName,
        department: normalizedProfile.department,
        project_code: normalizedProfile.projectCode,
        save_to_db: txnForm.saveToDb,
      });
      setTransactions(resp.data.transactions || []);
      const summary = resp.data.save_summary || {};
      setNotice(`거래 ${resp.data.count || 0}건 조회 완료 · 저장 ${summary.imported || 0}건 / 중복 ${summary.skipped || 0}건`);
      fetchStats();
    } catch (err) {
      setNotice(err.response?.data?.detail || "거래 조회에 실패했습니다.");
    } finally {
      setTxLoading(false);
    }
  };

  const tabs = [
    { id: "upload", label: "영수증 업로드", emoji: "📷" },
    { id: "history", label: "영수증 이력", emoji: "🗂️" },
    { id: "transactions", label: "카드 거래", emoji: "💳" },
    { id: "dashboard", label: "대시보드", emoji: "📊" },
    { id: "settings", label: "설정/매핑", emoji: "⚙️" },
  ];

  return (
    <div className="min-h-screen bg-slate-50 text-gray-800">
      {showInstallBanner && (
        <PWAInstallBanner
          onDismiss={() => {
            setShowInstallBanner(false);
            localStorage.setItem("arm-pwa-dismissed", "1");
          }}
        />
      )}

      <header className="bg-blue-700 text-white shadow-lg">
        <div className="max-w-7xl mx-auto px-4 py-4 flex flex-col md:flex-row md:items-center md:justify-between gap-3">
          <div>
            <h1 className="text-xl font-bold">ARM Platform</h1>
            <p className="text-blue-100 text-sm">다우오피스 경비 자동청구 운영 콘솔</p>
          </div>
          <div className="text-sm text-blue-100 text-right">
            <div>👤 {normalizedProfile.employeeName || "사용자 미설정"}</div>
            <div>{normalizedProfile.empNo || "사번/ID 미입력"} {normalizedProfile.department ? `· ${normalizedProfile.department}` : ""}</div>
          </div>
        </div>
      </header>

      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 flex gap-1 overflow-x-auto">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3.5 text-sm font-medium border-b-2 whitespace-nowrap transition-colors ${
                activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"
              }`}
            >
              {tab.emoji} {tab.label}
            </button>
          ))}
        </div>
      </nav>

      <main className="max-w-7xl mx-auto px-4 py-6 space-y-5">
        {notice && (
          <div className="rounded-2xl bg-blue-50 border border-blue-100 px-4 py-3 text-sm text-blue-700">
            {notice}
          </div>
        )}

        {features?.daou && (
          <div className="bg-white border rounded-2xl p-4 shadow-sm flex flex-col md:flex-row md:items-center md:justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-gray-800">다우오피스 연동 상태</div>
              <div className={`text-sm mt-1 ${features.daou.ready ? "text-green-600" : "text-amber-600"}`}>
                {features.daou.ready ? "운영 연결 준비 완료" : "설정 확인 필요"}
              </div>
            </div>
            <div className="text-xs text-gray-500">
              업로드 경로: <span className="font-mono">{features.receipt_upload_root}</span>
            </div>
          </div>
        )}

        {activeTab === "upload" && (
          <ReceiptUpload
            profile={normalizedProfile}
            onProfileRefresh={() => syncProfileFromServer(normalizedProfile.empNo, false)}
          />
        )}

        {activeTab === "history" && (
          <ReceiptHistory profile={normalizedProfile} />
        )}

        {activeTab === "transactions" && (
          <div className="space-y-5">
            <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
              <h2 className="text-lg font-bold text-gray-800">법인카드 거래 조회 및 저장</h2>
              <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">카드사</label>
                  <CardSelector value={txnForm.cardCompany} onChange={(value) => setTxnForm((prev) => ({ ...prev, cardCompany: value }))} />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">법인 ID</label>
                  <input
                    value={txnForm.corpId}
                    onChange={(e) => setTxnForm((prev) => ({ ...prev, corpId: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                    placeholder="corp_id"
                  />
                </div>
                <div className="flex items-end">
                  <label className="inline-flex items-center gap-2 text-sm text-gray-700">
                    <input
                      type="checkbox"
                      checked={txnForm.saveToDb}
                      onChange={(e) => setTxnForm((prev) => ({ ...prev, saveToDb: e.target.checked }))}
                    />
                    조회 후 DB/Inbox 저장
                  </label>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">조회 시작일</label>
                  <input
                    type="date"
                    value={txnForm.fromDate}
                    onChange={(e) => setTxnForm((prev) => ({ ...prev, fromDate: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">조회 종료일</label>
                  <input
                    type="date"
                    value={txnForm.toDate}
                    onChange={(e) => setTxnForm((prev) => ({ ...prev, toDate: e.target.value }))}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-1">카드번호 목록</label>
                <textarea
                  value={txnForm.cardNumbers}
                  onChange={(e) => setTxnForm((prev) => ({ ...prev, cardNumbers: e.target.value }))}
                  rows={3}
                  className="w-full border border-gray-300 rounded-xl px-4 py-3 text-sm resize-none"
                  placeholder="카드번호를 쉼표 또는 줄바꿈으로 입력하세요"
                />
              </div>

              <button
                onClick={fetchTransactions}
                disabled={txLoading}
                className="px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700 disabled:opacity-50"
              >
                {txLoading ? "조회 중..." : "거래 조회"}
              </button>
            </div>

            <TransactionList transactions={transactions} />
          </div>
        )}

        {activeTab === "dashboard" && (
          <Dashboard stats={stats} />
        )}

        {activeTab === "settings" && (
          <div className="space-y-5">
            <div className="bg-white border rounded-2xl p-5 shadow-sm space-y-4">
              <div>
                <h2 className="text-lg font-bold text-gray-800">사용자 기본정보</h2>
                <p className="text-sm text-gray-500 mt-1">PC와 모바일에서 동일하게 쓰기 위해 서버에도 저장됩니다.</p>
              </div>
              <div className="grid md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">다우오피스 ID / 사번</label>
                  <input
                    value={profile.empNo}
                    onChange={(e) => updateProfileField("empNo", e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                    placeholder="htkim 또는 htkim@company.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">이름</label>
                  <input
                    value={profile.employeeName}
                    onChange={(e) => updateProfileField("employeeName", e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                    placeholder="홍길동"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">부서</label>
                  <input
                    value={profile.department}
                    onChange={(e) => updateProfileField("department", e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                    placeholder="AI전략팀"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">기본 프로젝트 코드</label>
                  <input
                    value={profile.projectCode}
                    onChange={(e) => updateProfileField("projectCode", e.target.value)}
                    className="w-full border border-gray-300 rounded-xl px-4 py-2.5 text-sm"
                    placeholder="PJ-2026-001"
                  />
                </div>
              </div>

              <div className="flex gap-2 flex-wrap">
                <button
                  onClick={saveProfile}
                  className="px-4 py-2.5 bg-blue-600 text-white rounded-xl text-sm font-medium hover:bg-blue-700"
                >
                  프로필 저장
                </button>
                <button
                  onClick={syncDaouProfile}
                  className="px-4 py-2.5 bg-slate-100 text-slate-700 rounded-xl text-sm font-medium hover:bg-slate-200"
                >
                  다우 인사정보 동기화
                </button>
              </div>
            </div>

            <MappingManager expenseCodes={expenseCodes} />
          </div>
        )}
      </main>

      <footer className="mt-10 py-6 border-t border-gray-200 text-center text-sm text-gray-400">
        ARM Platform v2.1 · 
        <a href="https://github.com/thelab-bobkim/ARM" className="text-blue-500 hover:underline ml-1" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}

export default App;
