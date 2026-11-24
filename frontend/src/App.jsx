import { useEffect, useRef, useState } from "react";

import Disclaimer from "./components/Disclaimer";
import Header from "./components/Header";
import ResultsPanel from "./components/ResultsPanel";
import UploadPanel from "./components/UploadPanel";
import { scanPrescription, verifyPrescription } from "./services/api";

function App() {
  const [file, setFile] = useState(null);
  const [previewUrl, setPreviewUrl] = useState("");
  const [result, setResult] = useState(null);
  const [verification, setVerification] = useState(null);
  const [status, setStatus] = useState("idle");
  const [error, setError] = useState("");
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const handleSelect = (selectedFile) => {
    if (!selectedFile) {
      return;
    }

    if (!selectedFile.type.startsWith("image/")) {
      setError("Please choose an image file.");
      return;
    }

    if (selectedFile.size > 10 * 1024 * 1024) {
      setError("Image must be 10 MB or smaller.");
      return;
    }

    setFile(selectedFile);
    setPreviewUrl(URL.createObjectURL(selectedFile));
    setResult(null);
    setVerification(null);
    setError("");
  };

  const handleDrop = (event) => {
    handleSelect(event.dataTransfer.files?.[0]);
  };

  const handleAnalyze = async () => {
    if (!file) {
      return;
    }

    setStatus("scanning");
    setError("");
    setVerification(null);

    try {
      const data = await scanPrescription(file);
      setResult(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStatus("idle");
    }
  };

  const handleUpdateMedicine = (id, patch) => {
    setResult((current) => {
      if (!current) {
        return current;
      }
      return {
        ...current,
        medicines: current.medicines.map((medicine) =>
          medicine.id === id ? { ...medicine, ...patch } : medicine,
        ),
      };
    });
    setVerification(null);
  };

  const handleVerify = async () => {
    if (!result) {
      return;
    }

    setError("");
    setStatus("scanning");

    try {
      const data = await verifyPrescription({
        scan_id: result.scan_id,
        raw_text: result.raw_text,
        medicines: result.medicines.map((medicine) => ({
          id: medicine.id,
          name: medicine.name || medicine.matched_name,
          strength: medicine.strength || null,
          frequency: medicine.frequency || null,
          confirmed: true,
        })),
      });
      setVerification(data);
    } catch (requestError) {
      setError(requestError.message);
    } finally {
      setStatus("idle");
    }
  };

  return (
    <div className="app-shell">
      <Header />

      <main>
        <section className="hero">
          <div className="hero__copy">
            <span className="eyebrow">ML · DL · CV · OCR · NLP</span>
            <h1>Digitize prescriptions into structured medicine data.</h1>
            <p>
              Upload a prescription image to run preprocessing, OCR, entity extraction, fuzzy medicine
              matching, confidence scoring, and user verification.
            </p>
          </div>
          <div className="hero__stats">
            <div>
              <strong>5</strong>
              <span>pipeline stages</span>
            </div>
            <div>
              <strong>100%</strong>
              <span>user verified</span>
            </div>
          </div>
        </section>

        <div className="workspace">
          <UploadPanel
            file={file}
            previewUrl={previewUrl}
            status={status}
            onSelect={handleSelect}
            onDrop={handleDrop}
            onAnalyze={handleAnalyze}
            fileInputRef={fileInputRef}
            cameraInputRef={cameraInputRef}
          />
          <ResultsPanel
            result={result}
            error={error}
            status={status}
            verification={verification}
            onUpdateMedicine={handleUpdateMedicine}
            onVerify={handleVerify}
          />
        </div>

        <Disclaimer />
      </main>

      <footer className="site-footer">
        <span>MediScan-AI research prototype</span>
        <span>Not for clinical use</span>
      </footer>
    </div>
  );
}

export default App;
