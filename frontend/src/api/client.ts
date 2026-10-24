import type { Analysis, ApiErrorBody, DeliveryDay, Revisions } from './types';

export interface TimingParams {
  cutoff: string;
  lead: number;
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
    readonly requestId?: string | null,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

const BASE = '/api/v1';

function qs(params: Record<string, string | number>): string {
  return new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString();
}

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`${BASE}${path}`, { signal, headers: { Accept: 'application/json' } });
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') throw err;
    throw new ApiError('The Wind Desk API could not be reached. Check that the backend is running.', 0, 'network');
  }
  if (!res.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await res.json()) as ApiErrorBody;
    } catch {
      /* non-JSON error body */
    }
    throw new ApiError(
      body.error?.message ?? `Request failed (HTTP ${res.status}).`,
      res.status,
      body.error?.code ?? 'http_error',
      body.error?.request_id,
    );
  }
  return (await res.json()) as T;
}

export const api = {
  deliveryDay: (deliveryDate: string, t: TimingParams, signal?: AbortSignal) =>
    getJson<DeliveryDay>(`/delivery-days/${deliveryDate}?${qs({ cutoff: t.cutoff, lead_days: t.lead })}`, signal),
  revisions: (deliveryDate: string, t: TimingParams, signal?: AbortSignal) =>
    getJson<Revisions>(`/forecast-revisions/${deliveryDate}?${qs({ cutoff: t.cutoff, lead_days: t.lead })}`, signal),
  analysis: (from: string, to: string, t: TimingParams, signal?: AbortSignal) =>
    getJson<Analysis>(
      `/analysis?${qs({ decision_from: from, decision_to: to, cutoff: t.cutoff, lead_days: t.lead })}`,
      signal,
    ),
};

export function exportCsvUrl(from: string, to: string, t: TimingParams): string {
  return `${BASE}/analysis/export.csv?${qs({ decision_from: from, decision_to: to, cutoff: t.cutoff, lead_days: t.lead })}`;
}
