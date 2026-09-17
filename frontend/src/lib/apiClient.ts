/**
 * Air-Gapped Forensic Workstation Local API Client.
 *
 * Exclusively binds to 127.0.0.1:8000 (Loopback IPC).
 * Zero cloud dependencies, zero external telemetry.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000";

export interface Device {
  devicePath: string;
  model: string;
  serial: string;
  capacityBytes: number;
  capacityFormatted: string;
  storageType: string;
  busType: string;
  health: string;
  temp: string;
  isSystemDrive: boolean;
  isMounted: boolean;
  rawCapabilities: string[];
}

export interface SanitizationPlanResponse {
  status: string;
  device: Device;
  policy: {
    recommendedMethod: string;
    allowedMethods: string[];
    riskLevel: string;
    estimatedSeconds: number;
  };
}

export interface SanitizationReport {
  operationId: string;
  devicePath: string;
  serial: string;
  status: string;
  method: string;
  operatorId: string;
  caseId: string;
  durationSeconds: number;
  verification: {
    status: string;
    sectorsSampled: number;
    sectorsVerifiedZero: number;
    randomPatternMatches: number;
  };
  assurance: {
    score: number;
    level: string;
  };
  proof?: {
    certificateId: string;
    sha256Proof: string;
    hmacChainHash: string;
    signature: string;
    timestampUtc: string;
  };
}

export interface CarvedFile {
  file_id: string;
  mime: string;
  block_count: number;
  size_bytes: number;
  is_closed: boolean;
  reliability_score: number;
  score_breakdown: {
    C_hf: number;
    C_struct: number;
    delta_ent: number;
    C_sem: number;
  };
  triage_priority: "HIGH" | "MEDIUM" | "LOW";
  sha256: string;
  offset_bytes: number;
}

export interface CarvingJobResponse {
  status: string;
  jobId: string;
  progress?: number;
  blocksScanned?: number;
  totalBlocks?: number;
  orphansCount?: number;
  filesFound?: number;
}

export interface FileSanitizeResult {
  target_path: string;
  is_directory: boolean;
  bytes_scrubbed: number;
  slack_bytes_scrubbed: number;
  passes_completed: number;
  method: string;
  sha256_pre_wipe: string;
  sha256_post_verification: string;
  status: string;
  timestamp_utc: string;
  audit_hash: string;
}

class ForensiwipeClient {
  private base: string;

  constructor(baseUrl: string = API_BASE) {
    this.base = baseUrl;
  }

  private async request<T>(endpoint: string, options?: RequestInit): Promise<T> {
    const url = `${this.base}${endpoint}`;
    try {
      const res = await fetch(url, {
        ...options,
        headers: {
          "Content-Type": "application/json",
          ...(options?.headers || {}),
        },
      });
      if (!res.ok) {
        const errBody = await res.json().catch(() => ({}));
        throw new Error(errBody.message || `Request failed with status ${res.status}`);
      }
      return (await res.json()) as T;
    } catch (err: any) {
      console.warn(`[Forensiwipe API] IPC fetch error on ${endpoint}:`, err.message);
      throw err;
    }
  }

  // System & Overview
  async checkHealth(): Promise<{ status: string; version: string }> {
    return this.request("/api/health");
  }

  async getOverview(): Promise<any> {
    return this.request("/api/overview");
  }

  // Devices & Drive Sanitization (PS Req 1)
  async listDevices(includeMock: boolean = true): Promise<{ status: string; devices: Device[] }> {
    return this.request(`/api/devices?includeMock=${includeMock ? "true" : "false"}`);
  }

  async planSanitization(devicePath: string): Promise<SanitizationPlanResponse> {
    return this.request("/api/sanitization/plan", {
      method: "POST",
      body: JSON.stringify({ devicePath }),
    });
  }

  async executeSanitization(payload: {
    devicePath: string;
    serial: string;
    method: string;
    operatorId: string;
    caseId: string;
    passphrase?: string;
    allowLiveExecution?: boolean;
  }): Promise<{ status: string; report: SanitizationReport }> {
    return this.request("/api/sanitization/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getSanitizationStatus(opId: string): Promise<any> {
    return this.request(`/api/sanitization/${encodeURIComponent(opId)}/status`);
  }

  async getSanitizationReport(opId: string): Promise<{ status: string; report: SanitizationReport }> {
    return this.request(`/api/sanitization/${encodeURIComponent(opId)}/report`);
  }

  // Targeted File & Slack Sanitization (PS Req 2)
  async executeFileSanitize(payload: {
    targetPath: string;
    passes: number;
    operatorId: string;
    caseId: string;
    wipeSlack: boolean;
  }): Promise<{ status: string; result: FileSanitizeResult }> {
    return this.request("/api/filesanitize/execute", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  // Advanced Carving & ML Reassembly (PS Req 3)
  async startCarving(payload: {
    targetPath: string;
    caseId: string;
    investigator: string;
    deepMl?: boolean;
  }): Promise<{ status: string; jobId: string; job: any }> {
    return this.request("/api/carving/start", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  }

  async getCarvingStatus(jobId: string): Promise<CarvingJobResponse> {
    return this.request(`/api/carving/${encodeURIComponent(jobId)}/status`);
  }

  async getCarvingResults(jobId: string): Promise<{ status: string; jobId: string; files: CarvedFile[]; totalRecovered: number; certificateId: string }> {
    return this.request(`/api/carving/${encodeURIComponent(jobId)}/results`);
  }

  async getCarvingCertificate(jobId: string): Promise<any> {
    return this.request(`/api/carving/${encodeURIComponent(jobId)}/certificate`);
  }
}

export const apiClient = new ForensiwipeClient();
export default apiClient;
