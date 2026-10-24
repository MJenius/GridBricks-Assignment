import { keepPreviousData, useQuery } from '@tanstack/react-query';
import { api, type TimingParams } from './client';

// TanStack Query passes an AbortSignal; superseded requests are cancelled when filters change.

export function useDeliveryDay(deliveryDate: string, t: TimingParams) {
  return useQuery({
    queryKey: ['delivery-day', deliveryDate, t.cutoff, t.lead],
    queryFn: ({ signal }) => api.deliveryDay(deliveryDate, t, signal),
    placeholderData: keepPreviousData,
  });
}

export function useRevisions(deliveryDate: string, t: TimingParams) {
  return useQuery({
    queryKey: ['revisions', deliveryDate, t.cutoff, t.lead],
    queryFn: ({ signal }) => api.revisions(deliveryDate, t, signal),
    placeholderData: keepPreviousData,
  });
}

export function useAnalysis(from: string, to: string, t: TimingParams) {
  return useQuery({
    queryKey: ['analysis', from, to, t.cutoff, t.lead],
    queryFn: ({ signal }) => api.analysis(from, to, t, signal),
    placeholderData: keepPreviousData,
  });
}
