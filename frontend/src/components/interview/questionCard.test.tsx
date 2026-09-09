import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { AnswerPayload, InterviewQuestion } from "../../types";
import { QuestionCard } from "./QuestionCard";

const textQuestion: InterviewQuestion = {
  question_id: "hpi_005",
  section: "hpi",
  prompt_en: "Where exactly do you feel it?",
  prompt_hi: "यह ठीक कहाँ महसूस होता है?",
  input: "text",
  required: true,
  allow_other: false,
  choices: [],
};

describe("QuestionCard text mode", () => {
  it("defaults to typing and submits text", () => {
    const onSubmit = vi.fn();
    render(
      <QuestionCard
        question={textQuestion}
        language="en"
        onSubmit={(p: AnswerPayload) => onSubmit(p)}
      />,
    );

    const input = screen.getByPlaceholderText(/Type your answer/i);
    expect(input).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Continue" })).toBeDisabled();

    fireEvent.change(input, { target: { value: "Under the left ribs" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue" }));
    expect(onSubmit).toHaveBeenCalledWith({
      question_id: "hpi_005",
      text: "Under the left ribs",
    });
  });

  it("shows a graceful fallback when recording is unsupported (jsdom)", () => {
    render(
      <QuestionCard question={textQuestion} language="en" onSubmit={() => {}} />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Speak" }));
    expect(
      screen.getByText(/Voice recording is not supported/i),
    ).toBeInTheDocument();
    // Typing stays reachable.
    fireEvent.click(screen.getByRole("button", { name: "Type" }));
    expect(screen.getByPlaceholderText(/Type your answer/i)).toBeInTheDocument();
  });
});
