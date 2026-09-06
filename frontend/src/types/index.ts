// ─── Enums ────────────────────────────────────────────────────────────────────

export type OrderStatus =
  | "draft"
  | "confirmed"
  | "in_progress"
  | "partially_delivered"
  | "delivered"
  | "cancelled"
  | "refunded";

export type PaymentStatus =
  | "pending"
  | "completed"
  | "failed"
  | "refunded";

export type PaymentMethod =
  | "cash"
  | "bank_transfer"
  | "mobile_money"
  | "check"
  | "card";

export type RefundStatus =
  | "requested"
  | "under_review"
  | "approved"
  | "rejected"
  | "completed"
  | "cancelled";

export type UserRole = "admin" | "manager" | "operator";

export type DocumentType = "pro_forma" | "invoice" | "delivery_note" | "credit_note";

// ─── Utilisateur ──────────────────────────────────────────────────────────────

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: UserRole;
  status: string;
  created_at: string;
  updated_at: string;
}

export interface IssuerProfile {
  profile_type: "business" | "individual";
  display_name: string | null;
  company_name: string | null;
  tax_id: string | null;
  phone: string | null;
  email: string | null;
  address_line1: string | null;
  city: string | null;
  postal_code: string | null;
  country: string | null;
  signature_title: string | null;
  footer_notes: string | null;
  document_email: string | null;
  auto_send_documents: boolean;
  tax_included: boolean;
  primary_color: string | null;
  secondary_color: string | null;
  font_family: string | null;
  logo_path: string | null;
  stamp_path: string | null;
  signature_path: string | null;
  signature_text: string | null;
  account_email: string;
  account_name: string;
}

export interface Organization {
  id: string;
  code: string;
  name: string;
  legal_name: string | null;
  tax_id: string | null;
  email: string | null;
  phone: string | null;
  address_line1: string | null;
  postal_code: string | null;
  city: string | null;
  country: string | null;
  rccm: string | null;
  website: string | null;
  bank_name: string | null;
  bank_account: string | null;
  logo_url: string | null;
  is_active: boolean;
}

// ─── Client ───────────────────────────────────────────────────────────────────

export interface Client {
  id: string;
  code: string;
  client_type: string;
  status: string;
  full_name: string;
  company_name: string | null;
  tax_id: string | null;
  email: string | null;
  phone: string;
  address_line1: string | null;
  city: string | null;
  country: string;
  currency: string;
  credit_limit_cents: number;
  payment_terms_days: number;
  default_tax_rate: number;
  notes: string | null;
  created_at: string;
  updated_at: string;
}

export interface ClientCreate {
  client_type: string;
  full_name: string;
  phone: string;
  company_name?: string;
  tax_id?: string;
  email?: string;
  address_line1?: string;
  city?: string;
  country?: string;
  currency?: string;
  credit_limit_cents?: number;
  payment_terms_days?: number;
  default_tax_rate?: number;
  notes?: string;
}

export interface ClientUpdate {
  full_name?: string;
  phone?: string;
  company_name?: string;
  email?: string;
  address_line1?: string;
  city?: string;
  country?: string;
  credit_limit_cents?: number;
  payment_terms_days?: number;
  notes?: string;
}

