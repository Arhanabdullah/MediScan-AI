import { useEffect, useState } from "react";

import { fetchModelInfo } from "../services/api";

const MODEL_LABELS = {
  medicine_corrector: "Medicine typo corrector",
  ner: "Prescription entity recogniser",
};

function ModelPanel() {
  const [info, setInfo] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    fetchModelInfo()
      .then((data) => {
        if (active) {
          setInfo(data);
        }
      })
      .catch((requestError) => {
        if (active) {
          setError(requestError.message);
        }
      });
    return () => {
      active = false;
    };
  }, []);

  if (error) {
    return (
      <section className="panel model-panel" aria-label="Model status">
        <p className="model-panel__note">Model status unavailable: {error}</p>
      </section>
    );
  }

  if (!info) {
    return (
      <section className="panel model-panel" aria-label="Model status">
        <p className="model-panel__note">Loading model status…</p>
      </section>
    );
  }

  const models = Object.entries(info.trained_models || {});

  return (
    <section className="panel model-panel" aria-labelledby="model-title">
      <div className="panel__heading panel__heading--split">
        <div>
          <span className="step">03</span>
          <h2 id="model-title">Model status</h2>
          <p>
            {info.name} · v{info.version} · OCR: {info.ocr_backend}
          </p>
        </div>
        <span className={`model-status ${info.trained_model ? "model-status--active" : ""}`}>
          {info.trained_model ? "Trained models active" : "Baseline pipeline"}
        </span>
      </div>

      <div className="model-grid">
        {models.map(([key, model]) => {
          const testMetrics = model.metrics?.test || {};
          return (
            <article className="model-card" key={key}>
              <div className="model-card__head">
                <strong>{MODEL_LABELS[key] || key}</strong>
                <span>v{model.version}</span>
              </div>
              <p className="model-card__method">{model.method}</p>
              <div className="model-card__flags">
                <span>{model.enabled ? "Enabled" : "Disabled by default"}</span>
                <span>{model.available ? "Artifact loaded" : "No active artifact"}</span>
              </div>
              {Object.keys(testMetrics).length > 0 && (
                <div className="model-card__metrics">
                  {Object.entries(testMetrics)
                    .filter(([, value]) => typeof value === "number")
                    .map(([name, value]) => (
                      <span key={name}>
                        {name}: {value}
                      </span>
                    ))}
                </div>
              )}
              <p className="model-card__note">{model.note}</p>
            </article>
          );
        })}
      </div>

      <p className="model-panel__note">{info.note} Not for clinical use.</p>
    </section>
  );
}

export default ModelPanel;
