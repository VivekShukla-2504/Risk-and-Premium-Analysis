// Translating the UI's filter state into API query parameters / request bodies.

export const EMPTY_FILTERS = Object.freeze({
  policy_type: '',
  gender: '',
  age_band: '',
  claim_status: '',
  start_date: '',
  end_date: '',
  date_basis: 'policy_start',
});

const VALUE_KEYS = ['policy_type', 'gender', 'age_band', 'claim_status', 'start_date', 'end_date'];

export function filtersToParams(filters = {}) {
  const params = {};
  for (const k of VALUE_KEYS) {
    if (filters[k]) params[k] = filters[k];
  }
  // date_basis only matters when a date range is set
  if ((params.start_date || params.end_date) && filters.date_basis) params.date_basis = filters.date_basis;
  return params;
}

// For POST bodies: null when nothing is filtered (the API treats null as "whole portfolio").
export function filtersToBody(filters = {}) {
  const p = filtersToParams(filters);
  return Object.keys(p).length ? p : null;
}

export function countActiveFilters(filters = {}) {
  return VALUE_KEYS.filter((k) => Boolean(filters[k])).length;
}

export function validateFilters(filters = {}) {
  if (filters.start_date && filters.end_date && filters.start_date > filters.end_date) {
    return 'Start date must be on or before end date.';
  }
  return null;
}
