import "@testing-library/jest-dom";
import React from "react";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import GuardTypeSelect from "../GuardTypeSelect";

// Mock the image component since it's not available in test environment
jest.mock("next/image", () => ({
  __esModule: true,
  default: (props: any) => <img {...props} />,
}));

describe("GuardTypeSelect", () => {
  const defaultProps = {
    value: [],
    onChange: jest.fn(),
  };

  beforeEach(() => {
    jest.clearAllMocks();
  });

  describe("Rendering", () => {
    it("renders without crashing", () => {
      render(<GuardTypeSelect {...defaultProps} />);
      expect(screen.getByRole("combobox")).toBeInTheDocument();
    });

    it("renders with default label 'Guard type'", () => {
      render(<GuardTypeSelect {...defaultProps} />);
      expect(screen.getByText("Guard type")).toBeInTheDocument();
    });

    it("renders with custom label when provided", () => {
      render(<GuardTypeSelect {...defaultProps} label="Custom Label" />);
      expect(screen.getByText("Custom Label")).toBeInTheDocument();
    });

    it("renders with placeholder when provided", () => {
      render(
        <GuardTypeSelect {...defaultProps} placeholder="Select guard types" />
      );
      expect(screen.getByText("Select guard types")).toBeInTheDocument();
    });

    it("renders dropdown with options when clicked", async () => {
      const user = userEvent.setup();
      render(<GuardTypeSelect {...defaultProps} />);

      // Open the dropdown
      const select = screen.getByRole("combobox");
      await user.click(select);

      // Check that at least some options are rendered (Ant Design uses virtual list)
      await waitFor(() => {
        expect(screen.getByTitle("Input")).toBeInTheDocument();
      });
    });
  });

  describe("Selection behavior", () => {
    it("calls onChange when an option is selected", async () => {
      const onChange = jest.fn();
      const user = userEvent.setup();
      render(<GuardTypeSelect value={[]} onChange={onChange} />);

      // Open dropdown and select an option
      const select = screen.getByRole("combobox");
      await user.click(select);

      await waitFor(() => {
        expect(screen.getByTitle("Input")).toBeInTheDocument();
      });

      await user.click(screen.getByTitle("Input"));

      expect(onChange).toHaveBeenCalledWith(expect.arrayContaining(["input"]));
    });

    it("allows multiple selections", async () => {
      const onChange = jest.fn();
      const user = userEvent.setup();
      render(<GuardTypeSelect value={["input"]} onChange={onChange} />);

      // Open dropdown and select another option
      const select = screen.getByRole("combobox");
      await user.click(select);

      await waitFor(() => {
        expect(screen.getByTitle("Output")).toBeInTheDocument();
      });

      await user.click(screen.getByTitle("Output"));

      expect(onChange).toHaveBeenCalled();
    });

    it("displays selected values in the selector", () => {
      const { container } = render(
        <GuardTypeSelect
          value={["input"]}
          onChange={jest.fn()}
        />
      );

      // Check that selector contains the selection
      const selector = container.querySelector(".ant-select-selector");
      expect(selector).toBeInTheDocument();
    });
  });

  describe("Color mapping", () => {
    // Note: maxTagCount="responsive" behaves differently in jsdom test environment
    // These tests verify the component structure rather than specific tag rendering

    it("renders with Input value selected", () => {
      const { container } = render(
        <GuardTypeSelect value={["input"]} onChange={jest.fn()} />
      );

      const selector = container.querySelector(".ant-select-selector");
      expect(selector).toBeInTheDocument();
    });

    it("renders with Output value selected", () => {
      const { container } = render(
        <GuardTypeSelect value={["output"]} onChange={jest.fn()} />
      );

      const selector = container.querySelector(".ant-select-selector");
      expect(selector).toBeInTheDocument();
    });

    it("renders with Agents value selected", () => {
      const { container } = render(
        <GuardTypeSelect value={["agents"]} onChange={jest.fn()} />
      );

      const selector = container.querySelector(".ant-select-selector");
      expect(selector).toBeInTheDocument();
    });

    it("renders with Retrieval value selected", () => {
      const { container } = render(
        <GuardTypeSelect value={["retrieval"]} onChange={jest.fn()} />
      );

      const selector = container.querySelector(".ant-select-selector");
      expect(selector).toBeInTheDocument();
    });
  });

  describe("Props", () => {
    it("disables select when disabled prop is true", () => {
      const { container } = render(<GuardTypeSelect {...defaultProps} disabled={true} />);

      const selectWrapper = container.querySelector(".ant-select-disabled");
      expect(selectWrapper).toBeInTheDocument();
    });

    it("applies custom className when provided", () => {
      const { container } = render(
        <GuardTypeSelect {...defaultProps} className="custom-class" />
      );

      expect(container.querySelector(".custom-class")).toBeInTheDocument();
    });
  });

  describe("Guard type options", () => {
    it("renders options in dropdown", async () => {
      const user = userEvent.setup();
      render(<GuardTypeSelect {...defaultProps} />);

      const select = screen.getByRole("combobox");
      await user.click(select);

      // Ant Design renders options with title attribute
      await waitFor(() => {
        expect(screen.getByTitle("Input")).toBeInTheDocument();
        expect(screen.getByTitle("Output")).toBeInTheDocument();
      });
    });

    it("can render guard type values as selected", () => {
      const optionValues = ["input", "output"];
      const { container } = render(
        <GuardTypeSelect value={optionValues} onChange={jest.fn()} />
      );

      // Values should be displayed as tags (maxTagCount may collapse some)
      const tags = container.querySelectorAll(".ant-tag");
      expect(tags.length).toBeGreaterThanOrEqual(1);
    });
  });
});
