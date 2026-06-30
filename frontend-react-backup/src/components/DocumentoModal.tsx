import { useEffect, useRef, useState, useId } from "react";
import { X, FileText, Printer } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import mermaid from "mermaid";

mermaid.initialize({
  startOnLoad: false,
  theme: "dark",
  securityLevel: "loose",
  themeVariables: {
    fontSize: "14px",
  },
});

function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const rawId = useId().replace(/[:]/g, "");
  const [error, setError] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const render = async () => {
      try {
        const { svg } = await mermaid.render(`mmd-${rawId}`, chart.trim());
        if (!cancelled && ref.current) {
          ref.current.innerHTML = svg;
          setError(false);
        }
      } catch {
        if (!cancelled) setError(true);
      }
    };
    render();
    return () => {
      cancelled = true;
    };
  }, [chart, rawId]);

  if (error) {
    return (
      <pre className="bg-bg border border-border rounded-lg p-3 text-xs text-muted overflow-x-auto whitespace-pre-wrap">
        {chart}
      </pre>
    );
  }

  return <div ref={ref} className="my-4 flex justify-center overflow-x-auto [&_svg]:max-w-full" />;
}

export function MarkdownDoc({ contenido }: { contenido: string }) {
  return (
    <div className="prose-doc text-sm text-text leading-relaxed">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-xl font-bold text-text mt-2 mb-3 pb-2 border-b border-border">{children}</h1>,
          h2: ({ children }) => <h2 className="text-base font-semibold text-accent mt-5 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-sm font-semibold text-text mt-3 mb-1.5">{children}</h3>,
          p: ({ children }) => <p className="mb-2.5 text-muted">{children}</p>,
          ul: ({ children }) => <ul className="list-disc pl-5 mb-2.5 space-y-1 text-muted">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal pl-5 mb-2.5 space-y-1 text-muted">{children}</ol>,
          li: ({ children }) => <li className="text-muted">{children}</li>,
          strong: ({ children }) => <strong className="text-text font-semibold">{children}</strong>,
          a: ({ href, children }) => (
            <a href={href} target="_blank" rel="noopener noreferrer" className="text-accent underline hover:opacity-80">
              {children}
            </a>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-accent/40 pl-3 italic text-muted my-2">{children}</blockquote>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full text-xs border-collapse">{children}</table>
            </div>
          ),
          thead: ({ children }) => <thead className="bg-card2">{children}</thead>,
          th: ({ children }) => <th className="border border-border px-3 py-2 text-left font-semibold text-text">{children}</th>,
          td: ({ children }) => <td className="border border-border px-3 py-2 text-muted align-top">{children}</td>,
          code: ({ className, children }) => {
            const match = /language-(\w+)/.exec(className || "");
            const lang = match?.[1];
            const value = String(children).replace(/\n$/, "");
            if (lang === "mermaid") {
              return <Mermaid chart={value} />;
            }
            if (className) {
              return (
                <pre className="bg-bg border border-border rounded-lg p-3 text-xs overflow-x-auto my-3">
                  <code>{value}</code>
                </pre>
              );
            }
            return <code className="bg-card2 px-1.5 py-0.5 rounded text-[0.85em] text-accent">{children}</code>;
          },
          hr: () => <hr className="border-border my-4" />,
        }}
      >
        {contenido}
      </ReactMarkdown>
    </div>
  );
}

interface Props {
  titulo: string;
  contenido: string;
  onClose: () => void;
}

export function DocumentoModal({ titulo, contenido, onClose }: Props) {
  return (
    <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/70 animate-fade-in p-3 sm:p-4" onClick={onClose}>
      <div
        className="bg-card border border-border rounded-2xl w-full max-w-3xl max-h-[92vh] flex flex-col animate-slide-up"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between px-5 py-3.5 border-b border-border">
          <div className="flex items-center gap-2 min-w-0">
            <FileText size={18} className="text-amber-300 min-w-4" />
            <h3 className="text-sm font-semibold truncate">{titulo}</h3>
          </div>
          <div className="flex items-center gap-1">
            <button onClick={() => window.print()} className="p-1.5 rounded-lg text-muted hover:text-text" title="Imprimir / PDF">
              <Printer size={18} />
            </button>
            <button onClick={onClose} className="p-1.5 rounded-lg text-muted hover:text-text">
              <X size={20} />
            </button>
          </div>
        </div>
        <div className="overflow-y-auto px-5 py-4">
          {contenido ? (
            <MarkdownDoc contenido={contenido} />
          ) : (
            <p className="text-sm text-muted text-center py-10">Esta tarea no tiene un informe asociado.</p>
          )}
        </div>
      </div>
    </div>
  );
}
