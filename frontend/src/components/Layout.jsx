import React from 'react';

export function PageShell({ id, className = '', children }) {
  return <main id={id} className={`page-shell ${className}`.trim()}>{children}</main>;
}

export function PageHeader({ title, eyebrow = 'Basketball Brawl', meta }) {
  return <header className="page-header">
    <div><p className="page-eyebrow">{eyebrow}</p><h1>{title}</h1></div>
    {meta && <p className="page-meta">{meta}</p>}
  </header>;
}

export function SectionHeader({ title, meta, achievement }) {
  return <div className="section-title">
    <h2>{title}</h2>
    {(achievement || meta) && <span className={achievement ? 'achievement' : ''}>{achievement || meta}</span>}
  </div>;
}

export function Section({ title, meta, achievement, className = '', children }) {
  return <section className={`home-section ${className}`.trim()}>
    <SectionHeader title={title} meta={meta} achievement={achievement}/>
    {children}
  </section>;
}

export function Card({ as: Element = 'div', title, className = '', children }) {
  return <Element className={`content-card ${className}`.trim()}>
    {title && <h3 className="card-title">{title}</h3>}
    {children}
  </Element>;
}

export function TableCard({ children, className = '' }) {
  return <div className={`content-card table-card ${className}`.trim()}>{children}</div>;
}
