function ConfidenceBadge({ value, label = "Overall confidence" }) {
  const percent = Math.round(value * 100);
  const tone = percent >= 80 ? "high" : percent >= 55 ? "medium" : "low";

  return (
    <div className={`confidence confidence--${tone}`}>
      <div className="confidence__head">
        <span>{label}</span>
        <strong>{percent}%</strong>
      </div>
      <div className="confidence__bar">
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  );
}

export default ConfidenceBadge;
