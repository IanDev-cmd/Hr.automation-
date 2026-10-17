/** Client for the Sequel Support HR desk API. */

export class HRAutomataAPI {
  constructor(baseUrl = "") {
    this.baseUrl = String(baseUrl || "").replace(/\/$/, "");
    this.timeoutMs = 12000;
    this.token = "";
    try {
      this.token = sessionStorage.getItem("hr-token") || "";
    } catch (_err) {
      this.token = "";
    }
  }

  setToken(token) {
    this.token = token || "";
    try {
      if (this.token) sessionStorage.setItem("hr-token", this.token);
      else sessionStorage.removeItem("hr-token");
    } catch (_err) {
      /* the desk still works for this tab */
    }
  }

  async request(path, options = {}) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), this.timeoutMs);
    try {
      const response = await fetch(this.baseUrl + path, {
        method: options.method || "GET",
        headers: {
          "Content-Type": "application/json",
          ...(this.token ? { Authorization: "Bearer " + this.token } : {}),
          ...(options.headers || {})
        },
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

  issueToken(body) {
    return this.request("/api/v1/auth/token", { method: "POST", body });
  }

  executeSignature(body) {
    return this.request("/api/v1/hr/signatures/execute", { method: "POST", body });
  }

  chaseReference(body) {
    return this.request("/api/v1/hr/references/chase", { method: "POST", body });
  }

  historicCandidates() {
    return this.request("/api/v1/hr/candidates/historic");
  }
}
