import { useRef, useState } from "react";
import { Check, Copy } from "lucide-react";
import Button from "@/shared/ui/Button";
import { FAQ_EXAMPLES, FAQ_EXAMPLE_GROUPS } from "./assistantExamples";

export default function FaqExamples() {
  const fields = useRef<(HTMLTextAreaElement | null)[]>([]);
  const [copied, setCopied] = useState<number>();
  const [message, setMessage] = useState("");
  async function copyQuestion(question: string, index: number) {
    try {
      await navigator.clipboard.writeText(question);
      setCopied(index);
      setMessage("Pergunta copiada. Cole no campo de mensagem do Assistente.");
    } catch {
      setCopied(undefined);
      fields.current[index]?.focus();
      fields.current[index]?.select();
      setMessage(
        "O texto está selecionado. Use a opção Copiar do seu dispositivo e cole no Assistente.",
      );
    }
  }
  return (
    <details className="rounded-xl border border-divider bg-canvas/50 p-4">
      <summary className="cursor-pointer text-base font-semibold text-content focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
        Perguntas prontas para usar no Assistente
      </summary>
      <div className="mt-4 grid gap-3">
        <p className="text-sm leading-6 text-muted">
          Copie uma pergunta, feche a ajuda e cole na conversa. Você pode
          ajustar o período e o município antes de enviar.
        </p>
        {FAQ_EXAMPLE_GROUPS.map((group) => (
          <details
            key={group.title}
            className="rounded-xl border border-divider bg-surface p-3"
          >
            <summary className="cursor-pointer text-sm font-semibold text-content focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-brand">
              {group.title} · {group.questions.length} perguntas
            </summary>
            <div className="mt-3 grid gap-3">
              {group.questions.map((question) => {
                const index = FAQ_EXAMPLES.indexOf(question);
                return (
                  <div
                    key={question}
                    className="grid gap-2 rounded-xl border border-divider bg-surface p-3"
                  >
                    <textarea
                      ref={(element) => {
                        fields.current[index] = element;
                      }}
                      readOnly
                      rows={3}
                      aria-label={`Pergunta de exemplo ${index + 1}`}
                      value={question}
                      onFocus={(event) => event.currentTarget.select()}
                      className="w-full resize-none rounded-lg bg-transparent p-1 text-base leading-6 text-content focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-brand"
                    />
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="min-h-11 w-fit text-sm"
                      aria-label={`Copiar pergunta ${index + 1}`}
                      onClick={() => void copyQuestion(question, index)}
                      leftIcon={
                        copied === index ? (
                          <Check aria-hidden="true" className="size-4" />
                        ) : (
                          <Copy aria-hidden="true" className="size-4" />
                        )
                      }
                    >
                      {copied === index ? "Copiada" : "Copiar pergunta"}
                    </Button>
                  </div>
                );
              })}
            </div>
          </details>
        ))}
        <p role="status" className="text-sm text-brand">
          {message}
        </p>
        <p className="text-xs leading-5 text-muted">
          O resultado considera seu acesso e os dados disponíveis no período
          solicitado.
        </p>
      </div>
    </details>
  );
}
