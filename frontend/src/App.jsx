import { useState, useEffect } from "react";
import { ReceiptUpload, CardSelector, TransactionList, Dashboard } from "./components";
import axios from "axios";

const API_BASE = import.meta.env.VITE_API_URL || "/api";

function App() {
  const [activeTab, setActiveTab] = useState("upload");
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [cardCompany, setCardCompany] = useState("WOORI");
  const empNo = "EMP001"; // 실제 구현 시 JWT에서 추출

  useEffect(() => {
    if (activeTab === "dashboard") {
      fetchStats();
    }
  }, [activeTab]);

  const fetchStats = async () => {
    try {
      const resp = await axios.get(`${API_BASE}/dashboard/stats`);
      const data = resp.data;
      const approved = data.by_status?.find((s) => s.status === "APPROVED");
      const review = data.by_status?.find((s) => s.status === "PENDING");
      setStats({
        total_amount: data.by_status?.reduce((s, r) => s + (r.total_amount || 0), 0) || 0,
        auto_count: approved?.count || 0,
        review_count: review?.count || 0,
        gps_rate: 82,
      });
    } catch (_) {}
  };

  const tabs = [
    { id: "upload",      label: "영수증 업로드", emoji: "📷" },
    { id: "transactions",label: "거래 내역",     emoji: "📋" },
    { id: "dashboard",   label: "대시보드",      emoji: "📊" },
    { id: "settings",    label: "경비코드 관리", emoji: "⚙️" },
  ];

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 헤더 */}
      <header className="bg-blue-700 text-white shadow-lg">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">ARM Platform</h1>
            <p className="text-blue-200 text-xs">다우오피스 경비 자동청구 시스템 v2.0</p>
          </div>
          <div className="text-sm text-blue-200">
            👤 {empNo}
          </div>
        </div>
      </header>

      {/* 탭 네비게이션 */}
      <nav className="bg-white border-b border-gray-200 sticky top-0 z-10 shadow-sm">
        <div className="max-w-6xl mx-auto px-4 flex gap-1">
          {tabs.map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-5 py-3.5 text-sm font-medium border-b-2 transition-colors
                ${activeTab === tab.id
                  ? "border-blue-600 text-blue-600"
                  : "border-transparent text-gray-500 hover:text-gray-700"}`}
            >
              {tab.emoji} {tab.label}
            </button>
          ))}
        </div>
      </nav>

      {/* 메인 콘텐츠 */}
      <main className="max-w-6xl mx-auto px-4 py-6">
        {activeTab === "upload" && <ReceiptUpload empNo={empNo} />}

        {activeTab === "transactions" && (
          <div className="space-y-4">
            <div className="flex gap-4 items-end">
              <div className="w-48">
                <label className="block text-sm font-medium text-gray-700 mb-1">카드사</label>
                <CardSelector value={cardCompany} onChange={setCardCompany} />
              </div>
              <button
                onClick={async () => {
                  setLoading(true);
                  try {
                    const resp = await axios.post(`${API_BASE}/transactions`, {
                      card_company: cardCompany,
                      corp_id: "CORP001",
                      card_numbers: ["1234567890123456"],
                      from_date: new Date(new Date().setDate(1)).toISOString().split("T")[0],
                      to_date: new Date().toISOString().split("T")[0],
                    });
                    setTransactions(resp.data.transactions || []);
                  } catch (_) {} finally {
                    setLoading(false);
                  }
                }}
                disabled={loading}
                className="px-4 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700
                           disabled:opacity-50 text-sm font-medium"
              >
                {loading ? "조회 중..." : "거래 조회"}
              </button>
            </div>
            <TransactionList transactions={transactions} />
          </div>
        )}

        {activeTab === "dashboard" && <Dashboard stats={stats} />}

        {activeTab === "settings" && (
          <div className="max-w-2xl">
            <h2 className="text-xl font-bold text-gray-800 mb-4">경비코드 매핑 관리</h2>
            <p className="text-gray-500 text-sm mb-4">
              가맹점명과 경비코드를 수동으로 매핑하여 자동 분류 정확도를 높일 수 있습니다.
            </p>
            <div className="bg-white border rounded-lg p-5 space-y-3">
              <input
                placeholder="가맹점명 (예: 스타벅스)"
                className="w-full border border-gray-300 rounded-lg px-4 py-2.5 text-sm"
              />
              <CardSelector value="" onChange={() => {}} />
              <button className="w-full py-2.5 bg-blue-600 text-white rounded-lg text-sm font-medium hover:bg-blue-700">
                매핑 추가
              </button>
            </div>
          </div>
        )}
      </main>

      {/* 푸터 */}
      <footer className="mt-12 py-6 border-t border-gray-200 text-center text-sm text-gray-400">
        ARM Platform v2.0 · AWS Lightsail 13.125.110.156 ·{" "}
        <a href="https://github.com/thelab-bobkim/ARM" className="text-blue-500 hover:underline" target="_blank" rel="noreferrer">
          GitHub
        </a>
      </footer>
    </div>
  );
}

export default App;
