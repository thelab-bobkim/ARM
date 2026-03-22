import { useState, useEffect } from "react";
import { ReceiptUpload, CardSelector, TransactionList, Dashboard } from "./components";
import axios from "axios";

// ✅ PWA 설치 배너 컴포넌트
function PWAInstallBanner({ onDismiss }) {
  return (
    <div className="fixed bottom-0 left-0 right-0 z-50 bg-blue-700 text-white px-4 py-3 flex items-center justify-between shadow-2xl"
         style={{ paddingBottom: 'calc(0.75rem + env(safe-area-inset-bottom))' }}>
      <div className="flex items-center gap-3">
        <img src="/icons/icon-72x72.png" alt="ARM" className="w-10 h-10 rounded-xl" />
        <div>
          <p className="font-bold text-sm">ARM 경비 앱 설치</p>
          <p className="text-blue-200 text-xs">홈 화면에 추가하여 앱처럼 사용하세요</p>
        </div>
      </div>
      <div className="flex gap-2">
        <button
          onClick={onDismiss}
          className="px-3 py-1.5 text-xs text-blue-200 hover:text-white"
        >나중에</button>
        <button
          onClick={() => window.armPWA?.install()}
          className="px-4 py-1.5 bg-white text-blue-700 rounded-lg text-xs font-bold"
        >설치</button>
      </div>
    </div>
  );
}

const API_BASE = import.meta.env.VITE_API_URL || "/api";

function App() {
  const [activeTab, setActiveTab] = useState("upload");
  const [transactions, setTransactions] = useState([]);
  const [stats, setStats] = useState({});
  const [loading, setLoading] = useState(false);
  const [cardCompany, setCardCompany] = useState("WOORI");
  const [showInstallBanner, setShowInstallBanner] = useState(false);
  const [isStandalone, setIsStandalone] = useState(false);
  const empNo = "EMP001"; // 실제 구현 시 JWT에서 추출

  useEffect(() => {
    if (activeTab === "dashboard") {
      fetchStats();
    }
  }, [activeTab]);

  // PWA 설치 상태 감지
  useEffect(() => {
    const standalone = window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone === true;
    setIsStandalone(standalone);

    const handleInstallable = () => {
      if (!standalone && !localStorage.getItem('arm-pwa-dismissed')) {
        setTimeout(() => setShowInstallBanner(true), 3000);
      }
    };
    window.addEventListener('arm-pwa-installable', handleInstallable);
    window.addEventListener('arm-pwa-installed', () => setShowInstallBanner(false));
    return () => {
      window.removeEventListener('arm-pwa-installable', handleInstallable);
    };
  }, []);

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

  const handleDismissBanner = () => {
    setShowInstallBanner(false);
    localStorage.setItem('arm-pwa-dismissed', '1');
  };

  return (
    <div className="min-h-screen bg-gray-50">
      {/* PWA 설치 배너 */}
      {showInstallBanner && <PWAInstallBanner onDismiss={handleDismissBanner} />}
      {/* 헤더 */}
      <header className="bg-blue-700 text-white shadow-lg">
        <div className="max-w-6xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">ARM Platform {isStandalone && <span className="text-xs bg-green-500 px-1.5 py-0.5 rounded ml-1">앱</span>}</h1>
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
      <footer className="mt-12 py-6 border-t border-gray-200 text-center text-sm text-gray-400" style={{ paddingBottom: 'calc(1.5rem + env(safe-area-inset-bottom))' }}>
        ARM Platform v2.0 · AWS Lightsail ·{" "}
        <a href="https://github.com/thelab-bobkim/ARM" className="text-blue-500 hover:underline" target="_blank" rel="noreferrer">
          GitHub
        </a>
        {!isStandalone && (
          <span className="ml-3">
            · <button onClick={() => window.armPWA?.install()} className="text-blue-500 hover:underline">📱 앱 설치</button>
          </span>
        )}
      </footer>
    </div>
  );
}

export default App;
