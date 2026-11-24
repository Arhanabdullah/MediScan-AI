import { useState } from "react";

function UploadPanel({
  file,
  previewUrl,
  status,
  onSelect,
  onDrop,
  onAnalyze,
  fileInputRef,
  cameraInputRef,
}) {
  const [dragging, setDragging] = useState(false);
  const busy = status === "scanning";

  const handleInput = (event) => {
    onSelect(event.target.files?.[0]);
    event.target.value = "";
  };

  const handleDrop = (event) => {
    event.preventDefault();
    setDragging(false);
    onDrop(event);
  };

  return (
    <section className="panel upload-panel" aria-labelledby="upload-title">
      <div className="panel__heading">
        <span className="step">01</span>
        <div>
          <h2 id="upload-title">Upload prescription</h2>
          <p>Choose an image or capture one with your camera.</p>
        </div>
      </div>

      <div
        className={`dropzone${dragging ? " dropzone--active" : ""}${previewUrl ? " dropzone--has-file" : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        <input
          ref={fileInputRef}
          className="visually-hidden"
          type="file"
          accept="image/*"
          onChange={handleInput}
          aria-label="Choose a prescription image"
        />
        <input
          ref={cameraInputRef}
          className="visually-hidden"
          type="file"
          accept="image/*"
          capture="environment"
          onChange={handleInput}
          aria-label="Capture a prescription image"
        />

        {previewUrl ? (
          <div className="preview">
            <img src={previewUrl} alt="Selected prescription preview" />
            <div className="preview__caption">
              <span className="preview__name">{file?.name}</span>
              <button type="button" className="text-button" onClick={() => fileInputRef.current?.click()}>
                Replace
              </button>
            </div>
          </div>
        ) : (
          <div className="dropzone__empty">
            <div className="dropzone__icon">+</div>
            <strong>Drag and drop an image here</strong>
            <span>PNG, JPEG, WEBP, BMP, or TIFF up to 10 MB</span>
            <div className="dropzone__actions">
              <button type="button" className="button button--primary" onClick={() => fileInputRef.current?.click()}>
                Choose image
              </button>
              <button type="button" className="button button--ghost" onClick={() => cameraInputRef.current?.click()}>
                Use camera
              </button>
            </div>
          </div>
        )}
      </div>

      <button
        type="button"
        className="button button--primary button--wide"
        disabled={!file || busy}
        onClick={onAnalyze}
      >
        {busy ? "Analyzing image..." : "Analyze prescription"}
      </button>
    </section>
  );
}

export default UploadPanel;
