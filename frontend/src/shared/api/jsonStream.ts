export class JsonStreamFailure extends Error {
  readonly status: number;
  readonly data?: unknown;
  constructor(status: number, data?: unknown) {
    super("A resposta progressiva não pôde ser concluída.");
    this.status = status;
    this.data = data;
  }
}

/** Bounded NDJSON transport. Domain decoding belongs to the caller. */
export async function readJsonStream(
  response: Response,
  onData: (value: unknown) => void,
) {
  if (!response.body) throw new JsonStreamFailure(502);
  const reader = response.body.getReader();
  const decoder = new TextDecoder("utf-8", { fatal: true });
  let buffer = "",
    bytes = 0,
    seenData = false,
    finished = false;
  let result: unknown;
  const accept = (line: string) => {
    if (!line.trim()) return;
    if (finished) throw new JsonStreamFailure(502);
    let frame: Record<string, unknown>;
    try {
      frame = JSON.parse(line);
    } catch {
      throw new JsonStreamFailure(502);
    }
    if (
      !frame ||
      typeof frame !== "object" ||
      Array.isArray(frame) ||
      Object.keys(frame).some((k) => !["type", "status", "data"].includes(k))
    )
      throw new JsonStreamFailure(502);
    if (
      frame.type === "error" &&
      Number.isInteger(frame.status) &&
      Number(frame.status) >= 400 &&
      Number(frame.status) <= 599
    )
      throw new JsonStreamFailure(Number(frame.status), frame.data);
    if (frame.status !== 200) throw new JsonStreamFailure(502);
    if (frame.type === "data" && !seenData) {
      seenData = true;
      onData(frame.data);
    } else if (frame.type === "complete") {
      finished = true;
      result = frame.data;
    } else throw new JsonStreamFailure(502);
  };
  try {
    while (true) {
      const { value, done } = await reader.read();
      bytes += value?.byteLength ?? 0;
      if (bytes > 262144) throw new JsonStreamFailure(502);
      buffer += decoder.decode(value, { stream: !done });
      let newline: number;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        accept(buffer.slice(0, newline));
        buffer = buffer.slice(newline + 1);
      }
      if (done) {
        accept(buffer);
        break;
      }
    }
    if (!finished) throw new JsonStreamFailure(502);
    return JSON.stringify(result);
  } finally {
    await reader.cancel().catch(() => {});
    reader.releaseLock();
  }
}
