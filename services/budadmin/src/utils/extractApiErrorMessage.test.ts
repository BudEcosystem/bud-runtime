import { describe, it, expect } from "vitest";
import { extractApiErrorMessage } from "./extractApiErrorMessage";

describe("extractApiErrorMessage", () => {
  const fallback = "Something went wrong";

  it("returns the first msg from a Pydantic validation error array (422)", () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "name"],
              msg: "Value error, Prompt name can only contain alphanumeric characters",
              input: "dep_dep",
              ctx: {},
            },
          ],
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Prompt name can only contain alphanumeric characters"
    );
  });

  it("joins multiple Pydantic validation error messages", () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "name"],
              msg: "Name is required",
            },
            {
              type: "value_error",
              loc: ["body", "tags"],
              msg: "At least one tag is required",
            },
          ],
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Name is required. At least one tag is required"
    );
  });

  it("handles detail as a plain string (HTTPException)", () => {
    const error = {
      response: {
        data: {
          detail: "Agent with this name already exists",
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Agent with this name already exists"
    );
  });

  it("handles detail as an object with error field", () => {
    const error = {
      response: {
        data: {
          detail: {
            error: "Invalid configuration provided",
          },
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Invalid configuration provided"
    );
  });

  it("handles detail as an object with message field", () => {
    const error = {
      response: {
        data: {
          detail: {
            message: "Deployment failed due to resource limits",
          },
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Deployment failed due to resource limits"
    );
  });

  it("handles detail.errors array format", () => {
    const error = {
      response: {
        data: {
          detail: {
            error: "Validation failed",
            errors: ["Name too long", "Invalid characters"],
          },
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Name too long. Invalid characters"
    );
  });

  it("handles top-level message field (ClientException)", () => {
    const error = {
      response: {
        data: {
          message: "Service unavailable",
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Service unavailable"
    );
  });

  it("handles top-level msg field", () => {
    const error = {
      response: {
        data: {
          msg: "Value error, Prompt name can only contain letters",
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(
      "Value error, Prompt name can only contain letters"
    );
  });

  it("falls back to axios error message", () => {
    const error = {
      message: "Network Error",
    };
    expect(extractApiErrorMessage(error, fallback)).toBe("Network Error");
  });

  it("returns fallback when no error info is available", () => {
    expect(extractApiErrorMessage({}, fallback)).toBe(fallback);
    expect(extractApiErrorMessage(null, fallback)).toBe(fallback);
    expect(extractApiErrorMessage(undefined, fallback)).toBe(fallback);
  });

  it("handles empty detail array gracefully", () => {
    const error = {
      response: {
        data: {
          detail: [],
        },
      },
    };
    expect(extractApiErrorMessage(error, fallback)).toBe(fallback);
  });

  it("strips 'Value error, ' prefix from Pydantic messages for cleaner display", () => {
    const error = {
      response: {
        data: {
          detail: [
            {
              type: "value_error",
              loc: ["body", "name"],
              msg: "Value error, Prompt name can only contain alphanumeric characters and underscores",
            },
          ],
        },
      },
    };
    const result = extractApiErrorMessage(error, fallback);
    expect(result).toBe(
      "Prompt name can only contain alphanumeric characters and underscores"
    );
  });
});
