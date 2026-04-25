/** Component tests for FeedbackDialog.
 *
 * The radix-vue Dialog and Select components rely on portals + pointer-event
 * coercion that don't translate well to jsdom; we stub them with bare
 * passthrough components so the test focuses on the dialog's own logic
 * (decision toggle, suggestion-driven default, submit payload, error path).
 */
import { mount } from "@vue/test-utils";
import { ref } from "vue";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const mutateAsync = vi.fn();
const isPending = ref(false);

vi.mock("@/services/feedback", () => ({
  useSubmitFeedback: () => ({ mutateAsync, isPending }),
}));

vi.mock("@/components/ui/dialog", () => ({
  Dialog: {
    name: "Dialog",
    props: ["open"],
    emits: ["update:open"],
    template: '<div data-testid="dialog" :data-open="open"><slot /></div>',
  },
  DialogContent: { name: "DialogContent", template: "<div><slot /></div>" },
  DialogDescription: { name: "DialogDescription", template: "<div><slot /></div>" },
  DialogFooter: { name: "DialogFooter", template: "<div><slot /></div>" },
  DialogHeader: { name: "DialogHeader", template: "<div><slot /></div>" },
  DialogTitle: { name: "DialogTitle", template: "<h2><slot /></h2>" },
}));

vi.mock("@/components/ui/select", () => ({
  Select: {
    name: "Select",
    props: ["modelValue"],
    emits: ["update:modelValue"],
    template:
      '<div data-testid="final-action" :data-value="modelValue"><slot /></div>',
  },
  SelectContent: { name: "SelectContent", template: "<div><slot /></div>" },
  SelectItem: {
    name: "SelectItem",
    props: ["value"],
    template: '<div :data-value="value"><slot /></div>',
  },
  SelectTrigger: { name: "SelectTrigger", template: "<div><slot /></div>" },
  SelectValue: { name: "SelectValue", template: "<span></span>" },
}));

vi.mock("@/components/ui/label", () => ({
  Label: { name: "Label", template: "<label><slot /></label>" },
}));

vi.mock("@/components/ui/button", () => ({
  Button: {
    name: "Button",
    props: ["type", "variant", "disabled"],
    emits: ["click"],
    template:
      '<button :type="type ?? \'button\'" :data-variant="variant" ' +
      ':disabled="disabled" @click="$emit(\'click\', $event)"><slot /></button>',
  },
}));

import FeedbackDialog from "@/components/FeedbackDialog.vue";
import { ApiError } from "@/lib/api";
import type { AgentSuggestionResponse } from "@/types/api";

function buildSuggestion(
  overrides: Partial<AgentSuggestionResponse> = {},
): AgentSuggestionResponse {
  return {
    id: "sug-1",
    agentType: "analyst",
    action: "approve",
    confidence: 0.9,
    reasoning: "Looks fine",
    anomaliesDetected: [],
    phoenixTraceId: null,
    createdAt: "2026-04-25T10:00:00Z",
    ...overrides,
  };
}

const baseProps = () => ({
  open: true,
  orderId: "order-1",
  orderCode: "ORD-2026-04-000001",
  suggestion: buildSuggestion(),
});

beforeEach(() => {
  mutateAsync.mockReset();
  isPending.value = false;
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("FeedbackDialog", () => {
  it("pre-populates the final action from the suggestion when opened", async () => {
    const wrapper = mount(FeedbackDialog, {
      props: {
        ...baseProps(),
        open: false,
        suggestion: buildSuggestion({ action: "escalate" }),
      },
    });
    await wrapper.setProps({ open: true });
    await wrapper.vm.$nextTick();
    expect(
      wrapper.get('[data-testid="final-action"]').attributes("data-value"),
    ).toBe("escalate");
  });

  it("falls back to 'approve' when no suggestion is provided", async () => {
    const wrapper = mount(FeedbackDialog, {
      props: { ...baseProps(), open: false, suggestion: null },
    });
    await wrapper.setProps({ open: true });
    await wrapper.vm.$nextTick();
    expect(
      wrapper.get('[data-testid="final-action"]').attributes("data-value"),
    ).toBe("approve");
  });

  it("clicking a decision button highlights it as the active variant", async () => {
    const wrapper = mount(FeedbackDialog, { props: baseProps() });

    const decisionButtons = wrapper
      .findAll("button")
      .filter((b) => ["Accept", "Modify", "Reject"].some((l) => b.text().includes(l)));
    expect(decisionButtons).toHaveLength(3);

    expect(decisionButtons[0].attributes("data-variant")).toBe("default");
    await decisionButtons[2].trigger("click"); // Reject
    expect(decisionButtons[0].attributes("data-variant")).toBe("outline");
    expect(decisionButtons[2].attributes("data-variant")).toBe("default");
  });

  it("submits the expected payload and emits 'submitted' + close", async () => {
    mutateAsync.mockResolvedValueOnce({
      feedbackId: "fb-1",
      orderId: "order-1",
      newStatus: "approved",
      oldStatus: "pending_review",
    });

    const wrapper = mount(FeedbackDialog, { props: baseProps() });
    const textarea = wrapper.get("textarea");
    await textarea.setValue("  Looks good  ");
    await wrapper.get("form").trigger("submit");
    await wrapper.vm.$nextTick();
    await Promise.resolve();

    expect(mutateAsync).toHaveBeenCalledWith({
      orderId: "order-1",
      operatorDecision: "accepted",
      finalAction: "approve",
      operatorReason: "Looks good", // trimmed
    });
    expect(wrapper.emitted("submitted")).toHaveLength(1);
    expect(wrapper.emitted("update:open")).toEqual([[false]]);
  });

  it("sends a null operatorReason when the textarea is empty", async () => {
    mutateAsync.mockResolvedValueOnce({
      feedbackId: "fb-1",
      orderId: "order-1",
      newStatus: "approved",
      oldStatus: "pending_review",
    });

    const wrapper = mount(FeedbackDialog, { props: baseProps() });
    await wrapper.get("form").trigger("submit");
    await wrapper.vm.$nextTick();

    expect(mutateAsync.mock.calls[0][0].operatorReason).toBeNull();
  });

  it("renders the API error message when submission fails", async () => {
    mutateAsync.mockRejectedValueOnce(new ApiError(409, "Already reviewed"));

    const wrapper = mount(FeedbackDialog, { props: baseProps() });
    await wrapper.get("form").trigger("submit");
    await wrapper.vm.$nextTick();
    await Promise.resolve();
    await wrapper.vm.$nextTick();

    expect(wrapper.text()).toContain("Already reviewed");
    expect(wrapper.emitted("submitted")).toBeUndefined();
    expect(wrapper.emitted("update:open")).toBeUndefined();
  });

  it("disables the submit button while the mutation is pending", async () => {
    isPending.value = true;
    const wrapper = mount(FeedbackDialog, { props: baseProps() });
    const submit = wrapper.findAll("button").find((b) => b.attributes("type") === "submit");
    expect(submit?.attributes("disabled")).toBeDefined();
    expect(submit?.text()).toContain("Submitting");
  });
});
