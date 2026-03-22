import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "./index.css";

// ===== PWA 자동 업데이트 관리자 =====
function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;

  window.addEventListener("load", async () => {
    try {
      const registration = await navigator.serviceWorker.register("/sw.js", {
        scope: "/",
        // ✅ 핵심: 30초마다 SW 업데이트 체크 (기본값은 24시간)
        updateViaCache: "none",
      });

      console.log("[ARM PWA] 서비스워커 등록 완료:", registration.scope);

      // ─── 앱이 포커스될 때마다 업데이트 체크 ───
      document.addEventListener("visibilitychange", () => {
        if (document.visibilityState === "visible") {
          registration.update().catch(() => {});
        }
      });

      // ─── 새 SW 발견 시 처리 ───
      registration.addEventListener("updatefound", () => {
        const newWorker = registration.installing;
        if (!newWorker) return;

        newWorker.addEventListener("statechange", () => {
          if (
            newWorker.state === "installed" &&
            navigator.serviceWorker.controller
          ) {
            console.log("[ARM PWA] 새 버전 감지 - 자동 업데이트 배너 표시");
            showUpdateBanner(newWorker);
          }
        });
      });

      // ─── SW 교체 완료 → 페이지 자동 새로고침 ───
      navigator.serviceWorker.addEventListener("controllerchange", () => {
        console.log("[ARM PWA] SW 교체 완료 - 새로고침");
        window.location.reload();
      });

    } catch (error) {
      console.warn("[ARM PWA] 서비스워커 등록 실패:", error);
    }
  });
}

// ===== 업데이트 배너 표시 (자동 3초 후 적용) =====
function showUpdateBanner(newWorker) {
  // 이미 배너 있으면 중복 방지
  if (document.getElementById("arm-update-banner")) return;

  const banner = document.createElement("div");
  banner.id = "arm-update-banner";
  banner.style.cssText = `
    position: fixed; top: 0; left: 0; right: 0; z-index: 9999;
    background: linear-gradient(135deg, #1d4ed8, #2563eb);
    color: white; padding: 14px 20px;
    display: flex; align-items: center; justify-content: space-between;
    box-shadow: 0 4px 16px rgba(0,0,0,0.25);
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    font-size: 14px; animation: slideDown 0.3s ease;
  `;

  // 카운트다운 타이머 (3초)
  let countdown = 3;
  banner.innerHTML = `
    <style>
      @keyframes slideDown { from { transform: translateY(-100%); } to { transform: translateY(0); } }
    </style>
    <span>🔄 <strong>새 버전 업데이트</strong> 중... <span id="arm-countdown">${countdown}</span>초 후 자동 적용</span>
    <button id="arm-update-now" style="
      background: white; color: #1d4ed8; border: none; border-radius: 8px;
      padding: 6px 14px; font-weight: bold; cursor: pointer; font-size: 13px;
    ">지금 업데이트</button>
  `;
  document.body.prepend(banner);

  // 지금 업데이트 버튼
  document.getElementById("arm-update-now")?.addEventListener("click", () => {
    applyUpdate(newWorker, banner);
  });

  // 3초 카운트다운 후 자동 업데이트
  const timer = setInterval(() => {
    countdown--;
    const el = document.getElementById("arm-countdown");
    if (el) el.textContent = countdown;
    if (countdown <= 0) {
      clearInterval(timer);
      applyUpdate(newWorker, banner);
    }
  }, 1000);
}

function applyUpdate(newWorker, banner) {
  banner?.remove();
  newWorker.postMessage({ type: "SKIP_WAITING" });
}

// ===== PWA 설치 프롬프트 관리 =====
let deferredInstallPrompt = null;

window.addEventListener("beforeinstallprompt", (e) => {
  e.preventDefault();
  deferredInstallPrompt = e;
  window.armInstallPrompt = deferredInstallPrompt;
  window.dispatchEvent(new CustomEvent("pwa-installable"));
});

window.addEventListener("appinstalled", () => {
  deferredInstallPrompt = null;
  window.armInstallPrompt = null;
  window.dispatchEvent(new CustomEvent("pwa-installed"));
});

// ===== 오프라인/온라인 상태 감지 =====
window.addEventListener("online", () => {
  window.dispatchEvent(new CustomEvent("arm-network-online"));
  // 온라인 복귀 시 업데이트 체크
  navigator.serviceWorker?.getRegistration("/").then((reg) => reg?.update());
});

window.addEventListener("offline", () => {
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

registerServiceWorker();
hideSplashScreen();
