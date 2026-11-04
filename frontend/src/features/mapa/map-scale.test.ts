import { describe, expect, it } from "vitest";
import { classifyMapValues } from "./map-scale";

describe("classifyMapValues", () => {
  it("distinguishes known zero, positive and negative sequential values", () => {
    const scale = classifyMapValues([10, 20], "absolute");
    expect(scale.classify(0).state).toBe("observed");
    expect(scale.classify(0).color).toBeTruthy();
    expect(scale.classify(10).state).toBe("observed");
    expect(scale.classify(null).state).toBe("missing");
    expect(scale.classify(Number.NaN).state).toBe("missing");
  });

  it("centers change values around zero and provides a neutral scale for equal values", () => {
    const scale = classifyMapValues([-20, 0, 10], "diverging");
    expect(scale.classify(-20).color).not.toBe(scale.classify(10).color);
    expect(scale.classify(0).color).toBeTruthy();
    expect(classifyMapValues([4, 4], "absolute").classify(4).state).toBe(
      "observed",
    );
  });

  it("marks partial coverage apart from absent and zero values", () => {
    const scale = classifyMapValues([null, 0, 8], "absolute", new Set(["a"]));
    expect(scale.classify(0, "a").state).toBe("partial");
    expect(scale.classify(0, "b").state).toBe("observed");
    expect(scale.classify(null).state).toBe("missing");
    expect(
      classifyMapValues([null, null], "absolute").classify(null).state,
    ).toBe("missing");
    const partialZero = scale.classify(0, "a");
    expect(partialZero.state).toBe("partial");
    expect(partialZero.label).toContain("Zero observado");
    expect(partialZero.color).toBe("--map-zero");
  });

  it("handles all-zero and all-equal values without division by zero", () => {
    const zero = classifyMapValues([0, 0], "diverging");
    expect(zero.min).toBe(0);
    expect(zero.max).toBe(0);
    expect(zero.classify(0).color).toBe("--map-zero");
    const equal = classifyMapValues([4, 4], "absolute");
    expect(equal.classify(4).color).toBeTruthy();
  });
});
