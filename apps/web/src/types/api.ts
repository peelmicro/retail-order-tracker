/** Types that mirror the backend response shapes (camelCase via Pydantic alias). */

export type UserRole = "operator" | "admin";

export interface User {
  username: string;
  email: string;
  role: UserRole;
}

export interface LoginResponse {
  accessToken: string;
  tokenType: "bearer";
}

export interface ApiErrorShape {
  detail?: string;
}

// --- Domain enums (mirror src/domain/enums.py) ---------------------------

export type OrderStatus =
  | "pending_review"
  | "approved"
  | "clarification_requested"
  | "escalated"
  | "rejected_by_operator";

export type AgentAction = "approve" | "request_clarification" | "escalate";

export type OperatorDecision = "accepted" | "modified" | "rejected";

// --- Daily report --------------------------------------------------------

export interface RetailerCount {
  retailerCode: string;
  retailerName: string;
  ordersCount: number;
  totalAmount: number;
}

export interface DailyReport {
  fromDate: string;
  toDate: string;
  totalOrders: number;
  totalAmount: number;
  averageAmount: number;
  ordersByStatus: Record<string, number>;
  ordersByRetailer: RetailerCount[];
  ordersByAgentAction: Record<string, number>;
  suggestionsCount: number;
  feedbacksCount: number;
}

// --- Orders list + detail ------------------------------------------------

export interface OrderSummary {
  id: string;
  code: string;
  orderNumber: string;
  retailerCode: string;
  retailerName: string;
  supplierCode: string;
  supplierName: string;
  currencyCode: string;
  totalAmount: number;
  status: OrderStatus;
  orderDate: string;
  expectedDeliveryDate: string | null;
  hasSuggestion: boolean;
  suggestionAction: AgentAction | null;
  suggestionConfidence: number | null;
  hasFeedback: boolean;
  createdAt: string;
}

export interface OrderListResponse {
  items: OrderSummary[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface OrderLineItemResponse {
  lineNumber: number;
  productCode: string;
  productName: string | null;
  quantity: number;
  unitPrice: number;
  lineTotal: number;
}

export interface AgentSuggestionResponse {
  id: string;
  agentType: string;
  action: AgentAction;
  confidence: number;
  reasoning: string;
  anomaliesDetected: string[];
  phoenixTraceId: string | null;
  createdAt: string;
}

export interface AnalyseByOrderResponse {
  suggestionId: string;
  orderId: string;
  action: AgentAction;
  confidence: number;
  reasoning: string;
  anomaliesDetected: string[];
  phoenixTraceId: string | null;
  recentOrdersConsidered: number;
}

export interface FeedbackResponse {
  id: string;
  operatorDecision: OperatorDecision;
  finalAction: AgentAction;
  operatorReason: string | null;
  anomalyFeedback: Record<string, unknown>;
  createdAt: string;
}

export interface OrderDetailResponse {
  id: string;
  code: string;
  orderNumber: string;
  retailerCode: string;
  retailerName: string;
  supplierCode: string;
  supplierName: string;
  currencyCode: string;
  totalAmount: number;
  status: OrderStatus;
  orderDate: string;
  expectedDeliveryDate: string | null;
  rawPayload: Record<string, unknown>;
  documents: string[];
  lineItems: OrderLineItemResponse[];
  suggestion: AgentSuggestionResponse | null;
  feedback: FeedbackResponse | null;
  createdAt: string;
  updatedAt: string;
}

// --- Documents -----------------------------------------------------------

export interface DocumentResponse {
  id: string;
  code: string;
  filename: string;
  storagePath: string;
  presignedUrl: string | null;
}

// --- Feedback ------------------------------------------------------------

export interface FeedbackRequest {
  orderId: string;
  operatorDecision: OperatorDecision;
  finalAction: AgentAction;
  operatorReason?: string | null;
  anomalyFeedback?: Record<string, unknown>;
}

export interface FeedbackSubmittedResponse {
  feedbackId: string;
  orderId: string;
  newStatus: OrderStatus;
  oldStatus: OrderStatus;
}

// --- WebSocket events ----------------------------------------------------

export interface OrderCreatedEvent {
  eventType: "order.created";
  orderId: string;
  orderCode: string;
  retailerCode: string;
  retailerName: string;
  supplierCode: string;
  supplierName: string;
  currencyCode: string;
  totalAmount: number;
}

export interface OrderStatusChangedEvent {
  eventType: "order.status_changed";
  orderId: string;
  orderCode: string;
  oldStatus: OrderStatus;
  newStatus: OrderStatus;
  finalAction: AgentAction;
}

export type OrderEvent = OrderCreatedEvent | OrderStatusChangedEvent;
