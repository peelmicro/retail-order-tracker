/** Component tests for RunAnalysisButton.
 *
 * Mocks the @/services/agents mutation so we can drive its lifecycle
 * states from the test, and stubs the Button + icon imports so the test
 * works in jsdom without pulling in radix internals.
 */
import { mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// vi.mock factories are hoisted above local consts. Use vi.hoisted() so the
// shared spies are created in the same hoisted phase and are visible to both
// the factory and the test body. `isPending` is a ref-shaped object rather
// than a real Vue ref — the component reads `.value` once at render time,
// so we just set it before each mount instead of relying on reactivity.
const { mutateAsync, toastSuccess, toastError, isPending } = vi.hoisted(() => ({
  mutateAsync: vi.fn(),
  toastSuccess: vi.fn(),
  toastError: vi.fn(),
  isPending: { value: false },
}));

vi.mock("@/services/agents", () => ({
  useRunAnalystOnOrder: () => ({ mutateAsync, isPending }),
}));

vi.mock("vue-sonner", () => ({
  toast: { success: toastSuccess, error: toastError },
}));

vi.mock("@/components/ui/button", () => ({
  Button: {
    name: "Button",
    props: ["variant", "size", "disabled"],
    emits: ["click"],
    template:
      '<button :data-variant="variant" :data-size="size" :disabled="disabled" ' +
      "@click=\"$emit('click', $event)\"><slot /></button>",
  },
}));

vi.mock("lucide-vue-next", () => ({
  Sparkles: { name: "Sparkles", template: "<span />" },
}));

import RunAnalysisButton from "@/components/RunAnalysisButton.vue";
import { ApiError } from "@/lib/api";

beforeEach(() => {
  mutateAsync.mockReset();
  toastSuccess.mockReset();
  toastError.mockReset();
  isPending.value = false;
});

afterEach(() => {
  vi.clearAllMocks();
});

describe("RunAnalysisButton", () => {
  it("renders the idle label by default", () => {
    const wrapper = mount(RunAnalysisButton, {
      props: { orderId: "o-1", orderCode: "ORD-1" },
    });
    expect(wrapper.text()).toContain("Run analysis");
    expect(wrapper.get("button").attributes("disabled")).toBeUndefined();
  });

  it("shows the pending label and disables the button while running", () => {
    isPending.value = true;
    const wrapper = mount(RunAnalysisButton, {
      props: { orderId: "o-1" },
    });
    expect(wrapper.text()).toContain("Analysing");
    expect(wrapper.get("button").attributes("disabled")).toBeDefined();
  });

  it("calls mutateAsync with the order id and stops event propagation on click", async () => {
    mutateAsync.mockResolvedValueOnce({
      suggestionId: "s-1",
      orderId: "o-1",
      action: "escalate",
      confidence: 0.94,
      reasoning: "outliers",
      anomaliesDetected: [],
      phoenixTraceId: null,
      recentOrdersConsidered: 12,
    });

    const wrapper = mount(RunAnalysisButton, {
      props: { orderId: "o-1", orderCode: "ORD-2026-04-CB4EAD" },
    });

    const stopPropagation = vi.fn();
    await wrapper.get("button").trigger("click", { stopPropagation });
    await Promise.resolve();
    await Promise.resolve();

    expect(stopPropagation).toHaveBeenCalled();
    expect(mutateAsync).toHaveBeenCalledWith("o-1");
    expect(toastSuccess).toHaveBeenCalledTimes(1);
    expect(toastSuccess.mock.calls[0][0]).toContain("ORD-2026-04-CB4EAD");
    expect(toastSuccess.mock.calls[0][1].description).toContain("escalate");
    expect(toastSuccess.mock.calls[0][1].description).toContain("94%");
    expect(wrapper.emitted("completed")).toHaveLength(1);
  });

  it("surfaces ApiError messages via the error toast and does not emit 'completed'", async () => {
    mutateAsync.mockRejectedValueOnce(new ApiError(503, "Anthropic timeout"));

    const wrapper = mount(RunAnalysisButton, {
      props: { orderId: "o-1" },
    });
    await wrapper.get("button").trigger("click");
    await Promise.resolve();
    await Promise.resolve();

    expect(toastError).toHaveBeenCalledWith("Analyst run failed", {
      description: "Anthropic timeout",
    });
    expect(toastSuccess).not.toHaveBeenCalled();
    expect(wrapper.emitted("completed")).toBeUndefined();
  });
});
