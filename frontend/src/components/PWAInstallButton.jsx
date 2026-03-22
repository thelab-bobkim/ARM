import React, { useState, useEffect } from "react";

/**
 * PWA 설치 버튼 컴포넌트
 * - "홈 화면에 추가" 버튼 표시
 * - 오프라인 상태 표시
 * - 설치 완료 알림
 */
export default function PWAInstallButton() {
  const [canInstall, setCanInstall] = useState(false);
  const [isInstalled, setIsInstalled] = useState(false);
  const [isOffline, setIsOffline] = useState(!navigator.onLine);
  const [showOfflineBanner, setShowOfflineBanner] = useState(false);

  useEffect(() => {
    // 이미 standalone 모드(설치됨)인지 확인
    const isStandalone =
      window.matchMedia("(display-mode: standalone)").matches ||
      window.navigator.standalone === true;
    if (isStandalone) {
      setIsInstalled(true);
      return;
    }

    // 설치 가능 이벤트
    const onInstallable = () => setCanInstall(true);
    const onInstalled = () => {
      setCanInstall(false);
      setIsInstalled(true);
    };

    // 이미 준비된 프롬프트 확인
    if (window.armInstallPrompt) setCanInstall(true);

    window.addEventListener("pwa-installable", onInstallable);
    window.addEventListener("pwa-installed", onInstalled);

    // 네트워크 상태
    const onOnline = () => {
      setIsOffline(false);
      setShowOfflineBanner(false);
    };
    const onOffline = () => {
      setIsOffline(true);
      setShowOfflineBanner(true);
    };
    window.addEventListener("arm-network-online", onOnline);
    window.addEventListener("arm-network-offline", onOffline);

    return () => {
      window.removeEventListener("pwa-installable", onInstallable);
      window.removeEventListener("pwa-installed", onInstalled);
      window.removeEventListener("arm-network-online", onOnline);
      window.removeEventListener("arm-network-offline", onOffline);
    };
  }, []);

  const handleInstall = async () => {
    if (!window.armInstallPrompt) return;
    window.armInstallPrompt.prompt();
    const { outcome } = await window.armInstallPrompt.userChoice;
    if (outcome === "accepted") {
      console.log("[PWA] 사용자가 설치를 수락했습니다");
      setCanInstall(false);
    } else {
      console.log("[PWA] 사용자가 설치를 거절했습니다");
    }
    window.armInstallPrompt = null;
  };

  return (
    <>
      {/* 오프라인 배너 */}
      {showOfflineBanner && (
        <div className="fixed top-0 left-0 right-0 z-50 bg-yellow-500 text-white text-center py-2 px-4 text-sm font-medium flex items-center justify-center gap-2">
          <span>📵</span>
          <span>오프라인 상태 - 캐시된 데이터를 사용 중입니다</span>
          <button
            onClick={() => setShowOfflineBanner(false)}
            className="ml-2 text-white opacity-70 hover:opacity-100"
          >
            ✕
          </button>
        </div>
      )}

      {/* 온라인 복구 알림 */}
      {!isOffline && isInstalled && (
        <></>
      )}

      {/* PWA 설치 버튼 */}
      {canInstall && !isInstalled && (
        <div className="fixed bottom-4 left-4 right-4 z-40 md:left-auto md:right-6 md:w-80">
          <div className="bg-blue-600 text-white rounded-2xl shadow-2xl p-4 flex items-center gap-3">
            <div className="flex-shrink-0 bg-white rounded-xl p-2">
              <span className="text-blue-600 font-black text-lg">ARM</span>
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-sm">앱으로 설치하기</p>
              <p className="text-xs text-blue-200 truncate">홈 화면에 추가하면 더 빠르게!</p>
            </div>
            <button
              onClick={handleInstall}
              className="flex-shrink-0 bg-white text-blue-600 font-bold text-sm px-3 py-1.5 rounded-lg hover:bg-blue-50 transition-colors"
            >
              설치
            </button>
            <button
              onClick={() => setCanInstall(false)}
              className="flex-shrink-0 text-blue-200 hover:text-white text-lg leading-none"
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* 설치 완료 모드 표시 (standalone) */}
      {isInstalled && (
        <div className="fixed top-safe-area-inset-top left-0 right-0 z-50 bg-blue-600 text-white text-xs text-center py-1 flex items-center justify-center gap-1">
          <span>📱</span>
          <span>ARM Platform 앱 모드</span>
        </div>
      )}
    </>
  );
}
