import { parseDemoConstraints } from "./contextWeaverMcp";

describe("ContextWeaver explicit demo constraint extraction", () => {
  it("extracts the default demo budget and departure time without hidden context", () => {
    expect(
      parseDemoConstraints(
        "Help me make the next 45 minutes calm and productive. I need to leave by 07:42.",
      ),
    ).toEqual({ minutesAvailable: 45, departureTime: "07:42" });
  });

  it("supports hour expressions and normalizes AM/PM departure times", () => {
    expect(parseDemoConstraints("Plan the next 1.5 hours. I depart at 7:05 PM.")).toEqual({
      minutesAvailable: 90,
      departureTime: "19:05",
    });
  });

  it("does not invent a departure constraint when the user did not state one", () => {
    expect(parseDemoConstraints("Give me a focused plan for 30 mins.")).toEqual({
      minutesAvailable: 30,
    });
  });

  it("recognizes simple natural-language hour durations", () => {
    expect(parseDemoConstraints("I have half an hour to reset.")).toEqual({
      minutesAvailable: 30,
    });
    expect(parseDemoConstraints("I have an hour before the next task.")).toEqual({
      minutesAvailable: 60,
    });
  });

  it("combines hour and minute components instead of discarding the hours", () => {
    expect(
      parseDemoConstraints("Plan my next 1 hour and 30 minutes. I need to leave by 9:00 PM."),
    ).toEqual({
      minutesAvailable: 90,
      departureTime: "21:00",
    });
    expect(parseDemoConstraints("I have half an hour and 10 minutes to reset.")).toEqual({
      minutesAvailable: 40,
    });
  });

  it("preserves an explicit zero-minute constraint instead of inventing demo time", () => {
    expect(
      parseDemoConstraints("I have 0 minutes and must leave now. Do not schedule any actions."),
    ).toEqual({
      minutesAvailable: 0,
    });
  });

  it("fails safely to the bounded demo default for invalid explicit budgets", () => {
    expect(parseDemoConstraints("Plan the next 2 minutes.")).toEqual({
      minutesAvailable: 45,
    });
    expect(parseDemoConstraints("Plan the next 2000 minutes.")).toEqual({
      minutesAvailable: 45,
    });
  });
});