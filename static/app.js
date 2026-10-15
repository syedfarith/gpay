const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanels = {
  upload: document.getElementById("tab-upload"),
  camera: document.getElementById("tab-camera"),
};

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    tabButtons.forEach((b) => b.classList.remove("active"));
    btn.classList.add("active");
    Object.entries(tabPanels).forEach(([key, panel]) => {
      panel.classList.toggle("hidden", key !== btn.dataset.tab);
    });
    if (btn.dataset.tab !== "camera") stopCamera();
  });
});

async function handleApiResponse(res) {
  if (res.status === 401) {
    window.location.href = "/login";
    throw new Error("Session expired - redirecting to sign in");
  }
  return res;
}

const scanStatus = document.getElementById("scanStatus");
const payeeNameInput = document.getElementById("payeeName");
const payeeVpaInput = document.getElementById("payeeVpa");
const amountInput = document.getElementById("amount");
const noteInput = document.getElementById("note");
const rawUpiInput = document.getElementById("rawUpi");

function setStatus(msg, kind) {
  scanStatus.textContent = msg;
  scanStatus.className = "status" + (kind ? " " + kind : "");
}

function fillForm(data) {
  payeeNameInput.value = data.payee_name || "";
  payeeVpaInput.value = data.payee_vpa || "";
  if (data.amount) amountInput.value = data.amount;
  noteInput.value = data.note || "";
  rawUpiInput.value = data.raw || "";
}

// ---- Upload flow ----
document.getElementById("uploadScanBtn").addEventListener("click", async () => {
  const fileInput = document.getElementById("fileInput");
  if (!fileInput.files.length) {
    setStatus("Choose an image file first.", "error");
    return;
  }
  const formData = new FormData();
  formData.append("qr_image", fileInput.files[0]);

  setStatus("Scanning image...", "");
  try {
    const res = await handleApiResponse(await fetch("/api/scan-image", { method: "POST", body: formData }));
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Scan failed");
    fillForm(data);
    setStatus(`Decoded: ${data.payee_name} (${data.payee_vpa})`, "ok");
  } catch (err) {
    setStatus(err.message, "error");
  }
});

// ---- Camera flow ----
const video = document.getElementById("video");
const canvas = document.getElementById("canvas");
const startCamBtn = document.getElementById("startCamBtn");
const stopCamBtn = document.getElementById("stopCamBtn");
const camStatus = document.getElementById("camStatus");

let stream = null;
let scanLoopId = null;

async function startCamera() {
  try {
    stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: "environment" } });
    video.srcObject = stream;
    await video.play();
    startCamBtn.disabled = true;
    stopCamBtn.disabled = false;
    camStatus.textContent = "Scanning for a QR code...";
    scanLoop();
  } catch (err) {
    camStatus.textContent = "Could not access camera: " + err.message;
  }
}

function stopCamera() {
  if (scanLoopId) cancelAnimationFrame(scanLoopId);
  scanLoopId = null;
  if (stream) {
    stream.getTracks().forEach((t) => t.stop());
    stream = null;
  }
  startCamBtn.disabled = false;
  stopCamBtn.disabled = true;
  camStatus.textContent = "Camera is off.";
}

function scanLoop() {
  if (video.readyState === video.HAVE_ENOUGH_DATA) {
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    const ctx = canvas.getContext("2d");
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
    const imageData = ctx.getImageData(0, 0, canvas.width, canvas.height);
    const code = jsQR(imageData.data, imageData.width, imageData.height);
    if (code && code.data) {
      camStatus.textContent = "QR detected, decoding...";
      stopCamera();
      decodeRaw(code.data);
      return;
    }
  }
  scanLoopId = requestAnimationFrame(scanLoop);
}

async function decodeRaw(raw) {
  setStatus("Decoding scanned data...", "");
  try {
    const res = await handleApiResponse(
      await fetch("/api/decode-upi", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ raw }),
      })
    );
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Decode failed");
    fillForm(data);
    setStatus(`Decoded: ${data.payee_name} (${data.payee_vpa})`, "ok");
  } catch (err) {
    setStatus(err.message, "error");
  }
}

startCamBtn.addEventListener("click", startCamera);
stopCamBtn.addEventListener("click", stopCamera);

// ---- Generate receipt ----
const receiptImg = document.getElementById("receiptImg");
const previewPlaceholder = document.getElementById("previewPlaceholder");
const downloadLink = document.getElementById("downloadLink");

document.getElementById("detailsForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const generateBtn = document.getElementById("generateBtn");
  generateBtn.disabled = true;
  generateBtn.textContent = "Generating...";

  try {
    const res = await handleApiResponse(
      await fetch("/api/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          payee_name: payeeNameInput.value,
          payee_vpa: payeeVpaInput.value,
          amount: amountInput.value,
          note: noteInput.value,
          raw: rawUpiInput.value,
        }),
      })
    );
    if (!res.ok) {
      const data = await res.json();
      throw new Error(data.error || "Generation failed");
    }
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    receiptImg.src = url;
    receiptImg.classList.remove("hidden");
    previewPlaceholder.classList.add("hidden");
    downloadLink.href = url;
    downloadLink.classList.remove("hidden");
  } catch (err) {
    setStatus(err.message, "error");
  } finally {
    generateBtn.disabled = false;
    generateBtn.textContent = "Generate demo receipt";
  }
});
