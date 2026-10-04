const TONES = {
  info: 'border-brand/30 bg-brand-tint text-ink',
  warning: 'border-ochre/40 bg-ochre-tint text-ink',
  danger: 'border-brick/40 bg-brick-tint text-ink',
  success: 'border-sage/40 bg-sage-tint text-ink',
};

export default function Notice({ tone = 'info', title, children, className = '' }) {
  return (
    <div role={tone === 'danger' ? 'alert' : 'note'} className={`rounded-panel border px-3.5 py-2.5 text-[13.5px] leading-snug ${TONES[tone]} ${className}`}>
      {title && <p className="mb-0.5 font-semibold">{title}</p>}
      <div>{children}</div>
    </div>
  );
}
