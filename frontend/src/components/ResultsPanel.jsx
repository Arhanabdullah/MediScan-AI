import ConfidenceBadge from "./ConfidenceBadge";

const ENTITY_LABELS = {
  medicine_names: "Medicine names",
  strengths: "Strengths",
  frequencies: "Frequency",
  durations: "Duration",
  forms: "Forms",
};

function ResultsPanel({ result, error, status, verification, onUpdateMedicine, onVerify }) {
  if (status === "scanning") {
    return (
      <section className="panel results-panel" aria-live="polite">
        <div className="state">
          <div className="spinner" />
          <h2>Processing prescription</h2>
          <p>Preprocessing image, running OCR, and extracting medicine entities.</p>
        </div>
      </section>
    );
  }

  if (error) {
    return (
      <section className="panel results-panel" role="alert">
        <div className="state state--error">
          <div className="state__icon">!</div>
          <h2>Unable to complete the request</h2>
          <p>{error}</p>
        </div>
      </section>
    );
  }

  if (!result) {
    return (
      <section className="panel results-panel">
        <div className="state">
          <div className="state__icon state__icon--muted">MS</div>
          <h2>Results will appear here</h2>
          <p>Upload a prescription image and run the extraction pipeline to see detected medicines.</p>
          <ol className="pipeline-list">
            <li>Image preprocessing</li>
            <li>OCR text extraction</li>
            <li>NLP entity recognition</li>
            <li>Fuzzy medicine matching</li>
            <li>User verification</li>
          </ol>
        </div>
      </section>
    );
  }

  const entities = Object.entries(result.entities).filter(([, items]) => items.length > 0);
  const verifiedMedicines = verification?.final_result?.medicines ?? [];

  return (
    <section className="panel results-panel" aria-labelledby="results-title">
      <div className="panel__heading panel__heading--split">
        <div>
          <span className="step">02</span>
          <h2 id="results-title">Extracted information</h2>
          <p>{result.filename} · OCR engine: {result.ocr_engine}</p>
        </div>
        <ConfidenceBadge value={result.overall_confidence} />
      </div>

      {verification && (
        <div className="notice notice--success">
          <strong>Verification saved</strong>
          <span>{verifiedMedicines.length} medicine(s) confirmed by the user.</span>
        </div>
      )}

      {result.warnings.length > 0 && (
        <div className="notice notice--warning">
          <strong>Processing notes</strong>
          <ul>
            {result.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      )}

      {entities.length > 0 && (
        <div className="entity-section">
          <h3>Detected entities</h3>
          <div className="entity-groups">
            {entities.map(([key, items]) => (
              <div className="entity-group" key={key}>
                <span>{ENTITY_LABELS[key] || key}</span>
                <div className="entity-chips">
                  {items.map((entity) => (
                    <span className="chip" key={`${key}-${entity.value}`} title={`Confidence: ${entity.confidence}`}>
                      {entity.value}
                    </span>
                  ))}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <details className="raw-text">
        <summary>Raw OCR text</summary>
        <pre>{result.raw_text || "No readable text detected."}</pre>
      </details>

      <div className="medicine-section">
        <div className="section-heading">
          <h3>Medicines</h3>
          <span>{result.medicines.length} found</span>
        </div>

        {result.medicines.length === 0 ? (
          <p className="empty-inline">No medicine names were detected. Try a clearer image.</p>
        ) : (
          <div className="medicine-list">
            {result.medicines.map((medicine, index) => (
              <article className="medicine-card" key={medicine.id}>
                <div className="medicine-card__head">
                  <span className="medicine-card__index">{index + 1}</span>
                  <div className="medicine-card__meta">
                    <span>Match score: {medicine.match_score}</span>
                    <span>Confidence: {medicine.confidence}</span>
                  </div>
                </div>

                <label className="field field--full">
                  <span>Medicine name</span>
                  <input
                    type="text"
                    value={medicine.name ?? medicine.matched_name}
                    onChange={(event) => onUpdateMedicine(medicine.id, { name: event.target.value })}
                  />
                </label>

                <div className="field-row">
                  <label className="field">
                    <span>Strength</span>
                    <input
                      type="text"
                      value={medicine.strength ?? ""}
                      onChange={(event) => onUpdateMedicine(medicine.id, { strength: event.target.value })}
                    />
                  </label>
                  <label className="field">
                    <span>Frequency</span>
                    <input
                      type="text"
                      placeholder="Not detected"
                      value={medicine.frequency ?? ""}
                      onChange={(event) => onUpdateMedicine(medicine.id, { frequency: event.target.value })}
                    />
                  </label>
                </div>

                {medicine.alternatives.length > 0 && (
                  <p className="medicine-card__alternatives">
                    Other suggestions: {medicine.alternatives.join(", ")}
                  </p>
                )}
              </article>
            ))}
          </div>
        )}
      </div>

      <button
        type="button"
        className="button button--primary button--wide"
        disabled={result.medicines.length === 0}
        onClick={onVerify}
      >
        Confirm extracted medicines
      </button>
    </section>
  );
}

export default ResultsPanel;
