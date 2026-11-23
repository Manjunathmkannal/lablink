import { useState } from "react";
import { Sparkles, X, Send, Loader2 } from "lucide-react";
import { aiRecommend, aiSlots, aiDraft } from "../../api/aiApi";
import toast from "react-hot-toast";

const MODES = [
  { key: "recommend", label: "Find Equipment" },
  { key: "slots",     label: "Suggest Slots"  },
  { key: "draft",     label: "Draft Request"  },
];

export default function AIAssistant({ onClose }) {
  const [mode, setMode]       = useState("recommend");
  const [input, setInput]     = useState("");
  const [result, setResult]   = useState(null);
  const [loading, setLoading] = useState(false);

  const placeholders = {
    recommend: "Describe your project — e.g. 'I need a microcontroller for a robotics project'",
    slots:     "Describe when you need equipment — e.g. 'Arduino, 2 hours, next week'",
    draft:     "Describe your project so I can draft a request for you",
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;
    setLoading(true);
    setResult(null);
    try {
      let res;
      if (mode === "recommend") res = await aiRecommend({ query: input });
      else if (mode === "slots")  res = await aiSlots({ description: input });
      else                         res = await aiDraft({ description: input });
      setResult(res.data);
    } catch {
      toast.error("AI assistant unavailable — please try again");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-end p-4 sm:p-6 pointer-events-none">
      <div className="pointer-events-auto w-full max-w-md bg-white rounded-2xl shadow-2xl border border-gray-200 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 bg-gradient-to-r from-purple-600 to-blue-600 text-white">
          <div className="flex items-center gap-2">
            <Sparkles size={20} />
            <span className="font-semibold text-sm">AI Lab Assistant</span>
            <span className="text-xs bg-white/20 rounded px-1.5 py-0.5">Beta</span>
          </div>
          {onClose && (
            <button onClick={onClose} className="p-1 rounded hover:bg-white/20">
              <X size={16} />
            </button>
          )}
        </div>

        {/* Mode tabs */}
        <div className="flex border-b border-gray-100 bg-gray-50">
          {MODES.map((m) => (
            <button key={m.key} onClick={() => { setMode(m.key); setResult(null); setInput(""); }}
              className={`flex-1 py-2.5 text-xs font-medium transition-colors ${
                mode === m.key ? "text-primary border-b-2 border-primary bg-white" : "text-gray-500 hover:text-gray-700"
              }`}>
              {m.label}
            </button>
          ))}
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3 min-h-[200px] max-h-[380px]">
          {!result && !loading && (
            <p className="text-xs text-gray-400 text-center pt-6">
              {mode === "recommend" && "Tell me what your project needs and I'll suggest matching equipment."}
              {mode === "slots"     && "Describe your scheduling needs and I'll suggest available time slots."}
              {mode === "draft"     && "Describe your project and I'll prepare a formatted equipment request."}
            </p>
          )}
          {loading && (
            <div className="flex items-center justify-center pt-10">
              <Loader2 size={28} className="animate-spin text-primary" />
            </div>
          )}
          {result && (
            <div className="space-y-3 text-sm">
              {/* Recommendation mode */}
              {mode === "recommend" && result.recommendations && (
                <div>
                  <p className="font-medium text-gray-700 mb-2">Recommended Equipment:</p>
                  {result.recommendations.map((r, i) => (
                    <div key={i} className="bg-purple-50 rounded-lg p-3 mb-2">
                      <p className="font-medium text-purple-900">{r.name || r}</p>
                      {r.reason && <p className="text-xs text-purple-700 mt-1">{r.reason}</p>}
                    </div>
                  ))}
                  {result.explanation && (
                    <p className="text-xs text-gray-500 mt-2 italic">{result.explanation}</p>
                  )}
                </div>
              )}
              {/* Text-only result (slots, draft) */}
              {(mode === "slots" || mode === "draft") && (
                <div className="bg-blue-50 rounded-lg p-3 text-blue-900 whitespace-pre-line leading-relaxed text-xs">
                  {result.slots_suggestion || result.draft || result.message || JSON.stringify(result)}
                </div>
              )}
              {/* Fallback */}
              {mode === "recommend" && !result.recommendations && (
                <div className="bg-gray-50 rounded-lg p-3 text-gray-700 whitespace-pre-line text-xs">
                  {result.message || JSON.stringify(result)}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Input */}
        <form onSubmit={handleSubmit} className="p-3 border-t border-gray-100 flex gap-2">
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={placeholders[mode]}
            className="input text-sm flex-1"
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}
            className="btn-primary px-3 py-2 disabled:opacity-50">
            <Send size={16} />
          </button>
        </form>

        <p className="text-center text-xs text-gray-400 pb-2 px-4">
          AI is advisory only — it cannot approve bookings or override availability.
        </p>
      </div>
    </div>
  );
}
