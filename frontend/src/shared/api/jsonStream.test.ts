import { expect, it } from "vitest";
import { readJsonStream } from "./jsonStream";

it("remonta UTF-8 entre chunks e exige um único resultado final", async () => {
  const encoded = new TextEncoder().encode(
    '{"type":"data","status":200,"data":{"label":"Mês"}}\n{"type":"complete","status":200,"data":{"done":true}}\n',
  );
  const response = new Response(
    new ReadableStream({
      start(c) {
        for (const byte of encoded) c.enqueue(new Uint8Array([byte]));
        c.close();
      },
    }),
  );
  const data: unknown[] = [];
  expect(await readJsonStream(response, (v) => data.push(v))).toBe(
    '{"done":true}',
  );
  expect(data).toEqual([{ label: "Mês" }]);
});
it.each([
  '{"type":"data","status":200,"data":{}}\n',
  '{"type":"complete","status":200,"data":{}}\n{"type":"data","status":200,"data":{}}\n',
  "x".repeat(262145),
])(
  "recusa fluxo incompleto, evento após final ou excesso de bytes",
  async (text) => {
    await expect(
      readJsonStream(new Response(text), () => {}),
    ).rejects.toThrow();
  },
);
