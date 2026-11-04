import { beforeEach, describe, expect, it } from "vitest";
import {
  advanceAuthorizationGeneration,
  captureAuthorizationGeneration,
  currentAuthorizationGeneration,
} from "./authorization";

describe("geração da sessão", () => {
  beforeEach(() => advanceAuthorizationGeneration());

  it("invalida respostas iniciadas antes da troca de identidade", () => {
    const requestGeneration = captureAuthorizationGeneration();
    advanceAuthorizationGeneration();
    expect(currentAuthorizationGeneration()).not.toBe(requestGeneration);
  });
});
