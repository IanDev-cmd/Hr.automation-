/** Client for the Sequel Support HR desk API. */

export class HRAutomataAPI {
  constructor(baseUrl = "") {
    this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
    this.timeoutMs = 12000;
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(this.baseUrl + path, {
        method: options.method || "GET",
        headers: { "Content-Type": "application/json", ...(options.headers || {}) },
        body: options.body == null ? undefined : JSON.stringify(options.body),
        signal: controller.signal
      });
      const text = await response.text();
      let data = {};
      if (text) {
        try {
          data = JSON.parse(text);
        } catch (_err) {
          data = { detail: text };
        }
      }
      if (!response.ok) {
        const detail = data && (data.detail || data.message);
        const message = typeof detail === "string" ? detail : (detail ? JSON.stringify(detail) : response.statusText);
        const error = new Error(message || "The HR desk could not complete that request");
        error.status = response.status;
        throw error;
      }
      return data;
    } catch (err) {
      if (err && err.name === "AbortError") {
        throw new Error("The HR desk took too long to answer");
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
  }

  calculatePay(body) {
    return this.request("/api/v1/hr/pay/calculate", { method: "POST", body });
  }

  evaluateInterview(body) {
    return this.request("/api/v1/hr/interviews/evaluate", { method: "POST", body });
  }

  payrollHandoff(body) {
    return this.request("/api/v1/hr/payroll/handoff", { method: "POST", body });
  }

  checkGaps(history) {
    return this.request("/api/v1/hr/gaps/check", { method: "POST", body: { history } });
  }

  dbsRecheck(lastChecked) {
    return this.request("/api/v1/hr/dbs/recheck", { method: "POST", body: { last_checked: lastChecked } });
  }

  previewPurge(records) {
    return this.request("/api/v1/hr/gdpr/purge", { method: "POST", body: { records } });
  }
}