export interface ClientListResponse {
  items: Client[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Produit ──────────────────────────────────────────────────────────────────

export interface Product {
  id: string;
  code: string;
  name: string;
  description: string | null;
  short_description: string | null;
  category: string | null;
  sub_category: string | null;
  unit: string | null;
  currency: string;
  unit_price_cents: number;
  tax_rate: number;
  min_order_quantity: number;
  track_stock: boolean;
  stock_quantity: number | null;
  low_stock_threshold: number | null;
  status: string;
  notes: string | null;
  supplier_ref: string | null;
  barcode: string | null;
  is_low_stock: boolean;
  unit_price_tax_included_cents: number;
  created_at: string;
  updated_at: string;
}

export interface ProductCreate {
  name: string;
  unit_price_cents: number;
  description?: string;
  short_description?: string;
  category?: string;
  unit?: string;
  currency?: string;
  tax_rate?: number;
  min_order_quantity?: number;
  track_stock?: boolean;
  stock_quantity?: number;
  notes?: string;
  supplier_ref?: string;
  barcode?: string;
}

export interface ProductUpdate {
  name?: string;
  unit_price_cents?: number;
  description?: string;
  category?: string;
  unit?: string;
  tax_rate?: number;
  notes?: string;
}

// ─── Commande / Order ─────────────────────────────────────────────────────────

export interface OrderItem {
  id: string;
  description: string;
  quantity: number;
  delivered_quantity: number;
  invoiced_quantity: number;
  remaining_quantity: number;
  invoiceable_quantity: number;
  unit_price_cents: number;
  line_total_cents: number;
  delivered_line_total_cents: number;
  unit: string | null;
  item_code: string | null;
  notes: string | null;
  sort_order: number;
}

export interface OrderItemCreate {
  description: string;
  quantity: number;
  unit_price_cents: number;
  unit?: string;
  item_code?: string;
  notes?: string;
}

export interface Order {
  id: string;
  order_number: string;
  client_id: string;
  status: OrderStatus;
  payment_status: string;
  currency: string;
  subtotal_cents: number;
  tax_rate: number;
  tax_cents: number;
  discount_cents: number;
  shipping_cents: number;
  total_cents: number;
  delivered_subtotal_cents: number;
  delivered_tax_cents: number;
  delivered_total_cents: number;
  paid_cents: number;
  refunded_cents: number;
  balance_due_cents: number;
  has_reliquat: boolean;
  fully_delivered: boolean;
  days_overdue: number;
  purchase_order_ref: string | null;
  notes: string | null;
  due_date: string | null;
  delivery_date: string | null;
  delivered_at: string | null;
  items: OrderItem[];
  created_at: string;
  updated_at: string;
}

export interface OrderCreate {
  client_id: string;
  currency?: string;
  tax_rate?: number;
  discount_cents?: number;
  shipping_cents?: number;
  purchase_order_ref?: string;
  notes?: string;
  due_date?: string;
  delivery_date?: string;
  items: OrderItemCreate[];
}

export interface OrderUpdate {
  tax_rate?: number;
  discount_cents?: number;
  shipping_cents?: number;
  purchase_order_ref?: string;
  notes?: string;
  due_date?: string;
  delivery_date?: string;
  items?: OrderItemCreate[];
}

export interface OrderListResponse {
  items: Order[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Paiement / Payment ───────────────────────────────────────────────────────

export interface Payment {
  id: string;
  transaction_number: string;
  order_id: string;
  client_id: string;
  transaction_type: string;
  status: PaymentStatus;
  method: PaymentMethod;
  amount_cents: number;
  currency: string;
  external_reference: string | null;
  notes: string | null;
  completed_at: string | null;
  transaction_date: string;
  created_at: string;
}

export interface PaymentCreate {
  order_id: string;
  amount_cents: number;
  method: PaymentMethod;
  external_reference?: string;
  bank_name?: string;
  check_number?: string;
  notes?: string;
}

// ─── Remboursement / Refund ───────────────────────────────────────────────────

export interface Refund {
  id: string;
  refund_number: string;
  order_id: string;
  client_id: string;
  status: RefundStatus;
  reason: string;
  reason_detail: string;
  requested_amount_cents: number;
  approved_amount_cents: number | null;
  currency: string;
  rejection_reason: string | null;
  notes: string | null;
  requested_at: string;
  approved_at: string | null;
  completed_at: string | null;
  created_at: string;
}

export interface RefundCreate {
  order_id: string;
  original_transaction_id: string;
  amount_cents: number;
  reason: string;
  reason_detail: string;
  notes?: string;
}

// ─── Document ─────────────────────────────────────────────────────────────────

export interface Document {
  id: string;
  document_type: string;
  document_number: string;
  file_name: string;
  is_signed: boolean;
  is_stamped: boolean;
  created_at: string;
}

// ─── Pagination ───────────────────────────────────────────────────────────────

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Devis / Quote ────────────────────────────────────────────────────────────

export type QuoteStatus =
  | "draft"
  | "sent"
  | "accepted"
  | "rejected"
  | "expired"
  | "converted";

export interface QuoteItem {
  id: string;
  quote_id: string;
  product_id: string | null;
  description: string;
  quantity: number;
  unit_price_cents: number;
  total_cents: number;
  position: number;
}

export interface Quote {
  id: string;
  quote_number: string;
  client_id: string;
  client_name: string | null;
  status: QuoteStatus;
  currency: string;
  subtotal_cents: number;
  tax_rate: number;
  tax_cents: number;
  total_cents: number;
  notes: string | null;
  valid_until: string | null;
  sent_at: string | null;
  accepted_at: string | null;
  rejected_at: string | null;
  converted_to_order_id: string | null;
  created_by: string;
  items: QuoteItem[];
  created_at: string;
  updated_at: string;
}

export interface QuoteItemCreate {
  description: string;
  quantity: number;
  unit_price_cents: number;
  product_id?: string;
  position?: number;
}

export interface QuoteCreate {
  client_id: string;
  items: QuoteItemCreate[];
  currency?: string;
  tax_rate?: number;
  notes?: string;
  valid_until?: string;
}

export interface QuoteUpdate {
  client_id?: string;
  items?: QuoteItemCreate[];
  currency?: string;
  tax_rate?: number;
  notes?: string;
  valid_until?: string;
}

export interface QuoteListResponse {
  items: Quote[];
  total: number;
  skip: number;
  limit: number;
}

// ─── Rétro-compat (anciens noms utilisés dans certaines pages) ─────────────────
// Alias pour éviter de casser les imports existants
export type Produit = Product;
export type ProduitCreate = ProductCreate;
export type ProduitUpdate = ProductUpdate;
export type Commande = Order;
export type CommandeCreate = OrderCreate;
export type CommandeUpdate = OrderUpdate;
export type LigneCommande = OrderItem;
export type LigneCommandeCreate = OrderItemCreate;
export type Paiement = Payment;
export type PaiementCreate = PaymentCreate;
export type StatutCommande = OrderStatus;
export type MethodePaiement = PaymentMethod;
export type RoleUtilisateur = UserRole;
export type TypeDocument = DocumentType;
