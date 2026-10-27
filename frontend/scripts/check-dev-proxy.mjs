import assert from "node:assert/strict";
import { createServer as createHttpServer } from "node:http";
import { test } from "node:test";
import { createServer, loadConfigFromFile } from "vite";

test("proxy nunca injeta credenciais e preserva a identidade enviada pelo cliente", async (t) => {
  const previous = process.env.ORDERS_DEV_PROXY_TOKEN;
  process.env.ORDERS_DEV_PROXY_TOKEN =
    "synthetic-old-proxy-token-never-forward";
  t.after(() => {
    if (previous === undefined) delete process.env.ORDERS_DEV_PROXY_TOKEN;
    else process.env.ORDERS_DEV_PROXY_TOKEN = previous;
  });
  const upstream = createHttpServer((req, res) => {
    const authorized =
      req.headers.authorization === "Bearer synthetic-user-token";
    res.writeHead(authorized ? 200 : 401, {
      "Content-Type": "application/json",
    });
    res.end(JSON.stringify({ authorized }));
  });
  await new Promise((resolve) => upstream.listen(0, "127.0.0.1", resolve));
  t.after(() => {
    upstream.closeAllConnections();
    return new Promise((resolve) => upstream.close(resolve));
  });
  const config = await loadConfigFromFile({}, "vite.config.ts");
  assert.ok(config);
  assert.equal(config.config.server.host, "127.0.0.1");
  const rule = config.config.server.proxy["/api"];
  const vite = await createServer({
    configFile: false,
    logLevel: "silent",
    server: {
      host: "127.0.0.1",
      port: 0,
      proxy: {
        "/api": {
          ...rule,
          target: `http://127.0.0.1:${upstream.address().port}`,
        },
      },
    },
  });
  await vite.listen();
  t.after(() => vite.close());
  const base = `http://127.0.0.1:${vite.httpServer.address().port}`;
  for (const origin of [undefined, base, "https://attacker.invalid"]) {
    for (const path of [
      "/api/v1/inspections/orders",
      "/api/v1/inspections/queue/UC-1004/orders",
    ]) {
      const res = await fetch(base + path, {
        method: "POST",
        headers: origin ? { Origin: origin } : {},
        body: "{}",
      });
      assert.equal(res.status, 401);
      assert.deepEqual(await res.json(), { authorized: false });
    }
  }
  const authenticated = await fetch(base + "/api/v1/inspections/orders", {
    headers: { Authorization: "Bearer synthetic-user-token" },
  });
  assert.equal(authenticated.status, 200);
  assert.deepEqual(await authenticated.json(), { authorized: true });
});
