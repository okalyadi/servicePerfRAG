"use client";

import { useEffect, useRef } from "react";

export default function MermaidDiagram({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!ref.current || !chart.trim()) return;

    let cancelled = false;

    import("mermaid").then((mod) => {
      if (cancelled) return;
      const mermaid = mod.default;
      mermaid.initialize({ startOnLoad: false, theme: "dark" });

      const id = `mermaid-${Math.random().toString(36).slice(2)}`;
      mermaid.render(id, chart.trim()).then(({ svg }) => {
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
        }
      }).catch(() => {
        if (!cancelled && ref.current) {
          ref.current.innerHTML = `<pre class="text-xs text-gray-300 whitespace-pre overflow-x-auto">${chart}</pre>`;
        }
      });
    });

    return () => { cancelled = true; };
  }, [chart]);

  return <div ref={ref} className="w-full overflow-x-auto" />;
}
