import { CultureLab } from "../components/culture-lab";

export default function Home() {
  return (
    <main className="shell">
      <header className="hero">
        <div className="eyebrow">QLOO-POWERED CULTURAL INTELLIGENCE</div>
        <h1>CultureOS</h1>
        <p className="lede">
          Stress-test a launch concept against real cross-domain cultural affinities,
          then see which recommendations remain stable when the evidence changes.
        </p>
        <div className="trustRow" aria-label="Product principles">
          <span>Aggregate signals only</span>
          <span>No personal profiling</span>
          <span>Evidence trace included</span>
        </div>
      </header>
      <CultureLab />
      <footer className="footer">
        Qloo affinities are aggregate cultural signals, not causal claims or predictions about an individual.
      </footer>
    </main>
  );
}
