// The client-side state (one plain object; controllers change it, views only read what they are given).
export const state = {
  me: null,                 // logged-in user
  saved: [],                // saved e-mails
  currentId: null,          // id of the saved e-mail being edited, or null for a new draft
  lastAnalysis: null,       // { key, id, verdict, risk } of the last analysis shown
  modelsInfo: null,
  batch: null,              // last batch response
  pending: { tempToken: null, user: null, resetEmail: '', resendAt: 0 }
};
export const keyOf = f => JSON.stringify([f.from, f.subject, f.body]);
