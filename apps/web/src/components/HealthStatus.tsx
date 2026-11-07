"use client";

import { useEffect, useState } from "react";

interface HealthData {
  status: string;
  service: string;
  environment: string;
  sectors_supported: string[];
}

export default function HealthStatus() {
  const [data, setData] = useState<HealthData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState<boolean>(true);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
    fetch(`${apiUrl}/health`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((json) => {
        setData(json);
        setLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setLoading(false);
      });
  }, []);

  return (
    <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-6 max-w-xl mx-auto my-6">
      <div className="flex items-center justify-between mb-4 pb-2 border-b border-slate-100">
        <h3 className="font-semibold text-slate-800 text-lg">حالة النظام الفنية | System Status</h3>
        <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-800">
          Phase 1 Foundation
        </span>
      </div>

      {loading && <p className="text-slate-500 text-sm">جاري التحقق من اتصال الخادم...</p>}

      {error && (
        <div className="bg-amber-50 border border-amber-200 rounded-lg p-3 text-sm text-amber-800">
          <p className="font-medium">الخادم غير متصل محلياً (Backend Offline or Starting):</p>
          <p className="text-xs mt-1 text-slate-600">{error}</p>
        </div>
      )}

      {data && (
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-slate-500">حالة الخدمة (Service Status):</span>
            <span className="font-semibold text-emerald-600 uppercase">{data.status}</span>
          </div>
          <div className="flex justify-between">
            <span className="text-slate-500">البيئة (Environment):</span>
            <span className="font-mono text-slate-700">{data.environment}</span>
          </div>
          <div>
            <span className="text-slate-500 block mb-1">القطاعات المدعومة معمارياً (Sectors Supported):</span>
            <div className="flex gap-2">
              {data.sectors_supported.map((sector) => (
                <span
                  key={sector}
                  className="bg-slate-100 text-slate-700 px-2.5 py-1 rounded-md text-xs font-mono font-medium"
                >
                  {sector === "AGRI_FOOD" ? "الزراعة والأغذية (Agri-food)" : "الملابس والمنسوجات (Textiles/Apparel)"}
                </span>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
