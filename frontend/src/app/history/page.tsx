"use client";
/* eslint-disable @next/next/no-img-element -- API crops are displayed from the local recognition service. */

import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { AlertCircle, ChevronLeft, ChevronRight, Clock3, Loader2, RefreshCw, Search, SlidersHorizontal } from "lucide-react";
import type { DetectionHistoryItem, DetectionHistoryResponse, SearchPlatesResponse } from "../../types/api";
import { apiFetch } from "../../lib/api";
import { RequireAuth } from "../../components/auth-provider";

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const PAGE_SIZE = 20;

function imageUrl(url?: string | null) {
  if (!url) return null;
  return url.startsWith("http") ? url : `${API_BASE_URL}${url}`;
}

function formatDate(value?: string) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? value.replace("T", " ")
    : new Intl.DateTimeFormat("vi-VN", { dateStyle: "medium", timeStyle: "short" }).format(date);
}

export default function HistoryPage() {
  return <RequireAuth><HistoryWorkspace /></RequireAuth>;
}

function HistoryWorkspace() {
  const [items, setItems] = useState<DetectionHistoryItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [query, setQuery] = useState("");
  const [submittedQuery, setSubmittedQuery] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  const loadHistory = useCallback(async (currentPage: number, plateQuery: string) => {
    setIsLoading(true);
    setError(null);
    try {
      const endpoint = plateQuery
        ? `/api/license-plates/search?plate=${encodeURIComponent(plateQuery)}`
        : `/api/license-plates/history?page=${currentPage}&page_size=${PAGE_SIZE}`;
      const response = await apiFetch(endpoint);
      if (!response.ok) throw new Error(`Máy chủ trả về lỗi ${response.status}.`);

      if (plateQuery) {
        const data: SearchPlatesResponse = await response.json();
        setItems(data.results ?? []);
        setTotal(data.total ?? data.results?.length ?? 0);
      } else {
        const data: DetectionHistoryResponse = await response.json();
        setItems(data.items ?? []);
        setTotal(data.total ?? 0);
      }
    } catch (loadError) {
      setItems([]);
      setTotal(0);
      setError(loadError instanceof TypeError
        ? "Không thể kết nối Backend. Hãy kiểm tra dịch vụ FastAPI tại địa chỉ cấu hình."
        : loadError instanceof Error ? loadError.message : "Không tải được lịch sử nhận diện.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    // Fetch remote archive data when the selected page or search changes.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void loadHistory(page, submittedQuery);
  }, [loadHistory, page, submittedQuery]);

  const rangeLabel = useMemo(() => {
    if (total === 0) return "0 kết quả";
    if (submittedQuery) return `${items.length} kết quả khớp`;
    return `${(page - 1) * PAGE_SIZE + 1}–${Math.min(page * PAGE_SIZE, total)} trong ${total} bản ghi`;
  }, [items.length, page, submittedQuery, total]);

  function handleSearch(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setPage(1);
    setSubmittedQuery(query.trim());
  }

  function clearSearch() {
    setQuery("");
    setPage(1);
    setSubmittedQuery("");
  }

  return (
    <div className="history-page space-y-6 pb-10">
      <section className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div>
          <div className="eyebrow mb-3">
            <Clock3 aria-hidden="true" className="h-3.5 w-3.5" /> KHO KẾT QUẢ NHẬN DIỆN
          </div>
          <h1 className="text-3xl font-semibold tracking-tight text-slate-950 sm:text-4xl">Lịch sử nhận diện</h1>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-slate-600 sm:text-base">Tra cứu các lượt quét, biển số và thông tin xử lý được lưu bởi hệ thống.</p>
        </div>
        <div className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white px-4 py-3 shadow-sm">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-blue-50 text-blue-800"><SlidersHorizontal aria-hidden="true" className="h-5 w-5" /></div>
          <div><p className="text-[11px] font-semibold uppercase tracking-wider text-slate-500">Tổng bản ghi</p><p className="text-xl font-bold tabular-nums text-slate-950">{total.toLocaleString("vi-VN")}</p></div>
        </div>
      </section>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-[0_12px_40px_-28px_rgba(15,23,42,0.3)]">
        <div className="flex flex-col gap-4 border-b border-slate-100 px-5 py-5 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <div>
            <h3 className="text-sm font-semibold text-slate-900">Bản ghi gần đây</h3>
            <p className="mt-1 text-xs text-slate-500">{rangeLabel}</p>
          </div>
          <form onSubmit={handleSearch} className="flex w-full gap-2 sm:w-auto">
            <label className="relative min-w-0 flex-1 sm:w-72">
              <span className="sr-only">Tìm theo biển số</span>
              <Search aria-hidden="true" className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Nhập biển số cần tìm..." className="w-full rounded-lg border border-slate-200 bg-slate-50 py-2.5 pl-9 pr-3 text-sm text-slate-900 placeholder:text-slate-400 outline-none transition focus:border-blue-500 focus:bg-white focus:ring-2 focus:ring-blue-500/15" />
            </label>
            <button type="submit" className="rounded-lg bg-slate-900 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-blue-800">Tìm kiếm</button>
            {submittedQuery ? (
              <button type="button" onClick={clearSearch} aria-label="Xóa tìm kiếm" title="Xóa tìm kiếm" className="rounded-lg border border-slate-200 bg-white px-3 text-slate-600 transition hover:bg-slate-50 hover:text-slate-950"><RefreshCw aria-hidden="true" className="h-4 w-4" /></button>
            ) : (
              <button type="button" onClick={() => void loadHistory(page, "")} aria-label="Tải lại lịch sử" title="Tải lại lịch sử" className="rounded-lg border border-slate-200 bg-white px-3 text-slate-600 transition hover:bg-slate-50 hover:text-slate-950"><RefreshCw aria-hidden="true" className={`h-4 w-4 ${isLoading ? "animate-spin" : ""}`} /></button>
            )}
          </form>
        </div>

        {error && <div role="alert" className="mx-5 mt-4 flex items-start gap-2.5 rounded-xl border border-red-200 bg-red-50 p-3.5 text-sm text-red-800 sm:mx-6"><AlertCircle aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" /><span>{error}</span></div>}

        <div className="overflow-x-auto">
          <table className="w-full min-w-[780px] text-left text-sm">
            <thead className="bg-slate-50 text-[11px] uppercase tracking-[0.12em] text-slate-500">
              <tr>
                <th scope="col" className="px-5 py-3.5 font-semibold sm:px-6">ID</th>
                <th scope="col" className="px-4 py-3.5 font-semibold">Biển số</th>
                <th scope="col" className="px-4 py-3.5 font-semibold">Ảnh crop</th>
                <th scope="col" className="px-4 py-3.5 font-semibold">Phân loại</th>
                <th scope="col" className="px-4 py-3.5 font-semibold">Độ tin cậy</th>
                <th scope="col" className="px-5 py-3.5 font-semibold sm:px-6">Thời gian ghi nhận</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {isLoading ? (
                <tr><td colSpan={6} className="px-5 py-16 text-center text-sm text-slate-500"><span className="inline-flex items-center gap-2"><Loader2 aria-hidden="true" className="h-4 w-4 animate-spin text-blue-700" />Đang tải dữ liệu...</span></td></tr>
              ) : items.length > 0 ? items.map((item) => {
                const cropUrl = imageUrl(item.cropped_plate_url);
                return (
                  <tr key={item.id} className="transition-colors hover:bg-blue-50/40">
                    <td className="px-5 py-3.5 font-mono text-xs text-slate-500 sm:px-6">#{item.id}</td>
                    <td className="px-4 py-3.5"><span className="inline-flex rounded-md border border-amber-200 bg-amber-50 px-2.5 py-1 font-mono font-bold tracking-wide text-slate-900">{item.plate_number || "—"}</span></td>
                    <td className="px-4 py-3.5">{cropUrl ? <a href={cropUrl} target="_blank" rel="noreferrer" aria-label={`Mở ảnh crop của biển số ${item.plate_number}`} className="inline-flex rounded-md border border-slate-200 bg-white p-1 transition hover:border-blue-300 hover:shadow-sm"><img src={cropUrl} alt={`Ảnh crop biển số ${item.plate_number}`} className="h-8 max-w-20 object-contain" /></a> : <span className="text-xs text-slate-400">Không có ảnh</span>}</td>
                    <td className="px-4 py-3.5"><span className="inline-flex rounded-full bg-slate-100 px-2.5 py-1 text-xs font-medium text-slate-600">{item.plate_type === "two_line" ? "2 dòng" : item.plate_type === "one_line" ? "1 dòng" : "Không rõ"}</span></td>
                    <td className="px-4 py-3.5"><div className="flex items-center gap-2"><span className="h-1.5 w-12 overflow-hidden rounded-full bg-slate-100"><span className="block h-full rounded-full bg-teal-600" style={{ width: `${Math.max(0, Math.min(100, item.confidence * 100))}%` }} /></span><span className="font-semibold tabular-nums text-slate-700">{(item.confidence * 100).toFixed(1)}%</span></div></td>
                    <td className="px-5 py-3.5 text-xs text-slate-500 sm:px-6"><span className="inline-flex items-center gap-2"><Clock3 aria-hidden="true" className="h-3.5 w-3.5 text-slate-400" />{formatDate(item.created_at)}</span></td>
                  </tr>
                );
              }) : (
                <tr><td colSpan={6} className="px-5 py-16 text-center text-sm text-slate-500">{submittedQuery ? `Không tìm thấy kết quả cho “${submittedQuery}”.` : "Chưa có lượt nhận diện nào được ghi nhận."}</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <div className="flex flex-col gap-3 border-t border-slate-100 bg-slate-50/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
          <p className="text-xs text-slate-500">{submittedQuery ? `${items.length} kết quả tìm kiếm` : `Trang ${page} / ${totalPages}`}</p>
          {!submittedQuery && <div className="flex gap-2">
            <button type="button" onClick={() => setPage((current) => Math.max(1, current - 1))} disabled={page <= 1 || isLoading} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"><ChevronLeft aria-hidden="true" className="h-3.5 w-3.5" /> Trang trước</button>
            <button type="button" onClick={() => setPage((current) => Math.min(totalPages, current + 1))} disabled={page >= totalPages || isLoading} className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-slate-300 hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40">Trang sau <ChevronRight aria-hidden="true" className="h-3.5 w-3.5" /></button>
          </div>}
        </div>
      </section>
    </div>
  );
}
