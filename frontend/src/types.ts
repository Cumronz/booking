export type Role = "member" | "moderator" | "admin";

export interface UserBrief { id: number; username: string; first_name: string; last_name: string }
export interface User extends UserBrief { email: string; bio: string; role: Role; date_joined: string }

export interface Page<T> { count: number; next: string | null; previous: string | null; results: T[] }

export interface BookBrief { id: number; title: string; author: string; cover: string | null }
export interface Book extends BookBrief {
  genre: string; description: string; created_at: string;
  avg_rating: number | null; reviews_count: number;
  copies_total: number; available_copies: number; read_this_month: number;
}
export interface BookDetail extends Book { my_review: Review | null; my_reading: ReadingEntry | null }

export type Condition = "new" | "good" | "fair" | "worn";
export interface Copy {
  id: number; book: number; book_title: string; book_author: string; owner: UserBrief;
  condition: Condition; condition_display: string; pickup_place: string;
  is_active: boolean; available: boolean; created_at: string;
}

export type LoanStatus = "pending" | "accepted" | "rejected" | "cancelled" | "handed_over" | "returned";
export type LoanAction = "accept" | "reject" | "cancel" | "hand-over" | "return";
export interface Loan {
  id: number; copy_id: number; book: BookBrief; owner: UserBrief; borrower: UserBrief;
  pickup_place: string; requested_return_date: string; status: LoanStatus; status_display: string;
  message: string; created_at: string; handed_at: string | null; returned_at: string | null;
  is_overdue: boolean; days_overdue: number; available_actions: LoanAction[];
}

export interface Review {
  id: number; user: UserBrief; book: number; book_title: string; score: number; text: string;
  is_hidden: boolean; created_at: string; updated_at: string;
}

export type ReadingStatus = "want" | "reading" | "read";
export interface ReadingEntry {
  id: number; book: BookBrief; status: ReadingStatus; status_display: string;
  finished_at: string | null; updated_at: string;
}
export interface ReadingStats {
  by_status: Record<ReadingStatus, number>;
  read_this_month: number; read_this_year: number;
  months: { month: string; count: number }[];
}
