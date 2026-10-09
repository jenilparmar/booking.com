"use client";

import useSWR, { type SWRConfiguration } from "swr";

import { api, type Query } from "./api";

const opts: SWRConfiguration = { revalidateOnFocus: false, keepPreviousData: true };

function key(name: string, q?: Query) {
  return q ? [name, JSON.stringify(q)] : [name];
}

export const useProperties = () => useSWR(key("properties"), () => api.properties(), opts);
export const useSummary = (q: Query) => useSWR(key("summary", q), () => api.summary(q), opts);
export const useComparison = (q: Query) =>
  useSWR(key("comparison", q), () => api.comparison(q), opts);
export const useTrends = (q: Query) => useSWR(key("trends", q), () => api.trends(q), opts);
export const useTopics = (q: Query) => useSWR(key("topics", q), () => api.topics(q), opts);
export const useReviews = (q: Query) => useSWR(key("reviews", q), () => api.reviews(q), opts);
export const useCollectionHealth = () =>
  useSWR(key("collection-health"), () => api.collectionHealth(), opts);
