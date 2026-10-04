import axios from 'axios';

import { normalizeApiError, parseContentDisposition } from '../utils/errors.js';
import { filtersToBody, filtersToParams } from '../utils/params.js';
import { saveBlob } from '../utils/download.js';

export const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api';

const http = axios.create({ baseURL: API_BASE_URL, timeout: 30000 });

http.interceptors.response.use(
  (response) => response,
  (error) => Promise.reject(normalizeApiError(error, API_BASE_URL)),
);

const get = (path, filters, signal, extra = {}) =>
  http.get(path, { params: { ...filtersToParams(filters), ...extra }, signal }).then((r) => r.data);

// Every function takes (filters, signal) so pages can cancel stale requests when filters change.
export const api = {
  health: (signal) => http.get('/health', { signal }).then((r) => r.data),
  summary: (filters, signal) => get('/dashboard/summary', filters, signal),
  policyTypes: (filters, signal) => get('/analytics/policy-types', filters, signal),
  ageBands: (filters, signal) => get('/analytics/age-bands', filters, signal),
  claims: (filters, signal, { includePoints = false, maxPoints = 500 } = {}) =>
    get('/analytics/claims', filters, signal, includePoints ? { include_points: true, max_points: maxPoints } : {}),
  lossRatio: (filters, signal) => get('/analytics/loss-ratio', filters, signal),
  severity: (filters, signal) => get('/analytics/severity', filters, signal),
  frequency: (filters, signal) => get('/analytics/frequency', filters, signal),
  monthlyTrends: (filters, signal) => get('/analytics/monthly-trends', filters, signal),
  riskSegments: (filters, signal) => get('/analytics/risk-segments', filters, signal),
  rateIndication: (filters, targetLossRatioPct, signal) =>
    get('/analytics/rate-indication', filters, signal, { target_loss_ratio_pct: targetLossRatioPct }),
  scenario: (inputs, filters, signal) =>
    http.post('/analytics/scenario', { ...inputs, filters: filtersToBody(filters) }, { signal }).then((r) => r.data),
  scenarioCompare: (inputs, filters, signal) =>
    http.post('/analytics/scenario/compare', { ...inputs, filters: filtersToBody(filters) }, { signal }).then((r) => r.data),
  methodology: (signal) => http.get('/methodology', { signal }).then((r) => r.data),
  dataQuality: (signal) => http.get('/data-quality', { signal }).then((r) => r.data),
};

// Error bodies of blob responses arrive as Blobs; read the JSON detail so the user sees the real reason.
async function blobError(error) {
  const blob = error?.response?.data;
  if (blob instanceof Blob) {
    try {
      const body = JSON.parse(await blob.text());
      return normalizeApiError({ response: { status: error.response.status, data: body } }, API_BASE_URL);
    } catch {
      /* not JSON: fall through to the generic message */
    }
  }
  return normalizeApiError(error, API_BASE_URL);
}

export async function downloadReport({ section, format, filters, extraParams = {} }) {
  try {
    // plain axios (not `http`): the shared interceptor would discard the Blob error body
    const res = await axios.get(`${API_BASE_URL}/analytics/export`, {
      params: { ...filtersToParams(filters), ...extraParams, section, format },
      responseType: 'blob',
      timeout: 60000,
    });
    const name = parseContentDisposition(res.headers['content-disposition']) || `insurance_${section}.${format}`;
    saveBlob(res.data, name);
    return name;
  } catch (error) {
    throw await blobError(error);
  }
}
