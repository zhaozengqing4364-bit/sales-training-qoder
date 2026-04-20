import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ChatBubble } from "./chat-bubble";

describe("ChatBubble", () => {
  it("renders answer citations for ai messages when knowledge diagnostics are present", () => {
    render(
      <ChatBubble
        message="实习专家是一款企业内部智能演练平台。"
        sender="ai"
        timestamp="17:00"
        knowledgeAnswerDiagnostics={{
          mode: "grounded_strict",
          answerability: "sufficient",
          source_status: "hit",
          citations: [
            {
              knowledge_base_name: "产品知识库",
              document_title: "实习专家产品手册",
              snippet: "实习专家是一款面向企业内部训练的智能演练平台。",
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("知识库依据")).toBeTruthy();
    expect(screen.getByText("产品知识库 · 实习专家产品手册")).toBeTruthy();
    expect(screen.getByText("实习专家是一款面向企业内部训练的智能演练平台。")).toBeTruthy();
  });
});
