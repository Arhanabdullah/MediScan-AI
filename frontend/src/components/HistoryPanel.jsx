import { useCallback, useEffect, useState } from "react";

import { deleteResult, fetchHistory, fetchResult } from "../services/api";

function formatDate(value) {
  try {
    return new Intl.DateTimeFormat(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

function HistoryPanel({ username, refreshKey, onOpenResult, onError }) {
  const [items, setItems] = useState([]);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    if (!username) {
      setItems([]);
      return;
    }

    setBusy(true);
    try {
      setItems(await fetchHistory());
      onError("");
    } catch (requestError) {
      onError(requestError.message);
    } finally {
      setBusy(false);
    }
  }, [username, onError]);

  useEffect(() => {
    load();
  }, [load, refreshKey]);

  const handleOpen = async (scanId) => {
    setBusy(true);
    try {
      onOpenResult(await fetchResult(scanId));
      onError("");
    } catch (requestError) {
      onError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (scanId) => {
    setBusy(true);
    try {
      await deleteResult(scanId);
      await load();
      onError("");
    } catch (requestError) {
      onError(requestError.message);
    } finally {
      setBusy(false);
    }
  };

  if (!username) {
    return (
      <section className="panel history-panel history-panel--empty">
        <div>
          <h2>Prescription history</h2>
          <p>Sign in to save scans, view past results, and delete records.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel history-panel">
      <div className="section-heading">
        <h2>Prescription history</h2>
        <span>{busy ? "Loading..." : `${items.length} saved`}</span>
      </div>

      {items.length === 0 ? (
        <p className="empty-inline">No saved scans yet. Analyze a prescription while signed in to create one.</p>
      ) : (
        <div className="history-list">
          {items.map((item) => (
            <article className="history-item" key={item.scan_id}>
              <div className="history-item__main">
                <strong>{item.filename}</strong>
                <span>{formatDate(item.created_at)}</span>
              </div>
              <div className="history-item__meta">
                <span>{item.medicine_count} medicine(s)</span>
                <span>{Math.round(item.overall_confidence * 100)}% confidence</span>
                {item.verified && <span className="history-item__tag">verified</span>}
              </div>
              <div className="history-item__actions">
                <button type="button" className="text-button" disabled={busy} onClick={() => handleOpen(item.scan_id)}>
                  Open
                </button>
                <button type="button" className="text-button text-button--danger" disabled={busy} onClick={() => handleDelete(item.scan_id)}>
                  Delete
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

export default HistoryPanel;
