import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// ===== PWA 서비스워커 등록 =====
function registerServiceWorker() {
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker
        .register("/sw.js", { scope: "/" })
        .then((registration) => {
          console.log("[ARM PWA] 서비스워커 등록 성공:", registration.scope);

          // 업데이트 감지
          registration.addEventListener("updatefound", () => {
            const newWorker = registration.installing;
            newWorker?.addEventListener("statechange", () => {
              if (
                newWorker.state === "installed" &&
                navigator.serviceWorker.controller
              ) {
                console.log("[ARM PWA] 새 버전 사용 가능 - 페이지를 새로고침하세요");
                // 업데이트 알림 (선택적)
                if (window.confirm("ARM Platform 새 버전이 출시되었습니다. 지금 업데이트할까요?")) {
                  newWorker.postMessage({ type: "SKIP_WAITING" });
                  window.location.reload();
                }
              }
            });
          });
        })
        .catch((error) => {
          console.warn("[ARM PWA] 서비스워커 등록 실패:", error);
        });

      // 서비스워커 업데이트 후 자동 새로고침
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        window.location.reload();
      });
    });
  }
}

// ===== PWA 설치 프롬프트 관리 =====
let deferredInstallPrompt = null;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  console.log("[ARM PWA] 앱 설치 프롬프트 준비됨");

  // 전역으로 노출 (App 컴포넌트에서 사용 가능)
  window.armInstallPrompt = deferredInstallPrompt;

  // 설치 버튼 이벤트 발생
  window.dispatchEvent(new CustomEvent("pwa-installable"));
});

window.addEventListener("appinstalled", () => {
  console.log("[ARM PWA] 앱이 홈 화면에 설치되었습니다!");
  deferredInstallPrompt = null;
  window.armInstallPrompt = null;
  window.dispatchEvent(new CustomEvent("pwa-installed"));
});

// ===== 오프라인/온라인 상태 감지 =====
window.addEventListener("online", () => {
  console.log("[ARM PWA] 네트워크 연결 복구");
  window.dispatchEvent(new CustomEvent("arm-network-online"));
});

window.addEventListener("offline", () => {
  console.log("[ARM PWA] 네트워크 연결 끊김");
  window.dispatchEvent(new CustomEvent("arm-network-offline"));
});

// ===== 스플래시 스크린 숨기기 =====
function hideSplashScreen() {
  const splash = document.getElementById("app-loading");
  if (splash) {
    setTimeout(() => {
      splash.classList.add("hidden");
      setTimeout(() => splash.remove(), 500);
    }, 800);
  }
}

// ===== 앱 렌더링 =====
const root = ReactDOM.createRoot(document.getElementById("root"));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);

// 서비스워커 등록 및 스플래시 처리
registerServiceWorker();
hideSplashScreen();
