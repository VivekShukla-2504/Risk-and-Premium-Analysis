// Turn Axios/FastAPI failures into one predictable shape the UI can show.

export class ApiError extends Error {
  constructor(message, { status = null, canceled = false } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.canceled = canceled;
  }
}

function describeDetail(detail) {
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) {
    // FastAPI/Pydantic validation errors: [{ loc: ['query','age_band'], msg: '...' }]
    return detail
      .map((d) => {
        const field = Array.isArray(d.loc) ? d.loc.filter((p) => p !== 'body' && p !== 'query').join('.') : '';
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join('; ');
  }
  return null;
}

export function normalizeApiError(err, baseURL = '') {
  if (err instanceof ApiError) return err;
  if (err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError' || err?.name === 'AbortError') {
    return new ApiError('Request canceled', { canceled: true });
  }
  if (err?.response) {
    const { status, data } = err.response;
    const detail = describeDetail(data?.detail);
    if (status === 503) return new ApiError(detail || 'The data source is unavailable.', { status });
    if (status === 422) return new ApiError(detail || 'The request was not valid.', { status });
    if (status >= 500) return new ApiError(detail || 'The server hit an error. Check the backend log.', { status });
    return new ApiError(detail || `Request failed (HTTP ${status}).`, { status });
  }
  if (err?.code === 'ECONNABORTED') return new ApiError('The request timed out. Try again.');
  return new ApiError(
    `Cannot reach the API${baseURL ? ` at ${baseURL}` : ''}. Check that the backend is running and CORS allows this origin.`,
  );
}

// 'attachment; filename="report.csv"' -> 'report.csv'
export function parseContentDisposition(header) {
  if (!header) return null;
  const m = /filename\*?=(?:UTF-8'')?"?([^";]+)"?/i.exec(header);
  return m ? decodeURIComponent(m[1]) : null;
}
